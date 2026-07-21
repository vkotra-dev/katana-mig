---
type: Task Plan
title: Preserve Raw AI Response Text When Schema Validation Fails
status: ready
---

# Task: 001ec-preserve-raw-response-on-validation-failure

## Context
Every AI adapter's `.call()` method only constructs `AICallResult(parsed=..., raw_response=text)`
*after* `response_model.model_validate_json(text)` succeeds. When validation fails, `text` — the
actual thing the model returned, exactly what you'd want to see to debug *why* it failed — is
never returned to the caller. Every call site that catches this failure logs
`raw_response=None` to `ai_call_log`, so the one piece of data most useful for diagnosing a
validation failure is the one thing not captured. This affects the mapping call
(`review.py::propose_mapping`), the source-analysis call
(`source_analysis.py::analyze_source_slice`, fixed for its `ValidationError` path in 001eb, but
still logging `None` since the adapter never gives it anything else to log), and the feed-analysis
and lookup-mapping calls (`fibers.py::analyze_feed`, `fibers.py::submit_lookup_inputs`, both of
which don't even distinguish `ValidationError` from any other failure today).

## Requirements

1. **New exception carrying the raw text**: `AIResponseValidationError` in `ai/adapter.py`,
   alongside `AICallError`/`ConfigurationError` — wraps the raw response string and the original
   `pydantic.ValidationError`. (`pydantic.ValidationError` itself is not meant to be subclassed or
   given extra attributes — it's the Rust-backed `pydantic-core` type — so this must be a
   separate exception class, not a `ValidationError` subclass.)
2. **Every adapter wraps its own validation failure**: `anthropic_adapter.py`, `openai_adapter.py`,
   `gemini_adapter.py`, `mock_adapter.py` each catch `ValidationError` around their
   `model_validate_json`/`model_validate` call and re-raise `AIResponseValidationError(raw_response=..., original=exc)`
   instead of letting the bare `ValidationError` propagate.
3. **`ollama_adapter.py` is a special case**: it already retries internally on `ValidationError`
   (up to `max_retries`) before giving up. On final exhaustion it currently raises a plain
   `AICallError` whose message embeds `str(last_exc)` but not the actual last raw response text.
   Change the terminal failure to raise `AIResponseValidationError(raw_response=<last attempt's
   clean_content>, original=last_exc)` instead, so the most recent (still-invalid) response is
   preserved. Keep the retry-loop's internal logging/prompt-repair behavior unchanged.
4. **Every call site that logs on validation failure switches from catching `ValidationError` to
   catching `AIResponseValidationError`**, and logs `raw_response=exc.raw_response` instead of
   `None`:
   - `mapping/review.py::propose_mapping`
   - `management/source_analysis.py::analyze_source_slice`
   - `management/fibers.py::analyze_feed` (both of its two AI calls)
   - `management/fibers.py::submit_lookup_inputs`
5. **Don't touch true "no response" failures**: `AICallError` (network/provider errors — the
   request never got a response at all) keeps `raw_response=None`, correctly, since there's
   nothing to log. Only the "we got a response back and it failed our schema" case changes.

## Out of Scope
- Any change to `codegen/service.py` or `codegen/schema_analysis.py`'s AI call sites — check
  whether they have the same gap as a natural follow-up, not bundled into this task.
- Any change to retry behavior, model selection, or prompt content.
- Redacting/truncating the logged raw response for size — `ai_call_log.raw_response` is already a
  `Text` column with no length cap; out of scope to add one here.
