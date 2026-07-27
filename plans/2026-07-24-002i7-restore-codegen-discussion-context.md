# Plan 002i7 — Restore Codegen Discussion Context

Task: [002i7](../tasks/002i7-restore-codegen-discussion-context.md)
Domain: (none — restores existing behavior, no domain doc change)

## Current State

`generate_codegen_artifact()` (`engine/src/migrations_engine/codegen/service.py`) was refactored by
task 002i3 (commit `ec74516`) to loop over `destination_object_references`. In doing so, the two
`FeedComment` queries that used to run once per call were deleted entirely; the loop's call to
`_build_user_prompt()` now hardcodes `comments=[]` and `slice_comments=[]` (verified at
`service.py:137-138` on the current `master`). `FeedComment` is still imported, and
`_format_discussion()`/`_format_slice_discussion()` are unchanged and still invoked by
`_build_user_prompt()` — only the data source was removed.

Before 002i3, the function contained (immediately after resolving `source_slice`, before building
the system/user prompts):

```python
comments = list(db.execute(
    select(FeedComment, User.role)
    .join(User, User.user_id == FeedComment.user_id)
    .where(FeedComment.feed_id == source_definition_id, FeedComment.source_slice_id.is_(None))
    .order_by(FeedComment.created_at.asc())
).all())

slice_comments = list(db.execute(
    select(FeedComment, User.role)
    .join(User, User.user_id == FeedComment.user_id)
    .where(FeedComment.source_slice_id == source_slice.source_slice_id)
    .order_by(FeedComment.created_at.asc())
).all())
```

## Objective

Restore these two queries, positioned once before the per-table loop (not inside it, since comments
are feed/slice-scoped, not table-scoped), and pass the results into every loop iteration's
`_build_user_prompt()` call.

## Out of Scope

- Do NOT change `_format_discussion()` / `_format_slice_discussion()` formatting.
- Do NOT change comment creation/API endpoints.
- Do NOT touch any other part of 002i3's loop/skip logic — this is a targeted restoration only.

## Blast Radius

| File | Action | What changes |
|------|--------|-------------|
| `engine/src/migrations_engine/codegen/service.py` | modify | Restore two `FeedComment` queries above the loop; pass real `comments`/`slice_comments` instead of `[]`/`[]` |
| `engine/tests/test_codegen_service_api.py` | modify | Add regression test for discussion-comment inclusion |

## File Changes

### `engine/src/migrations_engine/codegen/service.py`

In `generate_codegen_artifact()`, after the `source_slice = _select_latest_approved_source_slice(...)`
line and before the `results: list[CodegenTriggerResponse] = []` / `for destination_object_name in
destination_references:` loop, add back:

```python
comments = list(db.execute(
    select(FeedComment, User.role)
    .join(User, User.user_id == FeedComment.user_id)
    .where(FeedComment.feed_id == source_definition_id, FeedComment.source_slice_id.is_(None))
    .order_by(FeedComment.created_at.asc())
).all())

slice_comments = list(db.execute(
    select(FeedComment, User.role)
    .join(User, User.user_id == FeedComment.user_id)
    .where(FeedComment.source_slice_id == source_slice.source_slice_id)
    .order_by(FeedComment.created_at.asc())
).all())
```

Inside the loop, change:

```python
user_prompt = _build_user_prompt(
    ...
    comments=[],
    slice_comments=[],
)
```

to:

```python
user_prompt = _build_user_prompt(
    ...
    comments=comments,
    slice_comments=slice_comments,
)
```

### `engine/tests/test_codegen_service_api.py`

Add a test that seeds one feed-level `FeedComment` (`source_slice_id=None`) and one slice-level
`FeedComment` (`source_slice_id=<the approved slice's id>`), triggers codegen via the `FakeAdapter`
pattern already used elsewhere in this file, and asserts the captured `user` prompt string contains
both comment bodies.

## Tests

- New: `test_codegen_includes_discussion_comments` (or similarly named) — feed-level + slice-level
  comment, assert both appear in the AI-facing user prompt.
- Regression: full suite (418 existing tests) continues to pass unchanged.

## Verification

```bash
.venv/bin/python -m pytest engine/tests/test_codegen_service_api.py -v
.venv/bin/python -m pytest engine/tests -q
```

Expected: new test passes; full suite reports 419 passed (418 + 1), 0 failed.

## Pitfalls

- Fetch comments **once**, before the loop — not per destination table. They don't vary by table,
  and re-querying per iteration would be both wasteful and a deviation from pre-002i3 behavior.
- Preserve query ordering: `source_slice` must already be resolved before the slice-comment query
  runs, matching the original (pre-002i3) code's sequencing.
- Don't conflate this with `Feed.mapping_hints` / `Feed.transformation_instructions` — unrelated
  fields, not affected by this regression or this fix.

## Commit

```
fix(codegen): restore feed/slice discussion comments dropped by the multi-table loop

Task 002i3's refactor hardcoded comments=[] and slice_comments=[] instead of
preserving the original FeedComment queries. Restore them, run once before the
per-table loop, reused across iterations. Add a regression test.
```
