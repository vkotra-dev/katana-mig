# Plan: 001eb — Harden Source-Analysis AI Call (Detailed Prompt + Header-Verbatim Guard)

## Task and Domain links

- Task: `tasks/001eb-source-analysis-schema-hardening.md`
- Domain: `docs/domain/ui.md` (no UI change — backend/schema-quality only)

## Current State

- `SYSTEM_PROMPT` (`source_analysis.py:37-40`): two sentences, no rules for
  masked-value handling, type inference, nullability, or max_length; no
  output-contract section.
- `ColumnSchema`/`AnalysisResult` (`source_analysis.py:43-51`): field names
  already match the new contract (`name`, `inferred_type`, `nullable`,
  `max_length`), but no `extra="forbid"`, no validators.
- `analyze_source_slice` (`source_analysis.py:54-165`): calls
  `adapter.call(system_prompt, sample_text, AnalysisResult)` (~line 103),
  logs the call, and on any exception does a single bare
  `except Exception as exc: log_ai_call(..., error_detail=str(exc)); raise`
  (~line 120-133) — no `AuthApiError` translation at all, unlike
  `review.py`'s `propose_mapping` (`ValidationError`/`AICallError`/generic
  three-way split with distinct user-facing errors).
- No guard today compares `analysis_result.columns`' names against the real
  `source_slice.header_csv` — this is the actual gap behind the production
  `claim_type` → `claim_claim` corruption (valid string, passes schema
  validation, silently persisted as the "real" column name).
- `header_csv` is reliably populated for **both** source types: CSV intake
  (`intake/csv_intake.py:63`) and fixed-length intake
  (`intake/fixed_intake.py:33,52`, derived from the parsed copybook's field
  names: `header_values = [field.name for field in fields]`) — confirmed
  `validate_against_header` doesn't need special-casing per source type.
- `SourceSchemaColumnResponse` (`api/schemas.py:459-463`) already mirrors
  `ColumnSchema` field-for-field — no API/frontend plumbing gap (unlike
  001ea's `nullable`, which needed new plumbing end-to-end).
- Existing tests construct fake AI responses directly:
  `test_source_analysis_api.py:194-197` and
  `test_source_analysis_service.py:129-241` (5 call sites) via
  `from migrations_engine.management.source_analysis import AnalysisResult,
  ColumnSchema` — plain imports, not module-qualified reach-ins like
  001ea's `mapping_review_module._ProposedBinding`. Spot-checked both
  files' fixture `header_csv` (`"CUST_ID,SURNAME"`) against their
  `ColumnSchema(name=...)` values — they match exactly, in order, so
  wiring in `validate_against_header` is not expected to break them.
  `test_source_analysis_models.py` and `test_fiber_ai_flow.py` don't
  reference these classes at all (the latter uses an unrelated
  `_FeedAnalysisResult` for the feed-analysis call type).

## Objective

1. Replace `SYSTEM_PROMPT` with the new version; preserve
   `_build_system_prompt`'s source_type/layout_information append.
2. New module `source_analysis_schemas.py` with the hardened classes;
   `source_analysis.py` imports from it.
3. Wire `validate_against_header` in right after parsing, before persisting.
4. Add `ValidationError`/`HeaderMismatch`-specific exception handling,
   mirroring `review.py`'s pattern, instead of the current bare re-raise.
5. Move the smoke-test scenarios into a real pytest file.

## Out of Scope

- `normalize_to_header` (the self-heal path) — not wired in; this task uses
  the strict-reject guard. Revisit only if reject-on-drift proves too
  disruptive in practice.
- Any change to `_build_value_summaries`, masking, or PII classification —
  unrelated to the AI schema-inference call.
- Any change to `SourceSchemaColumnResponse` or the frontend — field names
  already match, nothing to update.
- 001ea's mapping-call guard — separate task, separate call site, already
  planned.

## Blast Radius

- `engine/src/migrations_engine/management/source_analysis.py` (edited)
- `engine/src/migrations_engine/management/source_analysis_schemas.py` (new)
- `engine/tests/test_source_analysis_schemas.py` (new — moved smoke-test
  scenarios as real assertions)
- `engine/tests/test_source_analysis_api.py`,
  `engine/tests/test_source_analysis_service.py` (verify only — expected to
  pass unchanged per the spot-check above; touch only if the full run
  surfaces a mismatch)
- No DB migration — `SourceSchemaArtifact.columns` is JSON.
- No role-gating change.

## File Changes

**`engine/src/migrations_engine/management/source_analysis_schemas.py` (new)**
- `ColumnSchema` (`extra="forbid"`, `nullable` bool-strict validator,
  `max_length` non-negative validator), `AnalysisResult` (`extra="forbid"`),
  `HeaderMismatch`, `parse_header`, `validate_against_header`
  (`strict_order=True` default), `normalize_to_header` — as specified, no
  `__main__` block.

**`engine/src/migrations_engine/management/source_analysis.py`**
- Delete the inline `ColumnSchema`/`AnalysisResult` classes (lines 43-51);
  `from .source_analysis_schemas import AnalysisResult, ColumnSchema,
  HeaderMismatch, validate_against_header`.
- Replace `SYSTEM_PROMPT` (lines 37-40) with the new prompt text.
- Split the try/except around `adapter.call(...)` (~lines 102-133): add
  `except ValidationError` → log (via the existing error-path
  `log_ai_call(..., error_detail=...)`, unchanged — this branch fires
  before the success log at ~108-118 ever runs, so no duplicate row) →
  `AuthApiError("ai_schema_mismatch", "The AI generated an invalid source schema. Please retry.", 502)`
  (matching `review.py`'s code/message convention); keep the final bare
  `except Exception` for anything else, same as today. Import
  `ValidationError` from `pydantic` at the top of the try block (matching
  `review.py`'s local import style).
- **After** the try/except block closes (`analysis_result = result.parsed`
  has succeeded, `call_log` is bound to the row already written by the
  success `log_ai_call` at ~108-118) and **before**
  `schema_artifact = SourceSchemaArtifact(...)` (~line 135), wrap the new
  guard in its own local try/except — do NOT add a `HeaderMismatch`
  branch to the main try/except above, since that would require moving
  the call inside the try block and would fire *after* the success log
  already wrote a row, producing two rows for one call:
  ```python
  try:
      validate_against_header(analysis_result, source_slice.header_csv)
  except HeaderMismatch as exc:
      call_log.error_detail = str(exc)
      db.commit()
      raise AuthApiError("source_analysis_header_mismatch", str(exc), 422)
  ```
  This mutates the already-written row instead of calling `log_ai_call`
  again — exactly one `ai_call_log` row per logical call in every
  failure mode.

## Tests

- `test_source_analysis_schemas.py`: the good-path parse; camelCase/extra-key
  rejection; string-`nullable` rejection; negative-`max_length` rejection;
  `validate_against_header` catching a renamed column (the `claim_type` →
  `claim_claim` reproduction), a count mismatch, and a reordering (with
  `strict_order=True`); `normalize_to_header` repairing a pure rename.
- `source_analysis.py` engine test: `analyze_source_slice` raises a 422
  `AuthApiError` (not a raw exception) when the (mocked) AI response's
  column names don't match `header_csv`.
- Full existing suite (`test_source_analysis_api.py`,
  `test_source_analysis_service.py`, `test_source_analysis_models.py`):
  rerun after wiring in the guard — expected to pass unchanged per the
  spot-check in Current State, but confirm rather than assume.

## Verification

- `mypy --strict` / `ruff` clean.
- Manually run source analysis against a real feed slice; confirm the
  persisted `SourceSchemaArtifact.columns` names match the header exactly.
- Manually construct a deliberately corrupted AI response (rename one
  column) via a unit test and confirm it's now rejected with a 422 instead
  of silently persisted.
- Confirm a fixed-length-file feed's source analysis still succeeds (guard
  isn't source-type-specific, but this is the case most worth a real smoke
  test given the copybook-derived header path).

## Pitfalls

- Same increased-failure-rate consideration as 001ea: expect
  `ai_schema_mismatch`/`source_analysis_header_mismatch` responses to
  appear where a corrupted-but-previously-silent response used to succeed.
  This is the intended effect, not a regression — but worth mentioning to
  whoever's watching error rates after this ships.
- `validate_against_header`'s `strict_order=True` default rejects
  reordering, not just renaming/dropping — confirm the AI is realistically
  expected to preserve header order today (the new prompt explicitly
  instructs "in the SAME order the columns appear in the input header," so
  this should hold, but it's a stricter bar than a set-comparison would be).
- The `validate_against_header` call sits in its own `try/except` *outside*
  the main `adapter.call()` try/except — don't fold it into the main block
  or add a `HeaderMismatch` branch there; either mistake reintroduces the
  duplicate-row problem this structure exists to avoid (see File Changes).
- `call_log` (from the success `log_ai_call` at ~108-118) must still be a
  valid, committed row by the time the `HeaderMismatch` handler mutates
  it — don't reorder `analyze_source_slice` such that `call_log` could be
  unbound or stale at that point.

## Commit

Own commit. No ordering dependency on 001ea/001dy/001dz — different call
site, different file, no shared code paths besides both using `AuthApiError`
and `log_ai_call`.
