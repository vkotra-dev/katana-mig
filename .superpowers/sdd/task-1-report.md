# Task 1 Report — UPSERT SQL Generator

## What I implemented

- Added `engine/src/migrations_engine/codegen/lookup_upsert.py` with a pure `generate_lookup_upsert_sql()` helper.
- Supported the requested dialect branches:
  - PostgreSQL: `CREATE TABLE IF NOT EXISTS` + `INSERT ... ON CONFLICT`
  - MySQL: `CREATE TABLE IF NOT EXISTS` + `INSERT ... ON DUPLICATE KEY UPDATE`
  - MSSQL: `IF OBJECT_ID(..., 'U') IS NULL` + `MERGE`
  - Oracle: `IF OBJECT_ID(..., 'U') IS NULL` + `MERGE`
- Ensured deterministic row ordering by sorting source values.
- Escaped single quotes in source and destination values.
- Avoided the double `_ref_ref` suffix when the lookup name already ends with `_ref`.
- Added `engine/tests/test_bundle_sequencing.py` with 11 task-1 tests covering all requested behaviors.

## What I tested

RED:

- `python -m pytest test_bundle_sequencing.py -k test_postgresql_generates_on_conflict -v`
- Result: import failed because `migrations_engine.codegen.lookup_upsert` did not exist yet.

GREEN:

- `PYTHONPATH=/Users/vjkotra/projects/katana/.worktrees/001aq-bundle-sequencing/engine/src python -m pytest test_bundle_sequencing.py -v`
- Result: `11 passed`

## Files changed

- `engine/src/migrations_engine/codegen/lookup_upsert.py`
- `engine/tests/test_bundle_sequencing.py`

## Self-review findings

- The module stays pure and stdlib-only as required.
- The SQL output is deterministic for identical input maps regardless of dict insertion order.
- The task-1 test file is intentionally narrow; later tasks can append their own coverage to the same file.

## Concerns

- The test command from the plan needed an explicit `PYTHONPATH=engine/src` in this environment to resolve `migrations_engine.codegen.lookup_upsert`. The implementation itself is fine; the import path is the only adjustment needed for local verification.
