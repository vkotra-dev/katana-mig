from __future__ import annotations

from pathlib import Path

import pytest

from migrations_engine.ai.config import ConfigurationError, get_ai_config


FIXTURE_YAML = Path(__file__).parent / "fixtures" / "engine.yaml"


@pytest.fixture(autouse=True)
def _clear_ai_config_cache() -> None:
    get_ai_config.cache_clear()


def test_load_valid_config_from_fixture() -> None:
    config = get_ai_config(FIXTURE_YAML)

    assert config.models.planning == "claude-opus-4-8"
    assert config.models.review == "claude-sonnet-4-6"
    assert config.models.implementation == "claude-sonnet-4-6"
    assert config.migration_models.script_generation == "gpt-4o-mini"
    assert config.providers.anthropic_api_key_env == "ANTHROPIC_API_KEY"
    assert config.providers.openai_api_key_env == "OPENAI_API_KEY"


def test_substitutes_env_values_and_raises_for_missing_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    config_path = tmp_path / "engine.yaml"
    config_path.write_text(
        "models:\n"
        "  planning: ${MODEL_PLANNING}\n"
        "  review: ${MODEL_REVIEW}\n"
        "  implementation: ${MODEL_IMPLEMENTATION}\n"
        "migration:\n"
        "  models:\n"
        "    pii_review: ${MODEL_PII_REVIEW}\n"
        "    field_mapping: ${MODEL_FIELD_MAPPING}\n"
        "    script_generation: ${MODEL_SCRIPT_GENERATION}\n"
        "    script_correction: ${MODEL_SCRIPT_CORRECTION}\n"
        "providers:\n"
        "  anthropic_api_key_env: ANTHROPIC_API_KEY\n"
        "  openai_api_key_env: OPENAI_API_KEY\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("MODEL_PLANNING", "claude-opus-4-8")
    monkeypatch.setenv("MODEL_REVIEW", "claude-sonnet-4-6")
    monkeypatch.setenv("MODEL_IMPLEMENTATION", "claude-sonnet-4-6")
    monkeypatch.setenv("MODEL_PII_REVIEW", "claude-haiku-4-5-20251001")
    monkeypatch.setenv("MODEL_FIELD_MAPPING", "claude-opus-4-8")
    monkeypatch.setenv("MODEL_SCRIPT_GENERATION", "gpt-4o-mini")
    monkeypatch.setenv("MODEL_SCRIPT_CORRECTION", "claude-sonnet-4-6")

    config = get_ai_config(config_path)
    assert config.migration_models.pii_review == "claude-haiku-4-5-20251001"

    monkeypatch.delenv("MODEL_SCRIPT_CORRECTION", raising=False)
    with pytest.raises(ConfigurationError, match="MODEL_SCRIPT_CORRECTION"):
        get_ai_config.__wrapped__(config_path)
