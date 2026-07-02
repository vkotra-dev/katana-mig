from __future__ import annotations

from pathlib import Path

import pytest

from migrations_engine.ai.adapter import ConfigurationError
from migrations_engine.ai.config import (
    AIConfig,
    MigrationModelConfig,
    PlatformModelConfig,
    ProviderConfig,
    get_ai_config,
)
from migrations_engine.ai.factory import get_adapter


FIXTURE_YAML = Path(__file__).parent / "fixtures" / "engine.yaml"


@pytest.fixture(autouse=True)
def _clear_ai_config_cache() -> None:
    get_ai_config.cache_clear()


def _make_config(*, feed_analysis: str = "claude-sonnet-4-6") -> AIConfig:
    return AIConfig(
        models=PlatformModelConfig(
            planning="claude-opus-4-8",
            review="claude-sonnet-4-6",
            implementation="claude-sonnet-4-6",
        ),
        migration_models=MigrationModelConfig(
            pii_review="claude-haiku-4-5-20251001",
            field_mapping="claude-opus-4-8",
            script_generation="gpt-4o-mini",
            script_correction="claude-sonnet-4-6",
            impact_analysis="claude-sonnet-4-6",
            feed_analysis=feed_analysis,
        ),
        providers=ProviderConfig(
            anthropic_api_key_env="ANTHROPIC_API_KEY",
            openai_api_key_env="OPENAI_API_KEY",
        ),
    )


def test_feed_analysis_loaded_from_fixture() -> None:
    config = get_ai_config(FIXTURE_YAML)

    assert config.migration_models.feed_analysis == "claude-sonnet-4-6"


def test_feed_analysis_is_required_in_migration_models(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
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
        "    impact_analysis: ${MODEL_IMPACT_ANALYSIS}\n"
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
    monkeypatch.setenv("MODEL_IMPACT_ANALYSIS", "claude-sonnet-4-6")

    with pytest.raises(ConfigurationError, match="migration.models.feed_analysis"):
        get_ai_config.__wrapped__(config_path)


def test_get_adapter_routes_feed_analysis_to_anthropic(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("migrations_engine.ai.factory.get_ai_config", lambda: _make_config())
    monkeypatch.setenv("ANTHROPIC_API_KEY", "fake-key")

    adapter = get_adapter("feed_analysis")
    assert adapter.__class__.__name__ == "AnthropicAdapter"


def test_get_adapter_unknown_task_still_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("migrations_engine.ai.factory.get_ai_config", lambda: _make_config())

    with pytest.raises(ConfigurationError, match="Unknown AI task"):
        get_adapter("not_a_real_task")
