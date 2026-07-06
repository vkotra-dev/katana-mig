# Task 001bp — Bulk Approve/Reject All Snapshots on Review Page

**Plan:** `plans/2026-07-06-001bp-review-bulk-approve-reject.md`

## Context

The approve and reject endpoints (`POST /mapping/approve`, `POST /mapping/reject`) call `get_mapping()` internally, which returns a single snapshot — the most recently created draft for the feed. With two destination tables per feed (`policy_master`, `policy_claims`), each feed has two snapshot rows. A single Approve click only changes one snapshot's status. After reload, `representativeSnapshot = mappingSnapshots[0]` may already be "approved", so `showControls` becomes false and the stakeholder can no longer approve the remaining draft snapshot. The second table is permanently stuck in draft.

Additionally, the status badge reads `representativeSnapshot.status` (index 0) — after partial approval, it shows "approved" even though one table is still draft.

## Scope

**Backend:**
- `engine/src/migrations_engine/mapping/review.py` — `approve_mapping` and `reject_mapping` functions: query all draft snapshots for the feed (`source_definition_id`) and approve/reject every one in a single transaction
- `engine/src/migrations_engine/routes/mapping.py` — approve/reject route handlers (no signature change; behaviour flows from `review.py`)

**Frontend:**
- `web/app/projects/[id]/feeds/[feedId]/review/page.tsx`
  - `showControls`: change from `representativeSnapshot?.status === "draft"` to `mappingSnapshots.some(s => s.status === "draft")`
  - Status badge: derive aggregate status — "approved" only if all are approved; "rejected" if any is rejected; "draft" otherwise

## Out of Scope

- Per-table individual approve/reject (all tables in a feed move together)
- Notifications to operations after rejection
- New migrations (no schema change needed)

## Acceptance Criteria

- Clicking Approve on the review page approves ALL draft snapshots for the feed in one action
- Clicking Reject rejects ALL draft snapshots for the feed in one action
- Status badge correctly shows aggregate status across all snapshots
- `showControls` remains visible as long as any snapshot is still in draft
- Existing single-table feeds continue to work identically

## Pitfalls

- `approve_mapping` currently calls `create_approved_mapping_snapshot` which inserts a new row with `status="approved"`. Multi-table approval must loop over all drafts and update each in place (or insert approved rows), maintaining the existing version bump logic.
- The frontend `handleApprove` / `handleRequestRevision` already reload all snapshots after the call — no change needed there.

## Commit

- `fix(001bp): approve and reject all draft snapshots for a feed in one action`
