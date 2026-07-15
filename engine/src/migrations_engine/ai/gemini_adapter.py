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


try:  # pragma: no cover
    import google.genai as genai
    from google.genai import types as genai_types
except ImportError:  # pragma: no cover - environment shim for test isolation
    genai = ModuleType("google.genai")  # type: ignore[assignment]
    genai_types = ModuleType("google.genai.types")  # type: ignore[assignment]

    class _FakeClient:
        def __init__(self, *_args: Any, **_kwargs: Any) -> None:
            self.models = _FakeModels()

    class _FakeModels:
        def generate_content(self, *_args: Any, **_kwargs: Any) -> Any:
            raise RuntimeError("google-genai package is not installed")

    genai.Client = _FakeClient  # type: ignore[attr-defined]
    genai_types.GenerateContentConfig = object  # type: ignore[attr-defined]
    sys.modules.setdefault("google.genai", genai)
    sys.modules.setdefault("google.genai.types", genai_types)


class GeminiAdapter:
    def __init__(self, *, model_id: str, api_key_env: str) -> None:
        self._model_id = model_id
        self._api_key_env = api_key_env
        api_key = os.environ.get(self._api_key_env)
        if not api_key:
            raise ConfigurationError(api_key_env)
        self._client = genai.Client(api_key=api_key)

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
        system_prompt = f"{system}\n\nReturn valid JSON matching this schema:\n{schema}"
        model_id = self._resolve_model(task=task, model_policy=model_policy)
        logger.info("Gemini AI Call - Model: %s", model_id)
        logger.info("System Prompt:\n%s", system_prompt)
        logger.info("User Prompt:\n%s", user)
        try:
            response = self._client.models.generate_content(
                model=model_id,
                contents=user,
                config=genai_types.GenerateContentConfig(
                    system_instruction=system_prompt,
                    response_mime_type="application/json",
                ),
            )
        except Exception as exc:
            logger.error("Gemini AI Call Failed - Model: %s, Error: %s", model_id, exc)
            raise AICallError(str(exc)) from exc

        text = response.text
        if not isinstance(text, str) or not text:
            raise AICallError("Gemini response did not contain text content.")
        logger.info("Gemini Response:\n%s", text)
        parsed = response_model.model_validate_json(text)
        return AICallResult(parsed=parsed, raw_response=text)

    def _resolve_model(self, *, task: str | None, model_policy: ModelPolicy | None) -> str:
        if task is None:
            return self._model_id
        return resolve_model(task, model_policy, get_ai_config())
