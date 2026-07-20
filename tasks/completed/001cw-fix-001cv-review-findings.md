# Task: 001cw — Fix 001cv Code Review Findings

## Status
Ready

## Background

A high-effort code review of commit `7bb1b83` (001cv — Revise Transformation Instructions Template) surfaced 10 findings. Two are bugs with confirmed behavioral impact; two are latent defects that will surface when callers are added; the rest are cleanup and maintenance concerns.

## Goal

Fix the 4 actionable findings from the 001cv review:

1. **Stale tests** — `page.test.tsx` lines 335–341 assert prose from the old implementation; all five of those assertions will fail against the rewritten function.
2. **`destEntryId` quoting** — When `destRow` is null and `destEntryId` is a non-null string (e.g. `"entry-1"`), old code emitted the bare identifier; new code emits `"entry-1"` (JSON-quoted). Decide and enforce the intended encoding.
3. **`stagingSchema` guard missing** — `generateTransformationInstructionsTemplate` now uses `stagingSchema` at line 203 but has no internal fallback. Every other consumer (`generateCodingStandardsTemplate`) guards internally. Add `const schema = stagingSchema || "staging"` inside the function.
4. **`snapshot` variable shadow** — The `Array.find` callback on line 211 is also named `snapshot`, shadowing the outer `const snapshot`. Rename the callback parameter to `snap` to eliminate the shadow and future-edit trap.

## Out of Scope

- Finding 3 (null sentinel `NULL` → `null`): intentional per spec; acceptable for an LLM prompt.
- Findings 7–10 (fiber status duplication, fallback chain intent, intermediate variable, inconsistent fallback): deferred — pre-existing or low-priority cleanup.

## Files Changed

- `web/app/projects/[id]/codegen/page.tsx` — lines 192, 203, 210–211
- `web/app/projects/[id]/codegen/page.test.tsx` — lines 335–342

## Plan

[2026-07-20-001cw-fix-001cv-review-findings.md](../../plans/2026-07-20-001cw-fix-001cv-review-findings.md)

## Verification

1. `page.test.tsx` test "generates feed-specific transformation instructions" passes.
2. `stagingSchema` internal guard exists in `generateTransformationInstructionsTemplate`.
3. `snapshots.find` callback parameter is not named `snapshot`.
4. `destEntryId` encoding decision is explicit and tested.
5. TypeScript compilation passes with no new errors.
