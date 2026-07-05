from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import TypeVar

from pydantic import BaseModel

from .adapter import AICallError, ConfigurationError
from ..api.schemas import ModelPolicy

T = TypeVar("T", bound=BaseModel)

logger = logging.getLogger(__name__)

_FIXTURE_DIR = Path(__file__).resolve().parents[3] / "config" / "mock_responses"


class MockAdapter:
    """Returns canned JSON fixtures instead of calling a real AI provider.

    Fixtures live in engine/config/mock_responses/<ClassName>.json.
    Set any model config to "mock" to activate.
    """

    def __init__(self) -> None:
        if not _FIXTURE_DIR.exists():
            raise ConfigurationError(
                f"Mock response directory not found: {_FIXTURE_DIR}. "
                "Create it and add <ClassName>.json fixture files."
            )

    @property
    def model_id(self) -> str:
        return "mock"

    def call(
        self,
        system: str,
        user: str,
        response_model: type[T],
        *,
        task: str | None = None,
        model_policy: ModelPolicy | None = None,
    ) -> T:
        class_name = response_model.__name__
        fixture_path = _FIXTURE_DIR / f"{class_name}.json"
        logger.info("MockAdapter: loading fixture %s", fixture_path)
        if not fixture_path.exists():
            raise AICallError(
                f"No mock fixture found for {class_name}. "
                f"Create {fixture_path} with a valid JSON response."
            )
        raw = json.loads(fixture_path.read_text(encoding="utf-8"))
        logger.info("MockAdapter: returning fixture for %s", class_name)
        return response_model.model_validate(raw)
