---
type: Task Plan
title: Harden Source-Analysis AI Call — Detailed Prompt + Header-Verbatim Guard
status: ready
---

# Task: 001eb-source-analysis-schema-hardening

## Context
`analyze_source_slice` (`engine/src/migrations_engine/management/source_analysis.py`)
infers per-column schema (name/type/nullable/max_length) from sample rows via
AI, and persists it as the project's `SourceSchemaArtifact` — the source of
truth every downstream step (mapping, lookup, codegen) treats as the real
column list. Its current system prompt is two sentences with none of the
type-inference/masking/nullability/max_length rules, and its response schema
(`ColumnSchema`/`AnalysisResult`, `source_analysis.py:43-51`) has no
`extra="forbid"`, no `nullable`-must-be-bool validator, and — critically — no
check that the returned column **names** actually match the real header. This
is the root cause of a production incident where the model returned
`claim_claim` for a column that was actually `claim_type`: a syntactically
valid string, so schema validation passed, and the corrupted name then flowed
into every downstream mapping/codegen step as if it were real.

## Requirements

1. **System prompt**: replace `SYSTEM_PROMPT`
   (`source_analysis.py:37-40`) with the new version — explicit column-order/
   verbatim-copy rules, type-inference criteria (ignore masked/redacted
   values), nullability/max_length rules, and a strict output contract.
   Preserve `_build_system_prompt`'s existing behavior of appending
   `source_type`/`layout_information` after the base prompt.
2. **Response schema**: add a new module with `ColumnSchema` (`extra="forbid"`,
   `nullable` bool-strict validator, `max_length` non-negative validator),
   `AnalysisResult`, `HeaderMismatch`, `parse_header`, `validate_against_header`,
   `normalize_to_header`. `source_analysis.py` imports `ColumnSchema`/
   `AnalysisResult` from it (re-exported at module level so existing test
   imports `from migrations_engine.management.source_analysis import
   AnalysisResult, ColumnSchema` keep resolving without changes).
3. **Wire in the header-verbatim guard**: call `validate_against_header(analysis_result,
   source_slice.header_csv)` immediately after parsing (`source_analysis.py:119`),
   before the `SourceSchemaArtifact` is constructed — this is the actual
   fix for the production bug, not just stricter typing.
4. **Add proper error handling — without double-logging the same call**:
   `analyze_source_slice`'s AI-call try/except (`source_analysis.py:102-133`)
   currently has a single bare `except Exception as exc: log + raise` — no
   `ValidationError`-specific handling, unlike `propose_mapping`'s
   three-way split in `review.py`. Add a `ValidationError` branch there
   (safe — it fires before the success `log_ai_call` at ~108-118 ever
   runs). The `validate_against_header` guard is different: it runs
   *after* that success log has already written a row, so its failure
   handler must NOT call `log_ai_call` again (that would create two rows
   for one call) — instead mutate the existing `call_log.error_detail`
   and commit, then raise `AuthApiError` (422). See the plan for the
   exact placement.
5. **No inline smoke test**: move the `if __name__ == "__main__":` scenarios
   into a real pytest file under `engine/tests/`.
6. **Decision, stated not assumed**: use `validate_against_header` (reject on
   drift) as the wired-in guard, not `normalize_to_header` (silently repair
   a pure rename) — matches the "root-cause fix" framing in the module's own
   docstrings. Flag this explicitly for review before implementation, since
   it's the stricter of two reasonable choices.
7. **Verify against existing tests before assuming breakage**: spot-checked
   `test_source_analysis_api.py` and `test_source_analysis_service.py` — both
   already construct `ColumnSchema` names matching their fixture's
   `header_csv` exactly (e.g. `"CUST_ID,SURNAME"`), so wiring in the guard is
   not expected to break them. Still run the full suite after wiring it in,
   including `test_source_analysis_models.py`.

## Relationship to 001ea
001ea's `validate_source_fields` guards the *mapping* AI call against a
`source_field` that doesn't match `_latest_source_columns` — but that
function reads from the same `SourceSchemaArtifact` this task populates. If
source analysis itself corrupts a name and stores it, 001ea's guard compares
the mapping call's output against the *already-corrupted* "known" list and
won't catch it. This task fixes the corruption at its origin, before it's
ever persisted; 001ea's guard remains a useful second-layer check against a
different failure mode (the mapping AI inventing a field that matches
neither the corrupted nor the real list).
