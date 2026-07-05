from __future__ import annotations

from typing import Any

from .adapter import AIAdapter, ConfigurationError
from .anthropic_adapter import AnthropicAdapter
from .config import get_ai_config, resolve_model
from .gemini_adapter import GeminiAdapter
from .mock_adapter import MockAdapter
from ..api.schemas import ModelPolicy
from .openai_adapter import OpenAIAdapter


_SLOT_MAP = {
    "planning": lambda config: config.models.planning,
    "review": lambda config: config.models.review,
    "implementation": lambda config: config.models.implementation,
    "pii_review": lambda config: config.migration_models.pii_review,
    "field_mapping": lambda config: config.migration_models.field_mapping,
    "lookup_mapping": lambda config: config.migration_models.lookup_mapping,
    "script_generation": lambda config: config.migration_models.script_generation,
    "script_correction": lambda config: config.migration_models.script_correction,
    "schema_dependency": lambda config: config.migration_models.schema_dependency,
    "impact_analysis": lambda config: config.migration_models.impact_analysis,
    "feed_analysis": lambda config: config.migration_models.feed_analysis,
}


def _coerce_model_policy(model_policy: ModelPolicy | dict[str, Any] | None) -> ModelPolicy | None:
    if model_policy is None:
        return None
    if isinstance(model_policy, ModelPolicy):
        return model_policy
    return ModelPolicy.model_validate(model_policy)


def get_adapter(task: str, model_policy: ModelPolicy | dict[str, Any] | None = None) -> AIAdapter:
    config = get_ai_config()
    if task not in _SLOT_MAP:
        raise ConfigurationError(f"Unknown AI task: {task}")

    policy = _coerce_model_policy(model_policy)
    model_id = resolve_model(task, policy, config)
    if model_id.startswith("claude-") or model_id.startswith("anthropic/"):
        return AnthropicAdapter(model_id=model_id, api_key_env=config.providers.anthropic_api_key_env)
    if model_id.startswith("gpt-") or model_id.startswith("o1-") or model_id.startswith("o3-") or model_id.startswith("o4-"):
        return OpenAIAdapter(model_id=model_id, api_key_env=config.providers.openai_api_key_env)
    if model_id.startswith("gemini-") or model_id.startswith("models/gemini-"):
        return GeminiAdapter(model_id=model_id, api_key_env=config.providers.gemini_api_key_env)
    if model_id == "mock":
        return MockAdapter()
    raise ConfigurationError(f"Unrecognised model prefix for task {task}: {model_id}")
