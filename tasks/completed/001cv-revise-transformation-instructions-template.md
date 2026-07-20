# Task: 001cv — Revise Transformation Instructions Template

## Status
Completed

## Background

`generateTransformationInstructionsTemplate` in `web/app/projects/[id]/codegen/page.tsx` currently emits SQL execution strategy into the user prompt — phrases like "Create a lookup table", "Chunked / Batch Upsert", "Insert always has to be row by row only and follow the logging strategy", and a `strategy` local variable. These are SQL implementation details owned by the system prompt (global coding standards). Duplicating them in the user prompt creates redundancy and risks the user prompt overriding or conflicting with system-level rules.

## Goal

Replace the body of `generateTransformationInstructionsTemplate` so the user prompt contains only feed-specific mapping data:

1. Approved lookup names, source values, and destination values.
2. Source table identity and destination object identities with approved field bindings and lookup annotations.
3. Estimated source row count.

Delete the `strategy` local variable entirely. Remove all SQL implementation instructions from this function.

## Scope

**Only** edit `generateTransformationInstructionsTemplate`. Do not touch:
- `generateCodingStandardsTemplate`
- Any system-prompt variable or template literal
- SQL coding standards, lookup-resolution rules, MERGE rules, logging rules, transaction rules, `run_ref` rules, JSON output fields, stored-procedure generation rules

## Serialization Requirements

- `JSON.stringify(mapping.sourceValue)` for source lookup values
- `JSON.stringify(mapping.destRow)` for structured destination lookup values
- `JSON.stringify(mapping.destEntryId ?? null)` when no `destRow` exists
- Do not manually add quotation marks, double-stringify, or alter approved values

## Forbidden Phrases (must not appear in function output)

```
Create a lookup table
code generation lookup mechanism
find the id values
Table Mappings & Stored Procedures
Look for a table in the source schema
upsert the mapped source fields
Execution Strategy
Insert always has to be row by row
Chunked / Batch Upsert
Bulk copy upsert
follow the logging strategy
```

## Files Changed

- `web/app/projects/[id]/codegen/page.tsx` — replace `generateTransformationInstructionsTemplate` body; remove `strategy` variable

## Plan

[2026-07-20-001cv-revise-transformation-instructions-template.md](../plans/2026-07-20-001cv-revise-transformation-instructions-template.md)

## Verification

1. Diff for `generateTransformationInstructionsTemplate` shows only the intended body replacement.
2. `strategy` variable is absent.
3. `generateCodingStandardsTemplate` has no diff.
4. No system-prompt variable or builder changed.
5. Generated transformation prompt contains only migration-specific data.
6. TypeScript type-check passes with no new errors.
