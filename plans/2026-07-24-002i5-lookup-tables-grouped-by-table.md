# Plan 002i5 — Lookup Tables Grouped by Destination Table + Full Value Map

Task: [002i5](../tasks/002i5-lookup-tables-grouped-by-table.md)
Domain: `source-model.md`

## Current State

`_build_lookup_tables()` returns flat list with 5 sample mappings. AI cannot generate reliable JOIN queries.

## Objective

Extend `_build_lookup_tables()` to group lookups by destination table, pass full `value_map` (no cap).

## Out of Scope

- Multi-table codegen loop (task 002i3)
- Cross-proc FK resolution (task 002i6)
- Feed instructions template (task 002i2)

## Blast Radius

- Medium — modifies `_build_lookup_tables()` and `user_prompt.txt.j2`
- Depends on task 002i1 (lookup snapshot bug fix)

## File Changes

| File | Change |
|------|--------|
| `engine/src/migrations_engine/codegen/service.py` | Extend `_build_lookup_tables()` |
| `engine/src/migrations_engine/codegen/templates/user_prompt.txt.j2` | List lookups grouped by table with full mappings |

## Tests

- 2 lookups with 10+ mappings each → prompt contains all mappings
- Cross-table lookup appears under both tables

## Verification

1. `cd engine && .venv/bin/python -m pytest -xvs` — zero new failures
2. `cd web && npx tsc --noEmit` — zero errors

## Pitfalls

- `value_map` can be large — monitor prompt size
- Grouping logic must match field_bindings structure

## Commit

"feat(codegen): group lookup tables by destination table, pass full value_map"
