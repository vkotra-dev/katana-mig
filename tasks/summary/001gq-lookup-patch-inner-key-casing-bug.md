Task: tasks/completed/001gq-lookup-patch-inner-key-casing-bug.md
Plan: plans/2026-07-24-001gq-lookup-patch-inner-key-casing-bug.md
Commits: c98024a

## Changes Made

### `web/lib/lookup-api.ts`
- `patchLookupValueMap`: `add_source_value`, `remove_source_value`, and `move_source_value` request bodies now build explicit snake_case inner objects (`dest_id`, `source_value`, `old_dest_id`, `new_dest_id`) instead of forwarding the camelCase `input.addSourceValue`/etc. objects unchanged. The outer key was already snake_cased; the inner object was not, so the backend's `.get("dest_id", "")` always saw the default empty string and silently skipped the whole action.

### `web/lib/lookup-api.test.ts`
- The three existing tests (`sends addSourceValue as add_source_value...`, `sends removeSourceValue...`, `sends moveSourceValue...`) asserted the buggy camelCase-inner-key request body as correct. Updated all three to assert the corrected snake_case shape.

## Deviations from Plan

None — implementation matches the plan exactly (verified diff against plan during review).

## Tests

`cd web && npm test -- --run` — 337 passed, 0 failed (verified independently during review, not just taken from the implementer's report).
