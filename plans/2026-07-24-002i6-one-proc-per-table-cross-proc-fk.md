# Plan 002i6 — One-Proc-Per-Table + Cross-Proc FK Resolution

Task: [002i6](../tasks/002i6-one-proc-per-table-cross-proc-fk.md)
Domain: `source-model.md`

## Current State

- All table mappings generated in ONE stored procedure per feed
- `mig_upsert_log` table has `source_row_num` as numeric type (BIGINT/NUMBER)
- Detail tables resolve FKs within the same proc via direct table joins
- `system_prompt.txt.j2` generates a single proc block for all destination tables
- `codegen_logging_standards.yaml` documents `source_row_num` as a row counter

## Objective

### Part A: One-proc-per-table prompt rules
Update `system_prompt.txt.j2` to generate one PROCEDURE per `destination_object_name`, each with its own lookup DDL, seed data, and MERGE/UPSERT.

### Part B: Cross-proc FK resolution
Change `source_row_num` from numeric to string type in `_mig_upsert_log_ddl()`, add `ALTER TABLE` guard for existing projects, and update `codegen_logging_standards.yaml` with cross-proc FK resolution pattern via `mig_upsert_log`.

## Out of Scope

- New database migrations for `mig_upsert_log` DDL (handled by engine migration chain)
- Frontend changes — this is a backend + prompt-only change
- Multi-table codegen loop infrastructure (handled by task 002i3)

## Blast Radius

- High — modifies shared system prompt template and DDL generation across all 4 engine variants
- Affects every generated stored procedure going forward
- `ALTER TABLE` guard needed for existing projects with numeric `source_row_num`
- Token budget impact: longer system prompt from one-proc-per-table rules

## File Changes

| File | Change |
|------|--------|
| `engine/src/migrations_engine/codegen/templates/system_prompt.txt.j2` | One-proc-per-table rules + cross-proc FK resolution rules |
| `engine/src/migrations_engine/codegen/service.py` | `_mig_upsert_log_ddl()` column type change across all 4 engine branches |
| `engine/src/migrations_engine/codegen/codegen_logging_standards.yaml` | Cross-proc FK resolution via mig_upsert_log |

## Tests

- Seed feed with 2 tables → verify 2 stored procedures generated (one per table)
- Seed feed with master-detail pair → detail proc queries `mig_upsert_log` for master FK
- Seed feed with 1 table → verify no regression (still produces 1 proc)
- Unit test: `_mig_upsert_log_ddl()` returns string type for all 4 engines

## Verification

1. `cd engine && .venv/bin/python -m pytest -xvs` — zero new failures
2. `cd web && npx tsc --noEmit` — zero errors
3. Verify `_mig_upsert_log_ddl()` returns string type for `source_row_num` in all 4 engine branches (mssql, postgresql, mysql, oracle)
4. Verify existing single-table feeds still produce correct single proc

## Pitfalls

- **`ALTER TABLE` on existing `mig_upsert_log` table**: existing projects may have numeric `source_row_num` — must guard with `IF EXISTS` / `CASE` to only alter if column exists with wrong type
- **Token limits**: full `value_map` + one-proc-per-table rules = longer system prompt. Monitor token usage per generation.
- **Composite keys**: `source_row_num` is single-column; multi-column natural keys need string concatenation convention documented in prompt
- **Cross-proc FK resolution**: detail procs must query `mig_upsert_log` with business key to resolve FK to master tables populated by earlier procs — hard abort if FK not found

## Commit

"feat(codegen): one-proc-per-table prompt rules + cross-proc FK resolution via mig_upsert_log"
