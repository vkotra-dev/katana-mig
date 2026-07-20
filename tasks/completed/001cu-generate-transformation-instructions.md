# Task: 001cu-generate-transformation-instructions

## Objective
Restrict `generateTransformationInstructionsTemplate` in `web/app/projects/[id]/codegen/page.tsx` to generate only feed-specific user-prompt data. It must no longer emit SQL execution strategy or mapping implementation rules (e.g. chunking strategy, "Table Mappings & Stored Procedures", "upsert the mapped source fields"), as those responsibilities belong strictly to the system prompt.

## Description
The current implementation of `generateTransformationInstructionsTemplate` leaks system-level SQL generation logic into the user prompt. We need to replace the local sections (`lookupSection`, `mappingSection`, `strategy`) to only provide:
- Approved lookup names
- Approved lookup source and destination values
- Source table identity
- Destination object identities
- Approved field bindings and their lookup annotations
- Estimated source row count

The function should serialize the mapping data correctly and return a focused template literal.

## Related Files
- `web/app/projects/[id]/codegen/page.tsx`

## Status
Ready
