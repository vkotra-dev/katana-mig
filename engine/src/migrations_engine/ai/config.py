from __future__ import annotations

import os
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, cast

import yaml

from .adapter import ConfigurationError


_ENV_PATTERN = re.compile(r"^\$\{([A-Z0-9_]+)\}$")


@dataclass(frozen=True)
class PlatformModelConfig:
    planning: str
    review: str
    implementation: str


@dataclass(frozen=True)
class MigrationModelConfig:
    pii_review: str
    field_mapping: str
    lookup_mapping: str
    script_generation: str
    script_correction: str
    impact_analysis: str
    feed_analysis: str


@dataclass(frozen=True)
class ProviderConfig:
    anthropic_api_key_env: str
    openai_api_key_env: str


@dataclass(frozen=True)
class AIConfig:
    models: PlatformModelConfig
    migration_models: MigrationModelConfig
    providers: ProviderConfig


def _resolve_config_path(config_path: Path | str | None = None) -> Path:
    if config_path is not None:
        return Path(config_path)

    override = os.environ.get("CONFIG_PATH")
    if override:
        return Path(override)

    candidates = [
        Path.cwd() / "engine" / "config" / "engine.yaml",
        Path.cwd() / "config" / "engine.yaml",
        Path("/app/config/engine.yaml"),
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    raise ConfigurationError("engine.yaml not found in any configured location.")


def _substitute_env_values(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _substitute_env_values(child) for key, child in value.items()}
    if isinstance(value, list):
        return [_substitute_env_values(child) for child in value]
    if isinstance(value, str):
        match = _ENV_PATTERN.match(value)
        if match:
            env_name = match.group(1)
            if env_name not in os.environ:
                raise ConfigurationError(f"Missing required environment variable: {env_name}")
            return os.environ[env_name]
    return value


def _parse_config(raw: Any) -> AIConfig:
    if not isinstance(raw, dict):
        raise ConfigurationError("AI config must be a mapping.")

    models = _require_mapping(raw, "models")
    migration = _require_mapping(raw, "migration")
    migration_models = _require_mapping(migration, "models")
    providers = _require_mapping(raw, "providers")

    return AIConfig(
        models=PlatformModelConfig(
            planning=_require_str(models, "planning", "models.planning"),
            review=_require_str(models, "review", "models.review"),
            implementation=_require_str(models, "implementation", "models.implementation"),
        ),
        migration_models=MigrationModelConfig(
            pii_review=_require_str(migration_models, "pii_review", "migration.models.pii_review"),
            field_mapping=_require_str(migration_models, "field_mapping", "migration.models.field_mapping"),
            lookup_mapping=_require_str(migration_models, "lookup_mapping", "migration.models.lookup_mapping"),
            script_generation=_require_str(
                migration_models,
                "script_generation",
                "migration.models.script_generation",
            ),
            script_correction=_require_str(
                migration_models,
                "script_correction",
                "migration.models.script_correction",
            ),
            impact_analysis=_require_str(
                migration_models,
                "impact_analysis",
                "migration.models.impact_analysis",
            ),
            feed_analysis=_require_str(
                migration_models,
                "feed_analysis",
                "migration.models.feed_analysis",
            ),
        ),
        providers=ProviderConfig(
            anthropic_api_key_env=_require_str(
                providers, "anthropic_api_key_env", "providers.anthropic_api_key_env"
            ),
            openai_api_key_env=_require_str(providers, "openai_api_key_env", "providers.openai_api_key_env"),
        ),
    )


def _require_mapping(raw: dict[str, Any], key: str) -> dict[str, Any]:
    value = raw.get(key)
    if not isinstance(value, dict):
        raise ConfigurationError(f"AI config is missing required mapping: {key}")
    return cast(dict[str, Any], value)


def _require_str(raw: dict[str, Any], key: str, path: str) -> str:
    value = raw.get(key)
    if not isinstance(value, str) or not value:
        raise ConfigurationError(f"AI config is missing required string: {path}")
    return value


@lru_cache(maxsize=1)
def get_ai_config(config_path: Path | str | None = None) -> AIConfig:
    path = _resolve_config_path(config_path)
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    substituted = _substitute_env_values(raw)
    return _parse_config(substituted)
