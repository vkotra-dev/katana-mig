from __future__ import annotations

from pathlib import Path

import pytest

from migrations_engine.ai.adapter import ConfigurationError
from migrations_engine.ai.config import get_ai_config
from migrations_engine.ai.factory import get_adapter


@pytest.fixture(autouse=True)
def _clear_ai_config_cache() -> None:
    get_ai_config.cache_clear()


def test_impact_analysis_slot_is_available(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    config_path = tmp_path / "engine.yaml"
    config_path.write_text(
        "models:\n"
        "  planning: claude-opus-4-8\n"
        "  review: claude-sonnet-4-6\n"
        "  implementation: claude-sonnet-4-6\n"
        "migration:\n"
        "  models:\n"
        "    pii_review: claude-haiku-4-5-20251001\n"
        "    field_mapping: claude-opus-4-8\n"
        "    script_generation: gpt-4o-mini\n"
        "    script_correction: claude-sonnet-4-6\n"
        "    impact_analysis: claude-sonnet-4-6\n"
        "providers:\n"
        "  anthropic_api_key_env: ANTHROPIC_API_KEY\n"
        "  openai_api_key_env: OPENAI_API_KEY\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("CONFIG_PATH", str(config_path))
    monkeypatch.setenv("ANTHROPIC_API_KEY", "anthropic-secret")
    monkeypatch.setenv("OPENAI_API_KEY", "openai-secret")

    get_ai_config.cache_clear()
    adapter = get_adapter("impact_analysis")

    assert adapter.__class__.__name__ == "AnthropicAdapter"


def test_unknown_slot_still_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("migrations_engine.ai.factory.get_ai_config", lambda: None)

    with pytest.raises(ConfigurationError, match="Unknown AI task: nonexistent_slot_xyz"):
        get_adapter("nonexistent_slot_xyz")
