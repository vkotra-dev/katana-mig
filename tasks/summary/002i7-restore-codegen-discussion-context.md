Task: tasks/completed/002i7-restore-codegen-discussion-context.md
Plan: plans/2026-07-24-002i7-restore-codegen-discussion-context.md
Commits: c0042be (fix), deb78ae (plan file registration)

## Changes Made

### `engine/src/migrations_engine/codegen/service.py`
- Restored the two `FeedComment` queries (feed-level: `feed_id == source_definition_id,
  source_slice_id IS NULL`; slice-level: `source_slice_id == source_slice.source_slice_id`) that
  task 002i3's multi-table refactor had deleted.
- Queries now run once, immediately after `source_slice` is resolved and before the per-table
  loop — not per iteration, since comments are feed/slice-scoped, not table-scoped.
- Every loop iteration's `_build_user_prompt()` call now passes the real `comments`/
  `slice_comments` values instead of the hardcoded `[]`/`[]` that caused the regression.

### `engine/tests/test_codegen_service_api.py`
- New `test_codegen_includes_discussion_comments`: seeds one feed-level and one slice-level
  `FeedComment`, triggers codegen through the real API via `FakeAdapter`, and asserts the
  captured AI-facing user prompt contains both comment bodies and both section headers
  ("Feed discussion (context for mapping intent and business rules)", "Slice discussion (context
  for schema adjustments and anomalies)").

## Deviations from Plan

None. Implementation matches the plan's File Changes section exactly — same query placement, same
restoration approach, same test scenario.

## Domain Updates Required

None — task's own "Domain Updates Required" was `None` (restores existing, already-documented
behavior; nothing in `docs/domain/` describes discussion-comment inclusion as new).

## Tests

`.venv/bin/python -m pytest engine/tests -q` — 419 passed, 0 failed (418 baseline + 1 new).
Independently reran twice during review to confirm stability; both runs clean.
