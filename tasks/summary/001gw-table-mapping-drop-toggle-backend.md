Task: tasks/completed/001gw-table-mapping-drop-toggle-backend.md
Plan: plans/2026-07-25-001gw-table-mapping-drop-toggle-backend.md
Commits: 74871bd

## Changes Made

### `engine/src/migrations_engine/api/schemas.py`
- `MappingFieldBindingResponse.dropped: bool = False`.

### `engine/src/migrations_engine/mapping/snapshots.py`
- `FieldBinding.dropped: bool = False`; `create_approved_mapping_snapshot`'s `serialized_bindings` includes it.

### `engine/src/migrations_engine/mapping/review_repository.py`
- `snapshot_to_response`'s `MappingFieldBindingResponse(...)` construction includes `dropped=bool(binding.get("dropped", False))`.

### `engine/src/migrations_engine/mapping/review.py`
- `patch_mapping`'s `new_bindings.append({...})` includes `"dropped": binding.dropped`.

### `engine/src/migrations_engine/mapping/proposal.py`
- Re-propose merge logic (`propose_mapping`) carries `dropped` forward from `old_bindings_map[pair]` onto `fresh_b` for surviving pairs, independent of sign-off status — so re-running AI mapping doesn't silently un-drop a field the user excluded.

### `engine/src/migrations_engine/codegen/service.py`
- Three read-sites gained a `not binding.get("dropped")` filter: the required-NOT-NULL-field validation (`mapped_dest_fields`), `_select_lookup_snapshot_version`, and `_build_lookup_tables`.

### `engine/src/migrations_engine/codegen/templates/user_prompt.txt.j2`
- The field-bindings loop gained `if not binding.get('dropped')` — this is the critical fix: without it, a soft-deleted field would still appear in the text the SQL-generation AI reads and get generated into migration SQL regardless of the `dropped` flag.

### `engine/tests/test_mapping_review_api.py`, `engine/tests/test_codegen_service_api.py`
- 4 new tests: sign-off preservation across a toggle (both directions), `dropped` preserved through AI re-propose for an unsigned field, codegen 422 when the only mapping for a required field is dropped, and — the most load-bearing one — the dropped field's identifiers are absent from the actual rendered `user_prompt.txt.j2` text while a sibling active field's are present (verified via `FakeAdapter.calls[i].user`, which captures the literal rendered prompt).

## Deviations from Plan

None structural — matches the plan's diffs exactly (verified directly against `git show` during review, not taken on the report's word).

## Tests

`.venv/bin/python -m pytest engine/tests -q` — 402 passed, 0 failed (398 baseline before this task, +4 new tests, matching the plan's prediction exactly). Verified independently during review, not just taken from the commit message.
