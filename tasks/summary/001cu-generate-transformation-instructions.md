# Summary: 001cu-generate-transformation-instructions

## Objective
Restrict `generateTransformationInstructionsTemplate` to generate only feed-specific user-prompt data and remove SQL execution strategy rules.

## Changes Made
- Applied the provided patch to `web/app/projects/[id]/codegen/page.tsx`.
- Replaced the local logic for `lookupSection` and `mappingSection` to properly format and stringify field bindings and lookup values.
- Removed the `strategy` variable entirely and dropped all execution-strategy implementation instructions.
- Maintained the exact function signature and did not touch `generateCodingStandardsTemplate` or any global SQL generation rules.

## Results
- The function now strictly returns the approved mapping structure, leaving the SQL strategy enforcement to the system prompt.
- TypeScript compilation passed (existing unrelated test issues ignored).
