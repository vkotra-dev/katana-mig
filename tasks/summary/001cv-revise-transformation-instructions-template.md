# Summary: 001cv — Revise Transformation Instructions Template

## Objective
Restrict `generateTransformationInstructionsTemplate` to emit only feed-specific mapping data and remove all SQL execution strategy from the user prompt.

## Changes Made
- Replaced the body of `generateTransformationInstructionsTemplate` in `web/app/projects/[id]/codegen/page.tsx`.
- Removed the `strategy` local variable entirely.
- Removed all forbidden phrases: "Create a lookup table", "Chunked / Batch Upsert", "Insert always has to be row by row", "Execution Strategy", and related SQL directives.
- Function now outputs only: approved lookup names and source/destination values, source table identity, destination object field bindings with lookup annotations, and estimated source row count.
- `generateCodingStandardsTemplate` and all system-prompt builders left untouched.
- Serialization preserved: `JSON.stringify(mapping.sourceValue)`, `JSON.stringify(mapping.destRow)`, `JSON.stringify(mapping.destEntryId ?? null)`.

## Results
- User prompt is now lean and contains only migration-specific data.
- SQL execution strategy remains exclusively in the system prompt (global coding standards), eliminating redundancy and prompt conflict.
- TypeScript compilation passes.
