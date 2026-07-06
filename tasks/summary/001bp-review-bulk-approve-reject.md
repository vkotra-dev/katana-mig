# Task Summary — 001bp-review-bulk-approve-reject

Bulk approve/reject all draft mapping snapshots for a feed in a single action, solving the issue where multi-table feeds got stuck in partial-draft state.

## Changes

- **Backend Bulk Actions**: Updated `approve_mapping` and `reject_mapping` in [review.py](file:///Users/vjkotra/projects/katana/engine/src/migrations_engine/mapping/review.py) to look up and modify all draft snapshots for the source feed in a single transaction if no table name parameter is specified.
- **Single-Table Compatibility**: Hardened both functions so that non-draft snapshots continue to raise `422` error on explicit table path, keeping single-table flow identical to before.
- **Frontend Badge & Controls**: Calculated aggregate status badge and adjusted `showControls` on [review/page.tsx](file:///Users/vjkotra/projects/katana/web/app/projects/[id]/feeds/[feedId]/review/page.tsx) to reflect states across all snapshots (Approve/Reject controls visible if at least one snapshot is draft).
- **Automated Tests**: Added backend test in [test_mapping_review_api.py](file:///Users/vjkotra/projects/katana/engine/tests/test_mapping_review_api.py) and frontend test cases in [review/page.test.tsx](file:///Users/vjkotra/projects/katana/web/app/projects/[id]/feeds/[feedId]/review/page.test.tsx) for validation.
