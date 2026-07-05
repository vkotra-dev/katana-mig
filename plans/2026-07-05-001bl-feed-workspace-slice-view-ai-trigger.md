# Plan: 001bl — Feed Workspace: Slice Preview + AI Analyze Trigger

- **Task Link:** [001bl-feed-workspace-slice-view-ai-trigger.md](file:///Users/vjkotra/projects/katana/tasks/001bl-feed-workspace-slice-view-ai-trigger.md)
- **Domain Link:** [ui.md](file:///Users/vjkotra/projects/katana/docs/domain/ui.md)

## Objective

1. Clean up obsolete slice approval/rejection gates (overlay, state variables, handlers, badges, API imports) in `web/app/projects/[id]/feeds/[feedId]/page.tsx`.
2. Add a scrollable, read-only preview table showing raw CSV rows from `latestSlice.previewRows` (split on comma, aligned under headers from `listFeedSchema`).
3. Add an "Analyze with AI" trigger button that executes `proposeMappingSnapshot` and reloads mapping/lookup snapshot records on success.
4. Clean up the detail page test cases in `page.test.tsx` to align with the new layout and verify the flow.

## Blast Radius

Mainly `web/app/projects/[id]/feeds/[feedId]/page.tsx` and its test suite.

## File Changes

### `web/app/projects/[id]/feeds/[feedId]/page.tsx`

- Remove imports of `approveFeedSlice` and `rejectFeedSlice` from `feeds-api`.
- Add import of `proposeMappingSnapshot` from `mapping-api`.
- Remove state hooks: `rejectionReason`, `showRejectForm`.
- Add state hook: `analyzing` (boolean) and `analysisError` (string | null).
- Remove handlers: `handleApproveSlice`, `handleRejectSlice`.
- Add handler: `handleAnalyzeWithAi` calling `proposeMappingSnapshot`, catching 409 and reloading rather than failing, or showing inline errors.
- Remove computed variables: `isSliceApproved`, `isHardGated`.
- Update slice metadata card layout:
  - Rename header: "Slice Status" -> "Slice".
  - Replace status badge with green "received" dot/chip when slice is present.
  - Render a CSV preview table using `latestSlice.previewRows` and `feedSchema` (if `previewRows` has entries).
- Add "Analyze with AI" button below the preview.
- Remove "Workspace Locked" overlay on the right column.

### `web/app/projects/[id]/feeds/[feedId]/page.test.tsx`

- Remove `approveFeedSliceMock` / `rejectFeedSliceMock` mocks.
- Add `proposeMappingSnapshotMock` mock.
- Update test cases:
  - Remove test case "shows workspace lock banner when slice is pending".
  - Replace/update "unlocks downstream mappings..." to verify clicking "Analyze with AI" starts the mapping proposal successfully.

## Verification

- Run frontend vitest tests (`npm test`).

## Commit

- `feat(001bl): replace slice approval gate with slice preview and AI analyze trigger`
