# Task 001bg — Remove Global Approvals Inbox

**Plan:** `plans/2026-07-04-001bg-remove-global-approvals-inbox.md`

**Depends on:** none (standalone cleanup)

**Must complete before:** 001bf (Feeds Workspace UI) — 001bf wires approve/reject into the per-feed slice panel.

## Domain

- [source-model.md](/Users/vjkotra/projects/katana/docs/domain/source-model.md)

## Current State

- A global `/approvals` page (`ApprovalsInbox` component) lists all pending feed slices across all projects. Central team and project stakeholders approve or reject slices from this inbox.
- The Topbar shows an "Approvals" nav link for those roles, with a badge polling `GET /approvals/count` to show the pending count.
- The approve/reject/resubmit actions themselves call per-source endpoints (`/projects/{id}/sources/{sid}/slices/{sliceId}/approve` etc.) that will continue to exist.

## Problem

Slice approvals are being moved into the per-feed workspace (001bf), where they appear inline on the slice status panel of each feed's detail page. The global inbox and its nav link are therefore redundant — they create a confusing parallel path and the badge count becomes misleading once approval is per-feed.

## Objective

Remove the global approvals inbox and all code that exists solely to support it, while preserving the backend approve/reject/resubmit endpoints and the frontend API functions that call them (both are needed by 001bf).

## Scope

**Delete (frontend):**
- `web/app/approvals/page.tsx`
- `web/components/approvals/ApprovalsInbox.tsx`
- `web/components/approvals/__tests__/ApprovalsInbox.test.tsx`

**Modify (frontend):**
- `web/lib/ui-model.ts` — remove `{ label: "Approvals", href: "/approvals" }` from both `central_team` and `project_stakeholder` nav arrays.
- `web/components/Topbar.tsx` — remove `approvalCount` state, the `getPendingApprovalCount` import, the `useEffect` that calls it, and the badge rendering on the Approvals nav item.
- `web/lib/feed-slice-approval-api.ts` — remove `listPendingApprovals`, `getPendingApprovalCount`, `FeedSliceApprovalItem`, and `FeedSliceApprovalCount`. Keep `approveFeedSlice`, `rejectFeedSlice`, `resubmitFeedSlice`, and `FeedSliceApprovalApiError`.
- `web/components/__tests__/Topbar.test.tsx` — remove tests that assert the approval badge count.

**Delete (backend):**
- `GET /approvals` route from `engine/src/migrations_engine/routes/feed_slice_approval.py`
- `GET /approvals/count` route from `engine/src/migrations_engine/routes/feed_slice_approval.py`
- `list_pending_approvals()` function from `engine/src/migrations_engine/management/feeds.py`
- `count_pending_approvals()` function from `engine/src/migrations_engine/management/feeds.py`
- `FeedSliceApprovalItemResponse` schema from `engine/src/migrations_engine/api/schemas.py`
- `FeedSliceApprovalCountResponse` schema from `engine/src/migrations_engine/api/schemas.py`
- Unused imports left behind by the above removals.

**Keep (do not touch):**
- `POST .../slices/{sliceId}/approve` route — used by 001bf per-feed slice panel.
- `POST .../slices/{sliceId}/reject` route — same.
- `POST .../slices/{sliceId}/resubmit` route — same.
- `approve_source_slice`, `reject_source_slice`, `resubmit_source_slice` in `feeds.py`.
- `approveFeedSlice`, `rejectFeedSlice`, `resubmitFeedSlice` in `feed-slice-approval-api.ts`.

## Out of Scope

- Adding the per-feed slice approval panel — that is 001bf.
- Changing the slice status machine or database schema.

## Acceptance Criteria

- `/approvals` page returns 404.
- "Approvals" nav item is absent for all roles.
- Topbar renders without fetching `GET /approvals/count`.
- `GET /approvals` and `GET /approvals/count` backend routes return 404.
- `approveFeedSlice`, `rejectFeedSlice`, `resubmitFeedSlice` still callable and their backend routes still respond.
- All remaining tests pass.

## Pitfalls

- `feed-slice-approval-api.ts` exports `approveFeedSlice` and others — partial delete, not full file deletion. Keep the shared `requestJson`, `parseApiError`, `authHeaders` helpers and the error class.
- `feed_slice_approval.py` router stays registered in the app (the approve/reject/resubmit routes live in it) — only remove the two global GET handlers, not the file or the router registration.
- Check `feeds.py` imports: `FeedSliceApprovalItemResponse` and `FeedSliceApprovalCountResponse` are imported at the top — remove those imports along with the functions that use them.
- Confirm no other file imports `listPendingApprovals` or `getPendingApprovalCount` before deleting.

## Commit

- `chore(001bg): remove global approvals inbox and top-nav badge`
