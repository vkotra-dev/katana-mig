from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest
from pydantic import BaseModel

from migrations_engine.ai.adapter import ConfigurationError
from migrations_engine.ai.config import AIConfig, MigrationModelConfig, PlatformModelConfig, ProviderConfig
from migrations_engine.ai.factory import get_adapter


class DemoResponse(BaseModel):
    value: str


def _make_config(
    *,
    planning: str = "claude-opus-4-8",
    review: str = "claude-sonnet-4-6",
    implementation: str = "claude-sonnet-4-6",
    pii_review: str = "claude-haiku-4-5-20251001",
    field_mapping: str = "claude-opus-4-8",
    script_generation: str = "gpt-4o-mini",
    script_correction: str = "claude-sonnet-4-6",
    lookup_mapping: str = "claude-sonnet-4-6",
    feed_analysis: str = "claude-sonnet-4-6",
    impact_analysis: str = "claude-sonnet-4-6",
) -> AIConfig:
    return AIConfig(
        models=PlatformModelConfig(
            planning=planning,
            review=review,
            implementation=implementation,
        ),
        migration_models=MigrationModelConfig(
            pii_review=pii_review,
            field_mapping=field_mapping,
            script_generation=script_generation,
            script_correction=script_correction,
            lookup_mapping=lookup_mapping,
            feed_analysis=feed_analysis,
            impact_analysis=impact_analysis,
        ),
        providers=ProviderConfig(
            anthropic_api_key_env="ANTHROPIC_API_KEY",
            openai_api_key_env="OPENAI_API_KEY",
        ),
    )


def test_get_adapter_routes_by_model_prefix(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("migrations_engine.ai.factory.get_ai_config", lambda: _make_config())
    monkeypatch.setenv("ANTHROPIC_API_KEY", "anthropic-secret")
    monkeypatch.setenv("OPENAI_API_KEY", "openai-secret")

    anthropic_adapter = get_adapter("field_mapping")
    openai_adapter = get_adapter("script_generation")

    assert anthropic_adapter.__class__.__name__ == "AnthropicAdapter"
    assert openai_adapter.__class__.__name__ == "OpenAIAdapter"


def test_get_adapter_routes_lookup_mapping(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("migrations_engine.ai.factory.get_ai_config", lambda: _make_config())
    monkeypatch.setenv("ANTHROPIC_API_KEY", "anthropic-secret")

    adapter = get_adapter("lookup_mapping")

    assert adapter.__class__.__name__ == "AnthropicAdapter"


def test_get_adapter_rejects_unknown_task(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("migrations_engine.ai.factory.get_ai_config", lambda: _make_config())

    with pytest.raises(ConfigurationError, match="unknown_task"):
        get_adapter("unknown_task")


def test_anthropic_adapter_calls_sdk_and_parses_response(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_response = SimpleNamespace(content=[SimpleNamespace(text='{"value":"ok"}')])
    calls: dict[str, Any] = {}

    class FakeMessages:
        def create(self, **kwargs: Any) -> SimpleNamespace:
            calls.update(kwargs)
            return fake_response

    class FakeAnthropicClient:
        def __init__(self, *, api_key: str) -> None:
            calls["api_key"] = api_key
            self.messages = FakeMessages()

    monkeypatch.setenv("ANTHROPIC_API_KEY", "anthropic-secret")
    monkeypatch.setattr("migrations_engine.ai.factory.get_ai_config", lambda: _make_config())
    monkeypatch.setattr("anthropic.Anthropic", FakeAnthropicClient)

    adapter = get_adapter("planning")
    result = adapter.call("system prompt", "user prompt", DemoResponse)

    assert result.value == "ok"
    assert calls["api_key"] == "anthropic-secret"
    assert calls["model"] == "claude-opus-4-8"
    assert calls["max_tokens"] >= 4096
    assert calls["messages"] == [{"role": "user", "content": "user prompt"}]
    assert "system prompt" in calls["system"]
    assert "DemoResponse" in calls["system"]


def test_openai_adapter_calls_sdk_and_parses_response(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_response = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content='{"value":"ok"}'))]
    )
    calls: dict[str, Any] = {}

    class FakeCompletions:
        def create(self, **kwargs: Any) -> SimpleNamespace:
            calls.update(kwargs)
            return fake_response

    class FakeChat:
        def __init__(self) -> None:
            self.completions = FakeCompletions()

    class FakeOpenAIClient:
        def __init__(self, *, api_key: str) -> None:
            calls["api_key"] = api_key
            self.chat = FakeChat()

    monkeypatch.setenv("OPENAI_API_KEY", "openai-secret")
    monkeypatch.setattr("migrations_engine.ai.factory.get_ai_config", lambda: _make_config())
    monkeypatch.setattr("openai.OpenAI", FakeOpenAIClient)

    adapter = get_adapter("script_generation")
    result = adapter.call("system prompt", "user prompt", DemoResponse)

    assert result.value == "ok"
    assert calls["api_key"] == "openai-secret"
    assert calls["model"] == "gpt-4o-mini"
    assert calls["messages"][0]["role"] == "system"
    assert "system prompt" in calls["messages"][0]["content"]
    assert "DemoResponse" in calls["messages"][0]["content"]
    assert calls["messages"] == [
        {"role": "system", "content": calls["messages"][0]["content"]},
        {"role": "user", "content": "user prompt"},
    ]
    assert calls["response_format"] == {"type": "json_object"}


def test_missing_api_key_raises_at_call_time(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr("migrations_engine.ai.factory.get_ai_config", lambda: _make_config())

    with pytest.raises(ConfigurationError, match="ANTHROPIC_API_KEY"):
        get_adapter("field_mapping")
