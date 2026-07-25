Task: tasks/completed/001go-lookup-review-grid-wiring.md
Plan: plans/2026-07-24-001go-lookup-review-grid-wiring.md
Commits: 4fe43bc

## Changes Made

### `web/lib/lookup-api.ts`
- `patchLookupValueMap`: fixed `removeSourceValue`'s outer request-body key — was `body.removeSourceValue` (camelCase, silently ignored by the backend), now `body.remove_source_value` (snake_case, matching every other field in the function).

### `web/lib/lookup-api.test.ts`
- Added unit tests asserting the snake_case request-body encoding for `addSourceValue`, `removeSourceValue`, and `moveSourceValue`.

## Deviations from Plan

- This commit fixed only the *outer* key bug. The *inner* action-object keys (`destId`/`sourceValue` staying camelCase inside the now-snake_cased outer key) were a second, deeper instance of the same class of bug, not caught by this task — that was found and fixed separately as task 001gq.

## Tests

`cd web && npm test -- --run` — passing at time of commit (re-verified as part of the full suite in later session work; no regressions attributable to this change).
