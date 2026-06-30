# Task 001s — AI Adapter Layer

**Plan:** `plans/2026-06-29-001s-ai-adapters.md`

## Domain

- `docs/domain/governance.md` — model policy, key management rules

## Scope

Add an AI adapter package that reads model assignments from a YAML config file,
resolves provider API keys from environment variables, exposes a minimal
structured-output interface, and is the single call site for every stage that
needs an LLM (source analysis, mapping, code generation).

No source analysis, mapping, or codegen logic in this task — just the adapters
that those stages will call.

## Package layout

```
engine/src/migrations_engine/ai/
    __init__.py
    adapter.py            — AIAdapter protocol
    anthropic_adapter.py  — AnthropicAdapter implementation
    openai_adapter.py     — OpenAIAdapter implementation
    factory.py            — get_adapter(task) -> AIAdapter
    config.py             — YAML loader for AI model config

engine/config/
    engine.yaml           — model slot config (env-var substitution)
```

## Config file — `engine/config/engine.yaml`

```yaml
models:
  planning: ${MODEL_PLANNING}
  review: ${MODEL_REVIEW}
  implementation: ${MODEL_IMPLEMENTATION}
migration:
  models:
    pii_review: ${MODEL_PII_REVIEW}
    field_mapping: ${MODEL_FIELD_MAPPING}
    script_generation: ${MODEL_SCRIPT_GENERATION}
    script_correction: ${MODEL_SCRIPT_CORRECTION}
providers:
  anthropic_api_key_env: ANTHROPIC_API_KEY
  openai_api_key_env: OPENAI_API_KEY
```

Every `${VAR}` is substituted at load time from the process environment.
`ConfigurationError` is raised if the variable is not set. The `providers`
values are the **names** of the API-key environment variables, not the keys
themselves — the adapters call `os.environ[config.providers.anthropic_api_key_env]`
at call time.

Config path resolution order (same as migrations project):
1. `CONFIG_PATH` env var (explicit override)
2. `./engine/config/engine.yaml` (run from repo root)
3. `./config/engine.yaml` (run from `engine/`)
4. `/app/config/engine.yaml` (container default)

## `ai/config.py` — YAML loader

Dataclasses for the config shape:

```python
@dataclass(frozen=True)
class PlatformModelConfig:
    planning: str
    review: str
    implementation: str

@dataclass(frozen=True)
class MigrationModelConfig:
    pii_review: str
    field_mapping: str
    script_generation: str
    script_correction: str

@dataclass(frozen=True)
class ProviderConfig:
    anthropic_api_key_env: str
    openai_api_key_env: str

@dataclass(frozen=True)
class AIConfig:
    models: PlatformModelConfig
    migration_models: MigrationModelConfig
    providers: ProviderConfig
```

Loader:

```python
import re, os, yaml
from functools import lru_cache
from pathlib import Path

_ENV_PATTERN = re.compile(r"\$\{([A-Z0-9_]+)\}")

@lru_cache(maxsize=1)
def get_ai_config(config_path: Path | str | None = None) -> AIConfig:
    path = _resolve_config_path(config_path)
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    substituted = _substitute_env_values(raw)
    return _parse_config(substituted)
```

`_substitute_env_values` walks the parsed YAML dict recursively, replacing every
`${VAR}` string with `os.environ[VAR]`. Raises `ConfigurationError` if the
variable is missing. The function signature is the same pattern used in
`migrations/engine/src/migrations_engine/infra/service.py`.

`_parse_config` validates the dict structure and builds the frozen dataclasses.
Raises `ConfigurationError` with a descriptive message for any missing or
invalid field.

## `.env` additions

```
# Provider keys (read by adapters at call time via providers.anthropic_api_key_env)
ANTHROPIC_API_KEY=
OPENAI_API_KEY=

# Model slots (substituted into engine.yaml at startup)
MODEL_PLANNING=claude-opus-4-8
MODEL_REVIEW=claude-sonnet-4-6
MODEL_IMPLEMENTATION=claude-sonnet-4-6
MODEL_PII_REVIEW=claude-haiku-4-5-20251001
MODEL_FIELD_MAPPING=claude-opus-4-8
MODEL_SCRIPT_GENERATION=gpt-4o-mini
MODEL_SCRIPT_CORRECTION=claude-sonnet-4-6
```

These are required: the YAML uses `${VAR}` substitution which raises at startup
if any `MODEL_*` variable is absent. The API keys are read lazily at call time.

## `config.py` (Pydantic Settings) — no change to model slots

Model slots and provider keys are NOT added to the Pydantic `Settings` class.
They live entirely in `engine.yaml` + environment. The existing `Settings` class
(DB credentials, JWT secret, bootstrap admin, etc.) is unchanged.

## AIAdapter protocol

```python
from typing import Protocol, TypeVar
from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)

class AIAdapter(Protocol):
    def call(self, system: str, user: str, response_model: type[T]) -> T:
        """Send a prompt, return a validated Pydantic model instance."""
        ...

    @property
    def model_id(self) -> str:
        """The model identifier used for this adapter (for audit logging)."""
        ...
```

## Factory

```python
def get_adapter(task: str) -> AIAdapter:
    """Return a configured AIAdapter for the given task slot.

    task: one of "planning", "review", "implementation",
          "pii_review", "field_mapping", "script_generation", "script_correction"

    Model is resolved from get_ai_config().
    Provider is inferred from the model id:
      "claude-*" or "anthropic/*"  → AnthropicAdapter
      "gpt-*" or "o1-*"           → OpenAIAdapter

    Raises ConfigurationError for unknown task or unrecognised model prefix.
    """
```

Model slot lookup:

```python
_SLOT_MAP = {
    "planning":          lambda c: c.models.planning,
    "review":            lambda c: c.models.review,
    "implementation":    lambda c: c.models.implementation,
    "pii_review":        lambda c: c.migration_models.pii_review,
    "field_mapping":     lambda c: c.migration_models.field_mapping,
    "script_generation": lambda c: c.migration_models.script_generation,
    "script_correction": lambda c: c.migration_models.script_correction,
}
```

Model slot → pipeline stage mapping:

| Slot | Used by |
|---|---|
| `planning` | Source analysis (001v) |
| `pii_review` | PII masking during intake (001q) |
| `field_mapping` | Mapping stage (001w) |
| `script_generation` | Code generation (001y) |
| `script_correction` | Codegen validation fix-up (001y) |
| `review` | Review gates (001z) |
| `implementation` | Run execution helpers (001t) |

## AnthropicAdapter

- Reads API key via `os.environ[config.providers.anthropic_api_key_env]`
  at call time; raises `ConfigurationError` if missing
- Model ID comes from the resolved slot (e.g. `"claude-opus-4-8"`)
- Structured output: include `response_model.model_json_schema()` in system prompt;
  parse response with `response_model.model_validate_json()`
- Raises `AICallError` on `anthropic.APIError`
- No retry logic (YAGNI)

## OpenAIAdapter

- Reads API key via `os.environ[config.providers.openai_api_key_env]`
  at call time; raises `ConfigurationError` if missing
- Model ID comes from the resolved slot (e.g. `"gpt-4o-mini"`)
- Uses the `openai` Python SDK
- Structured output: `response_format={"type": "json_object"}` + schema in system prompt;
  parse response with `response_model.model_validate_json()`
- Raises `AICallError` on `openai.OpenAIError`
- No retry logic (YAGNI)

## Error types

```python
class AICallError(Exception):
    """Raised when the AI provider returns an error."""

class ConfigurationError(Exception):
    """Raised when a required config value is missing, invalid, or unrecognised."""
```

## Tests

- YAML loading: valid config file → correct `AIConfig` dataclass values
- YAML loading: missing `${MODEL_PLANNING}` env var → `ConfigurationError` at load
- YAML loading: missing required YAML section → `ConfigurationError` at load
- `get_adapter("field_mapping")` returns `AnthropicAdapter` (default model is `claude-*`)
- `get_adapter("script_generation")` returns `OpenAIAdapter` (default model is `gpt-*`)
- `get_adapter("unknown_task")` raises `ConfigurationError`
- Missing API key env var raises `ConfigurationError` at call time (not startup)
- `AnthropicAdapter.call()` constructs prompt correctly (mocked SDK)
- `OpenAIAdapter.call()` constructs prompt correctly (mocked SDK)
- `AICallError` wraps provider API errors for both adapters
- No live API calls in tests; config loaded from a fixture YAML in tests

## Acceptance criteria

- [ ] `engine/config/engine.yaml` exists with the exact model slot structure shown above
- [ ] `from migrations_engine.ai.factory import get_adapter` works
- [ ] `get_adapter("field_mapping")` returns an `AnthropicAdapter`
- [ ] `get_adapter("script_generation")` returns an `OpenAIAdapter`
- [ ] Missing `MODEL_*` env var raises `ConfigurationError` at startup (YAML substitution)
- [ ] Missing API key raises `ConfigurationError` at call time (not startup)
- [ ] `call()` returns a validated Pydantic model instance for both adapters
- [ ] Pydantic `Settings` class unchanged — no model slot fields added
- [ ] `.env` contains placeholder entries for all keys and slots
- [ ] All tests pass without network access

## Notes

- `anthropic` and `openai` SDKs must both be added to `pyproject.toml` / `requirements.txt`
- `pyyaml` already a dependency in the migrations project; add to katana engine if missing
- Model slots are deployment-level config only — no per-project override
- Provider is inferred from the model ID string; no separate provider field needed
- YAML loading pattern mirrors `migrations/engine/src/migrations_engine/infra/service.py`
- Config path resolution mirrors migrations: `CONFIG_PATH` env var → `engine/config/engine.yaml` → `config/engine.yaml` → `/app/config/engine.yaml`
