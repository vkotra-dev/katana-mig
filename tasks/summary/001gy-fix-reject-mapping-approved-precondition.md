Task: tasks/completed/001gy-fix-reject-mapping-approved-precondition.md
Plan: plans/2026-07-25-001gy-fix-reject-mapping-approved-precondition.md
Commits: c7b3214

## Changes Made

### `engine/src/migrations_engine/mapping/review.py`
- `reject_mapping()`: both status filters changed from `"draft"` to `"approved"`; error message updated to `"No approved mapping snapshots exist to reject."` This is the actual fix — the "Reject" button was only ever reachable when `aggregateStatus === "approved"`, so the backend's old `"draft"` filter meant every click 404'd.

### `engine/tests/test_mapping_review_api.py`
- `test_reject_marks_snapshot_rejected` repurposed to `test_request_revision_marks_snapshot_draft_and_returns_ball_to_operator` — now correctly points at `/mapping/revision` and asserts `status == "draft"` + `current_ball_role == "central_team"` (its original scenario — stakeholder, draft snapshot, with a reason — was always `request_revision`'s shape, not reject's).
- New `test_reject_marks_approved_snapshot_rejected_and_clears_ball` — propose → approve → reject (seeds an `ADMIN_ROLE` user inline) → asserts `status == "rejected"`, `current_ball_role is None`, and that rejecting a second time 404s (nothing left in `approved` state to match).
- `test_bulk_approve_and_reject_multiple_snapshots` — removed the manual `s.status = "draft"` DB-mutation workaround; now rejects directly from `approved` using an inline-seeded `ADMIN_ROLE` token instead of `stakeholder_token`.

### `web/app/projects/[id]/feeds/[feedId]/review/page.test.tsx`
- Added the missing `rejectMappingSnapshotMock,` to the `vi.hoisted()` destructuring list — this was the entire cause of the whole file failing to load.
- New test: renders the page as an admin session with an `approved` snapshot, clicks "Reject", asserts `rejectMappingSnapshot` was called with the right args.

### `web/lib/mapping-api.test.ts`
- Fixed the stale chained-mock response body: `status: "rejected"` → `status: "draft"`, matching what the `requestRevision` call at that position actually asserts.

## Deviations from Plan

None structural — implementation matches the plan almost line-for-line, including the exact test code specified in the plan's File Changes section.

## Tests

`.venv/bin/python -m pytest engine/tests -q` — **403 passed, 0 failed**. Matches the plan's prediction exactly (400 baseline + 1 new test + 2 previously-failing tests now fixed in place).

`cd web && npm test -- --run` — verified across 5 separate runs during review: 4 of 5 showed **337 passed, 0 failed**; one showed 336 passed / 1 failed in `app/projects/[id]/feeds/[feedId]/page.test.tsx` (an `AiLogViewer` header-text assertion, unrelated file). Traced this specifically rather than accepting the "pre-existing" label on faith: reverting `731ad19`'s button-className diff appeared to fix it in one experiment, but running that same single test file in isolation at current `HEAD` (buttons included) also passed — so the button diff was a red herring, and this is a low-frequency, non-deterministic flake in the full-suite run, not a regression caused by this task or `731ad19`. Not investigated further as it's out of this task's scope; worth a dedicated look if it recurs often enough to be disruptive.

All verification numbers in this summary were produced by commands executed during this review, not carried over from the implementer's report.
