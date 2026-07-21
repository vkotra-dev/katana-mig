---
type: Task Plan
title: Fix mypy union-attr Errors in approve_mapping/reject_mapping/unapprove_mapping
status: ready
---

# Task: 001ei-fix-mapping-snapshot-optional-typing

## Context
`mapping/review.py`'s `approve_mapping`, `reject_mapping`, and `unapprove_mapping` all branch on
whether a single `destination_object_name` was passed (single-table path) or not (bulk path).
The single-table path calls the scalar-returning `latest_snapshot()` (`MappingSnapshot | None`),
wraps it in a one-item list, then filters out `None` — but mypy never narrows the list's element
type past that filter, so every later use of `snapshot.status`/`.destination_object_name`/etc. in
the shared post-branch code is flagged `Item "None" of "MappingSnapshot | None" has no attribute
"..."` (confirmed: 36 `mypy --strict` errors, all in these three functions, all this same root
cause). The bulk path never has this problem — it's already `Sequence[MappingSnapshot]` from a
direct `.scalars(...).all()` query, no `None` involved.

## Requirements

1. **Root-cause fix, not a type-annotation workaround**: rewrite the single-table branch in all
   three functions to run its own `.scalars(...).all()` query (filtered to one
   `destination_object_name`, ordered so the latest is first, `.limit(1)`) instead of calling
   `latest_snapshot()` and post-filtering. Both branches then produce the same type —
   `Sequence[MappingSnapshot]` — with no `None` anywhere, so the `[s for s in ... if s is not
   None]` filter step is removed entirely, not just type-annotated away.
2. **`approve_mapping`** (`review.py:174-177`) and **`reject_mapping`** (`review.py:289-291`):
   identical shape — replace with:
   ```python
   if destination_object_name:
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
   else:
       ...  # existing bulk query, unchanged
   ```
3. **`unapprove_mapping`** (`review.py:352-354`) has one real difference: its single-table branch
   also filters `s.status == "approved"` (the bulk branch already has `status == "approved"` in
   its `WHERE` clause). The replacement query must add that same condition to the `WHERE` clause
   directly, not drop it:
   ```python
   if destination_object_name:
       snapshots = db.scalars(
           select(MappingSnapshot)
           .where(
               MappingSnapshot.project_id == project_id,
               MappingSnapshot.source_definition_id == source_definition_id,
               MappingSnapshot.destination_object_name == destination_object_name,
               MappingSnapshot.status == "approved",
           )
           .order_by(MappingSnapshot.created_at.desc(), MappingSnapshot.mapping_snapshot_id.desc())
           .limit(1)
       ).all()
   else:
       ...  # existing bulk query, unchanged
   ```
4. **No behavior change** — same rows selected, same order, same downstream logic. This is a
   type-shape fix, not a logic change; every existing test must pass unchanged.
5. **`get_mapping`/`patch_mapping`** (`review.py:31,72`), which call `latest_snapshot()` directly
   as a scalar and correctly handle the `None` case already, are untouched — this task doesn't
   change `latest_snapshot()`'s signature or behavior, only removes its use from the three
   functions that were misusing it as a pseudo-list source.

## Out of Scope
- Any change to `latest_snapshot()` itself, or its other 2 call sites.
- Any of the other 36-minus-fixed mypy errors elsewhere in the codebase (there are none elsewhere
  — this task's fix accounts for all 36, confirmed via the earlier mypy run: every error was in
  one of these three functions).
- Any logic/behavior change beyond the type-shape restructure.

## Dependencies
None.
