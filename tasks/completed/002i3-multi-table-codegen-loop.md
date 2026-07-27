---
id: 002i3
title: Multi-table codegen artifact generation loop
status: completed
created: 2026-07-24
priority: high
depends-on: []
domain: engine
---

# Task 002i3 — Multi-Table Codegen Artifact Generation

## Context

`_primary_destination_object_name()` (service.py:369) returns `references[0]` only. `generate_codegen_artifact()` is called once from the route, processing only one table. If a feed maps to multiple destination tables, only the first gets a codegen artifact.

This is the **root cause** of the problem — it blocks everything else in this spec.

## Domain Updates Required

- `docs/domain/source-model.md` — Update "Code generation artifact" section: clarify that a feed can produce multiple artifacts (one per destination object)

## Current State

- `generate_codegen_artifact()` processes one table, creates one artifact
- Route handler `routes/codegen.py:33` calls it once, returns single response
- `build_delivery_bundle_text` already handles multiple artifacts — the plumbing exists, nothing was ever creating a second artifact

## Objective

1. Modify `generate_codegen_artifact()` to iterate over ALL `destination_object_references`, creating one artifact per table
2. Catch `AuthApiError` per-table — if a table has no approved MappingSnapshot, log a warning and skip it
3. Change return type to `list[CodegenTriggerResponse]`
4. Update route handler to return the list

## Files Changed

| File | Change |
|------|--------|
| `engine/src/migrations_engine/codegen/service.py` | Multi-table loop in `generate_codegen_artifact()` |
| `engine/src/migrations_engine/routes/codegen.py` | Return type changes to list, return all results |

## Tests

- Seed a feed with 2 destination tables, both with approved mappings → verify 2 artifacts created
- Seed a feed with 2 destination tables, 1 with approved mapping → verify 1 artifact created, 1 skipped (no error)
- Seed a feed with 3 destination tables, all approved → verify 3 artifacts

## Verification

1. `cd engine && .venv/bin/python -m pytest -xvs` — zero new failures
2. `cd web && npx tsc --noEmit` — zero errors

## Pitfalls

- The function currently returns `CodegenTriggerResponse` — return type must change to `list[CodegenTriggerResponse]`
- Each iteration creates its own artifact with a new ID
- The `AuthApiError` catch must be inside the loop, not around it
- `_select_latest_approved_mapping_snapshot()` raises on no match — this is the exception we catch per-table

## Commit

"feat(codegen): iterate over all destination references, one artifact per table"
