from __future__ import annotations

import os
import sys
from types import ModuleType
from typing import TypeVar

from pydantic import BaseModel

from .adapter import AICallError, ConfigurationError

T = TypeVar("T", bound=BaseModel)


try:  # pragma: no cover - exercised indirectly through adapter tests
    import openai
except ImportError:  # pragma: no cover - environment shim for test isolation
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


class OpenAIAdapter:
    def __init__(self, *, model_id: str, api_key_env: str) -> None:
        self._model_id = model_id
        self._api_key_env = api_key_env
        api_key = os.environ.get(self._api_key_env)
        if not api_key:
            raise ConfigurationError(self._api_key_env)
        self._client = openai.OpenAI(api_key=api_key)

    @property
    def model_id(self) -> str:
        return self._model_id

    def call(self, system: str, user: str, response_model: type[T]) -> T:
        schema = response_model.model_json_schema()
        prompt = f"{system}\n\nReturn valid JSON matching this schema:\n{schema}"
        try:
            response = self._client.chat.completions.create(
                model=self._model_id,
                messages=[
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": user},
                ],
                response_format={"type": "json_object"},
            )
        except openai.OpenAIError as exc:  # pragma: no cover - exercised via adapter test doubles
            raise AICallError(str(exc)) from exc

        content = response.choices[0].message.content
        if not isinstance(content, str):
            raise AICallError("OpenAI response did not contain text content.")
        return response_model.model_validate_json(content)
