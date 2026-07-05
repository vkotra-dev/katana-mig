# Task 001bl — Feed Workspace: Slice Preview + AI Analyze Trigger

**Plan:** `plans/2026-07-05-001bl-feed-workspace-slice-view-ai-trigger.md`

## Context

The feed detail workspace still carries the slice approval gate from the old model where operators uploaded slices and a central reviewer had to sign off before mapping could begin. With 001bj removing slice upload (feeds are immutable after creation), approval is no longer meaningful. The gate now just blocks legitimate mapping work.

Two things are needed in its place:
1. **Slice preview** — a read-only view of the masked slice data so operators can validate PII removal before running AI analysis.
2. **"Analyze with AI" button** — the trigger for AI Call 1 (feed columns + DDL → multi-table field mapping + FK classification). Currently there is no button in the feed workspace that starts the mapping proposal.

`FeedSliceRecord.previewRows` already exists (up to 10 CSV rows populated at intake time) — no new backend endpoint needed for the preview.

## Scope

### A. Remove from `web/app/projects/[id]/feeds/[feedId]/page.tsx`

State and computed values:
- `rejectionReason` state
- `showRejectForm` state
- `isSliceApproved` computed value (line 96)
- `isHardGated` computed value (line 98)

Handlers:
- `handleApproveSlice` function
- `handleRejectSlice` function

Imports:
- `approveFeedSlice` from `feeds-api`
- `rejectFeedSlice` from `feeds-api`

JSX:
- "Workspace Locked" overlay (the absolute-positioned overlay on the right column, lines ~389–398)
- Approve/Reject buttons and rejection form in the slice panel
- `approvalRejectionReason` display block
- Status badge showing approved/pending/rejected (no longer meaningful without approval flow)
- The `relative` positioning wrapper on the right column div (only needed for the overlay)

### B. Rename slice panel

Rename "Slice Status" heading → **"Slice"**. Replace the status badge with a simple "received" indicator (e.g. a green dot or static "received" chip) when a slice is present.

### C. Add slice preview

Below the slice metadata (version, row count) add a scrollable read-only preview table built from `latestSlice.previewRows`. The rows are raw CSV strings — split on `,` to get columns. Use `latestSlice`'s `FeedSchemaColumnRecord` list (already fetched via `listFeedSchema`) for column headers.

If `previewRows` is empty, show "No preview available."

Keep the preview compact — `max-h-48 overflow-y-auto`, monospace font, `text-[10px]`.

### D. Add "Analyze with AI" button

Add to the left column (below the slice preview):

- Calls `proposeMappingSnapshot(token, projectId, feedId)` from `mapping-api`
- Label: "Analyze with AI" / loading state: "Analyzing…"
- Enabled when `!hasNoSlices && !analyzing`
- On success: reload mapping snapshot (`getMappingSnapshot`) and lookup maps
- On error: show inline error in the left column

State: `const [analyzing, setAnalyzing] = useState(false)`

Import to add: `proposeMappingSnapshot` from `../../../../../lib/mapping-api`

### E. Right column

Remove the `relative` class and the overlay. The right column is always fully interactive. The "No mapping proposals generated yet" empty state in the Field Mappings section is sufficient guidance when AI hasn't been run yet.

## Out of Scope

- Removing `approveFeedSlice` / `rejectFeedSlice` backend routes — separate decision.
- Changing the feed list (`SourceList.tsx`) — unaffected.
- The business user review route (`/feeds/[feedId]/review`) — unaffected.

## Acceptance Criteria

- No "Workspace Locked" overlay appears on the feed detail page.
- No Approve/Reject buttons appear anywhere on the feed detail page.
- The left column shows: slice metadata, scrollable masked data preview, "Analyze with AI" button.
- Clicking "Analyze with AI" triggers the mapping proposal and populates the Field Mappings section on success.
- The right column (Field Mappings, Lookup Fibers, Reviews) is always visible and interactive.
- When no slice exists, "Analyze with AI" is disabled.
- All remaining tests pass.

## Pitfalls

- `previewRows` is a `string[]` of raw CSV rows — the first element may or may not be a header row depending on how the intake wrote it. Use `listFeedSchema` columns (already fetched as `feedSchema` state) as the column headers rather than parsing the first preview row.
- `proposeMappingSnapshot` may return a 409 if a mapping already exists and is in a non-terminal state — handle this gracefully (reload the existing mapping rather than showing a raw error).
- Do not remove `hasNoSlices` — it is still used to gate the "Analyze with AI" button and show the "No slices" empty state in the slice panel.

## Commit

- `feat(001bl): replace slice approval gate with slice preview and AI analyze trigger`
