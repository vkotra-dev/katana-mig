# Plan: 001et — Consolidate Audit-Trace Strategy into Per-Engine Coding Standards

## Task and Domain links

- Task: `tasks/001et-audit-strategy-per-engine-coding-standards.md`
- Domain: no `docs/domain/` page documents this content — no update required.

## Audience note

Written for an agent with no prior context. This plan replaces the *entire* content of
`codegen_coding_standards.yaml` and makes two related code changes. **All new content in this plan
has already been built and verified**: parsed successfully with `yaml.safe_load`, rendered through
the (corrected) loader for all 4 engines, checked for zero leftover unsubstituted `$variable`
references, and checked for zero remaining `oc_stag`/`cxp` literals. Copy it verbatim — do not
"improve" wording or SQL syntax while transcribing; if something looks wrong, stop and ask rather
than silently changing it, since the SQL specifics here (especially Oracle's two-statement pattern
and MySQL's row-by-row approach) were deliberately chosen for engine-specific correctness reasons
explained in the task file.

## Current State (verbatim)

### The full committed YAML file (this entire file gets replaced)

`engine/src/migrations_engine/ai/prompts/codegen_coding_standards.yaml` currently has 6 top-level
keys: `shared_header`, `shared_footer`, `postgresql`, `mssql`, `oracle`, `mysql`. Confirm this
matches before starting: `.venv/bin/python -c "import yaml; print(sorted(yaml.safe_load(open('engine/src/migrations_engine/ai/prompts/codegen_coding_standards.yaml')).keys()))"`
must print `['mssql', 'mysql', 'oracle', 'postgresql', 'shared_footer', 'shared_header']`. The
`mssql` section currently has hardcoded `oc_stag`/`cxp` literals (5 occurrences) and no
`_row_num` requirement; `postgresql`/`mysql`/`oracle` currently have only 2 lines each (no
"Migration SP Requirements" section at all). This is the bug/gap this task fixes.

### `engine/src/migrations_engine/codegen/coding_standards.py` (full current file — the loader this
task fixes)

```python
from __future__ import annotations

from pathlib import Path
from string import Template

import yaml

_YAML_PATH = Path(__file__).parent.parent / "ai" / "prompts" / "codegen_coding_standards.yaml"


def render_coding_standards_template(
    *,
    db_engine: str | None,
    staging_schema: str | None,
    destination_schema: str | None,
) -> str:
    data = yaml.safe_load(_YAML_PATH.read_text(encoding="utf-8"))

    engine_name = db_engine or "target database"
    stg = staging_schema or "staging"
    dest = destination_schema or "destination"
    lower_engine = (db_engine or "").lower()
    engine_key = "mssql" if lower_engine == "sqlserver" else lower_engine

    header = Template(data["shared_header"]).substitute(
        dest=dest, stg=stg, engineName=engine_name
    ).rstrip("\n")
    footer = data["shared_footer"].rstrip("\n")
    specific = data.get(engine_key, "")

    if specific:
        header = header + "\n" + specific.rstrip("\n")

    return f"{header}\n\n{footer}"
```

**Critical bug this task fixes in the loader**: `specific` (the engine-specific block) is used
**raw**, never passed through `Template(...).substitute(...)`. Once the YAML content below adds
`$stg`/`$dest` merge fields *inside* the engine-specific sections (not just `shared_header`), this
raw usage would leak literal `$stg`/`$dest` text into the rendered output instead of substituting
real values. This was caught by actually building and rendering the new content against the
current loader before writing this plan — confirmed the bug is real, not hypothetical.

### `engine/src/migrations_engine/codegen/service.py`, lines 477-506 (`_build_system_prompt`, in
full — the function this task simplifies)

```python
def _build_system_prompt(
    *,
    project_config: MigrationProjectConfig,
    destination_object_name: str,
    project_definition: ProjectDefinition,
    run_ref: str,
) -> str:
    template = jinja_env.get_template("system_prompt.txt.j2")
    base_prompt = template.render(
        project_config=project_config,
        destination_object_name=destination_object_name,
        project_definition=project_definition,
    ).strip()
    
    parts = [base_prompt, "", "RUN LOGGING REQUIREMENTS"]
    parts.append(
        f"Every staging table must include [_row_num] BIGINT IDENTITY(1,1) NOT NULL as its FIRST column.\n"
        f"Every data movement stored procedure must use MERGE (not standalone INSERT or UPDATE).\n"
        f"Every MERGE must include an OUTPUT clause that writes to [{project_config.staging_schema or 'stg'}].[mig_upsert_log]:\n"
        f"  OUTPUT\n"
        f"    '{run_ref}',\n"
        f"    '<dest_table_name>',\n"
        f"    src.[_row_num],\n"
        f"    CAST(inserted.<dest_pk_column> AS NVARCHAR(255)),\n"
        f"    $action\n"
        f"  INTO [{project_config.staging_schema or 'stg'}].[mig_upsert_log]\n"
        f"      (run_ref, dest_table, source_row_num, dest_row_id, action);\n"
        f"Replace <dest_table_name> with the actual destination table name and <dest_pk_column> with its primary key column."
    )
    return "\n".join(parts)
```

Lines 120-125 (the call site, part of `generate_codegen_artifact` — quoted with 1 line of context
before and after for locating it):

```python
    system_prompt = _build_system_prompt(
        project_config=project_config,
        destination_object_name=destination_object_name,
        project_definition=project_definition,
        run_ref=f"{project_id}_{source_definition_id}",
    )
```

## Objective

1. Replace `codegen_coding_standards.yaml` in full with the corrected/expanded content below.
2. Fix the loader to substitute merge fields inside the engine-specific block too.
3. Simplify `_build_system_prompt` to just the Jinja-rendered base prompt — delete the hardcoded
   "RUN LOGGING REQUIREMENTS" append and the now-unused `run_ref` parameter, update the call site.

## File Changes

### 1. `engine/src/migrations_engine/ai/prompts/codegen_coding_standards.yaml`

Replace the entire file content with:

```yaml
shared_header: |
  ### Coding Standards and Guidelines

  1. **Schemas and Scoping**:
     - Migration and utility stored procedures must be created under the staging schema, not the destination schema.
     - All destination tables must be created under the "$dest" schema.
     - All staging and source tables must be read from the "$stg" schema.
     - All DDL for lookup tables must be created in the "$stg" schema.

  2. **Database Engine Conventions ($engineName)**:
     - Write all DDL and stored procedures complying with the standard coding conventions pertinent to $engineName.

shared_footer: |
  3. **General Best Practices**:
     - Ensure all scripts are repeatable and idempotent. Use SQL Server-compatible idempotent patterns: CREATE OR ALTER for stored procedures and IF OBJECT_ID(...) IS NULL for tables. Do not drop and recreate persistent tables merely to make a script repeatable.
     - Use explicit column lists in all INSERT statements.
     - Do not hardcode environment-specific values. Do not create arbitrary default timestamps for business data columns. Database-managed audit columns, such as migration-log timestamps, may use an appropriate default when explicitly required by the schema.

postgresql: |2
       - Use standard PostgreSQL coding conventions: lowercase identifiers, snake_case for tables/columns, explicit type casting (e.g. ::date, ::integer).
       - Stored procedures/functions should be written in PL/pgSQL using dollar-quoting.
       - Every procedure must be idempotent and re-creatable: use CREATE OR REPLACE PROCEDURE/FUNCTION. Never use CREATE PROCEDURE alone.
       - Every table DDL must be idempotent: use CREATE TABLE IF NOT EXISTS. Never emit an unconditional CREATE TABLE statement.

       **Migration SP Requirements:**
         1. A top-level CALL to a PROCEDURE is auto-transactional (PostgreSQL 11+); wrap nested risky DML in BEGIN ... EXCEPTION WHEN OTHERS THEN ROLLBACK; RAISE; END for explicit rollback-and-rethrow.
         2. Validate source table is non-empty before upserting; RAISE EXCEPTION if empty. The empty source validation must occur before any INSERT/UPDATE executes.
         3. Use RAISE EXCEPTION for all error raising, with ERRCODE set where applicable.
         4. Every staging table must include a _row_num BIGSERIAL column as its first column, providing a stable source-row identifier for audit logging. Use dest_row_id::text for future-safe action logging. Capture affected rows via the INSERT ... ON CONFLICT ... RETURNING clause in one set-based operation — never loop per row.
         5. NULL values in source columns flow through unchanged unless destination is NOT NULL
         6. Note index requirements on ON CONFLICT target columns in comments — the ON CONFLICT clause requires a UNIQUE index or constraint on the conflict target.
         7. FK lookups must be resolved via JOIN in the upsert's source SELECT, not scalar subqueries. Every row gets its own resolved FK value.
         8. run_ref must be dynamically generated inside the procedure using gen_random_uuid() combined with a timestamp and the procedure's own name. Never accept as a parameter, never hardcode.
            WRONG:  run_ref TEXT := '00000000-0000-4000-8000-...';
            CORRECT: run_ref TEXT := 'proc_name' || '_' || to_char(clock_timestamp(), 'YYYYMMDDHH24MISS') || '_' || gen_random_uuid()::text;
         9. Schemas $stg and $dest are assumed to exist. Never create, drop, or alter schemas in procedures or migration scripts.
         10. Declare only variables that are used. Remove unused declarations.
         11. Never update the primary key column in the ON CONFLICT DO UPDATE SET clause. The conflict target column must never appear in the UPDATE column list.
         12. Verify parenthesis and quoting balance before outputting SQL.
         13. CRITICAL: System-managed row-level audit and technical columns that track creation or modification in THIS database — such as created_at, created_by, inserted_at, inserted_by, updated_at, updated_by — must not be copied from the source or included in the ON CONFLICT DO UPDATE SET clause unless the column is explicitly identified as source-system business data.
         14. RAISE EXCEPTION format-string/USING clause order must be correct: RAISE EXCEPTION 'message: %', value USING ERRCODE = 'P0001'; never swap positional arguments.
         15. CRITICAL: Every stored procedure must wrap risky DML in a nested BEGIN ... EXCEPTION WHEN OTHERS THEN ROLLBACK; RAISE; END block so errors propagate with rollback.
         16. CRITICAL: ALL lookup tables created in the same script must be used by at least one relevant upsert source SELECT via JOIN to resolve FK values per row — not just some of them. Never create lookup tables and then ignore them.

         The correct pattern is:
         SELECT
             s.*,
             lk1.id AS resolved_fk1_id,
             lk2.id AS resolved_fk2_id
         FROM $stg.source_table s
         LEFT JOIN $stg.lookup_table_1 lk1
             ON lk1.code_column = s.source_code_column_1
         LEFT JOIN $stg.lookup_table_2 lk2
             ON lk2.code_column = s.source_code_column_2
         WHERE s.pk_column IS NOT NULL

         Then reference resolved_fk1_id and resolved_fk2_id in the INSERT/UPDATE clauses instead of the raw source code columns.
         17. Every upsert must log to $stg.mig_upsert_log (columns: run_ref, dest_table, source_row_num, dest_row_id, action). PostgreSQL's MERGE (15+) has no OUTPUT clause; use INSERT ... ON CONFLICT ... RETURNING with a CTE:
         WITH upserted AS (
             INSERT INTO $dest.dest_table (...)
             SELECT ... FROM $stg.source_table
             ON CONFLICT (key_column) DO UPDATE SET ...
             RETURNING dest_pk_column AS dest_row_id, (xmax = 0) AS is_insert, _row_num AS source_row_num
         )
         INSERT INTO $stg.mig_upsert_log (run_ref, dest_table, source_row_num, dest_row_id, action)
         SELECT 'run_ref_value', 'dest_table_name', source_row_num, dest_row_id::text,
                CASE WHEN is_insert THEN 'INSERT' ELSE 'UPDATE' END
         FROM upserted;
         (xmax = 0 is the standard PostgreSQL idiom for "this row was just inserted, not updated" within the same statement.)
         18. Duplicate source-key checks must be performed for every ON CONFLICT target column set before executing the upsert. If duplicate source keys exist, RAISE EXCEPTION before the upsert runs.
         19. Lookup seed data must be idempotent. Use INSERT ... ON CONFLICT DO NOTHING so rerunning the script cannot create duplicate lookup values.
         20. For lookup tables created by the script, every business code column used for FK resolution must have a UNIQUE constraint or index.
         21. Before upserting, validate that every required FK lookup resolved successfully. If a non-NULL source lookup code cannot be resolved to a required destination FK, RAISE EXCEPTION before executing the upsert. Preserve NULL only when the source value and destination FK are legitimately nullable.

mssql: |2
       - Use T-SQL coding conventions: UPPERCASE SQL keywords, square brackets for identifiers only when necessary, proper schema qualifiers.
       - Always use CREATE OR ALTER PROCEDURE, never CREATE PROCEDURE alone. Scripts must be idempotent and runnable multiple times without error.
       - Every CREATE TABLE statement must be idempotent. Use IF OBJECT_ID(N'[schema].[table]', N'U') IS NULL before CREATE TABLE. Never emit an unconditional CREATE TABLE statement.

       **Migration SP Requirements:**
         1. SET XACT_ABORT ON immediately after SET NOCOUNT ON
         2. Validate source table is non-empty before MERGE; THROW if empty. The empty source validation THROW must occur before any MERGE statement executes.
         3. Use THROW not RAISERROR for all error raising (SQL Server 2012+)
         4. Every staging table must include [_row_num] BIGINT IDENTITY(1,1) NOT NULL as its first column, providing a stable source-row identifier for audit logging. Use CAST(COALESCE(inserted.[pk], deleted.[pk]) AS NVARCHAR(255)) for future-safe action logging. The CAST to NVARCHAR(255) is required to match the dest_row_id column type in mig_upsert_log. Use inserted and deleted pseudo-table aliases when logging destination-table column values in the OUTPUT clause. The MERGE source alias may be referenced only for source metadata such as source_row_num. Never use the target alias to retrieve the affected destination row identifier. OUTPUT INTO [$stg].[mig_upsert_log] must specify the explicit destination column list: ([run_ref], [dest_table], [source_row_num], [dest_row_id], [action]).
         5. NULL values in source columns flow through unchanged unless destination is NOT NULL
         6. Note index requirements on MERGE join key columns in comments
         7. FK lookups must be resolved via JOIN in MERGE source SELECT, not scalar variables. Every row gets its own resolved FK value.
         8. run_ref must be dynamically generated inside the procedure using OBJECT_NAME(@@PROCID) as the procedure name prefix combined with GETDATE() and NEWID(). Never accept as parameter, never hardcode.
            WRONG:  DECLARE @run_ref = '00000000-0000-4000-8000-...'
            CORRECT: DECLARE @run_ref NVARCHAR(255) = OBJECT_NAME(@@PROCID) + '_' +
                     CONVERT(NVARCHAR(20), GETDATE(), 120) + '_' +
                     CAST(NEWID() AS NVARCHAR(36));
         9. Schemas [$dest] and [$stg] are assumed to exist. Never create, drop, or alter schemas in procedures or migration scripts.
         10. Declare only variables that are used. Remove unused declarations.
         11. Never update the primary key column in WHEN MATCHED THEN UPDATE SET. The ON clause join key must never appear in the UPDATE column list.
         12. Verify bracket and parenthesis balance before outputting SQL.
         13. CRITICAL: System-managed row-level audit and technical columns that track creation or modification in THIS database — such as created_at, created_by, inserted_at, inserted_by, updated_at, updated_by, rowversion, and timestamp — must not be copied from the source or included in WHEN MATCHED THEN UPDATE SET unless the column is explicitly identified as source-system business data.

             Business date fields from the source system that represent original business event dates are legitimate update columns and should be included.

             If unsure whether a column is an audit timestamp or a business date, check the source DDL. Audit timestamps are typically auto-generated using DEFAULT GETDATE(), DEFAULT SYSUTCDATETIME(), rowversion, timestamp, or similar database-managed behavior and must not be overwritten on update.

             rowversion and SQL Server timestamp columns must not be explicitly inserted or updated.

             WRONG:  target.created_at = source.created_at
             WRONG:  target.inserted_by = source.inserted_by
             CORRECT: Omit created_at, inserted_by, and similar system-managed columns entirely from the UPDATE SET column list.
         14. THROW syntax must follow the correct T-SQL argument order: THROW error_number, message_string, state; Never swap the message and state arguments.
         15. CRITICAL: Every stored procedure must wrap all DML in TRY...CATCH with explicit transaction management: BEGIN TRY / BEGIN TRANSACTION ... COMMIT / END TRY then BEGIN CATCH / IF @@TRANCOUNT > 0 ROLLBACK / THROW / END CATCH.
         16. CRITICAL: ALL lookup tables created in the same script must be used by at least one relevant MERGE source SELECT via JOIN to resolve FK values per row — not just some of them. Never create lookup tables and then ignore them in the MERGE. Never alias a source column as an FK id — that is not a JOIN.

         The correct pattern is:
         USING (
             SELECT
                 s.*,
                 lk1.[id] AS resolved_fk1_id,
                 lk2.[id] AS resolved_fk2_id
             FROM [$stg].[source_table] s
             LEFT JOIN [$stg].[lookup_table_1] lk1
                 ON lk1.[code_column] = s.[source_code_column_1]
             LEFT JOIN [$stg].[lookup_table_2] lk2
                 ON lk2.[code_column] = s.[source_code_column_2]
             WHERE s.[pk_column] IS NOT NULL
         ) AS source

         Then reference source.resolved_fk1_id and source.resolved_fk2_id in the UPDATE SET and INSERT VALUES clauses instead of the raw source code columns.
         17. Every MERGE statement must include an OUTPUT clause logging to [$stg].[mig_upsert_log]. After all MERGEs complete, return a result set with run_ref, rows_inserted, rows_updated, completed_at derived from the log table.
         18. Duplicate source-key checks must be performed for every key or composite key used in the MERGE ON clause before executing MERGE. If duplicate source keys exist, THROW before MERGE. Also validate that required MERGE key columns are not NULL.
         19. Lookup seed data must be idempotent. Never emit unconditional INSERT statements for lookup rows. Use IF NOT EXISTS or INSERT ... WHERE NOT EXISTS so rerunning the script cannot create duplicate lookup values.
         20. For lookup tables created by the script, every business code column used for FK resolution must have a UNIQUE constraint or UNIQUE index.
         21. Before MERGE, validate that every required FK lookup resolved successfully. If a non-NULL source lookup code cannot be resolved to a required destination FK, THROW before executing MERGE. Preserve NULL only when the source value and destination FK are legitimately nullable.

oracle: |2
       - Use PL/SQL coding conventions: UPPERCASE keywords/types, clear EXCEPTION blocks, schema-qualified table references.
       - All object names must respect Oracle length limits (max 30 or 128 characters depending on version).
       - Every procedure must be idempotent and re-creatable: use CREATE OR REPLACE PROCEDURE. Never use CREATE PROCEDURE alone.
       - Every table DDL must be idempotent: wrap CREATE TABLE in a check against USER_TABLES (Oracle has no native CREATE TABLE IF NOT EXISTS pre-23c):
         BEGIN
           EXECUTE IMMEDIATE 'CREATE TABLE ...';
         EXCEPTION
           WHEN OTHERS THEN
             IF SQLCODE != -955 THEN RAISE; END IF; -- ORA-00955: name already used by an existing object
         END;

       **Migration SP Requirements:**
         1. Wrap all DML in an explicit BEGIN ... EXCEPTION WHEN OTHERS THEN ROLLBACK; RAISE; END block. Oracle needs explicit transaction management for multi-statement procedures — never rely on implicit commit behavior mid-procedure.
         2. Validate source table is non-empty before upserting; RAISE_APPLICATION_ERROR if empty. The empty source validation must occur before any UPDATE/INSERT executes.
         3. Use RAISE_APPLICATION_ERROR(-20001, message) for all custom error raising, using an error number in the reserved -20000 to -20999 range.
         4. Every staging table must include a _row_num NUMBER GENERATED ALWAYS AS IDENTITY column as its first column, providing a stable source-row identifier for audit logging. Since MERGE does not support RETURNING, capture affected rows via a two-statement UPDATE/INSERT pattern (each using RETURNING ... BULK COLLECT INTO) instead of a single MERGE — never loop per source row for the DML itself (looping is only used for the FORALL log insert from the collected arrays).
         5. NULL values in source columns flow through unchanged unless destination is NOT NULL
         6. Note index requirements on the WHERE EXISTS/NOT EXISTS join key columns.
         7. FK lookups must be resolved via JOIN in the UPDATE/INSERT source queries, not scalar subqueries.
         8. run_ref must be dynamically generated inside the procedure using SYS_GUID() combined with SYSTIMESTAMP and the procedure name (via $$PLSQL_UNIT). Never accept as a parameter, never hardcode.
            WRONG:  v_run_ref := '00000000-0000-4000-8000-...';
            CORRECT: v_run_ref := $$PLSQL_UNIT || '_' || TO_CHAR(SYSTIMESTAMP, 'YYYYMMDDHH24MISS') || '_' || RAWTOHEX(SYS_GUID());
         9. Schemas $stg and $dest are assumed to exist. Never create, drop, or alter schemas/users in procedures or migration scripts.
         10. Declare only variables that are used. Remove unused declarations.
         11. Never update the primary key column in the UPDATE SET clause.
         12. Verify parenthesis balance before outputting SQL.
         13. CRITICAL: System-managed row-level audit and technical columns that track creation or modification in THIS database — such as created_at, created_by, inserted_at, inserted_by, updated_at, updated_by — must not be copied from the source or included in the UPDATE SET clause unless the column is explicitly identified as source-system business data.
         14. RAISE_APPLICATION_ERROR argument order must be (error_number, message[, keep_errors]); never swap the error number and message arguments.
         15. CRITICAL: Every stored procedure must wrap all DML in BEGIN...EXCEPTION WHEN OTHERS THEN ROLLBACK; RAISE; END with explicit transaction management.
         16. CRITICAL: ALL lookup tables created in the same script must be used by at least one relevant JOIN in both the UPDATE and INSERT source queries — not just some of them. Never create lookup tables and then ignore them.

         The correct pattern is:
         UPDATE $dest.dest_table d SET ...
         WHERE EXISTS (
             SELECT 1 FROM $stg.source_table s
             LEFT JOIN $stg.lookup_table_1 lk1
                 ON lk1.code_column = s.source_code_column_1
             WHERE s.pk_column = d.pk_column
         )

         (and equivalently in the paired INSERT ... SELECT ... WHERE NOT EXISTS statement)
         17. Both the UPDATE and INSERT statements must use RETURNING dest_pk_column, _row_num BULK COLLECT INTO v_dest_ids, v_source_rows (separately for each), then FORALL i IN 1..v_dest_ids.COUNT INSERT INTO $stg.mig_upsert_log (run_ref, dest_table, source_row_num, dest_row_id, action) VALUES (v_run_ref, 'dest_table_name', v_source_rows(i), TO_CHAR(v_dest_ids(i)), 'UPDATE_OR_INSERT') — action is known statically per statement (not per row), since UPDATE and INSERT are separate here.
         18. Duplicate source-key checks must be performed before the UPDATE/INSERT pair executes. If duplicate source keys exist, RAISE_APPLICATION_ERROR before the pair runs.
         19. Lookup seed data must be idempotent. Use INSERT INTO ... SELECT ... WHERE NOT EXISTS (...) so rerunning the script cannot create duplicate lookup values.
         20. For lookup tables created by the script, every business code column used for FK resolution must have a UNIQUE constraint or index.
         21. Before the UPDATE/INSERT pair, validate that every required FK lookup resolved successfully. If a non-NULL source lookup code cannot be resolved to a required destination FK, RAISE_APPLICATION_ERROR before executing the pair. Preserve NULL only when the source value and destination FK are legitimately nullable.

mysql: |2
       - Use standard MySQL coding conventions: backticks for reserved word identifiers, snake_case table/column names.
       - Stored procedures should use clear parameter scoping and DELIMITER declarations.
       - Every procedure must be idempotent and re-creatable: use DROP PROCEDURE IF EXISTS followed by CREATE PROCEDURE (MySQL has no CREATE OR ALTER/CREATE OR REPLACE PROCEDURE).
       - Every table DDL must be idempotent: use CREATE TABLE IF NOT EXISTS.

       **Migration SP Requirements:**
         1. START TRANSACTION explicitly; DECLARE EXIT HANDLER FOR SQLEXCEPTION at the top that performs ROLLBACK and re-signals the error (MySQL has no native TRY/CATCH — this handler is the closest equivalent).
         2. Validate source table is non-empty before upserting; SIGNAL SQLSTATE '45000' if empty. The empty source validation must occur before any INSERT executes.
         3. Use SIGNAL SQLSTATE for all error raising, never rely on implicit warnings.
         4. Every staging table must include a _row_num BIGINT AUTO_INCREMENT column as its first column, providing a stable source-row identifier for audit logging. INSERT ... ON DUPLICATE KEY UPDATE does not report per-row identity/action in a set-based way. Audit logging therefore requires row-by-row processing: cursor over source rows, one INSERT ... ON DUPLICATE KEY UPDATE per row, then ROW_COUNT() immediately after (1=inserted, 2=updated, 0=unchanged) plus LAST_INSERT_ID() or the resolved natural key as dest_row_id, one row per source row into mig_upsert_log.
         5. NULL values in source columns flow through unchanged unless destination is NOT NULL
         6. Note index requirements on the ON DUPLICATE KEY UPDATE's unique/primary key columns.
         7. FK lookups must be resolved via JOIN in the cursor's source query, not scalar subqueries inside the loop body.
         8. run_ref must be dynamically generated using UUID() combined with NOW() and the procedure name. Never accept as a parameter, never hardcode.
            WRONG:  SET run_ref = '00000000-0000-4000-8000-...';
            CORRECT: SET run_ref = CONCAT('proc_name', '_', DATE_FORMAT(NOW(), '%Y%m%d%H%i%s'), '_', UUID());
         9. Schemas (databases) $stg and $dest are assumed to exist. Never create, drop, or alter schemas/databases in procedures or migration scripts.
         10. Declare only variables that are used. Remove unused DECLAREs.
         11. Never update the primary key column in the ON DUPLICATE KEY UPDATE clause.
         12. Verify backtick and parenthesis balance before outputting SQL.
         13. CRITICAL: System-managed row-level audit and technical columns that track creation or modification in THIS database — such as created_at, created_by, updated_at, updated_by — must not be copied from source or included in ON DUPLICATE KEY UPDATE unless explicitly identified as source-system business data.
         14. SIGNAL SQLSTATE syntax must set both SQLSTATE and MESSAGE_TEXT correctly: SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'description'; never omit the SQLSTATE value.
         15. CRITICAL: Every stored procedure must declare its exit handler at the top performing ROLLBACK before re-raising, since MySQL has no TRY/CATCH block syntax.
         16. CRITICAL: ALL lookup tables created in the same script must be used via JOIN when building the cursor's source query — not just some of them. Never create lookup tables and then ignore them.

         The correct pattern is:
         DECLARE cur CURSOR FOR
           SELECT s.*, lk1.id AS resolved_fk1_id, lk2.id AS resolved_fk2_id
           FROM stg_source_table s
           LEFT JOIN stg_lookup_table_1 lk1 ON lk1.code_column = s.source_code_column_1
           LEFT JOIN stg_lookup_table_2 lk2 ON lk2.code_column = s.source_code_column_2
           WHERE s.pk_column IS NOT NULL;
         17. Every processed row must be logged to $stg.mig_upsert_log (run_ref, dest_table, source_row_num, dest_row_id, action) via the per-row ROW_COUNT()/LAST_INSERT_ID() pattern from item 4 — this is inherently row-by-row in MySQL, not set-based; note this explicitly as a comment in the generated procedure, and batch-commit every 500 rows for large source tables to bound transaction overhead.
         18. Duplicate source-key checks must be performed for every key/composite key used as the ON DUPLICATE KEY UPDATE target before the cursor loop begins; SIGNAL SQLSTATE on duplicates.
         19. Lookup seed data must be idempotent: use INSERT IGNORE or INSERT ... ON DUPLICATE KEY UPDATE so rerunning the script cannot create duplicate lookup values.
         20. For lookup tables created by the script, every business code column used for FK resolution must have a UNIQUE KEY.
         21. Before the cursor loop, validate every required FK lookup resolved via a pre-flight SELECT COUNT(*) ... WHERE resolved_fk IS NULL AND source_code IS NOT NULL; SIGNAL SQLSTATE before processing if any are unresolved.
```

After creating the file, verify with:
```bash
.venv/bin/python -c "
import yaml
d = yaml.safe_load(open('engine/src/migrations_engine/ai/prompts/codegen_coding_standards.yaml').read())
print(sorted(d.keys()))
print(repr(d['postgresql'][:10]))
print(repr(d['oracle'][:10]))
print(repr(d['mysql'][:10]))
"
```
Expect: `['mssql', 'mysql', 'oracle', 'postgresql', 'shared_footer', 'shared_header']`, and all three
`repr(...)` lines to print `'     - Use'` (5 leading spaces).

### 2. `engine/src/migrations_engine/codegen/coding_standards.py`

Find the exact block quoted above under "Current State" and replace it with:

```python
from __future__ import annotations

from pathlib import Path
from string import Template

import yaml

_YAML_PATH = Path(__file__).parent.parent / "ai" / "prompts" / "codegen_coding_standards.yaml"


def render_coding_standards_template(
    *,
    db_engine: str | None,
    staging_schema: str | None,
    destination_schema: str | None,
) -> str:
    data = yaml.safe_load(_YAML_PATH.read_text(encoding="utf-8"))

    engine_name = db_engine or "target database"
    stg = staging_schema or "staging"
    dest = destination_schema or "destination"
    lower_engine = (db_engine or "").lower()
    engine_key = "mssql" if lower_engine == "sqlserver" else lower_engine

    mapping = {"dest": dest, "stg": stg, "engineName": engine_name}
    header = Template(data["shared_header"]).substitute(mapping).rstrip("\n")
    footer = data["shared_footer"].rstrip("\n")
    specific_raw = data.get(engine_key, "")

    if specific_raw:
        specific = Template(specific_raw).substitute(mapping)
        header = header + "\n" + specific.rstrip("\n")

    return f"{header}\n\n{footer}"
```

The only substantive change: `specific` is now passed through `Template(specific_raw).substitute(mapping)`
before being appended, using the same `mapping` dict already built for `shared_header`. Without
this, every `$stg`/`$dest` reference newly added inside the engine-specific sections (step 1 above)
would appear as literal, unsubstituted text in the rendered output.

### 3. `engine/src/migrations_engine/codegen/service.py`

**3a.** Find the exact `_build_system_prompt` function quoted in full above under "Current State"
and replace it with:

```python
def _build_system_prompt(
    *,
    project_config: MigrationProjectConfig,
    destination_object_name: str,
    project_definition: ProjectDefinition,
) -> str:
    template = jinja_env.get_template("system_prompt.txt.j2")
    return template.render(
        project_config=project_config,
        destination_object_name=destination_object_name,
        project_definition=project_definition,
    ).strip()
```

(The `run_ref` parameter and the "RUN LOGGING REQUIREMENTS" append are both removed. Audit-trace
guidance now comes entirely from `project_definition.codegen_instructions`, which
`system_prompt.txt.j2` already embeds — see `system_prompt.txt.j2:54-56`, unchanged by this task.)

**3b.** Find the exact call site quoted above under "Current State":

```python
    system_prompt = _build_system_prompt(
        project_config=project_config,
        destination_object_name=destination_object_name,
        project_definition=project_definition,
        run_ref=f"{project_id}_{source_definition_id}",
    )
```

Replace with:

```python
    system_prompt = _build_system_prompt(
        project_config=project_config,
        destination_object_name=destination_object_name,
        project_definition=project_definition,
    )
```

(Only the `run_ref=...` kwarg is removed. The `_build_user_prompt` call immediately below this one
in the same function still has its own, separate `run_ref=f"{project_id}_{source_definition_id}"`
kwarg — do not touch that one, it's unrelated and still needed.)

## Tests

**1. Update `engine/tests/test_codegen_coding_standards.py`'s existing tests** (from `001er`) — the
assertions on the presence of specific mssql substrings mostly still hold, but add new assertions
confirming the merge-field fix and the new content:

- `test_mssql_standards_include_engine_specific_block`: add these two lines to the existing test
  body. Do **not** add an assertion like `"[cxp]" not in result` here — this test already calls
  `render_coding_standards_template(..., destination_schema="cxp")`, so `[cxp]` legitimately
  appears in the output via correct `$dest` substitution; asserting its absence would fail on
  correct behavior, not catch a bug. The `oc_stag` check below is sufficient to prove the
  hardcoded literal is gone, since `"oc_stag"` is never a parameter value in this test:
  ```python
      assert "oc_stag" not in result
      assert "[_row_num] BIGINT IDENTITY(1,1) NOT NULL" in result
  ```

**2. Add new tests** to the same file, verifying the new per-engine "Migration SP Requirements"
content and that merge fields substitute correctly inside engine-specific sections (the bug fixed
in step 2 above):

```python
def test_postgresql_standards_include_migration_sp_requirements():
    result = render_coding_standards_template(
        db_engine="postgresql", staging_schema="stg", destination_schema="cxp"
    )
    assert "Migration SP Requirements" in result
    assert "gen_random_uuid()" in result
    assert '"stg".mig_upsert_log' not in result  # not bracketed like mssql
    assert "stg.mig_upsert_log" in result  # $stg substituted correctly inside the engine block
    assert "xmax = 0" in result


def test_mysql_standards_include_migration_sp_requirements():
    result = render_coding_standards_template(
        db_engine="mysql", staging_schema="stg", destination_schema="cxp"
    )
    assert "Migration SP Requirements" in result
    assert "ROW_COUNT()" in result
    assert "stg.mig_upsert_log" in result
    assert "row-by-row" in result  # the explicit efficiency caveat must be present


def test_oracle_standards_include_migration_sp_requirements():
    result = render_coding_standards_template(
        db_engine="oracle", staging_schema="stg", destination_schema="cxp"
    )
    assert "Migration SP Requirements" in result
    assert "BULK COLLECT INTO" in result
    assert "stg.mig_upsert_log" in result
    assert "RETURNING" in result
    assert "MERGE does not support RETURNING" in result or "does not support RETURNING" in result


def test_merge_fields_substitute_inside_engine_specific_section():
    # Regression test for the loader bug found while building this task: the engine-specific
    # block was previously never passed through Template.substitute(), so $stg/$dest would leak
    # through as literal text instead of the actual schema names.
    result = render_coding_standards_template(
        db_engine="postgresql", staging_schema="my_custom_stg", destination_schema="my_custom_dest"
    )
    assert "$stg" not in result
    assert "$dest" not in result
    assert "my_custom_stg" in result
    assert "my_custom_dest" in result
```

**3. Add a new test file `engine/tests/test_codegen_system_prompt.py`** for the
`_build_system_prompt` simplification. Read `test_codegen_service_api.py`'s `_seed_project()`
helper and imports first to match style (it seeds a `ProjectDefinition`/`ProjectRegistry`/
`SourceDefinition` with `MappingSnapshot`), but this new test only needs to call
`_build_system_prompt` directly, not the full `generate_codegen_artifact` flow:

```python
from migrations_engine.codegen.service import _build_system_prompt
from migrations_engine.api.schemas import MigrationProjectConfig
from migrations_engine.db.models import ProjectDefinition


def test_build_system_prompt_no_longer_appends_run_logging_requirements():
    project_definition = ProjectDefinition(
        definition_id="def-1",
        project_id="proj-1",
        name="Test",
        status="active",
        codegen_instructions="Custom standards go here.",
    )
    config = MigrationProjectConfig(target_db_engine="postgresql", staging_schema="stg")

    result = _build_system_prompt(
        project_config=config,
        destination_object_name="customer",
        project_definition=project_definition,
    )

    assert "RUN LOGGING REQUIREMENTS" not in result
    assert "mig_upsert_log" not in result
    assert "Custom standards go here." in result
```

Confirm this test's `ProjectDefinition(...)` constructor call matches the model's actual required
fields by checking `engine/src/migrations_engine/db/models.py`'s `ProjectDefinition` class before
running — add any other required fields this abbreviated example omits.

**4. Fix `engine/tests/codegen/test_bundle_logging.py`** — this file was not found by an initial
search for existing coverage of this area (that search only checked `engine/tests/*.py`, not the
`engine/tests/codegen/` subdirectory — check subdirectories too when scanning for existing tests
before assuming there's none). It has 5 tests; 3 exercise a separate, untouched function
(`_assemble_sql_bundle`) and must be left alone; 2 directly call `_build_system_prompt(...,
run_ref=...)` and assert on the now-removed "RUN LOGGING REQUIREMENTS" content — these fail with
`TypeError: _build_system_prompt() got an unexpected keyword argument 'run_ref'` once step 3 lands.

Find this exact block (the full current content of the file):

```python
from migrations_engine.codegen.service import _assemble_sql_bundle, GeneratedSQL, _build_system_prompt
from migrations_engine.api.schemas import MigrationProjectConfig
from migrations_engine.db.models import ProjectDefinition


def make_sql(ddl="CREATE TABLE [stg].[t] ([id] INT);", views=None):
    return GeneratedSQL(staging_ddl=ddl, lookup_ddl=[], seed_data=[], stored_procedures=[], views=views or [])


def test_log_table_prepended_when_staging_schema_set():
    bundle = _assemble_sql_bundle(make_sql(), staging_schema="oc_stag")
    assert "mig_upsert_log" in bundle
    assert bundle.index("mig_upsert_log") < bundle.index("CREATE TABLE [stg].[t]")


def test_log_table_omitted_when_staging_schema_none():
    bundle = _assemble_sql_bundle(make_sql(), staging_schema=None)
    assert "mig_upsert_log" not in bundle


def test_if_not_exists_guard_present():
    bundle = _assemble_sql_bundle(make_sql(), staging_schema="oc_stag")
    assert "IF OBJECT_ID" in bundle
    assert "IS NULL" in bundle


def test_system_prompt_includes_run_logging_block():
    config = MigrationProjectConfig(
        target_db_engine="mssql",
        staging_schema="oc_stag",
        destination_schema="dbo",
    )
    prompt = _build_system_prompt(
        project_config=config,
        destination_object_name="policy_claims",
        project_definition=ProjectDefinition(),
        run_ref="proj123_src456",
    )
    assert "RUN LOGGING REQUIREMENTS" in prompt
    assert "_row_num" in prompt
    assert "mig_upsert_log" in prompt
    assert "proj123_src456" in prompt
    assert "$action" in prompt


def test_system_prompt_run_ref_is_baked_in():
    config = MigrationProjectConfig(staging_schema="oc_stag")
    prompt = _build_system_prompt(
        project_config=config,
        destination_object_name="policy_master",
        project_definition=ProjectDefinition(),
        run_ref="myproject_myfeed",
    )
    assert "'myproject_myfeed'" in prompt
```

Replace with (removes the two `_build_system_prompt` tests and their now-unused imports; the 3
`_assemble_sql_bundle` tests are untouched, byte-for-byte):

```python
from migrations_engine.codegen.service import _assemble_sql_bundle, GeneratedSQL


def make_sql(ddl="CREATE TABLE [stg].[t] ([id] INT);", views=None):
    return GeneratedSQL(staging_ddl=ddl, lookup_ddl=[], seed_data=[], stored_procedures=[], views=views or [])


def test_log_table_prepended_when_staging_schema_set():
    bundle = _assemble_sql_bundle(make_sql(), staging_schema="oc_stag")
    assert "mig_upsert_log" in bundle
    assert bundle.index("mig_upsert_log") < bundle.index("CREATE TABLE [stg].[t]")


def test_log_table_omitted_when_staging_schema_none():
    bundle = _assemble_sql_bundle(make_sql(), staging_schema=None)
    assert "mig_upsert_log" not in bundle


def test_if_not_exists_guard_present():
    bundle = _assemble_sql_bundle(make_sql(), staging_schema="oc_stag")
    assert "IF OBJECT_ID" in bundle
    assert "IS NULL" in bundle
```

**Do not touch `_assemble_sql_bundle`/`_mig_upsert_log_ddl` themselves** (lines 449-474 of
`codegen/service.py`) — they're a separate, hardcoded, MSSQL-only DDL-injection mechanism,
independent of the prompt-text changes in this task. This was found while running the full test
suite and is a real, currently-shipping bug (it prepends MSSQL-specific `IF OBJECT_ID`/bracket
syntax into every generated bundle regardless of the project's actual `target_db_engine`) —
explicitly out of scope for this task; tracked separately (see `tasks/TASK_INDEX.md` for whether a
follow-up task exists by the time this plan is executed).

## Verification

```bash
cd /Users/vjkotra/projects/katana
.venv/bin/ruff check engine/src/migrations_engine/codegen/coding_standards.py engine/src/migrations_engine/codegen/service.py engine/tests/test_codegen_coding_standards.py engine/tests/test_codegen_system_prompt.py engine/tests/codegen/test_bundle_logging.py
```
Expect: `All checks passed!`

```bash
.venv/bin/python -m mypy engine/src/migrations_engine/codegen/coding_standards.py engine/src/migrations_engine/codegen/service.py --strict
```
Expect: no new errors versus the pre-existing baseline (the `yaml` stub-missing error on
`coding_standards.py` is pre-existing, confirmed against `ai/prompt.py` having the identical error
— not something to fix here). Compare via `git checkout HEAD~1 -- <file>` + rerun +
`git checkout HEAD -- <file>` if anything else appears.

```bash
.venv/bin/pytest engine/tests/test_codegen_coding_standards.py engine/tests/test_codegen_system_prompt.py -q
```
Expect: all tests pass (7 original + 2 updated assertions + 4 new + 1 new file = confirm exact
count matches what was actually written).

```bash
.venv/bin/pytest engine/tests -q
```
Expect: full suite passes, same count as before plus the new tests, zero failures.

## Pitfalls

- **The loader bug (step 2) is not optional or cosmetic — it's load-bearing for this entire
  task.** Without it, every `$stg`/`$dest` reference added to the engine-specific sections renders
  as literal text (`Write to $stg.mig_upsert_log` instead of `Write to stg.mig_upsert_log`) in
  whatever a user sees after clicking "Suggest Standards." Confirm the new
  `test_merge_fields_substitute_inside_engine_specific_section` test actually fails if this fix is
  skipped, before considering it done (temporarily revert just the loader change, rerun the test,
  confirm it fails, then reapply the fix).
- **Oracle's `MERGE` genuinely does not support `RETURNING`** — this was confirmed correct while
  drafting this content, not a stylistic choice. Do not "simplify" Oracle's two-statement
  UPDATE/INSERT pattern back into a single `MERGE ... RETURNING` — that would generate SQL that
  fails to compile on real Oracle.
- **MySQL's audit logging is intentionally row-by-row, not set-based**, unlike the other three
  engines — this is a real, called-out limitation of `INSERT ... ON DUPLICATE KEY UPDATE`, not an
  oversight. Don't "fix" it to look more like the other engines' set-based patterns without
  understanding this constraint first.
- **`$$PLSQL_UNIT` in the oracle section is intentional Oracle syntax**, not a typo — `string.Template`
  interprets `$$` as an escaped literal `$`, so after substitution it correctly renders as
  `$PLSQL_UNIT` (real Oracle syntax for the current procedure's own name). Don't "fix" this to
  `$PLSQL_UNIT` in the YAML source — that would make `Template.substitute()` try to look up a
  variable named `PLSQL_UNIT` in the mapping dict and raise a `KeyError` at render time, since it's
  not one of the 3 supplied merge fields.
- **Don't touch `_build_user_prompt`'s own `run_ref` parameter or its call site** — it's a
  separate, still-needed parameter for a different function; only `_build_system_prompt`'s copy of
  this value is being removed.
- **This task does not touch `001es`** (the frontend button wiring) — different files, no
  dependency in either direction. Both can be worked in either order.

## Commit

Own commit. Suggested message: `feat: per-engine audit-trace strategy in coding standards, fix
hardcoded schema names, remove redundant hardcoded system-prompt append (001et)`.
