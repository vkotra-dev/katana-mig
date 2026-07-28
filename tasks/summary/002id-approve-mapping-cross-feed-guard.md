Task: tasks/completed/002id-approve-mapping-cross-feed-guard.md
Plan: plans/2026-07-28-002id-approve-mapping-cross-feed-guard.md

## Changes Made

### `engine/src/migrations_engine/mapping/review.py`
- Added imports: `and_`, `or_` from `sqlalchemy`; `Feed` from `..db.models`.
- Added a cross-feed conflict guard inside `approve_mapping()`, as a full pre-pass over `drafts`
  before the existing mutation loop (not interleaved with it, so a bulk-approve call can never
  partially apply if one of several tables conflicts). For each draft, queries whether any other
  feed (`source_definition_id != source_definition_id`, excluding discarded feeds) or a
  project-scoped (`NULL`-`source_definition_id`) `MappingSnapshot` is already `approved` for the
  same `destination_object_name`. If so, raises `AuthApiError("mapping_table_conflict", ..., 409,
  detail)` with `detail` containing `destination_object_name`, `conflicting_source_definition_id`,
  and `conflicting_mapping_snapshot_id`.
- Reused the exact `outerjoin(Feed, ...)`/`Feed.status != "discarded"` pattern already established
  in `proposal.py`, rather than a second implementation of "approved anywhere in the project."
- `LookupValueMap`/`LookupSnapshot` approval logic (lines ~251-268) untouched — no
  `source_definition_id` on those models, no analogous conflict possible.

### `docs/domain/source-model.md`
- **Updated**. Added a note after the feed-scoped unique-index description (line ~423) explaining
  the new runtime invariant: at most one feed (or a project-scoped snapshot) may hold an approved
  `MappingSnapshot` for a given destination table at a time, and why (duplicate codegen procs
  otherwise). `timestamp` already current (same-day edit).

### `engine/tests/test_mapping_review_api.py`
New tests, all covering scenarios from the plan:
- `test_approve_succeeds_for_feed_without_conflict` — happy path unaffected.
- `test_approve_rejected_when_another_feed_has_approved` — 409, `detail` dict asserted
  (`conflicting_source_definition_id`, `destination_object_name`), no mutation of the rejected
  draft.
- `test_approve_blocked_by_null_scoped_approved_snapshot` — project-scoped row also blocks.
- `test_discarded_feed_approved_snapshot_does_not_block` — discarded feeds excluded.
- `test_bulk_approve_two_distinct_tables_no_conflict` — regression guard for the existing
  multi-table bulk-approve happy path.
- `test_bulk_approve_one_conflicting_table_rejects_no_partial_mutation` — the critical no-partial-
  mutation case: one conflicting + one clean table in the same bulk call, whole call rejects,
  neither snapshot mutated.

## Deviations from Plan

None — implementation matches the plan's File Changes section exactly, including the `detail`
dict fields and the pre-pass-before-mutation placement.

## Bugs found and fixed during implementation (not part of the original plan)

Five of the six new tests initially failed due to test-authoring bugs, not guard-logic bugs:
- Objects created but never `db.add()`-ed before `db.commit()` (SQLAlchemy doesn't track objects
  that were never added to the session) — the guard's query correctly found nothing because the
  row was genuinely never persisted.
- `DetachedInstanceError` from accessing ORM object attributes after the session that created them
  had closed — fixed by capturing plain string IDs (e.g. `snap_a_id`) before the `with
  SessionLocal()` block closes, instead of holding onto detached ORM objects.

Verified these fixes are correct, not a workaround masking a real bug: re-ran the full suite after
the fixes and confirmed the guard's actual behavior (409 on conflict, 200 otherwise, no partial
mutation) independently.

## Domain Updates Required

- `docs/domain/source-model.md` — **Updated** (see above).

## Tests

```
.venv/bin/python -m pytest engine/tests/test_mapping_review_api.py -q
31 passed, 2 warnings

.venv/bin/python -m pytest engine/tests -q
452 passed, 2 warnings

.venv/bin/python scripts/validate_okf.py
✓ All files OKF-compliant. No issues found (12/12 domain pages).
```

Independently verified — ran both suites and the OKF validator myself before confirming
completion, not just accepting the reported test count.
