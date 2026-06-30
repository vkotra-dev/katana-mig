from __future__ import annotations

from typing import Protocol, TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class AIAdapter(Protocol):
    def call(self, system: str, user: str, response_model: type[T]) -> T:
        """Send a prompt and return a validated Pydantic model instance."""

    @property
    def model_id(self) -> str:
        """The model identifier used for this adapter."""


class AICallError(Exception):
    """Raised when the AI provider returns an error."""


class ConfigurationError(Exception):
    """Raised when a required config value is missing, invalid, or unrecognised."""

