# Task: 001cu — Generate Transformation Instructions

## Status
Completed

## Background

`generateTransformationInstructionsTemplate` in `web/app/projects/[id]/codegen/page.tsx` was emitting SQL execution strategy into the user prompt — chunking strategy, upsert rules, "Table Mappings & Stored Procedures" headings — content that belongs exclusively in the system prompt (global coding standards). This created redundancy and confusion in the AI prompt, with user-prompt directives potentially conflicting with or overriding system-prompt standards.

## Goal

Restrict `generateTransformationInstructionsTemplate` to only serialize feed-specific mapping data:
1. Approved lookup names and their source → destination value mappings.
2. Approved destination object field bindings (with lookup annotations).
3. Estimated source row count.

Drop the `strategy` variable and all SQL execution directives entirely.

## Design Decisions

- No changes to `generateCodingStandardsTemplate` — SQL standards stay in the system prompt.
- No changes to backend templates or system prompt `.j2` files.
- Function signature unchanged — callers unaffected.

## Changes

- `web/app/projects/[id]/codegen/page.tsx` — replaced `generateTransformationInstructionsTemplate` body; removed `strategy` variable

## Plan

[2026-07-20-001cu-generate-transformation-instructions.md](../plans/2026-07-20-001cu-generate-transformation-instructions.md)

## Summary

[summary/001cu-generate-transformation-instructions.md](../summary/001cu-generate-transformation-instructions.md)

## Verification

1. `strategy` variable absent from `generateTransformationInstructionsTemplate`.
2. Generated template contains only lookup data, field bindings, and row count — no SQL directives.
3. `generateCodingStandardsTemplate` has no diff.
4. TypeScript compilation passes.
