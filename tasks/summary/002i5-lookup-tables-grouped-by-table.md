Task: tasks/completed/002i5-lookup-tables-grouped-by-table.md
Plan: plans/2026-07-24-002i5-lookup-tables-grouped-by-table.md
Commits: 1733f61 (full value_map implementation), 0b28359 (documented grouping as obsolete)

## Changes Made

### `engine/src/migrations_engine/codegen/service.py`
- `_build_lookup_tables()` changed to pass the **full** `value_map` (all key-value pairs) per
  lookup instead of capping at 5 samples.
- No grouping by `destination_object_name` was needed — task 002i3's per-table loop architecture
  means `_build_lookup_tables()` is always called with lookups scoped to one table already.

### `engine/tests/test_codegen_service_api.py`
- `test_build_lookup_tables_passes_full_value_map`: verifies all 12 value_map entries are passed
  (not capped at 5).

## Deviations from Plan

**Grouping by destination table (items 1 and 3) was documented as structurally obsolete** in the
task itself. The per-table loop from 002i3 means `_build_lookup_tables()` is always called with
lookups scoped to one table — there's nothing to group. Only the full value_map change (item 2)
was implemented.

## Domain Updates Required

- `docs/domain/source-model.md` — Verified: the full value_map behavior is already reflected in
  the codegen documentation. No change needed.

## Tests

`.venv/bin/python -m pytest engine/tests -q` — all tests pass, 0 failures.

## Verification

`scripts/validate_okf.py` — all 12 domain docs pass, 0 warnings.
