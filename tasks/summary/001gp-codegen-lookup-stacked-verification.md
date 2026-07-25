Task: tasks/completed/001gp-codegen-lookup-stacked-verification.md
Plan: plans/2026-07-24-001gp-codegen-lookup-stacked-verification.md
Commits: 1f36714

## Changes Made

### `engine/tests/test_lookup_mapping_api.py`
- Added `LookupSnapshot` to the model imports.
- Added `test_patch_lookup_value_map_resets_approved_snapshots_to_draft` — verifies `PATCH /lookup-maps` with `add_source_value` or `remove_source_value` resets an approved `LookupSnapshot` back to `draft` (clears `status` and `approved_at`).

### `engine/tests/test_bundle_sequencing.py`
- Added `test_generate_lookup_upsert_sql_handles_one_to_many_stacked_mappings` — verifies `generate_lookup_upsert_sql()` produces valid DML for `postgresql`, `mysql`, `mssql`, and `oracle` when multiple source values map to the same destination (e.g. `{"A": "ACTIVE", "B": "ACTIVE", "C": "BLOCKED"}`), asserting the correct dialect-specific upsert syntax for each (`ON CONFLICT ... DO UPDATE`, `ON DUPLICATE KEY UPDATE`, `MERGE`).

## Deviations from Plan

None known — this task was backend-only test coverage, no production code changed.

## Tests

`.venv/bin/python -m pytest engine/tests -q` — passing at time of commit (re-verified as part of the full suite in later session work; no regressions attributable to this change).
