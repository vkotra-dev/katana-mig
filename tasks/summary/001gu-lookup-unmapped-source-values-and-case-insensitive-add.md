Task: tasks/completed/001gu-lookup-unmapped-source-values-and-case-insensitive-add.md
Plan: plans/2026-07-25-001gu-lookup-unmapped-source-values-and-case-insensitive-add.md
Commits: 1763d06

## Changes Made

### `engine/migrations/versions/0041_add_unmapped_source_values_column.py` (created)
- New `unmapped_source_values` JSON column on `lookup_value_maps`, `down_revision = "0040"`.

### `engine/src/migrations_engine/db/models.py`
- `LookupValueMap.unmapped_source_values: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)`.

### `engine/src/migrations_engine/api/schemas.py`
- `LookupValueMapResponse.unmapped_source_values: list[str] = Field(default_factory=list)`.

### `engine/src/migrations_engine/management/fibers.py`
- `_sync_lookup_value_map_from_proposed_mappings` gained an `unmatched_source_values: list[str] | None = None` parameter, set on `val_map.unmapped_source_values` in both branches (guarded with `is not None` on the update branch, so `_bridge_lookup_fiber_to_value_map`'s re-sync — which doesn't have this data — doesn't clobber a previously-recorded list with `[]`).
- `submit_lookup_inputs` now passes `ai_result.unmatched_source_values` at the call site — restoring a value the AI was already computing (`_LookupMappingResult.unmatched_source_values`) but that was previously discarded after the AI call.

### `engine/src/migrations_engine/management/lookup_mapping.py`
- New `_add_source_value_action(lookup_map, dest_id, src_val)` helper, replacing the inline `add_source_value` block. Order of checks: (1) case-insensitive match against existing `source_value_map` keys — same `dest_id` is a no-op, a *different* `dest_id` raises `AuthApiError("duplicate_source_value", ..., 409)`; (2) if no case-insensitive match, validate `dest_id` against known `destination_mappings`/`destination_table` entries — if unrecognized, append to `unmapped_source_values` instead of fabricating a new group; (3) otherwise proceed with the existing stack-or-create logic.
- `_lookup_value_map_response` includes `unmapped_source_values=row.unmapped_source_values or []`.

### `engine/tests/test_lookup_mapping_api.py`
- Added `test_patch_add_source_value_rejects_cross_destination_duplicate`, `test_patch_add_source_value_no_op_on_same_destination_duplicate`, `test_patch_add_source_value_unknown_dest_routes_to_unmapped`, `test_sync_lookup_value_map_wires_unmatched_source_values`.

### `web/lib/lookup-api.ts`, `web/components/projects/LookupMappingTable.tsx`, `web/components/projects/ReviewGrid.tsx`, `web/app/projects/[id]/feeds/[feedId]/review/page.tsx`
- `unmappedSourceValues` threaded end-to-end: API response mapping → `LookupMappingTable`'s new amber "Unmapped source values" list (rendered below the table, matching `ReviewGrid.tsx`'s existing `unmappedSourceFields` visual pattern) → `ReviewGrid` prop passthrough → `review/page.tsx`'s `lookupGroups.push`.
- This commit's diff also includes the `bg-amber-500/10` badge-conflict fix and `max-w-[240px]`→`max-w-60` rename — these are task 001gt's changes, bundled into the same commit rather than committed separately (see Deviations).

## Deviations from Plan

- **Migration `0040_add_destination_mappings_column.py` (from the earlier, already-completed task 001fi) was retroactively rewritten** in this commit — not part of 001gu's plan or task scope. The original used raw MySQL-only SQL (`ALTER TABLE ... ADD COLUMN IF NOT EXISTS`, `MODIFY COLUMN ... NOT NULL`); the rewrite uses a dialect-agnostic SQLAlchemy-inspector check (`if "destination_mappings" not in columns: op.add_column(...)`) and **drops the `NOT NULL` enforcement entirely** (column is now `nullable=True` at the DB level in both `0040` and the new `0041`, relying only on the ORM model's `nullable=False` for application-level enforcement, not a real DB constraint). The new `0041` migration follows this same inspector-based, `nullable=True` pattern rather than the plan's originally-specified raw-SQL/MySQL pattern. This is a real, undocumented blast-radius surprise — it touched a prior, already-shipped task's migration file — and the dropped `NOT NULL` constraint is a schema-integrity gap worth a follow-up if it matters for this project (flagging here rather than silently accepting it).
- 001gt's frontend fixes (badge conflict, `max-w` rename) landed in this same commit rather than their own — see 001gt's separate task status; its code is correct but not yet in its own atomic commit.

## Tests

`.venv/bin/python -m pytest engine/tests -q` — 398 passed, 0 failed (verified independently during review). `cd web && npm test -- --run` — 337 passed, 0 failed (verified independently, after a follow-up fix to `LookupMappingTable.tsx` unrelated to this task's own scope — see task 001gv).
