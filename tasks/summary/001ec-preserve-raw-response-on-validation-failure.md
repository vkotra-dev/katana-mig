# Summary: 001ec — Preserve Raw AI Response Text When Schema Validation Fails

## What was built
Every AI adapter used to discard the model's actual response text the moment schema validation
failed — `AICallResult(parsed=..., raw_response=text)` was only ever constructed on the success
path. Failure logs to `ai_call_log` recorded `raw_response=None`, losing the one thing most
useful for debugging why a call failed.

### Key changes
- **`AIResponseValidationError`** (`ai/adapter.py`): new exception carrying `raw_response` and
  the original error — necessary because `pydantic.ValidationError` is Rust-backed and can't be
  subclassed or given extra attributes.
- **All five adapters** (anthropic, openai, gemini, mock, ollama) now wrap their validation call
  and raise this instead of letting a bare `ValidationError` propagate. Ollama is a special case —
  it already retries internally on validation failure; only its terminal failure (after
  `max_retries`) was changed, using the *last* attempt's text.
- **Five call sites updated**: `propose_mapping`, `analyze_source_slice`, both AI calls in
  `analyze_feed`, and `submit_lookup_inputs` now catch `AIResponseValidationError` and log
  `raw_response=exc.raw_response` instead of `None`.
- **`db.commit()` before every re-raise**: `log_ai_call()` only does `db.add()` + `db.flush()`,
  never commits. `get_db()`'s session context manager rolls back anything uncommitted when a
  route handler's exception propagates out — so every exception branch that logs and re-raises
  (7 branches total across `review.py`, `source_analysis.py`, `fibers.py`, including the
  pre-existing generic `except Exception` fallbacks, not just the new validation-specific ones)
  needed an explicit commit or its audit row would silently vanish on rollback.

## Verification
New tests confirm `AIResponseValidationError.raw_response` matches the fed-in text at the adapter
level (including an Ollama-specific test confirming it's the last retry's content, not the
first). Call-site tests verify the persisted `ai_call_log` row via a genuine regression pattern —
either through the real HTTP request path with a fresh session afterward, or via an explicit
`db.rollback()` before querying, which only leaves the row behind if `db.commit()` actually ran
(verified locally by temporarily removing the commit and confirming the test then fails).
