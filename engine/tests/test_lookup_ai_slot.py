from __future__ import annotations

from pathlib import Path

import pytest

from migrations_engine.ai.adapter import ConfigurationError
from migrations_engine.ai.config import AIConfig, MigrationModelConfig, PlatformModelConfig, ProviderConfig, get_ai_config
from migrations_engine.ai.factory import get_adapter


FIXTURE_YAML = Path(__file__).parent / "fixtures" / "engine.yaml"


@pytest.fixture(autouse=True)
def _clear_ai_config_cache() -> None:
    get_ai_config.cache_clear()


def _make_config(*, lookup_mapping: str = "claude-sonnet-4-6") -> AIConfig:
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
            lookup_mapping=lookup_mapping,
            feed_analysis="claude-sonnet-4-6",
            impact_analysis="claude-sonnet-4-6",
        ),
        providers=ProviderConfig(
            anthropic_api_key_env="ANTHROPIC_API_KEY",
            openai_api_key_env="OPENAI_API_KEY",
        ),
    )


def test_migration_model_config_has_lookup_mapping_field() -> None:
    config = _make_config()
    assert config.migration_models.lookup_mapping == "claude-sonnet-4-6"


def test_fixture_yaml_includes_lookup_mapping() -> None:
    config = get_ai_config(FIXTURE_YAML)
    assert config.migration_models.lookup_mapping == "claude-sonnet-4-6"


def test_get_adapter_routes_lookup_mapping_to_anthropic(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("migrations_engine.ai.factory.get_ai_config", lambda: _make_config())
    monkeypatch.setenv("ANTHROPIC_API_KEY", "fake-key")

    adapter = get_adapter("lookup_mapping")
    assert adapter.__class__.__name__ == "AnthropicAdapter"


def test_get_adapter_unknown_task_still_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("migrations_engine.ai.factory.get_ai_config", lambda: _make_config())

    with pytest.raises(ConfigurationError, match="Unknown AI task"):
        get_adapter("not_a_real_task")
