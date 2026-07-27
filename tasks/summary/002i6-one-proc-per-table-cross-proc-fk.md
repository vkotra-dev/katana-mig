Task: tasks/completed/002i6-one-proc-per-table-cross-proc-fk.md
Plan: plans/2026-07-24-002i6-one-proc-per-table-cross-proc-fk.md
Commits: c822e61 (implementation)

## Changes Made

### `engine/src/migrations_engine/codegen/templates/system_prompt.txt.j2`
- Added one-proc-per-table rules: AI generates one stored procedure per `destination_object_name`.
- Added cross-proc FK resolution rules using `mig_upsert_log` as a shared lookup table.

### `engine/src/migrations_engine/codegen/service.py`
- `_mig_upsert_log_ddl()` changed `source_row_num` from numeric to string type in all 4 engine
  variants (PostgreSQL: VARCHAR(255), MSSQL: NVARCHAR(255), Oracle: VARCHAR2(255), MySQL: VARCHAR(255)).

### `engine/src/migrations_engine/ai/prompts/codegen_logging_standards.yaml`
- Added cross-proc FK resolution via `mig_upsert_log` for all 4 engines.
- Added composite key convention for multi-column natural keys.
- Added `dest_row_id` casting rule per engine.

### `engine/tests/test_codegen_service_api.py`
- `test_system_prompt_has_one_proc_per_table_rule`: verifies one-proc-per-table rule in system prompt.
- `test_logging_standards_include_cross_proc_fk_rules`: verifies cross-proc FK rules in logging YAML.

## Deviations from Plan

None. Implementation matches the plan's File Changes section exactly.

## Domain Updates Required

- `docs/domain/source-model.md` — Verified: one-proc-per-table and cross-proc FK resolution
  are reflected in the codegen documentation. No change needed.

## Tests

`.venv/bin/python -m pytest engine/tests -q` — all tests pass, 0 failures.

## Verification

`scripts/validate_okf.py` — all 12 domain docs pass, 0 warnings.
