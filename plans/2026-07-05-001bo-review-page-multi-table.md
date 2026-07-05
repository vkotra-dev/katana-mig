# Plan: 001bo — Fix Review Page to Display Multiple Destination Tables

- **Task Link:** [001bo-review-page-multi-table.md](file:///Users/vjkotra/projects/katana/tasks/001bo-review-page-multi-table.md)
- **Domain Link:** [ui.md](file:///Users/vjkotra/projects/katana/docs/domain/ui.md)

## Objective

1. Update the review page at `web/app/projects/[id]/feeds/[feedId]/review/page.tsx` to fetch all snapshots (regardless of status, since we want to review them before/after approval) using `getAllApprovedMappingSnapshots(token, projectId, feedId, true)`.
2. Re-implement the mapping table builder `mappingTablesMap` by iterating over all mapping snapshots instead of just one single snapshot, grouping field bindings by `destinationObjectName`.
3. Use the first snapshot (`allMappingSnapshots[0]`) to drive metadata like status badge, created timestamp, and approve/reject controls.

## File Changes

### `web/app/projects/[id]/feeds/[feedId]/review/page.tsx`

- Replace `getMappingSnapshot` import with `getAllApprovedMappingSnapshots` from `mapping-api`.
- Replace `mappingSnapshot` state (`MappingReviewRecord | null`) with `mappingSnapshots` state (`MappingSnapshotRecord[]`).
- Replace `getMappingSnapshot` invocation in `loadAllData` with `getAllApprovedMappingSnapshots(token, projectId, feedId, true)`.
- Re-build `mappingTablesMap` using all returned snapshots, mapping each snapshot to a `MappingTableRecord` where the group key is `snapshot.destinationObjectName`.
- Use `mappingSnapshots[0]` to drive status display ("approved", "draft", etc.) and action buttons (Approve, Reject).

### `web/app/projects/[id]/feeds/[feedId]/review/page.test.tsx`

- Update mock definitions for vitest.
- Update assertions in the test suite to expect rendering of multiple tables.

## Verification

- Run frontend tests `npm test`.

## Commit

- `feat(001bo): fix review page to display all destination tables`
