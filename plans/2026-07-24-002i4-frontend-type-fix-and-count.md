# Plan 002i4 — Frontend Type/Mapper Fix + Count Display

Task: [002i4](../tasks/completed/002i4-frontend-type-fix-and-count.md)
Domain: (none)

## Current State

`triggerCodegen()` returns `Promise<CodegenTriggerRecord>` (singular). `mapTriggerResponse()` built for one object. Page component discards return value.

## Objective

Change return type to list, replace mapper, display count of generated procedures.

## Out of Scope

- Any backend changes
- Prompt changes
- Multi-table artifact generation (task 002i3 handles that)

## Blast Radius

- Low — frontend-only, no API changes (just type changes)

## File Changes

| File | Change |
|------|--------|
| `web/lib/codegen-api.ts` | Return type to list, array mapper |
| `web/app/projects/[id]/codegen/page.tsx` | Display count of generated procedures |

## Tests

- Unit: `mapTriggerResponseList()` returns array
- Integration: trigger codegen, verify UI shows count

## Verification

1. `cd web && npx tsc --noEmit` — zero errors
2. `cd web && npx vitest run` — zero failures

## Pitfalls

- `mapTriggerResponse()` is fully replaced, not augmented
- Page must capture the response to display count
- Edge case: 0 tables (all skipped)

## Commit

"feat(web): update codegen API return type to list, display generation count"
