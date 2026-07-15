from __future__ import annotations

import logging
import os
import sys
from types import ModuleType
from typing import Any, TypeVar

from pydantic import BaseModel

from .adapter import AICallError, AICallResult, ConfigurationError
from .config import get_ai_config, resolve_model
from ..api.schemas import ModelPolicy

T = TypeVar("T", bound=BaseModel)

logger = logging.getLogger(__name__)


try:  # pragma: no cover - exercised indirectly through adapter tests
    import anthropic
except ImportError:  # pragma: no cover - environment shim for test isolation
    anthropic = ModuleType("anthropic")

    class _APIError(Exception):
        pass

    class _AnthropicMessages:
        def create(self, *_args: Any, **_kwargs: Any) -> Any:
            raise RuntimeError("anthropic package is not installed")

    class _AnthropicClient:
        def __init__(self, *_args: Any, **_kwargs: Any) -> None:
            self.messages = _AnthropicMessages()

    anthropic.APIError = _APIError  # type: ignore[attr-defined]
    anthropic.Anthropic = _AnthropicClient  # type: ignore[attr-defined]
    sys.modules.setdefault("anthropic", anthropic)


class AnthropicAdapter:
    def __init__(self, *, model_id: str, api_key_env: str) -> None:
        self._model_id = model_id
        self._api_key_env = api_key_env
        api_key = os.environ.get(self._api_key_env)
        if not api_key:
            raise ConfigurationError(self._api_key_env)
        self._client = anthropic.Anthropic(api_key=api_key)

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
        logger.info("Anthropic AI Call - Model: %s", model_id)
        logger.info("System Prompt:\n%s", prompt)
        logger.info("User Prompt:\n%s", user)
        try:
            response = self._client.messages.create(
                model=model_id,
                max_tokens=4096,
                system=prompt,
                messages=[{"role": "user", "content": user}],
            )
        except anthropic.APIError as exc:  # pragma: no cover - exercised via adapter test doubles
            logger.error("Anthropic AI Call Failed - Model: %s, Error: %s", model_id, exc)
            raise AICallError(str(exc)) from exc

        content = getattr(response, "content", None)
        text = _extract_text(content)
        logger.info("Anthropic Response:\n%s", text)
        parsed = response_model.model_validate_json(text)
        return AICallResult(parsed=parsed, raw_response=text)

    def _resolve_model(self, *, task: str | None, model_policy: ModelPolicy | None) -> str:
        if task is None:
            return self._model_id
        return resolve_model(task, model_policy, get_ai_config())


def _extract_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            text = getattr(item, "text", None)
            if isinstance(text, str):
                parts.append(text)
        if parts:
            return "".join(parts)
    raise AICallError("Anthropic response did not contain text content.")
