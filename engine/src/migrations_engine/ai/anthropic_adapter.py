from __future__ import annotations

import os
from typing import Any, TypeVar

import anthropic
from pydantic import BaseModel

from .adapter import AICallError, ConfigurationError

T = TypeVar("T", bound=BaseModel)


class AnthropicAdapter:
    def __init__(self, *, model_id: str, api_key_env: str) -> None:
        self._model_id = model_id
        self._api_key_env = api_key_env

    @property
    def model_id(self) -> str:
        return self._model_id

    def call(self, system: str, user: str, response_model: type[T]) -> T:
        api_key = os.environ.get(self._api_key_env)
        if not api_key:
            raise ConfigurationError(self._api_key_env)
        client = anthropic.Anthropic(api_key=api_key)
        schema = response_model.model_json_schema()
        prompt = f"{system}\n\nReturn valid JSON matching this schema:\n{schema}"
        try:
            response = client.messages.create(
                model=self._model_id,
                max_tokens=1024,
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
