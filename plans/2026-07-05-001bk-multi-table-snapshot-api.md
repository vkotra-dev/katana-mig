# Plan: 001bk — Multi-Table Snapshot API

- **Task Link:** [001bk-multi-table-snapshot-api.md](file:///Users/vjkotra/projects/katana/tasks/001bk-multi-table-snapshot-api.md)
- **Domain Link:** [source-model.md](file:///Users/vjkotra/projects/katana/docs/domain/source-model.md)

## Current State

- The backend has a single-table endpoint `GET /projects/{project_id}/sources/{source_definition_id}/mapping-snapshot` which returns the snapshot for the first destination table.
- There is no endpoint returning all approved mapping snapshots (for each destination table) for a feed source definition.
- The client side `getLatestApprovedMappingSnapshot` maps to `/mapping-snapshot`.

## Objective

1. Create a backend route `GET /projects/{project_id}/sources/{source_definition_id}/mapping-snapshots` that queries for all approved `MappingSnapshot` records, returns the latest per `destination_object_name`, and orders them by name.
2. Add a corresponding frontend API client function `getAllApprovedMappingSnapshots` in `web/lib/mapping-api.ts`.
3. Verify if `web/app/projects/[id]/feeds/[feedId]/page.tsx` uses `getLatestApprovedMappingSnapshot` and wire it up if needed.
4. Add backend test coverage verifying 0, 1, and 2 tables mapping responses.

## Out of Scope

- Removing single-table query parameter support on `/mapping-snapshot`.
- Modifying codegen scripts compiler logic.

## Blast Radius

Minimal. Only affects mapping snapshot APIs.

## File Changes

### `engine/src/migrations_engine/routes/mapping_snapshots.py`

- Add `GET /projects/{project_id}/sources/{source_definition_id}/mapping-snapshots` endpoint.
- Retrieve approved snapshots for `project_id` + `source_definition_id`, filter/group latest per table in Python (group by `destination_object_name`, select latest by `created_at` / `approved_at`), and return `list[MappingSnapshotResponse]`.

### `web/lib/mapping-api.ts`

- Export `getAllApprovedMappingSnapshots` calling the new list endpoint.

## Tests

### `engine/tests/test_mapping_snapshots.py` or new backend tests

- Create integration tests checking return structures for 0, 1, and 2 table snapshots.

## Verification

- Run backend pytest.
- Run frontend vitest tests.

## Pitfalls

- Ensure that grouping by `destination_object_name` selects the correct latest approved snapshot. Sorting by `created_at` descending and using a dictionary/map in Python is simple and correct:
  ```python
  snapshots = db.scalars(
      select(MappingSnapshot)
      .where(
          MappingSnapshot.project_id == project_id,
          MappingSnapshot.source_definition_id == source_definition_id,
          MappingSnapshot.status == APPROVED_SNAPSHOT_STATUS,
      )
      .order_by(
          MappingSnapshot.destination_object_name.asc(),
          MappingSnapshot.created_at.desc(),
      )
  ).all()
  # Dedup in Python:
  seen = set()
  latest_snapshots = []
  for s in snapshots:
      if s.destination_object_name not in seen:
          seen.add(s.destination_object_name)
          latest_snapshots.append(s)
  ```
  This is extremely clean and matches exactly what we need!

## Commit

- `feat(001bk): add list-approved-snapshots route for multi-table mapping`
