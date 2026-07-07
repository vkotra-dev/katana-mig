# Task 001bu — Feed Slice Rejection: Status Banner and Data Replacement

**Plan:** `plans/2026-07-07-001bu-feed-slice-rejection-replacement.md`

## Context

When a feed slice is uploaded it enters `pending_approval`. An admin approves or rejects it. If rejected, the feeds workspace gives the user no clear signal and no path forward — the rejection reason is buried in the slice card, and there is no upload control visible. Similarly, when a slice is `pending_approval`, there is no prominent indication that work is blocked waiting for approval.

## Scope

**Frontend only:**

1. **Status banner (all roles):** When the latest slice is `pending_approval`, show an amber info banner at the top of the feed workspace: "Source data is pending approval — field mapping analysis will be available once the slice is approved."

2. **Rejection state:** When the latest slice is `rejected`:
   - Show a red alert banner at the top with `approvalRejectionReason` and a file input + "Upload replacement" button
   - On successful upload: reload slices; new slice enters `pending_approval` and the amber banner appears

3. **Approved state:** When the latest slice is `approved`, show a quiet "Upload new slice" control at the bottom of the Slice panel (left column). This covers the case where an operator discovers a data gap after approval and needs to submit a corrected file for the same feed. On upload: new slice enters `pending_approval` and the amber banner appears.

4. **Pending approval state:** No upload control — one slice must clear the review queue before a new one is submitted.

5. **Add `resubmitFeedSlice` to `feeds-api.ts`:** Backend `POST /sources/{id}/slices/{sliceId}/resubmit` route exists but has no frontend counterpart. Wire it up client-side only — not exposed in UI in this task.

## Out of Scope

- Admin approval/reject controls (already exist on the admin-side UI)
- Notifications / email when slice is approved or rejected
- Showing banner on the project feeds list page (only the feed workspace page)

## Acceptance Criteria

- `pending_approval` slice → amber banner visible at top of feed workspace for all roles
- `rejected` slice → red banner with rejection reason + file upload control visible
- Uploading a replacement file succeeds → slice list reloads → amber "pending approval" banner replaces the red banner
- `approved` slice → no banner shown
- TypeScript compiles without new errors

## Pitfalls

- `latestSlice` is `slices[slices.length - 1]` (backend returns ascending by `created_at`) — after uploading a replacement, the new `pending_approval` slice becomes the last entry; verify the reload path uses the same derivation
- The file upload control should only appear for `central_team` OR for any authenticated user (check who can call `uploadFeedSlice` — the backend route uses `get_current_user`, so all roles can upload; show the control to all)
- `resubmitFeedSlice` requires `source_slice_id` of the rejected slice plus an optional `encoding` field — pass `latestSlice.sourceSliceId`

## Commit

- `feat(001bu): show approval status banner and data replacement upload on rejected feed slice`
