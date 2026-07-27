---
id: 002i5
title: Lookup tables grouped by destination table with full value_map
status: completed
created: 2026-07-24
priority: high
depends-on: [002i1]
domain: engine
---

# Task 002i5 — Lookup Tables Grouped by Destination Table + Full Value Map

## Context

`_build_lookup_tables()` (service.py:452-496) returns a flat list of all lookup tables, passing only 5 sample mappings per lookup. The AI cannot reliably write JOIN queries or seed data from samples alone.

## Domain Updates Required

- `docs/domain/source-model.md` — Update "Code generation artifact" section to note that lookups are now passed with full value_map

## Current State

- `_build_lookup_tables()` returns flat list with 5 sample mappings
- AI sees only 5 source→dest pairs, cannot generate reliable JOIN queries
- No grouping by destination table

## Objective

1. Extend `_build_lookup_tables()` to group lookups by `destination_object_name`
2. Pass the **full** `value_map` (all key-value pairs, no cap) per lookup
3. Update `user_prompt.txt.j2` to list lookups grouped by table
4. Update `GeneratedSQL` model if needed (no change needed — `stored_procedures: list[str]` already supports multiple entries)

## Files Changed

| File | Change |
|------|--------|
| `engine/src/migrations_engine/codegen/service.py` | Extend `_build_lookup_tables()` to group by table, pass full value_map |
| `engine/src/migrations_engine/codegen/templates/user_prompt.txt.j2` | List lookups grouped by table with full mappings |

## Tests

- Seed feed with 2 lookups, each with 10+ mappings → verify prompt contains all 20 mappings
- Feed with lookup used by multiple tables → lookup appears under both tables

## Verification

1. `cd engine && .venv/bin/python -m pytest -xvs` — zero new failures
2. `cd web && npx tsc --noEmit` — zero errors

## Pitfalls

- `_build_lookup_tables()` already exists — extend, don't replace
- `value_map` can be large (50+ entries) — ensure prompt doesn't exceed token limits
- Grouping requires understanding which lookups belong to which table (from field_bindings)

## Commit

"feat(codegen): group lookup tables by destination table, pass full value_map"
