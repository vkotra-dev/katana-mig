from __future__ import annotations

from pathlib import Path

import pytest

from migrations_engine.ai.adapter import ConfigurationError
from migrations_engine.ai.config import get_ai_config
from migrations_engine.ai.factory import get_adapter, _SLOT_MAP


FIXTURE_YAML = Path(__file__).parent / "fixtures" / "engine.yaml"


@pytest.fixture(autouse=True)
def _clear_ai_config_cache() -> None:
    get_ai_config.cache_clear()


def test_impact_analysis_slot_is_in_factory(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config_file = tmp_path / "engine.yaml"
    config_file.write_text(
        "models:\n"
        "  planning: claude-3-haiku-20240307\n"
        "  review: claude-3-haiku-20240307\n"
        "  implementation: claude-3-haiku-20240307\n"
        "migration:\n"
        "  models:\n"
        "    pii_review: claude-3-haiku-20240307\n"
        "    field_mapping: claude-3-haiku-20240307\n"
        "    lookup_mapping: claude-3-haiku-20240307\n"
        "    script_generation: claude-3-haiku-20240307\n"
        "    script_correction: claude-3-haiku-20240307\n"
        "    feed_analysis: claude-3-haiku-20240307\n"
        "    impact_analysis: claude-3-haiku-20240307\n"
        "providers:\n"
        "  anthropic_api_key_env: ANTHROPIC_API_KEY\n"
        "  openai_api_key_env: OPENAI_API_KEY\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("CONFIG_PATH", str(config_file))
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")

    get_ai_config.cache_clear()
    try:
        assert "impact_analysis" in _SLOT_MAP
        adapter = get_adapter("impact_analysis")
        assert adapter.__class__.__name__ == "AnthropicAdapter"
    finally:
        get_ai_config.cache_clear()


def test_unknown_slot_still_raises() -> None:
    assert "nonexistent_slot_xyz" not in _SLOT_MAP
