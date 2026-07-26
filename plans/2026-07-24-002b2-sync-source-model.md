---
id: 002b2
title: Sync docs/domain/source-model.md against actual codebase
status: ready
created: 2026-07-24
domain: docs/domain/source-model.md
task: 002b2
---

# Plan: Sync docs/domain/source-model.md

## Task and Domain Links

- **Task:** [002b2](../tasks/002b2-sync-domain-docs-source-model.md)
- **Domain Doc:** `docs/domain/source-model.md`

## Current State

`docs/domain/source-model.md` was last updated 2026-07-25. It's the largest and most frequently changed doc, covering feeds, fibers, mappings, lookups, and related artifacts.

## Objective

Read `docs/domain/source-model.md` section by section, cross-reference against `db/models.py` for ALL source-related models (Feed, FeedSlice, FeedSliceRow, FeedComment, SourceSchemaArtifact, SourceValueSummary, MappingSnapshot, LookupSnapshot, LookupValueMap, ProjectFiber, MappingArtifact, DryRunArtifact, ProjectSchemaAnalysis, CodeGenerationArtifact, AICallLog, MappingBindingSignOff, LookupSignOff, MappingBindingSignOff). Also verify against `routes/feeds.py`, `routes/fibers.py`, `routes/mapping.py`, `routes/lookup.py`, `routes/sign_offs.py`.

## Out of Scope

- Any other domain doc files
- Backend implementation changes

## Blast Radius

One file: `docs/domain/source-model.md`

## File Changes

- `docs/domain/source-model.md` — patch in-place

## Verification

1. For each model, run `grep -A N "class ModelName" engine/src/migrations_engine/db/models.py` and compare every field
2. Specifically verify new fields:
   - `SourceSchemaArtifact.destination_ddl` (Text)
   - `LookupValueMap.destination_mappings` (JSON list)
   - `LookupValueMap.unmapped_source_values` (JSON list)
   - `ProjectFiber.field_bindings` (JSON list, nullable)
   - `Feed.mapping_hints` (Text)
   - `Feed.transformation_instructions` (Text)
3. Verify fiber status enums match actual values
4. Verify sign-off models match actual sign-off workflow
5. Verify all API endpoints match actual routes

## Pitfalls

- This is the largest doc (760 lines) and most frequently changed — easy to miss a single field drift
- `ProjectFiber.field_bindings` is a new nullable JSON field that may not be in the doc at all
- `LookupValueMap.destination_mappings` and `unmapped_source_values` were added after the last sync
- Fiber state machine states may not match the simplified statuses actually used in code
- Backward-compatible aliases (`SourceDefinition = Feed`, etc.) are not domain-level concepts and should not be in the doc

## Tests

N/A — documentation-only change, no test suite applies.

## Commit

```
docs(domain): sync source-model.md against codebase

Cross-reference docs/domain/source-model.md against ORM models (Feed,
FeedSlice, FeedComment, SourceSchemaArtifact, SourceValueSummary,
MappingSnapshot, LookupSnapshot, LookupValueMap, ProjectFiber, and all
artifact/sign-off models). Fix field descriptions, fiber state machines,
lookup value mapping structure, sign-off workflow, and API endpoints.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
```
