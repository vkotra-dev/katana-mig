# Task 001ca — Lookup Fiber → LookupValueMap Bridge

**Plan:** `plans/2026-07-08-001ca-lookup-fiber-bridge.md`

## Context

When an operator completes the lookup fiber workflow (maps values in the workspace, gets approved), the confirmed mappings live in the `LookupMapping` table. Snapshot generation reads from `LookupValueMap`, a completely separate table that nobody writes to during the fiber workflow. The result: `generate_lookup_snapshot` raises `409 lookup_values_unmapped` even though the operator finished all their work.

## Scope

**Backend only — single function change:**

In `approve_fiber` (`management/fibers.py`), after setting `fiber.status = "business_approved"` and before `db.commit()`, for `fiber_type == "lookup"` fibers:

1. Query all `LookupMapping` rows for this fiber where `status == "confirmed"`
2. Build `source_value_map = {mapping.source_value: _extract_destination_id(mapping.dest_row)}` for each confirmed mapping that has a `dest_row`
3. Query the `LookupDestFeed` for this fiber to get the destination reference rows (`columns`) — needed to populate `LookupValueMap.destination_table`
4. Query `LookupDestEntry` rows via the `LookupDestFeed` to get the full destination table rows
5. Upsert `LookupValueMap`: if a draft already exists for `(source_definition_id=fiber.feed_id, lookup_name=fiber.fiber_key)`, replace `source_value_map` and `destination_table`; otherwise insert a new one

`_extract_destination_id` already exists in `management/lookup_mapping.py` — import and reuse it.

## Out of Scope

- `generate_lookup_snapshot` — no changes; it stays as an explicit operator step
- Frontend — no changes
- `trigger_fiber` — no changes
- Automatic snapshot generation on approval

## Acceptance Criteria

- After `approve_fiber` succeeds, a `LookupValueMap` row exists for the fiber's `lookup_name` with `source_value_map` populated from confirmed `LookupMapping` rows
- `generate_lookup_snapshot` succeeds without manual `LookupValueMap` creation
- Fibers with no confirmed mappings still transition to `business_approved` (no 500)
- Existing `LookupValueMap` rows created manually are replaced (not duplicated) on approval

## Pitfalls

- `_extract_destination_id` is private to `lookup_mapping.py` — either import it or move it to a shared utility. Importing across management modules is acceptable.
- A fiber may have multiple `lookup_name` values if `submit_lookup_inputs` was called with more than one lookup. Group by `lookup_name` and upsert one `LookupValueMap` per name.
- `LookupDestFeed` has a `unique=True` FK on `fiber_id` — there is exactly one dest feed per fiber. `LookupDestEntry` rows join through `dest_feed_id`.
- Do the upsert inside the same DB session before `db.commit()` so the whole approval is atomic.

## Commit

- `fix(001ca): bridge confirmed lookup fiber mappings into LookupValueMap on approval`
