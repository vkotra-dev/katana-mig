from __future__ import annotations

from .adapter import AIAdapter, ConfigurationError
from .anthropic_adapter import AnthropicAdapter
from .config import get_ai_config
from .openai_adapter import OpenAIAdapter


_SLOT_MAP = {
    "planning": lambda config: config.models.planning,
    "review": lambda config: config.models.review,
    "implementation": lambda config: config.models.implementation,
    "pii_review": lambda config: config.migration_models.pii_review,
    "field_mapping": lambda config: config.migration_models.field_mapping,
    "script_generation": lambda config: config.migration_models.script_generation,
    "script_correction": lambda config: config.migration_models.script_correction,
    "impact_analysis": lambda config: config.migration_models.impact_analysis,
}


def get_adapter(task: str) -> AIAdapter:
    config = get_ai_config()
    if task not in _SLOT_MAP:
        raise ConfigurationError(f"Unknown AI task: {task}")

    model_id = _SLOT_MAP[task](config)
    if model_id.startswith("claude-") or model_id.startswith("anthropic/"):
        return AnthropicAdapter(model_id=model_id, api_key_env=config.providers.anthropic_api_key_env)
    if model_id.startswith("gpt-") or model_id.startswith("o1-"):
        return OpenAIAdapter(model_id=model_id, api_key_env=config.providers.openai_api_key_env)
    raise ConfigurationError(f"Unrecognised model prefix for task {task}: {model_id}")
