from __future__ import annotations

import os
import sys
from types import ModuleType
from typing import Any, TypeVar

from pydantic import BaseModel

from .adapter import AICallError, ConfigurationError

T = TypeVar("T", bound=BaseModel)


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

    def call(self, system: str, user: str, response_model: type[T]) -> T:
        schema = response_model.model_json_schema()
        prompt = f"{system}\n\nReturn valid JSON matching this schema:\n{schema}"
        try:
            response = self._client.messages.create(
                model=self._model_id,
                max_tokens=4096,
                system=prompt,
                messages=[{"role": "user", "content": user}],
            )
        except anthropic.APIError as exc:  # pragma: no cover - exercised via adapter test doubles
            raise AICallError(str(exc)) from exc

        content = getattr(response, "content", None)
        text = _extract_text(content)
        return response_model.model_validate_json(text)


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
