Task: tasks/completed/002ia-artifact-history-order-and-lookup-id-rename.md
Plan: plans/2026-07-28-002ia-artifact-history-order-and-lookup-id-rename.md

## Changes Made

### `engine/src/migrations_engine/codegen/service.py`
- `list_codegen_artifacts()`: `ORDER BY` changed from
  `destination_object_name.asc(), created_at.desc()` to `created_at.desc()` only — the "Artifact
  history" panel now shows one true chronological feed across all destination tables instead of
  blocks grouped by table.
- `_build_lookup_tables()`: renamed `dest_val` → `id` in both the `sample_mappings` dict key and
  the hardcoded reference-table `columns` list. The value was already the business id (via
  `_extract_destination_id()`'s priority chain, which favors an actual `id` column); it was just
  mislabeled downstream.
- Added `_ensure_tz()` helper and applied it in `_trigger_response()` (`created_at`) and
  `_artifact_response()` (`created_at`, `superseded_at`). Not in the original plan — surfaced while
  writing the new chronological-ordering test: SQLite stores `DateTime(timezone=True)` columns as
  naive datetimes, so comparing/sorting them against tz-aware values broke. The service layer now
  always returns tz-aware datetimes regardless of backend storage behavior.

### `engine/src/migrations_engine/codegen/templates/user_prompt.txt.j2`
- `{{ m.dest_val }}` → `{{ m.id }}` in the LOOKUP REFERENCE TABLES rendering.

### `engine/src/migrations_engine/codegen/templates/system_prompt.txt.j2`
- Reference-table column description and the FK-resolution `SELECT @_<lookup_name>_id = CAST(ref.dest_val ...)` rule both updated to `id`.

### `engine/src/migrations_engine/codegen/lookup_upsert.py`
- Renamed `dest_val` → `id` in the generated SQL text for all four engines (postgresql, mysql,
  mssql, oracle) — CREATE TABLE column list, INSERT column list, `ON CONFLICT`, `ON DUPLICATE KEY`,
  and `MERGE` statements. This is the deterministic seed-SQL generator used when a lookup fiber is
  approved (`management/fibers.py:491`), independent of the AI-generated codegen bundle — both
  surfaces now agree on the column name.

### Tests
- `engine/tests/test_codegen_service_api.py`: fixed dict-style access
  (`result[0]["created_at"]`) to attribute access (`result[0].created_at`) — `list_codegen_artifacts`
  returns `CodegenArtifactResponse` model objects, not dicts. Added
  `test_list_codegen_artifacts_is_chronological` per the plan. Updated `dest_val` → `id` assertion.
- `engine/tests/test_codegen_system_prompt.py`: updated `dest_val` → `id` assertions (sample
  mapping dict and columns list).
- `engine/tests/test_bundle_sequencing.py`: updated ~10 `dest_val` → `id` SQL-text assertions
  across all four engine branches.

## Deviations from Plan

- Added `_ensure_tz()` — not in the plan, but a necessary fix surfaced by the new ordering test
  (SQLite naive-datetime storage vs. tz-aware comparison). In scope: same file, same function
  family (`_trigger_response`/`_artifact_response`), required for the new test to be meaningful
  rather than incidentally passing.
- No other deviations. `source_val` untouched, `build_delivery_bundle_text`'s grouping-by-table
  ordering untouched, `LookupSnapshot`/`LookupValueMap` shapes untouched — all as scoped.

## Domain Updates Required

- `docs/domain/ui.md` — **Updated**. The "Artifact history" bullet now states ordering is
  chronological (`created_at desc`) across all destination tables, not grouped by table.
  `timestamp` frontmatter bumped to 2026-07-28 (actual change date, not copy-pasted).
- No other domain page — confirmed at task creation (grepped for `dest_val`/`source_val`, no
  hits in `docs/domain/`); still true, no other page was touched.

## Tests

```
.venv/bin/python -m pytest engine/tests/test_codegen_service_api.py engine/tests/test_codegen_system_prompt.py engine/tests/test_bundle_sequencing.py -q
55 passed, 2 warnings

.venv/bin/python -m pytest engine/tests -q
429 passed, 2 warnings

.venv/bin/python scripts/validate_okf.py
✓ All files OKF-compliant. No issues found (12/12 domain pages).
```

Independently reran both the targeted and full suite, and the OKF validator, before confirming
completion — all three clean.
