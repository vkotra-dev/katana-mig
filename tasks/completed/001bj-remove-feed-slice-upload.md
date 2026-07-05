# Task 001bj — Remove Feed Slice Upload from Feed Detail Page

**Plan:** `plans/2026-07-05-001bj-remove-feed-slice-upload.md`

## Context

The feed detail workspace (`/feeds/[feedId]`) contains an "Upload New Slice" card that lets an operator paste raw CSV to create a new slice version. This is a drift from the intended design.

Feeds are immutable once created. The PII-masking and analysis pipeline runs once against the feed data — allowing arbitrary re-upload from the workspace undermines that guarantee and could silently invalidate prior mapping and lookup work. New feeds are added via the "Add Feed" route on the project page, which is the correct and only intake path.

## Scope

### `web/app/projects/[id]/feeds/[feedId]/page.tsx`

Remove:
- `uploadText` state and `setUploadText`
- `uploading` state and `setUploading`
- `handleUploadSlice` function (lines ~138–148)
- `uploadFeedSlice` import (line 11)
- The "Upload New Slice" card JSX (lines ~382–401)
- Update the "Workspace Locked" overlay text (line ~411): remove the phrase "or submit a new version" — the lock message should only say the slice must be approved, not invite re-upload

## Out of Scope

- The slice status panel and approval/rejection actions — those remain unchanged.
- The "Add Feed" flow on the project page — unchanged.
- Any backend route for uploading a slice — not removed here; that is a separate decision.

## Acceptance Criteria

- The feed detail page shows no "Upload New Slice" card.
- No `uploadText`, `uploading`, or `handleUploadSlice` references remain in `page.tsx`.
- `uploadFeedSlice` is not imported in `page.tsx`.
- The workspace locked overlay message no longer mentions submitting a new version.
- All remaining tests pass.

## Commit

- `fix(001bj): remove feed slice upload card from feed detail workspace`
