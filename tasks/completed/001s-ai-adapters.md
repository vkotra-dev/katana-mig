# Task 001s — AI Adapter Layer

**Plan:** `plans/2026-06-29-001s-ai-adapters.md`

## Domain

- `docs/domain/governance.md` — model policy, key management rules

## Scope

Add an AI adapter package that reads API keys and model assignments from environment,
exposes a minimal structured-output interface, and is the single call site for every
stage that needs an LLM (source analysis, mapping, code generation).

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
```

## Settings additions (`config.py`)

```python
# Provider keys
anthropic_api_key: str | None = Field(default=None, alias="ANTHROPIC_API_KEY")
openai_api_key: str | None = Field(default=None, alias="OPENAI_API_KEY")

# Model slots — deployment-level defaults; no per-project override
model_planning: str = Field(default="claude-opus-4-8",          alias="MODEL_PLANNING")
model_pii_review: str = Field(default="claude-haiku-4-5-20251001", alias="MODEL_PII_REVIEW")
model_field_mapping: str = Field(default="claude-opus-4-8",     alias="MODEL_FIELD_MAPPING")
model_script_generation: str = Field(default="gpt-4o-mini",     alias="MODEL_SCRIPT_GENERATION")
model_script_correction: str = Field(default="claude-sonnet-4-6", alias="MODEL_SCRIPT_CORRECTION")
model_review: str = Field(default="claude-sonnet-4-6",          alias="MODEL_REVIEW")
model_implementation: str = Field(default="claude-sonnet-4-6",  alias="MODEL_IMPLEMENTATION")
```

Model slots map to pipeline stages:

| Slot | Used by |
|---|---|
| `planning` | Source analysis (001v) |
| `pii_review` | PII masking during intake (001q) |
| `field_mapping` | Mapping stage (001w) |
| `script_generation` | Code generation (001y) |
| `script_correction` | Codegen validation fix-up (001y) |
| `review` | Review gates (001z) |
| `implementation` | Run execution helpers (001t) |

No key = adapter raises `ConfigurationError` at call time, not at startup.
The engine starts fine without keys; only stages that call the adapter fail.

## `.env` additions

```
ANTHROPIC_API_KEY=
OPENAI_API_KEY=

MODEL_PLANNING=claude-opus-4-8
MODEL_PII_REVIEW=claude-haiku-4-5-20251001
MODEL_FIELD_MAPPING=claude-opus-4-8
MODEL_SCRIPT_GENERATION=gpt-4o-mini
MODEL_SCRIPT_CORRECTION=claude-sonnet-4-6
MODEL_REVIEW=claude-sonnet-4-6
MODEL_IMPLEMENTATION=claude-sonnet-4-6
```

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

    task: one of "planning", "pii_review", "field_mapping", "script_generation",
          "script_correction", "review", "implementation"

    Provider is inferred from the model id:
      "claude-*" or "anthropic/*"  → AnthropicAdapter
      "gpt-*" or "o1-*"           → OpenAIAdapter
    """
```

Provider is inferred from the model ID — no explicit provider field needed.
Unrecognised task raises `ConfigurationError`.

## AnthropicAdapter

- Reads `ANTHROPIC_API_KEY` from settings; raises `ConfigurationError` if missing
- Model determined by the task slot (e.g. `settings.model_field_mapping`)
- Structured output: include `response_model.model_json_schema()` in system prompt;
  parse response with `response_model.model_validate_json()`
- Raises `AICallError` on `anthropic.APIError`
- No retry logic (YAGNI)

## OpenAIAdapter

- Reads `OPENAI_API_KEY` from settings; raises `ConfigurationError` if missing
- Model determined by the task slot (e.g. `settings.model_script_generation`)
- Uses the `openai` Python SDK
- Structured output: use `response_format={"type": "json_object"}` + schema in system prompt;
  parse response with `response_model.model_validate_json()`
- Raises `AICallError` on `openai.OpenAIError`
- No retry logic (YAGNI)

## Error types

```python
class AICallError(Exception):
    """Raised when the AI provider returns an error."""

class ConfigurationError(Exception):
    """Raised when a required API key or task slot is missing or unrecognised."""
```

## Tests

- `get_adapter("field_mapping")` returns `AnthropicAdapter` (default model is `claude-*`)
- `get_adapter("script_generation")` returns `OpenAIAdapter` (default model is `gpt-*`)
- `get_adapter("unknown_task")` raises `ConfigurationError`
- Missing `ANTHROPIC_API_KEY` raises `ConfigurationError` at call time for Anthropic tasks
- Missing `OPENAI_API_KEY` raises `ConfigurationError` at call time for OpenAI tasks
- `AnthropicAdapter.call()` constructs prompt correctly (mocked SDK)
- `OpenAIAdapter.call()` constructs prompt correctly (mocked SDK)
- `AICallError` wraps provider API errors for both adapters
- No live API calls in tests

## Acceptance criteria

- [ ] `from migrations_engine.ai.factory import get_adapter` works
- [ ] `get_adapter("field_mapping")` returns an `AnthropicAdapter`
- [ ] `get_adapter("script_generation")` returns an `OpenAIAdapter`
- [ ] Missing provider key raises `ConfigurationError` at call time
- [ ] `call()` returns a validated Pydantic model instance for both adapters
- [ ] All 7 model slots present in `config.py` with sensible defaults
- [ ] `.env` contains placeholder entries for all keys and slots
- [ ] All tests pass without network access

## Notes

- `anthropic` and `openai` SDKs must both be added to `pyproject.toml` / `requirements.txt`
- Model slots are deployment-level config only — no per-project override
- Provider is inferred from the model ID string; do not add a separate provider field
- Pattern matches `migrations/engine/config/engine.yaml` model slot taxonomy
