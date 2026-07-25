Task: tasks/completed/001gr-lookup-json-mutation-not-detected-bug.md
Plan: plans/2026-07-25-001gr-lookup-json-mutation-not-detected-bug.md
Commits: af8b9da

## Changes Made

### `engine/src/migrations_engine/management/lookup_mapping.py`
- Added `from sqlalchemy.orm.attributes import flag_modified` import.
- Added `flag_modified(lookup_map, "destination_mappings")` immediately after each of the 3 `lookup_map.destination_mappings = mappings` assignments (in `add_source_value`, `remove_source_value`, `move_source_value` handling blocks inside `update_lookup_value_map`).
- Root cause fixed: `destination_mappings` is a plain (unwrapped) SQLAlchemy `JSON` column; all three handlers shallow-copy the list (`list(lookup_map.destination_mappings or [])`) and then mutate an *existing, shared* group dict in place before reassigning — SQLAlchemy's change detection saw old==new and silently skipped the `UPDATE`. `flag_modified` forces the write.

### `engine/tests/test_lookup_mapping_api.py`
- Added `test_patch_add_source_value_stacks_into_existing_group`, `test_patch_add_source_value_stacks_when_destination_mappings_preseeded`, `test_patch_remove_source_value_from_preseeded_group`, `test_patch_move_source_value_between_existing_groups` — all hit the real API (not mocks) and proved the mutation was previously silently dropped for the "existing group" branch of each handler.

## Deviations from Plan

- Plan's optional Step 6 (defensive `flag_modified` on the full-`destination_mappings`-overwrite branch, which was proven safe without it) was **not** applied — correctly, since it was explicitly marked optional in the plan and that branch already builds fresh dict objects each time.

## Tests

`.venv/bin/python -m pytest engine/tests -q` — 391 passed, 0 failed (verified independently during review).
