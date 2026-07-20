# Plan: 2026-07-20-001cu-generate-transformation-instructions

[Task](../tasks/001cu-generate-transformation-instructions.md) | [Domain](../docs/domain/governance.md)

## Current State
The `generateTransformationInstructionsTemplate` function in `web/app/projects/[id]/codegen/page.tsx` builds a template for "Feed-specific transformation instructions". However, it currently generates implementation-level instructions like "Create a lookup table", "Chunked / Batch Upsert", and "Insert always has to be row by row only and follow the logging strategy". These are SQL execution details that must be enforced by the AI's system prompt (the global coding standards), not the user prompt.

## Objective
Update `generateTransformationInstructionsTemplate` so it *only* outputs mapping definitions:
1. Approved lookup data and seed values.
2. Approved destination mappings (source field -> destination column bindings).
3. Source characteristics (estimated row count).

It must completely drop all references to implementation details and strategy.

## Out of Scope
- Modifications to `generateCodingStandardsTemplate`.
- Modifications to any system-prompt template literal or variable.
- Changes to SQL standards, transaction rules, run_ref rules, or lookup-resolution rules.

## Blast Radius
- The prompt sent to the LLM during "Generate SQL" will be leaner and will lack the previously generated SQL directives. Since the system prompt already handles SQL standards, this removes redundancy and confusion.
- The UI textbox displaying the "Feed-specific transformation instructions" will show the leaner format.

## File Changes
- `web/app/projects/[id]/codegen/page.tsx`:
  - Replace the entire body of `generateTransformationInstructionsTemplate` (lines ~145-210).
  - Ensure the `strategy` variable is removed entirely.
  - Implement the exact patch provided by the user.
  - Make no other edits.

## Tests
- TypeScript compilation and type-checking (via `npx tsc` or Next.js build).

## Verification
- Show the git diff for `web/app/projects/[id]/codegen/page.tsx`.
- Confirm `strategy` variable is absent.
- Confirm `generateCodingStandardsTemplate` has no diff.
- Run `npm run typecheck` (or similar) on `web/` to confirm the code still compiles properly.

## Pitfalls
- Accidentally changing quotes, spacing, or stringification logic that could break JSON structure in the prompt.
- Editing code outside the `generateTransformationInstructionsTemplate` function.
- Changing `destRow` stringification behavior (it must be `JSON.stringify(mapping.destRow)`).

## Commit
- feat: Restrict codegen instructions template to mapping data only (001cu)
