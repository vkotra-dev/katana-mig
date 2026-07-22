---
type: Task Plan
title: Make mig_upsert_log DDL Injection Engine-Aware
status: ready
---

# Task: 001eu-engine-aware-mig-upsert-log-ddl

## Context

Found while implementing `001et`: `codegen/service.py::_mig_upsert_log_ddl` (lines 449-463)
generates hardcoded, MSSQL-only DDL for the audit-log table (`IF OBJECT_ID(...) IS NULL BEGIN
CREATE TABLE [schema].[mig_upsert_log] (...) END;` — T-SQL bracket syntax, `IDENTITY(1,1)`,
`DATETIME2(0)`). `_assemble_sql_bundle` (lines 466-474) prepends this DDL to **every** generated
SQL bundle whenever `staging_schema` is set — **regardless of the project's actual
`target_db_engine`**.

This means a postgres/mysql/oracle project's delivered SQL bundle gets invalid T-SQL syntax
mechanically injected into it after the AI generates its response. This is independent of and
unaffected by `001et`'s prompt-text changes — `001et` only fixes what guidance the AI *receives*;
this bug is a separate, code-level, deterministic post-processing step that runs regardless of what
the AI was told.

## Requirements

1. `_mig_upsert_log_ddl` must produce syntactically correct DDL for whatever the project's actual
   `target_db_engine` is (mssql/postgresql/mysql/oracle), not just mssql.
2. `_assemble_sql_bundle` must be passed (or must derive) the actual engine, not just
   `staging_schema`, to select the correct DDL variant.
3. Existing tests `test_log_table_prepended_when_staging_schema_set`,
   `test_log_table_omitted_when_staging_schema_none`, `test_if_not_exists_guard_present`
   (`engine/tests/codegen/test_bundle_logging.py`) must continue to pass unchanged for the mssql
   case (they don't pass an engine today — confirm what engine, if any, they should now pass, and
   whether their default/omitted-engine behavior should still produce mssql-shaped DDL for backward
   compatibility, or require an explicit engine going forward).
4. New tests for postgresql/mysql/oracle equivalents of the existing 3 tests.

## Out of Scope

- No change to `001et`'s scope (prompt-text/coding-standards content) — separate, already-landed
  work.
- No change to how the AI-generated `GeneratedSQL` fields themselves get assembled beyond the
  `mig_upsert_log` DDL prefix.

## Dependencies

None. Independent of `001et`/`001es`.
