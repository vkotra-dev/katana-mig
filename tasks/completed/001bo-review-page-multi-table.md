# Task 001bo — Fix Review Page to Display Multiple Destination Tables

**Plan:** `plans/2026-07-05-001bo-review-page-multi-table.md`

## Context

The review page at `/projects/[id]/feeds/[feedId]/review` calls `getMappingSnapshot` (GET `/mapping`) which returns a single snapshot. With two destination tables per feed (`policy_master`, `policy_claims`), only the most recently created snapshot is returned — the other table is never rendered. The `mappingTablesMap` builder falls back to `snapshot.destinationObjectName` as the group key because `destinationTableName` is never stored in binding dicts, causing all bindings to collapse into one group.

## Scope

- `web/app/projects/[id]/feeds/[feedId]/review/page.tsx` only
- Replace `getMappingSnapshot` with `getAllApprovedMappingSnapshots(..., true)` to fetch all snapshots for the feed
- Change state from single `MappingReviewRecord | null` to `MappingSnapshotRecord[]`
- Build `mappingTablesMap` from each snapshot's `destinationObjectName` directly
- Use `allMappingSnapshots[0]` as the representative snapshot for status display and approve/reject controls

## Out of Scope

- Per-table approve/reject (out of scope; single-snapshot backend behavior is acceptable)
- Backend changes (the `?any_status=true` endpoint already exists from 001bm)

## Acceptance Criteria

- Both `policy_master` and `policy_claims` tables render in the ReviewGrid
- Status badge and approve/reject controls display correctly
- TypeScript compiles with no new errors

## Pitfalls

- `approveMappingSnapshot` / `rejectMappingSnapshot` still operate on one snapshot at a time — only the latest snapshot's status changes; per-table approval is deferred
- `MappingSnapshotRecord` does not have `destinationFields`; do not reference it

## Commit

- `feat(001bo): fix review page to display all destination tables`
