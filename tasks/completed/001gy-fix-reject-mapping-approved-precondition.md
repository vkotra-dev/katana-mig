---
id: 001gy
title: Fix Reject-Mapping Precondition Mismatch and Repair Broken Tests from the Request-Revision/Reject Split
status: completed
created: 2026-07-25
priority: critical
domain: backend / frontend / mapping
depends-on: []
---

# Task 001gy — Fix Reject-Mapping Precondition Mismatch and Repair Broken Tests

- **Plan**: [2026-07-25-001gy-fix-reject-mapping-approved-precondition.md](../plans/2026-07-25-001gy-fix-reject-mapping-approved-precondition.md)
- **Domain**: [source-model.md](../docs/domain/source-model.md)

## Context

Commit `492684f` split the old, misleadingly-named `reject_mapping()` (which actually just reset a snapshot to `draft`) into two real functions: `request_revision()` (stakeholder, returns to `draft`, ball to `central_team`) and a new terminal `reject_mapping()` (PM/Admin only, sets `status="rejected"`, `current_ball_role=None`). This work was independently verified against the actual diffs (not the implementer's report, which twice in this same effort claimed test results that didn't match reality) — the split itself is real, correct, and committed. But two things are broken:

### 1. The "Reject" button can never succeed when clicked

`review/page.tsx`'s "Reject" button only renders when `aggregateStatus === "approved"` (search `onClick={handleReject}` — it's inside the same conditional block as "Revert to Draft", both gated on `(role === "pm" || role === "admin") && aggregateStatus === "approved"`). But `reject_mapping()` (`engine/src/migrations_engine/mapping/review.py`, currently lines 435-483) only matches snapshots where `MappingSnapshot.status == "draft"` (both the `destination_object_name`-scoped branch, line 452, and the bulk branch, line 463). Since the button is only reachable when every snapshot is already `"approved"`, there are never any `"draft"` snapshots to match — clicking "Reject" always 404s with `"No draft mapping snapshots exist to reject."` **Confirmed with the product owner: Reject should operate on `approved` snapshots** — it sits next to "Revert to Draft" for a reason: from an approved state, PM/Admin either walks it back to draft (soft undo) or kills it outright (hard terminal state). This task changes the backend to match the UI, not the other way around.

### 2. Two pre-existing backend tests broke and were never updated

Confirmed by directly running the suite (not assumed): `.venv/bin/python -m pytest engine/tests -q` → **2 failed, 400 passed**.

- `test_reject_marks_snapshot_rejected` (`engine/tests/test_mapping_review_api.py:518-537`): calls `POST /mapping/reject` with `stakeholder_token` and a `{"reason": ...}` body, right after `propose` (so the snapshot is still `draft`) — this is actually `request_revision()`'s exact shape (stakeholder-initiated, draft snapshot, includes a reason), not reject's. It fails now because `/mapping/reject` requires PM/Admin (`stakeholder_token` → `403`) and no longer accepts a body. **This test's scenario belongs to `request_revision`, not `reject_mapping`** — repurpose it rather than patching it to "pass" under the wrong endpoint.
- `test_bulk_approve_and_reject_multiple_snapshots` (`engine/tests/test_mapping_review_api.py:719-818`): approves 2 snapshots, then **manually reverts them to `draft` via direct DB mutation** (line 796-797, comment: `# Revert to draft for testing reject`) specifically to work around the old `reject_mapping()`'s draft-only precondition, then calls `/mapping/reject` with `stakeholder_token`. Fails the same way (403). Once reject operates on `approved`, this manual revert hack becomes unnecessary and should be removed — reject directly from the approved state the test already put the snapshots in.

Neither new function (`request_revision`, `reject_mapping`) got any test coverage of its own from `492684f` — this task adds it.

### 3. Two frontend test breakages, purely mechanical, unrelated to the design question

- `review/page.test.tsx` **fails to load at all**: `ReferenceError: rejectMappingSnapshotMock is not defined`. Root cause confirmed by reading the file directly: `rejectMappingSnapshotMock` is defined in the `vi.hoisted(() => ({...}))` factory (line 32) and referenced inside the `vi.mock("../../../../../../lib/mapping-api", ...)` factory (line 64), but was never added to the destructuring assignment that pulls names out of `vi.hoisted()`'s return value (lines 5-25 — `requestRevisionMock` is there, `rejectMappingSnapshotMock` is not). This single missing line drops **the entire test file** from the suite (confirmed: frontend total went from 337 to 322 — a ~15-test gap, not just "1 failed").
- `web/lib/mapping-api.test.ts` (around line 202-204): the 4th chained `mockResolvedValueOnce` in the combined propose/patch/approve/`requestRevision` test still returns a mock response body with `status: "rejected"` (line 180) — stale from when this call position exercised the old `rejectMappingSnapshot`. The test now calls `requestRevision(...)` and asserts `status: "draft"` against that same stale mock body, so it fails.

## Requirements

1. `reject_mapping()` (`review.py`): change both status filters from `"draft"` to `"approved"`. Update the "no snapshots" error message accordingly (currently says "No draft mapping snapshots exist to reject.").
2. Repurpose `test_reject_marks_snapshot_rejected` into a test for `request_revision()`: point it at `/mapping/revision`, assert `status == "draft"` (not `"rejected"`) and that the ball returns to `central_team`. Rename the function to reflect what it actually tests.
3. Add a new, genuinely missing test for `reject_mapping()`: propose → approve → reject (PM or Admin role token, no request body) → assert `status == "rejected"` and `current_ball_role is None`. Follow `test_unapprove_mapping_by_pm`'s existing pattern (`review.py:457-516`, currently the only place in this file that seeds a PM-role user) for auth setup, or use `ADMIN_ROLE` instead (simpler — `ADMIN_ROLE` bypasses the `pm_user_id`-membership check in `user_has_project_access`, `engine/src/migrations_engine/management/access.py:61-68`, so no `registry.pm_user_id` wiring is needed).
4. `test_bulk_approve_and_reject_multiple_snapshots`: remove the manual `s.status = "draft"` DB-mutation workaround (lines 796-797) and its surrounding now-unnecessary re-fetch; call `/mapping/reject` directly against the `approved` snapshots using a PM/Admin token instead of `stakeholder_token`.
5. `review/page.test.tsx`: add `rejectMappingSnapshotMock,` to the destructuring list (lines 5-25) that pulls names out of `vi.hoisted()`.
6. `web/lib/mapping-api.test.ts`: change the stale mock response body's `status: "rejected"` (line 180) to `status: "draft"`.
7. Add one new frontend test exercising `handleReject`/the "Reject" button from `aggregateStatus === "approved"`, asserting `rejectMappingSnapshot` is called — this specific gap (no test drives the real reachable state) is exactly what let the precondition mismatch ship unnoticed.

## Files to Change

1. `engine/src/migrations_engine/mapping/review.py` — `reject_mapping()` status filter.
2. `engine/tests/test_mapping_review_api.py` — repurpose one test, add one new test, fix one test's auth/setup.
3. `web/app/projects/[id]/feeds/[feedId]/review/page.test.tsx` — one-line destructuring fix, one new test.
4. `web/lib/mapping-api.test.ts` — one-line stale mock fix.

## Verification

```bash
.venv/bin/python -m pytest engine/tests -q
cd web && npm test -- --run
```

Both must show zero failures with counts you've actually run and read, not assumed. Given this exact task's context, do not report a pass count without having executed the command in this same turn.

---
Plan: plans/2026-07-25-001gy-fix-reject-mapping-approved-precondition.md
Summary: tasks/summary/001gy-fix-reject-mapping-approved-precondition.md
