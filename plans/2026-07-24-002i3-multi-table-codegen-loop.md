# Plan 002i3 — Multi-Table Codegen Artifact Generation

Task: [002i3](../tasks/002i3-multi-table-codegen-loop.md)
Domain: `source-model.md`

## Current State

`_primary_destination_object_name()` returns `references[0]` only. `generate_codegen_artifact()` called once from the route handler, processes only one table.

## Objective

Loop over ALL `destination_object_references`, creating one artifact (and one AI call) per table. Catch `AuthApiError` per-table, skip tables without approved mappings. Return `list[CodegenTriggerResponse]`.

## Out of Scope

- Prompt changes (handled by other tasks)
- Frontend changes (handled by task 002i4)

## Blast Radius

- Medium — core function modified, route handler return type changed
- All existing single-table feeds continue to work (one artifact returned, same as before)
- New feeds with multiple tables get multiple artifacts

## File Changes

| File | Change |
|------|--------|
| `engine/src/migrations_engine/codegen/service.py` | Multi-table loop in `generate_codegen_artifact()` |
| `engine/src/migrations_engine/routes/codegen.py` | Return type changes to list |

## Tests

- Feed with 2 approved mappings → 2 artifacts created
- Feed with 1 approved, 1 not → 1 artifact created, 1 skipped (logged warning)
- Feed with 3 approved → 3 artifacts

## Verification

1. `cd engine && .venv/bin/python -m pytest -xvs` — zero new failures
2. `cd web && npx tsc --noEmit` — zero errors

## Pitfalls

- Return type changes from single to list
- `AuthApiError` must be caught per-table, not around the whole loop
- `_select_latest_approved_mapping_snapshot()` raises — this is the catch point

## Commit

"feat(codegen): iterate over all destination references, one artifact per table"
