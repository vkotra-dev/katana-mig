# Task 001bk — Multi-Table Snapshot API

**Plan:** `plans/2026-07-05-001bk-multi-table-snapshot-api.md`

## Context

001bd shipped multi-table AI mapping: one AI call creates N `MappingSnapshot` records (one per identified destination table) in a single DB transaction. The backend query layer (`select_latest_approved_mapping_snapshot` in `snapshots.py`) and the codegen/execution private helpers already correctly filter by `source_definition_id` — those code review findings are resolved.

The remaining gap is in the API route and its frontend caller:

- `GET /projects/{project_id}/sources/{source_definition_id}/mapping-snapshot` (no query param) defaults to `destination_object_references[0]` — silently returning only the first table's approved snapshot for multi-table feeds.
- `getLatestApprovedMappingSnapshot` in `web/lib/mapping-api.ts` calls this route without a table name — same silent [0] behaviour.
- There is no route that returns all approved snapshots for a source in one call. The feed workspace and codegen pipeline have no way to discover which destination tables have approved snapshots without knowing the table names upfront.

## Objective

Add a list endpoint for approved mapping snapshots (`GET /projects/{project_id}/sources/{source_definition_id}/mapping-snapshots`) that returns all approved snapshots for a source, and wire it up in the frontend.

## Scope

### A. Backend — `engine/src/migrations_engine/routes/mapping_snapshots.py`

Add a new GET route:

```
GET /projects/{project_id}/sources/{source_definition_id}/mapping-snapshots
```

Returns all approved `MappingSnapshot` records for the source, ordered by `destination_object_name` for stable output. Response model: `list[MappingSnapshotResponse]`.

Implementation: query `MappingSnapshot` where `project_id = X AND source_definition_id = Y AND status = "approved"`, ordered by `destination_object_name ASC, created_at DESC`. Return all, not just latest — callers use latest per table via `DISTINCT ON` or by grouping in Python.

Alternatively (simpler): return the latest approved snapshot per destination table using a subquery:
```sql
SELECT DISTINCT ON (destination_object_name) *
FROM mapping_snapshots
WHERE project_id = :pid AND source_definition_id = :sdid AND status = 'approved'
ORDER BY destination_object_name, created_at DESC
```

### B. Backend — `engine/src/migrations_engine/api/schemas.py`

No new schema needed — reuse `MappingSnapshotResponse` as list item.

### C. Frontend — `web/lib/mapping-api.ts`

Add:

```typescript
export async function getAllApprovedMappingSnapshots(
  token: string,
  projectId: string,
  sourceDefinitionId: string,
): Promise<MappingSnapshotRecord[]>
// GET /projects/{projectId}/sources/{sourceDefinitionId}/mapping-snapshots
// Returns one record per destination table (latest approved)
```

The existing `getLatestApprovedMappingSnapshot` (single-table, hits `/mapping-snapshot`) is retained — it is still valid for single-table use. Do not remove it.

### D. Frontend — wire up in feed detail page (optional for this task)

If the feed workspace needs to display the approved mapping grid for all tables: replace the single `getLatestApprovedMappingSnapshot` call with `getAllApprovedMappingSnapshots` and merge the bindings. This is in scope only if the feed detail page is currently using `getLatestApprovedMappingSnapshot` for the review grid display. Verify before changing.

## Out of Scope

- Changing the codegen pipeline to generate SQL for multiple tables per source — that is a larger architectural change and a separate task.
- Changing `_primary_destination_object_name` in `codegen/service.py` — single-table codegen is acceptable for now.
- Removing or making `destination_object_name` required on the existing `/mapping-snapshot` GET route — backwards compatibility.

## Acceptance Criteria

- `GET /projects/{project_id}/sources/{source_definition_id}/mapping-snapshots` returns one approved snapshot per destination table for the source.
- A source with N destination tables returns N records (or fewer if some have no approved snapshot yet).
- `getAllApprovedMappingSnapshots` in `mapping-api.ts` calls the new route and returns `MappingSnapshotRecord[]`.
- The existing single-table route and `getLatestApprovedMappingSnapshot` are unchanged.
- Tests cover the list endpoint: 0 tables, 1 table, 2 tables.

## Pitfalls

- SQLAlchemy does not support `DISTINCT ON` natively — use a subquery to select max `created_at` per `destination_object_name`, then join back to get the full row, OR use Python grouping after fetching.
- The new route must still enforce `require_project_access` before querying.
- If `source_definition_id` has no approved snapshots the route returns `[]`, not 404.

## Commit

- `feat(001bk): add list-approved-snapshots route for multi-table mapping`
