from __future__ import annotations

from dataclasses import dataclass
from typing import Generic, Protocol, TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


@dataclass
class AICallResult(Generic[T]):
    """Wraps both the parsed Pydantic model and the raw provider response string."""

    parsed: T
    raw_response: str


class AIAdapter(Protocol):
    def call(self, system: str, user: str, response_model: type[T]) -> AICallResult[T]:
        """Send a prompt and return parsed model + raw response string."""

    @property
    def model_id(self) -> str:
        """The model identifier used for this adapter."""


class AICallError(Exception):
    """Raised when the AI provider returns an error."""


class ConfigurationError(Exception):
    """Raised when a required config value is missing, invalid, or unrecognised."""

class AIResponseValidationError(Exception):
    """Raised when the AI returns a response that fails schema validation."""
    def __init__(self, raw_response: str, original: Exception):
        super().__init__(str(original))
        self.raw_response = raw_response
        self.original = original

