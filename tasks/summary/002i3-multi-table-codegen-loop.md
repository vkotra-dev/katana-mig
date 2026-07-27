Task: tasks/completed/002i3-multi-table-codegen-loop.md
Plan: plans/2026-07-24-002i3-multi-table-codegen-loop.md
Commits: ec74516 (implementation), 3ae6b4e-era docs follow-up captured separately in 002i7's close-out

## Changes Made

### `engine/src/migrations_engine/codegen/service.py`
- `generate_codegen_artifact()` rewritten to loop over every entry in
  `source_definition.destination_object_references`, instead of only ever resolving
  `references[0]` via the now-removed `_primary_destination_object_name()`.
- Each iteration: fetches that table's approved `MappingSnapshot`, skips (with a logged warning,
  not a hard failure) if none exists or `destination_columns` is missing, runs its own AI call,
  and creates its own `CodeGenerationArtifact`.
- Return type changed from `CodegenTriggerResponse` to `list[CodegenTriggerResponse]`.

### `engine/src/migrations_engine/routes/codegen.py`
- `response_model` and return type changed to `list[CodegenTriggerResponse]`.

### `engine/tests/test_codegen_service_api.py`
- 3 new tests: multi-table (2 approved tables → 2 artifacts), partial mappings (1 of 2 approved →
  1 artifact, 1 silently skipped), full multi-table coverage.

### `docs/domain/source-model.md`
- "Run reference" section updated to state a single trigger now produces one artifact per
  destination table, not one artifact total; documents the per-table skip behavior and the
  `list[CodegenTriggerResponse]` response shape. Timestamp bumped to 2026-07-27. This update was
  missed in the original implementation round and only added during governance close-out —
  see Deviations below.

## Deviations from Plan

**Undisclosed regression, caught in review, fixed as a separate task (002i7):** the refactor
deleted the two `FeedComment` queries (feed-level + slice-level discussion comments) that used to
run once per call, replacing them with hardcoded `comments=[]`/`slice_comments=[]` inside the loop.
This silently dropped all team-discussion context from every codegen AI call — not scoped to the
new multi-table behavior, it affected single-table feeds too. This was not mentioned in the
original implementation report; it was found during independent review of the diff, not
self-reported. Filed and fixed as task 002i7 (commit `c0042be`), which restores the two queries
above the loop and adds a regression test (`test_codegen_includes_discussion_comments`) asserting
discussion content actually reaches the AI prompt.

**Domain doc update was skipped in the original round.** The task's own "Domain Updates Required"
called for a `source-model.md` update; the original implementation commit (`ec74516`) did not
include it. Added during this governance close-out, not part of the original commit.

## Tests

`.venv/bin/python -m pytest engine/tests -q` — 419 passed, 0 failed (full suite, run after 002i7's
fix was also in place; 002i3 alone landed at 418/418 with 0 regressions before 002i7 added its one
additional test).

## Verification

`scripts/validate_okf.py` — all 12 domain docs pass, 0 warnings, after the source-model.md fix.
