Task: tasks/completed/002i4-frontend-type-fix-and-count.md
Plan: plans/2026-07-24-002i4-frontend-type-fix-and-count.md
Commits: dc469da (implementation + plan + task files)

## Changes Made

### `web/lib/codegen-api.ts`
- `triggerCodegen()` return type changed from `Promise<CodegenTriggerRecord>` to
  `Promise<CodegenTriggerRecord[]>`.
- `mapTriggerResponse()` replaced with `mapTriggerResponseList()` — no other callers exist.

### `web/app/projects/[id]/codegen/page.tsx`
- Captures the codegen response to display a count: "Generated N procedure(s) — X table(s) had
  no approved mapping".

## Deviations from Plan

None. Implementation matches the plan's File Changes section exactly.

## Domain Updates Required

- None — frontend-only change, no domain model/API/role/workflow/UI screen changes.

## Tests

TypeScript type-check passes (`npx tsc --noEmit`), no failures.

## Verification

`scripts/validate_okf.py` — all 12 domain docs pass, 0 warnings.
