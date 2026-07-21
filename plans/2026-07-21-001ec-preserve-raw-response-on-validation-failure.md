# Plan: 001ec — Preserve Raw AI Response Text When Schema Validation Fails

## Task and Domain links

- Task: `tasks/001ec-preserve-raw-response-on-validation-failure.md`
- Domain: none — backend-internal error handling / observability, no
  UI/API-surface change

## Current State

- `AICallResult(parsed=..., raw_response=text)` (`ai/adapter.py:11-16`) is
  only constructed *after* `response_model.model_validate_json(text)`
  succeeds, in every adapter:
  - `anthropic_adapter.py:83-84`
  - `openai_adapter.py:91-92`
  - `gemini_adapter.py:86-87`
  - `mock_adapter.py:57-59` (`model_validate`, not `model_validate_json`,
    but same shape)
  - `ollama_adapter.py:122-125` — different: this one already retries
    internally on `ValidationError` (`ollama_adapter.py:126-130`, up to
    `max_retries`), then on exhaustion raises `AICallError(f"Model
    returned invalid JSON after {max_retries} attempts: {last_exc}")`
    (`ollama_adapter.py:133`) — `last_exc`'s string form doesn't include
    the raw text either.
- When validation fails, `text`/`content`/`clean_content` — the actual
  provider response — is never returned to the caller. Every call site
  that logs on this failure passes `raw_response=None`:
  - `mapping/review.py::propose_mapping`, `except ValidationError`
    branch (added in 001ea)
  - `management/source_analysis.py::analyze_source_slice`, `except
    ValidationError` branch (added in 001eb) — this task closes the gap
    001eb couldn't close on its own, since the adapter never gave it
    anything but `None` to log
  - `management/fibers.py::analyze_feed`, both of its AI calls
    (`except Exception`, lines ~655-667 and ~729-741) — no
    `ValidationError`-specific handling at all today
  - `management/fibers.py::submit_lookup_inputs` (`except Exception`,
    ~875-884) — same
- `codegen/service.py::generate_codegen_artifact` and
  `codegen/schema_analysis.py::run_schema_analysis` have the identical
  `except Exception: raw_response=None` gap — confirmed present, but
  explicitly out of scope per this task (not part of "mapping and lookup
  source").
- `pydantic.ValidationError` is the Rust-backed `pydantic-core` type —
  not meant to be subclassed or given extra attributes by user code, so
  carrying the raw text alongside it needs a separate wrapper exception,
  not a `ValidationError` subclass.

## Objective

1. Add `AIResponseValidationError` to `ai/adapter.py`.
2. Every adapter (`anthropic`, `openai`, `gemini`, `mock`) wraps its
   `ValidationError` and re-raises `AIResponseValidationError` with the
   raw text attached.
3. `ollama_adapter.py`'s terminal retry-exhaustion failure raises
   `AIResponseValidationError` (carrying the last attempt's raw text)
   instead of a bare `AICallError`.
4. Five call sites (`review.py`, `source_analysis.py`, `fibers.py` x3)
   catch `AIResponseValidationError` instead of `ValidationError` (or, for
   the three `fibers.py` sites, add it as a new specific branch ahead of
   the generic `except Exception`) and log `raw_response=exc.raw_response`.

## Out of Scope

- `codegen/service.py` / `codegen/schema_analysis.py` — same gap exists,
  confirmed, deliberately not bundled into this task per explicit scope
  ("same for mapping and lookup source"). Natural follow-up task.
- Retry behavior, model selection, prompt content — unchanged.
- Truncating/redacting the logged raw response — `ai_call_log.raw_response`
  is already an uncapped `Text` column.
- `AICallError`'s handling (network/provider failures with no response at
  all) — correctly keeps `raw_response=None`, not touched.

## Blast Radius

- `engine/src/migrations_engine/ai/adapter.py` (edited — new exception)
- `engine/src/migrations_engine/ai/anthropic_adapter.py` (edited)
- `engine/src/migrations_engine/ai/openai_adapter.py` (edited)
- `engine/src/migrations_engine/ai/gemini_adapter.py` (edited)
- `engine/src/migrations_engine/ai/mock_adapter.py` (edited)
- `engine/src/migrations_engine/ai/ollama_adapter.py` (edited)
- `engine/src/migrations_engine/mapping/review.py` (edited)
- `engine/src/migrations_engine/management/source_analysis.py` (edited)
- `engine/src/migrations_engine/management/fibers.py` (edited, 3 call
  sites)
- No DB migration, no API schema change, no frontend change — purely
  what gets logged to `ai_call_log.raw_response` on an existing failure
  path.

## File Changes

**`engine/src/migrations_engine/ai/adapter.py`**
```python
class AIResponseValidationError(Exception):
    """Raised when the provider responded, but the response failed schema validation.

    Carries the raw response text so callers can log what the model
    actually returned, not just the validation error message.
    """
    def __init__(self, raw_response: str, original: "ValidationError") -> None:
        self.raw_response = raw_response
        self.original = original
        super().__init__(str(original))
```
(import `pydantic.ValidationError` for the type hint, matching this
file's existing style)

**`anthropic_adapter.py` / `openai_adapter.py` / `gemini_adapter.py`**
- Wrap the existing `parsed = response_model.model_validate_json(text)`
  (or `content`/`text` per file) in `try/except ValidationError as exc:
  raise AIResponseValidationError(raw_response=text, original=exc) from exc`.

**`mock_adapter.py`**
- Same wrap around `parsed = response_model.model_validate(raw)`, using
  `raw_text` as the raw response.

**`ollama_adapter.py`**
- Keep the internal retry loop (`except ValidationError as exc:` at
  ~line 126, logging + updating the prompt) unchanged.
- Change the terminal failure at ~line 133 from
  `raise AICallError(f"Model returned invalid JSON after {max_retries} attempts: {last_exc}") from last_exc`
  to `raise AIResponseValidationError(raw_response=clean_content, original=last_exc) from last_exc`
  — `clean_content` here is the last attempt's (still-invalid) response,
  which is what's actually useful to see.

**`mapping/review.py::propose_mapping`**
- Change `except ValidationError as exc:` to
  `except AIResponseValidationError as exc:`; change
  `raw_response=None` to `raw_response=exc.raw_response`; change
  `error_detail=f"ValidationError: {exc}"` to
  `error_detail=f"ValidationError: {exc.original}"`.
- Import `AIResponseValidationError` from `..ai.adapter`.

**`management/source_analysis.py::analyze_source_slice`**
- Same substitution in its `except ValidationError` branch (added in
  001eb).

**`management/fibers.py::analyze_feed` (both AI calls) and
`submit_lookup_inputs`**
- Add `except AIResponseValidationError as exc:` ahead of the existing
  `except Exception as exc:`, logging `raw_response=exc.raw_response`
  and `error_detail=str(exc.original)`; keep the generic `except
  Exception` fallback for everything else, unchanged.

## Tests

- Adapter-level unit tests (one per adapter, or parametrized): feed a
  response that fails `model_validate_json`, assert
  `AIResponseValidationError` is raised with `.raw_response` equal to the
  exact text that was fed in.
- `ollama_adapter` test: assert exhausting retries raises
  `AIResponseValidationError` with `.raw_response` set to the *last*
  attempt's content, not the first.
- One test per updated call site (`propose_mapping`,
  `analyze_source_slice`, `analyze_feed` x2, `submit_lookup_inputs`):
  mock the adapter to raise `AIResponseValidationError`, assert the
  resulting `ai_call_log` row has `raw_response` populated (not `None`)
  and the correct `error_detail`.
- Rerun existing adapter/call-site test suites — anything currently
  asserting `raw_response is None` on a validation failure needs updating
  to expect the real text instead.

## Verification

- `mypy --strict` / `ruff` clean across all touched files.
- Manually trigger a validation failure against a real or mocked
  provider (e.g. a fixture that violates `extra="forbid"`) for at least
  one of the 5 call sites and confirm the resulting `ai_call_log` row's
  `raw_response` contains the actual invalid JSON, not `null`.

## Pitfalls

- Don't let `AIResponseValidationError` leak up to API responses as a raw
  500 — every call site must still translate it into the appropriate
  `AuthApiError` (or, for the 3 `fibers.py` sites that currently just
  `raise` the bare exception, preserve that existing behavior — this task
  only changes what gets *logged*, not the error-handling/status-code
  behavior established by 001ea/001eb for their two call sites).
- `ollama_adapter.py`'s retry loop's *intermediate* `except
  ValidationError` (the one that triggers a retry, not the terminal one)
  must stay catching `ValidationError` directly, since that's what
  `model_validate_json` still raises inside the loop — only the *final*
  raise (after retries are exhausted) changes to
  `AIResponseValidationError`.
- Watch for `except Exception` blocks silently catching
  `AIResponseValidationError` too broadly if the new specific `except`
  clause isn't ordered *before* the generic one in each of the 3
  `fibers.py` sites — Python matches `except` clauses in order.

## Commit

Own commit. No ordering dependency on 001dy/001dz/001ea/001eb, but
conceptually completes what 001ea and 001eb's `ValidationError` handling
couldn't finish on their own (the adapter never gave them a raw response
to log).
