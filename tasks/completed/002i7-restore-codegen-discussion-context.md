---
id: 002i7
title: Restore feed/slice discussion comments dropped by the multi-table codegen loop
status: completed
created: 2026-07-24
priority: high
depends-on: [002i3]
domain: engine
---

# Task 002i7 — Restore Codegen Discussion Context

## Context

Task 002i3's multi-table refactor of `generate_codegen_artifact()` (commit `ec74516`) deleted the
two `FeedComment` queries that fetched feed-level and slice-level discussion comments, and replaced
them with hardcoded `comments=[]` / `slice_comments=[]` passed into `_build_user_prompt()`. This was
not an intentional design change — it was an undisclosed regression caught during review of 002i3,
not mentioned in that task's summary.

The rendering machinery (`_format_discussion()`, `_format_slice_discussion()`, and the
`FeedComment` import/type hints in `_build_user_prompt()`) is all still present and unchanged — only
the data feeding it was dropped. This means every codegen run, single-table or multi-table, now
silently loses all team-discussion context ("Feed discussion (context for mapping intent and
business rules)") that the AI used to see when generating SQL.

## Domain Updates Required

- None — this restores existing, already-documented behavior. No model/API/role/workflow/UI
  change; nothing in `docs/domain/` describes discussion-comment inclusion as new or changed.

## Current State

- `generate_codegen_artifact()` (`engine/src/migrations_engine/codegen/service.py`) loops over
  `destination_object_references` and calls `_build_user_prompt(..., comments=[], slice_comments=[])`
  unconditionally inside the loop.
- `FeedComment` is still imported and `_format_discussion`/`_format_slice_discussion` still exist
  and are still called by `_build_user_prompt()` — the plumbing works, it's just fed empty lists.
- Before task 002i3, these were two `db.execute(select(FeedComment, User.role)...)` queries run once
  per call, before the (single-table) generation logic ran.

## Objective

1. Restore the two `FeedComment` queries (feed-level: `FeedComment.feed_id == source_definition_id,
   FeedComment.source_slice_id.is_(None)`; slice-level: `FeedComment.source_slice_id ==
   source_slice.source_slice_id`), run **once, before the per-table loop** — comments are scoped to
   the feed/slice, not to any individual destination table, so they must not be re-fetched (or
   worse, left empty) per iteration.
2. Pass the restored `comments`/`slice_comments` values into every loop iteration's
   `_build_user_prompt()` call, replacing the hardcoded `[]`/`[]`.
3. Add a regression test asserting the AI-facing user prompt actually contains discussion content
   when `FeedComment` rows exist for the feed/slice.

## Out of Scope

- No changes to `_format_discussion()` / `_format_slice_discussion()` formatting logic itself.
- No changes to comment creation/API endpoints.
- Not re-litigating any other part of 002i3's multi-table loop design.

## Files Changed

| File | Change |
|------|--------|
| `engine/src/migrations_engine/codegen/service.py` | Move the two `FeedComment` queries back above the per-table loop in `generate_codegen_artifact()`; reuse across iterations |
| `engine/tests/test_codegen_service_api.py` | Add regression test asserting discussion comments appear in the rendered prompt |

## Tests

- Seed a feed with one `FeedComment` (feed-level, `source_slice_id=None`) and one slice-level
  comment; trigger codegen; assert the `FakeAdapter`'s captured `user` prompt contains both comment
  bodies (matching the existing `_format_discussion`/`_format_slice_discussion` output format).
- Existing 418 tests continue to pass with no regressions.

## Verification

```bash
.venv/bin/python -m pytest engine/tests/test_codegen_service_api.py -v
.venv/bin/python -m pytest engine/tests -q
```

Expected: new test passes, full suite shows 418 + 1 new, 0 failures.

## Pitfalls

- Comments must be fetched **once**, outside the loop — querying per destination table would be
  wasteful (same rows every time) and is not what the pre-002i3 code did.
- `source_slice` must be resolved before the slice-comment query, same ordering as before 002i3's
  refactor (the slice-comment query depends on `source_slice.source_slice_id`).
- Don't confuse this with `Feed`-level `mapping_hints`/`transformation_instructions` — those are
  separate fields, unaffected by this regression.

## Commit

```
fix(codegen): restore feed/slice discussion comments dropped by the multi-table loop

Task 002i3's refactor of generate_codegen_artifact() hardcoded comments=[] and
slice_comments=[] instead of preserving the original FeedComment queries, silently
removing all discussion context from every codegen AI call. Restore the two queries,
run once before the per-table loop, reused across iterations. Add a regression test.
```
