# Plan: 001ei — Fix mypy union-attr Errors in approve/reject/unapprove_mapping

## Task and Domain links

- Task: `tasks/001ei-fix-mapping-snapshot-optional-typing.md`
- Domain: none — internal type-correctness fix, no behavior change

## Current State

- `mapping/review.py` has 36 `mypy --strict` errors, confirmed (via direct run, compared against
  the pre-refactor baseline to rule out anything introduced by the `001ee`-`001eg` module split)
  to be entirely in `approve_mapping`, `reject_mapping`, `unapprove_mapping`.
- All three share: `if destination_object_name: drafts = [latest_snapshot(...)]; drafts = [s for
  s in drafts if s is not None]` vs. `else: drafts = db.scalars(select(...)...).all()`. mypy
  infers the variable's type from the first branch (`list[MappingSnapshot | None]`) and never
  narrows it past the filter, so every later `snapshot.<attr>` access in the shared post-branch
  code (looping over `drafts`, building `MappingReviewResponse`, etc.) is flagged.
- `unapprove_mapping`'s single-table branch additionally filters `s.status == "approved"` —
  confirmed by reading the code directly — which the replacement query must preserve in its
  `WHERE` clause, not drop.
- `latest_snapshot()` (`review_repository.py:43-58`) has 2 other call sites (`get_mapping`,
  `patch_mapping`) that correctly use it as a scalar lookup with proper `None` handling —
  confirmed via grep; not touched by this task.

## Objective

Replace the single-table branch in all three functions with a `.scalars(...).all()` query shaped
like the bulk branch's, so both branches of each function produce `Sequence[MappingSnapshot]` —
never `None` — eliminating the type mismatch at its source instead of patching it with an
annotation.

## Out of Scope

- `latest_snapshot()` itself or its other call sites.
- Any behavior/logic change — same snapshots selected, same order, same everything except the
  type mypy sees.

## Blast Radius

- `engine/src/migrations_engine/mapping/review.py` (edited — 3 functions, ~10 lines changed
  total)
- No other file — this is entirely internal to `review.py`.

## File Changes

**`engine/src/migrations_engine/mapping/review.py`**

`approve_mapping` (lines 174-177) and `reject_mapping` (lines 289-291): replace
```python
drafts = [latest_snapshot(db, project_id=project_id, source_definition_id=source_definition_id, destination_object_name=destination_object_name)]
drafts = [s for s in drafts if s is not None]
```
with
```python
drafts = db.scalars(
    select(MappingSnapshot)
    .where(
        MappingSnapshot.project_id == project_id,
        MappingSnapshot.source_definition_id == source_definition_id,
        MappingSnapshot.destination_object_name == destination_object_name,
    )
    .order_by(MappingSnapshot.created_at.desc(), MappingSnapshot.mapping_snapshot_id.desc())
    .limit(1)
).all()
```

`unapprove_mapping` (lines 352-354): same shape, plus `MappingSnapshot.status == "approved"` in
the `WHERE` clause (preserving the extra filter its single-table branch currently applies via
post-filter).

After this, `latest_snapshot` may become unused in `review.py`'s imports if these were its only
call sites in this file — confirm and drop the import if so (check `get_mapping`/`patch_mapping`
don't also need it imported here; they call it via `review_repository.latest_snapshot` already
per the `001ef`/`001eg` split, so this import may already be scoped correctly — verify before
assuming either way).

## Tests

- No new test behavior — this is a pure type-shape fix. Full `test_mapping_review_api.py` run
  should pass with zero changes to any assertion.
- Specifically exercise: single-table approve/reject/unapprove (the branch being changed),
  bulk approve/reject/unapprove (the unchanged branch, as a regression check), and
  `unapprove_mapping`'s single-table path specifically against a snapshot that is NOT currently
  `"approved"` (e.g. still `"draft"`) — confirm it's correctly excluded (returns "not found"
  rather than incorrectly un-approving a draft), verifying the `status == "approved"` condition
  survived the move into the `WHERE` clause correctly.

## Verification

- `mypy --strict engine/src/migrations_engine/mapping/review.py` — 0 errors (down from 36).
- `ruff check` clean (unchanged from current state — this fix shouldn't introduce any).
- Full test suite green, no assertions changed.
- Manually exercise approve/reject/unapprove through the real API, both single-table and bulk,
  to confirm no behavior regression.

## Pitfalls

- Don't lose `unapprove_mapping`'s `status == "approved"` filter when rewriting its single-table
  branch — it's easy to copy-paste `approve_mapping`'s version verbatim and miss that one
  function has an extra condition the other two don't.
- `.limit(1)` combined with the `order_by` must produce the exact same "latest" row
  `latest_snapshot()` would have returned — same ordering columns, same direction — or this
  silently changes which snapshot gets approved/rejected/unapproved when duplicates exist.
- Confirm `latest_snapshot`'s import in `review.py` (if any) is still needed by
  `get_mapping`/`patch_mapping`'s own use of it before removing it — don't break an unrelated
  function's import while cleaning up.

## Commit

Own commit. No dependency on any other in-flight task.
