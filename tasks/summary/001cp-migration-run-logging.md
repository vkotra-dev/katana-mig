# Summary: 001cp — Migration Run Logging

## What was built

Implemented tracking and auditing for every SQL migration run, allowing reconciliation of source rows to destination rows. 

### Bundle DDL Prepended
- Modified `_assemble_sql_bundle` in `codegen/service.py` to unconditionally prepend a `mig_upsert_log` CREATE TABLE block (protected by `IF OBJECT_ID IS NULL`) if `staging_schema` is configured.
- The `mig_upsert_log` table lives in the destination's staging schema and is append-only across multiple migration bundle executions.

### System Prompt Injections
- Updated `_build_system_prompt` to inject a `RUN LOGGING REQUIREMENTS` block that forces the AI to:
  1. Add `_row_num BIGINT IDENTITY(1,1)` as the first column of every staging table it uses.
  2. Use `MERGE ... OUTPUT` statements (instead of standard `INSERT`/`UPDATE` loops) to generate the stored procedures.
  3. Output the results of the `MERGE` directly into the `mig_upsert_log` table.
- Passed `run_ref` (e.g. `'{project_id}_{source_definition_id}'`) to the system prompt generator, ensuring the AI bakes this exact literal into the output statement for tracking.

### Tests
- Created `tests/codegen/test_bundle_logging.py` to ensure the DDL is correctly prepended when `staging_schema` is present, and omitted when it's not.
- Added tests to verify the `RUN LOGGING REQUIREMENTS` section is properly appended to the system prompt and includes the correct `run_ref` literal.
