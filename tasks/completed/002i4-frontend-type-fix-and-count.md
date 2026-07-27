---
id: 002i4
title: Frontend type/mapper fix + count display for multi-table codegen
status: completed
completed: 2026-07-24
created: 2026-07-24
priority: medium
depends-on: [002i3]
domain: web
---

# Task 002i4 — Frontend Type/Mapper Fix + Count Display

## Context

The codegen API return type changes from single response to list (task 002i3). The frontend TypeScript types must be updated to match, and the UI should display the count of generated procedures.

## Domain Updates Required

- None — frontend-only change

## Current State

- `web/lib/codegen-api.ts:204-213` defines `triggerCodegen()` returning `Promise<CodegenTriggerRecord>` (singular)
- `mapTriggerResponse()` is a mapper built for one object
- `codegen/page.tsx:332` discards the return value, calls `refreshArtifacts()` to re-fetch
- No user-visible count of generated procedures

## Objective

1. Change `triggerCodegen()` return type to `Promise<CodegenTriggerRecord[]>`
2. Replace `mapTriggerResponse()` with `mapTriggerResponseList()` — there are no other callers
3. Display count: "Generated N procedure(s) — X table(s) had no approved mapping"
4. Use the response count to show a summary badge or text after codegen completes

## Files Changed

| File | Change |
|------|--------|
| `web/lib/codegen-api.ts` | Return type changes to list, array mapper |
| `web/app/projects/[id]/codegen/page.tsx` | Display count of generated procedures |

## Tests

- Unit: `mapTriggerResponseList()` returns array of mapped records
- Integration: trigger codegen with multi-table feed → UI shows count

## Verification

1. `cd web && npx tsc --noEmit` — zero errors
2. `cd web && npx vitest run` — zero failures

## Pitfalls

- `mapTriggerResponse()` is completely replaced, not augmented
- The page component currently discards the return value — this must capture the response to display the count
- The success message must handle edge case: 0 tables (all skipped)

## Commit

"feat(web): update codegen API return type to list, display generation count"
