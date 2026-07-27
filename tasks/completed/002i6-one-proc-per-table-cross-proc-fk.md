---
id: 002i6
title: One-proc-per-table prompt rules + Cross-proc FK resolution via mig_upsert_log
status: completed
completed: 2026-07-24
created: 2026-07-24
priority: high
depends-on: [002i3, 002i5]
domain: engine
---

# Task 002i6 — One-Proc-Per-Table + Cross-Proc FK Resolution

## Context

Two high-risk, interconnected changes:

1. **One-proc-per-table**: AI should generate one stored procedure per destination table instead of one proc handling all tables.
2. **Cross-proc FK resolution**: Detail procs need to resolve FKs to master tables populated by earlier procs, using `mig_upsert_log` as a shared lookup table.

These are combined into one task because both modify the system prompt template and the logging standards YAML.

## Domain Updates Required

- `docs/domain/source-model.md` — Update "Code generation artifact" section for one-proc-per-table
- `docs/domain/source-model.md` — Update "Migration run logging" section for `source_row_num` type change and cross-proc FK resolution

## Current State

- All table mappings generated in ONE stored procedure
- `mig_upsert_log` is per-proc, scoped to `run_ref`
- `source_row_num` is numeric (`BIGINT`/`NUMBER`/`NVARCHAR(255)`)

## Objective

### Part A: One-proc-per-table prompt rules
1. Update `system_prompt.txt.j2` with explicit rules: generate one PROCEDURE per `destination_object_name`
2. Each proc handles its own lookup DDL, seed data, and one MERGE/UPsert
3. Cross-table references: detail procs query `$dest` tables directly for master data

### Part B: Cross-proc FK resolution via mig_upsert_log
1. Update `_mig_upsert_log_ddl()` — change `source_row_num` from numeric to string type in all 4 engine variants
2. Add guarded `ALTER TABLE` for existing projects with numeric-typed log tables
3. Update `codegen_logging_standards.yaml` — specify `source_row_num` stores business key, detail procs query it for FK resolution
4. Add FK resolution hard-abort rule per engine (PostgreSQL/MSSQL/Oracle/MySQL)
5. Add composite key convention for multi-column natural keys
6. Add `dest_row_id` casting rule per engine

## Files Changed

| File | Change |
|------|--------|
| `engine/src/migrations_engine/codegen/templates/system_prompt.txt.j2` | One-proc-per-table rules + cross-proc FK rules |
| `engine/src/migrations_engine/codegen/service.py` | `_mig_upsert_log_ddl()` column type change across all 4 engine branches |
| `engine/src/migrations_engine/ai/prompts/codegen_logging_standards.yaml` | Cross-proc FK resolution via mig_upsert_log |

## Tests

- Seed feed with 2 tables → verify 2 stored procedures generated
- Seed feed with master-detail pair → detail proc queries `mig_upsert_log` for master FK
- Existing single-table feeds → still produce one proc (no regression)
- Existing project with `mig_upsert_log` table → ALTER TABLE guard doesn't break existing table

## Verification

1. `cd engine && .venv/bin/python -m pytest -xvs` — zero new failures
2. `cd web && npx tsc --noEmit` — zero errors
3. Verify `_mig_upsert_log_ddl()` returns string type for `source_row_num` in all 4 engines

## Pitfalls

- **DDL migration risk**: existing projects' `mig_upsert_log` table may have numeric `source_row_num` — must handle with `ALTER TABLE` guard
- **Token limits**: full `value_map` + one-proc rules = longer system prompt. Monitor token usage.
- **Composite keys**: `source_row_num` is single-column; multi-column natural keys need string concatenation

## Commit

"feat(codegen): one-proc-per-table prompt rules + cross-proc FK resolution via mig_upsert_log"
