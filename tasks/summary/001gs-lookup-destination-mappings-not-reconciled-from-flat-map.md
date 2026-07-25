Task: tasks/completed/001gs-lookup-destination-mappings-not-reconciled-from-flat-map.md
Plan: plans/2026-07-25-001gs-lookup-destination-mappings-not-reconciled-from-flat-map.md
Commits: 23c9134

## Changes Made

### `engine/src/migrations_engine/management/lookup_mapping.py`
- Added `_reconcile_destination_mappings(lookup_map) -> list[dict[str, Any]]` helper: shallow-copies `destination_mappings`, and if empty but `source_value_map` has entries, rebuilds groups from the flat map first (logic extracted verbatim from what `move_source_value` already did inline).
- `add_source_value` and `remove_source_value`: `mappings = list(lookup_map.destination_mappings or [])` replaced with `mappings = _reconcile_destination_mappings(lookup_map)`. Previously, if `destination_mappings` was never explicitly seeded (only `source_value_map` was), these two handlers silently dropped every sibling source value already mapped to the same destination.
- `move_source_value`: its inline reconciliation block (11 lines) replaced with a single call to the new shared helper — pure de-duplication, no behavior change (this handler already worked correctly).

### `engine/tests/test_lookup_mapping_api.py`
- Added `test_patch_add_source_value_reconciles_from_source_value_map_when_destination_mappings_empty`, `test_patch_remove_source_value_reconciles_from_source_value_map_when_destination_mappings_empty` (previously failing, now pass), and `test_patch_move_source_value_reconciles_from_source_value_map_when_destination_mappings_empty` (a behavior-preservation guard for the `move_source_value` refactor — already passed before and after).

## Deviations from Plan

None — matches the plan exactly.

## Tests

`.venv/bin/python -m pytest engine/tests -q` — 394 passed, 0 failed (verified independently during review).
