# Task: 001cp — Migration Run Logging

## Status
Ready

## Background

Generated SQL bundles currently have no audit trail of what was upserted during execution. When a stored proc runs against the destination DB, there is no record of which source rows produced which destination rows, or how many rows went into each table. Post-execution reconciliation has to be done manually or from external tooling.

## Goal

Every generated SQL bundle includes:
1. A `mig_upsert_log` table in the staging schema (created once per project, append-only)
2. Every staging table has a `_row_num BIGINT IDENTITY(1,1)` column as its first column
3. Every stored proc uses `MERGE … OUTPUT` to write one log row per upserted row

This enables: row count per destination table fiber, source→destination ID mapping, and execution history across multiple runs.

## Design Decisions

- `mig_upsert_log` lives in the **destination SQL Server staging schema** — not in Katana's MySQL DB. No Alembic migration.
- Created with `IF OBJECT_ID(...) IS NULL` guard — never dropped, append-only across runs.
- `run_ref = '{project_id}_{source_definition_id}'` baked as a string literal at codegen time — no runtime parameter.
- `dest_table` column is the fiber discriminator: one source row feeding two destination tables produces two log rows.
- Row counts per fiber: `GROUP BY run_ref, dest_table, action`.

## Log Table Schema (in staging schema)

```sql
IF OBJECT_ID(N'[{staging_schema}].[mig_upsert_log]', N'U') IS NULL
BEGIN
    CREATE TABLE [{staging_schema}].[mig_upsert_log] (
        [log_id]         BIGINT IDENTITY(1,1) PRIMARY KEY,
        [run_ref]        NVARCHAR(255) NOT NULL,   -- '{project_id}_{source_definition_id}'
        [dest_table]     NVARCHAR(255) NOT NULL,   -- destination table name
        [source_row_num] BIGINT        NULL,        -- _row_num from staging table
        [dest_row_id]    NVARCHAR(255) NULL,        -- PK of destination row
        [action]         NVARCHAR(10)  NOT NULL,    -- 'INSERT' or 'UPDATE'
        [logged_at]      DATETIME2(0)  NOT NULL DEFAULT GETDATE()
    );
END;
```

## Changes

All changes are in `engine/src/migrations_engine/codegen/service.py` only:

1. **`_mig_upsert_log_ddl(staging_schema)`** — new helper that returns the CREATE block
2. **`_assemble_sql_bundle(generated_sql, *, staging_schema)`** — prepends log table DDL as first block
3. **`_build_system_prompt(..., run_ref)`** — adds `RUN LOGGING REQUIREMENTS` block instructing AI to:
   - Add `[_row_num] BIGINT IDENTITY(1,1)` as first staging table column
   - Use MERGE (not standalone INSERT/UPDATE)
   - Include OUTPUT clause writing to `mig_upsert_log`

## Files Changed

- `engine/src/migrations_engine/codegen/service.py` — 3 targeted changes
- `engine/tests/codegen/test_bundle_logging.py` (new) — unit tests

## Plan

[2026-07-10-migration-run-logging.md](../docs/superpowers/plans/2026-07-10-migration-run-logging.md)

## Verification

1. Generate SQL → download bundle → first block is `mig_upsert_log` CREATE with IF NOT EXISTS guard
2. Staging table DDL has `[_row_num] BIGINT IDENTITY(1,1)` as first column
3. Stored proc uses MERGE + OUTPUT into `mig_upsert_log`
4. `run_ref` in OUTPUT matches `'{project_id}_{source_definition_id}'`
5. Run on SQL Server → `SELECT * FROM [stg].[mig_upsert_log]` shows one row per upserted row
6. Feed writing to two destination tables → `GROUP BY dest_table, action` shows counts per fiber
7. Re-running the bundle → rows accumulate (no data loss from prior runs)
