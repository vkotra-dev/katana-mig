from __future__ import annotations

import logging
import os
import sys
from types import ModuleType
from typing import TypeVar

from pydantic import BaseModel

from .adapter import AICallError, AICallResult
from .config import get_ai_config, resolve_model
from ..api.schemas import ModelPolicy

T = TypeVar("T", bound=BaseModel)

logger = logging.getLogger(__name__)

_DEFAULT_BASE_URL = "http://localhost:11434/v1"

try:  # pragma: no cover
    import openai
except ImportError:  # pragma: no cover - shim for test isolation
    openai = ModuleType("openai")

    class _OpenAIError(Exception):
        pass

    class _OpenAICompletions:
        def create(self, *_args: object, **_kwargs: object) -> object:
            raise RuntimeError("openai package is not installed")

    class _OpenAIChat:
        def __init__(self) -> None:
            self.completions = _OpenAICompletions()

    class _OpenAIClient:
        def __init__(self, *_args: object, **_kwargs: object) -> None:
            self.chat = _OpenAIChat()

    openai.OpenAIError = _OpenAIError  # type: ignore[attr-defined]
    openai.OpenAI = _OpenAIClient  # type: ignore[attr-defined]
    sys.modules.setdefault("openai", openai)


class OllamaAdapter:
    def __init__(self, *, model_id: str) -> None:
        self._model_id = model_id.removeprefix("ollama/")
        base_url = os.environ.get("OLLAMA_BASE_URL", _DEFAULT_BASE_URL)
        
        # Workaround for macOS Python failing to resolve .local mDNS domains
        if ".local" in base_url:
            try:
                from urllib.parse import urlparse
                import subprocess
                import re
                host = urlparse(base_url).hostname
                if host and host.endswith(".local"):
                    out = subprocess.check_output(["ping", "-c", "1", host], stderr=subprocess.STDOUT, text=True)
                    match = re.search(r'\(([\d\.]+)\)', out)
                    if match:
                        ip = match.group(1)
                        base_url = base_url.replace(host, ip)
                        logger.info(f"Resolved {host} to {ip} via ping workaround")
            except Exception as e:
                logger.warning(f"Failed to resolve .local hostname via ping: {e}")
                
        self._client = openai.OpenAI(base_url=base_url, api_key="ollama")

    @property
    def model_id(self) -> str:
        return self._model_id

    def call(
        self,
        system: str,
        user: str,
        response_model: type[T],
        *,
        task: str | None = None,
        model_policy: ModelPolicy | None = None,
    ) -> AICallResult[T]:
        schema = response_model.model_json_schema()
        prompt = f"{system}\n\nReturn valid JSON matching this schema:\n{schema}"
        model_id = self._resolve_model(task=task, model_policy=model_policy)
        logger.info("Ollama AI Call - Model: %s", model_id)
        logger.info("System Prompt:\n%s", prompt)
        logger.info("User Prompt:\n%s", user)
        
        max_retries = 3
        last_exc = None
        
        for attempt in range(max_retries):
            try:
                response = self._client.chat.completions.create(
                    model=model_id,
                    messages=[
                        {"role": "system", "content": prompt},
                        {"role": "user", "content": user},
                    ],
                    response_format={"type": "json_object"},
                )
            except openai.OpenAIError as exc:  # pragma: no cover
                logger.error("Ollama AI Call Failed - Model: %s, Error: %s", model_id, exc)
                raise AICallError(str(exc)) from exc

            content = response.choices[0].message.content
            if not isinstance(content, str):
                raise AICallError("Ollama response did not contain text content.")
                
            # Clean markdown code blocks if the model wrapped the JSON
            clean_content = content.strip()
            if clean_content.startswith("```json"):
                clean_content = clean_content[7:]
            elif clean_content.startswith("```"):
                clean_content = clean_content[3:]
            if clean_content.endswith("```"):
                clean_content = clean_content[:-3]
            clean_content = clean_content.strip()

            logger.info("Ollama Response (Attempt %d):\n%s", attempt + 1, clean_content)
            from pydantic import ValidationError
            try:
                parsed = response_model.model_validate_json(clean_content)
                return AICallResult(parsed=parsed, raw_response=clean_content)
            except ValidationError as exc:
                logger.warning("Failed to parse Ollama JSON response on attempt %d: %s", attempt + 1, exc)
                last_exc = exc
                # Update prompt to explicitly ask it to fix the JSON error
                prompt = f"{system}\n\nReturn valid JSON matching this schema:\n{schema}\n\nIMPORTANT: Your previous response was INVALID JSON. Fix this error: {exc}"

        logger.error("Ollama failed to produce valid JSON after %d attempts", max_retries)
        raise AICallError(f"Model returned invalid JSON after {max_retries} attempts: {last_exc}") from last_exc

    def _resolve_model(self, *, task: str | None, model_policy: ModelPolicy | None) -> str:
        if task is None:
            return self._model_id
        resolved = resolve_model(task, model_policy, get_ai_config())
        return resolved.removeprefix("ollama/")
