# Plan: 001er — Extract Codegen Coding Standards Template into a Backend Prompt File (Backend)

## Task and Domain links

- Task: `tasks/001er-extract-codegen-coding-standards-backend.md`
- Design: `docs/superpowers/specs/2026-07-22-codegen-coding-standards-prompt-extraction-design.md`
- Domain: no `docs/domain/` page documents this template — no update required.

## Audience note

Written for an agent with no prior context. Every code block below is exact, ready to use
verbatim. Re-read `web/app/projects/[id]/codegen/page.tsx` lines 81-179 before starting to confirm
`generateCodingStandardsTemplate` still matches what's quoted below — if it's drifted, stop and
reconcile by hand rather than guessing.

## Current State (verbatim)

`web/app/projects/[id]/codegen/page.tsx`, lines 81-179, in full — this is the function being
transcribed into YAML. Read it carefully; every line of text inside the template-literal blocks
must be transcribed exactly, including whitespace/indentation, into the new YAML file:

```tsx
const generateCodingStandardsTemplate = (
  dbEngine: string,
  stagingSchema: string,
  destSchema: string
): string => {
  const engineName = dbEngine || "target database";
  const stg = stagingSchema || "staging";
  const dest = destSchema || "destination";

  let specificStandards = "";
  const lowerEngine = dbEngine?.toLowerCase() || "";
  if (lowerEngine === "postgresql") {
    specificStandards = `
     - Use standard PostgreSQL coding conventions: lowercase identifiers, snake_case for tables/columns, explicit type casting (e.g. ::date, ::integer).
     - Stored procedures/functions should be written in PL/pgSQL using dollar-quoting.`;
  } else if (lowerEngine === "mssql" || lowerEngine === "sqlserver") {
    specificStandards = `
     - Use T-SQL coding conventions: UPPERCASE SQL keywords, square brackets for identifiers only when necessary, proper schema qualifiers.
     - Always use CREATE OR ALTER PROCEDURE, never CREATE PROCEDURE alone. Scripts must be idempotent and runnable multiple times without error.
     - Every CREATE TABLE statement must be idempotent. Use IF OBJECT_ID(N'[schema].[table]', N'U') IS NULL before CREATE TABLE. Never emit an unconditional CREATE TABLE statement.

     **Migration SP Requirements:**
       1. SET XACT_ABORT ON immediately after SET NOCOUNT ON
       2. Validate source table is non-empty before MERGE; THROW if empty. The empty source validation THROW must occur before any MERGE statement executes.
       3. Use THROW not RAISERROR for all error raising (SQL Server 2012+)
       4. Use CAST(COALESCE(inserted.[pk], deleted.[pk]) AS NVARCHAR(255)) for future-safe action logging. The CAST to NVARCHAR(255) is required to match the dest_row_id column type in mig_upsert_log. Use inserted and deleted pseudo-table aliases when logging destination-table column values in the OUTPUT clause. The MERGE source alias may be referenced only for source metadata such as source_row_num. Never use the target alias to retrieve the affected destination row identifier. OUTPUT INTO [oc_stag].[mig_upsert_log] must specify the explicit destination column list: ([run_ref], [dest_table], [source_row_num], [dest_row_id], [action]).
       5. NULL values in source columns flow through unchanged unless destination is NOT NULL
       6. Note index requirements on MERGE join key columns in comments
       7. FK lookups must be resolved via JOIN in MERGE source SELECT, not scalar variables. Every row gets its own resolved FK value.
       8. run_ref must be dynamically generated inside the procedure using OBJECT_NAME(@@PROCID) as the procedure name prefix combined with GETDATE() and NEWID(). Never accept as parameter, never hardcode.
          WRONG:  DECLARE @run_ref = '00000000-0000-4000-8000-...'
          CORRECT: DECLARE @run_ref NVARCHAR(255) = OBJECT_NAME(@@PROCID) + '_' + 
                   CONVERT(NVARCHAR(20), GETDATE(), 120) + '_' + 
                   CAST(NEWID() AS NVARCHAR(36));
       9. Schemas [cxp] and [oc_stag] are assumed to exist. Never create, drop, or alter schemas in procedures or migration scripts.
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
           FROM [oc_stag].[source_table] s
           LEFT JOIN [oc_stag].[lookup_table_1] lk1 
               ON lk1.[code_column] = s.[source_code_column_1]
           LEFT JOIN [oc_stag].[lookup_table_2] lk2 
               ON lk2.[code_column] = s.[source_code_column_2]
           WHERE s.[pk_column] IS NOT NULL
       ) AS source

       Then reference source.resolved_fk1_id and source.resolved_fk2_id in the UPDATE SET and INSERT VALUES clauses instead of the raw source code columns.
       17. Every MERGE statement must include an OUTPUT clause logging to [oc_stag].[mig_upsert_log]. After all MERGEs complete, return a result set with run_ref, rows_inserted, rows_updated, completed_at derived from the log table.
       18. Duplicate source-key checks must be performed for every key or composite key used in the MERGE ON clause before executing MERGE. If duplicate source keys exist, THROW before MERGE. Also validate that required MERGE key columns are not NULL.
       19. Lookup seed data must be idempotent. Never emit unconditional INSERT statements for lookup rows. Use IF NOT EXISTS or INSERT ... WHERE NOT EXISTS so rerunning the script cannot create duplicate lookup values.
       20. For lookup tables created by the script, every business code column used for FK resolution must have a UNIQUE constraint or UNIQUE index.
       21. Before MERGE, validate that every required FK lookup resolved successfully. If a non-NULL source lookup code cannot be resolved to a required destination FK, THROW before executing MERGE. Preserve NULL only when the source value and destination FK are legitimately nullable.`;
  } else if (lowerEngine === "oracle") {
    specificStandards = `
     - Use PL/SQL coding conventions: UPPERCASE keywords/types, clear EXCEPTION blocks, schema-qualified table references.
     - All object names must respect Oracle length limits (max 30 or 128 characters depending on version).`;
  } else if (lowerEngine === "mysql") {
    specificStandards = `
     - Use standard MySQL coding conventions: backticks for reserved word identifiers, snake_case table/column names.
     - Stored procedures should use clear parameter scoping and DELIMITER declarations.`;
  }

  return `### Coding Standards and Guidelines

1. **Schemas and Scoping**:
   - Migration and utility stored procedures must be created under the staging schema, not the destination schema.
   - All destination tables must be created under the "${dest}" schema.
   - All staging and source tables must be read from the "${stg}" schema.
   - All DDL for lookup tables must be created in the "${stg}" schema.

2. **Database Engine Conventions (${engineName})**:
   - Write all DDL and stored procedures complying with the standard coding conventions pertinent to ${engineName}.${specificStandards}

3. **General Best Practices**:
   - Ensure all scripts are repeatable and idempotent. Use SQL Server-compatible idempotent patterns: CREATE OR ALTER for stored procedures and IF OBJECT_ID(...) IS NULL for tables. Do not drop and recreate persistent tables merely to make a script repeatable.
   - Use explicit column lists in all INSERT statements.
   - Do not hardcode environment-specific values. Do not create arbitrary default timestamps for business data columns. Database-managed audit columns, such as migration-log timestamps, may use an appropriate default when explicitly required by the schema.`;
};
```

Note the exact concatenation shape at `` `...pertinent to ${engineName}.${specificStandards}` `` —
`specificStandards`, when non-empty, is a string that **starts with its own leading newline**
(`` `\n     - Use ...` ``), so it appends directly onto the end of that sentence with no extra
blank line. When `specificStandards` is empty (unrecognized/no engine), the sentence just ends
with a period and nothing after it.

`routes/projects.py`, lines 55-63 (the reference pattern for the new GET endpoint — same
`require_project_access` + `get_current_user` shape):

```python
@router.get("/{project_id}", response_model=ProjectResponse)
def get_project_by_id(
    project_id: str,
    actor: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ProjectResponse:
    require_project_access(db, user=actor, project_id=project_id)
    return get_project(db, project_id=project_id)
```

`api/schemas.py`, line 107 (the exact valid engine values — already lowercase):

```python
TargetDbEngine = Literal["mssql", "oracle", "postgresql", "mysql"]
```

`management/projects.py`, line 157-159 (`get_project`, already imported into `routes/projects.py`):

```python
def get_project(db: Session, *, project_id: str) -> ProjectResponse:
    registry, definition = _get_project_rows(db, project_id)
    return _project_response(registry, definition)
```

`ai/prompt.py`, in full (the existing `Prompt` class — quoted so the new loader's style can match
its conventions without literally reusing its code, per the task's explicit decision not to extend
this class):

```python
import logging
import yaml
from pathlib import Path
from string import Template

_LOGGER = logging.getLogger(__name__)
_PROMPTS_DIR = Path(__file__).parent / "prompts"

class _WarnOnMissing(dict[str, str]):
    def __init__(self, name: str, mapping: dict[str, str]) -> None:
        super().__init__(mapping)
        self._name = name

    def __missing__(self, key: str) -> str:
        _LOGGER.warning("Missing prompt field '%s' in prompt '%s'", key, self._name)
        return ""

class Prompt:
    def __init__(self, name: str) -> None:
        self._name = name
        path = _PROMPTS_DIR / f"{name}.yaml"
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        self._system = data["system"]
        self._user = data["user"]
        self._fields: dict[str, str] = {}

    def set(self, **kwargs: str) -> "Prompt":
        self._fields.update(kwargs)
        return self

    def get_prompt(self) -> tuple[str, str]:
        mapping = _WarnOnMissing(self._name, self._fields)
        system = Template(self._system).substitute(mapping).strip()
        user = Template(self._user).substitute(mapping).strip()
        return system, user
```

## Objective

1. Create `engine/src/migrations_engine/ai/prompts/codegen_coding_standards.yaml` transcribing the
   content above.
2. Create a small loader function that renders it, producing output identical to
   `generateCodingStandardsTemplate`'s current behavior for every engine value.
3. Create the new `GET /projects/{project_id}/codegen-coding-standards-template` endpoint.

## File Changes

### 1. New file: `engine/src/migrations_engine/ai/prompts/codegen_coding_standards.yaml`

Create this file with exactly this content. **This exact content has already been verified**: it
was generated programmatically from the original JS template, loaded back with `yaml.safe_load`,
run through the loader function in step 2 below, and compared byte-for-byte against
`generateCodingStandardsTemplate`'s actual output for `mssql`, `postgresql`, and the
no-engine-specified case — all three matched exactly. Copy it verbatim, including the exact number
of spaces on every line (the `mssql`/`postgresql`/`oracle`/`mysql` sections use the explicit YAML
block-scalar indentation indicator `|2`, and their content lines have **7 leading spaces** — 2 for
the indicator plus the original 5-space indentation from the JS template — do not "clean up" or
reduce this indentation, it is intentional and verified):

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

mssql: |2
       - Use T-SQL coding conventions: UPPERCASE SQL keywords, square brackets for identifiers only when necessary, proper schema qualifiers.
       - Always use CREATE OR ALTER PROCEDURE, never CREATE PROCEDURE alone. Scripts must be idempotent and runnable multiple times without error.
       - Every CREATE TABLE statement must be idempotent. Use IF OBJECT_ID(N'[schema].[table]', N'U') IS NULL before CREATE TABLE. Never emit an unconditional CREATE TABLE statement.

       **Migration SP Requirements:**
         1. SET XACT_ABORT ON immediately after SET NOCOUNT ON
         2. Validate source table is non-empty before MERGE; THROW if empty. The empty source validation THROW must occur before any MERGE statement executes.
         3. Use THROW not RAISERROR for all error raising (SQL Server 2012+)
         4. Use CAST(COALESCE(inserted.[pk], deleted.[pk]) AS NVARCHAR(255)) for future-safe action logging. The CAST to NVARCHAR(255) is required to match the dest_row_id column type in mig_upsert_log. Use inserted and deleted pseudo-table aliases when logging destination-table column values in the OUTPUT clause. The MERGE source alias may be referenced only for source metadata such as source_row_num. Never use the target alias to retrieve the affected destination row identifier. OUTPUT INTO [oc_stag].[mig_upsert_log] must specify the explicit destination column list: ([run_ref], [dest_table], [source_row_num], [dest_row_id], [action]).
         5. NULL values in source columns flow through unchanged unless destination is NOT NULL
         6. Note index requirements on MERGE join key columns in comments
         7. FK lookups must be resolved via JOIN in MERGE source SELECT, not scalar variables. Every row gets its own resolved FK value.
         8. run_ref must be dynamically generated inside the procedure using OBJECT_NAME(@@PROCID) as the procedure name prefix combined with GETDATE() and NEWID(). Never accept as parameter, never hardcode.
            WRONG:  DECLARE @run_ref = '00000000-0000-4000-8000-...'
            CORRECT: DECLARE @run_ref NVARCHAR(255) = OBJECT_NAME(@@PROCID) + '_' + 
                     CONVERT(NVARCHAR(20), GETDATE(), 120) + '_' + 
                     CAST(NEWID() AS NVARCHAR(36));
         9. Schemas [cxp] and [oc_stag] are assumed to exist. Never create, drop, or alter schemas in procedures or migration scripts.
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
             FROM [oc_stag].[source_table] s
             LEFT JOIN [oc_stag].[lookup_table_1] lk1 
                 ON lk1.[code_column] = s.[source_code_column_1]
             LEFT JOIN [oc_stag].[lookup_table_2] lk2 
                 ON lk2.[code_column] = s.[source_code_column_2]
             WHERE s.[pk_column] IS NOT NULL
         ) AS source

         Then reference source.resolved_fk1_id and source.resolved_fk2_id in the UPDATE SET and INSERT VALUES clauses instead of the raw source code columns.
         17. Every MERGE statement must include an OUTPUT clause logging to [oc_stag].[mig_upsert_log]. After all MERGEs complete, return a result set with run_ref, rows_inserted, rows_updated, completed_at derived from the log table.
         18. Duplicate source-key checks must be performed for every key or composite key used in the MERGE ON clause before executing MERGE. If duplicate source keys exist, THROW before MERGE. Also validate that required MERGE key columns are not NULL.
         19. Lookup seed data must be idempotent. Never emit unconditional INSERT statements for lookup rows. Use IF NOT EXISTS or INSERT ... WHERE NOT EXISTS so rerunning the script cannot create duplicate lookup values.
         20. For lookup tables created by the script, every business code column used for FK resolution must have a UNIQUE constraint or UNIQUE index.
         21. Before MERGE, validate that every required FK lookup resolved successfully. If a non-NULL source lookup code cannot be resolved to a required destination FK, THROW before executing MERGE. Preserve NULL only when the source value and destination FK are legitimately nullable.

oracle: |2
       - Use PL/SQL coding conventions: UPPERCASE keywords/types, clear EXCEPTION blocks, schema-qualified table references.
       - All object names must respect Oracle length limits (max 30 or 128 characters depending on version).

mysql: |2
       - Use standard MySQL coding conventions: backticks for reserved word identifiers, snake_case table/column names.
       - Stored procedures should use clear parameter scoping and DELIMITER declarations.
```

After creating the file, verify with:
```bash
.venv/bin/python -c "
import yaml
d = yaml.safe_load(open('engine/src/migrations_engine/ai/prompts/codegen_coding_standards.yaml').read())
print(repr(d['postgresql'][:10]))
print(repr(d['mssql'][:10]))
"
```
Expect both to print `'     - Use'` (5 leading spaces, then `- Use`) — if either prints `'- Use'`
(0 leading spaces) or fewer/more than 5 spaces, the file's indentation doesn't match what was
verified and must be fixed before continuing.

### 2. New file: `engine/src/migrations_engine/codegen/coding_standards.py`

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

Note precisely how this reproduces the original JS behavior:
- `lowerEngine === "mssql" || lowerEngine === "sqlserver"` in the JS maps to both keys resolving to
  the same `mssql` YAML section — the `engine_key` line above handles that alias.
- The JS's `` `...pertinent to ${engineName}.${specificStandards}` `` concatenation (engine block
  appended directly onto the header's last line, with the engine block's own leading `\n`
  supplying the line break) is reproduced by `header + "\n" + specific.rstrip("\n")` — the explicit
  `"\n"` here does the same job the JS string's implicit leading newline did there. The YAML
  section content itself starts directly at `     - Use T-SQL...` (5 leading spaces, preserved via
  the `|2` indentation indicator, no separate leading blank line needed in the YAML source) — this
  was verified to reproduce the JS output byte-for-byte, see the note under step 1.
- When `specific` is empty (unrecognized engine), `header` is used as-is (matching the JS, where
  `specificStandards` being `""` means nothing gets appended after the period).

### 3. `engine/src/migrations_engine/api/schemas.py`

Add a new response model. Find the `MigrationProjectConfig` class (around line 177, quoted above
under Current State) and add this new class immediately after it, before the next class:

```python
class CodegenCodingStandardsTemplateResponse(BaseModel):
    template: str
```

### 4. `engine/src/migrations_engine/routes/projects.py`

Add the new import. Find this line (quoted in full above under Current State):

```python
from ..api.schemas import (
    MembershipResponse,
    ProjectCreateRequest,
    ProjectMemberResponse,
    ProjectResponse,
    ProjectUpdateRequest,
    ProjectCopyRequest,
    AssignProjectManagerRequest,
    CodegenInstructionsRequest,
)
```

Replace with:

```python
from ..api.schemas import (
    CodegenCodingStandardsTemplateResponse,
    MembershipResponse,
    ProjectCreateRequest,
    ProjectMemberResponse,
    ProjectResponse,
    ProjectUpdateRequest,
    ProjectCopyRequest,
    AssignProjectManagerRequest,
    CodegenInstructionsRequest,
)
```

Add a new import for the loader, right after the existing `from ..management.projects import ...`
line:

```python
from ..codegen.coding_standards import render_coding_standards_template
```

Add the new route. Find this exact block (quoted in full above under Current State — the
`patch_codegen_instructions` route, the last route in the file):

```python
@router.patch("/{project_id}/codegen-instructions", response_model=ProjectResponse)
def patch_codegen_instructions(
    project_id: str,
    body: CodegenInstructionsRequest,
    actor: User = Depends(get_central_team_user),
    db: Session = Depends(get_db),
) -> ProjectResponse:
    require_project_access(db, user=actor, project_id=project_id)
    return update_project(
        db,
        actor=actor,
        project_id=project_id,
        body=ProjectUpdateRequest(codegen_instructions=body.codegen_instructions),
    )
```

Add this new route immediately after it (same file, end of file):

```python


@router.get("/{project_id}/codegen-coding-standards-template", response_model=CodegenCodingStandardsTemplateResponse)
def get_codegen_coding_standards_template(
    project_id: str,
    actor: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CodegenCodingStandardsTemplateResponse:
    require_project_access(db, user=actor, project_id=project_id)
    project = get_project(db, project_id=project_id)
    config = project.domain_config
    template = render_coding_standards_template(
        db_engine=config.target_db_engine if config else None,
        staging_schema=config.staging_schema if config else None,
        destination_schema=config.destination_schema if config else None,
    )
    return CodegenCodingStandardsTemplateResponse(template=template)
```

## Tests

Add to a new file `engine/tests/test_codegen_coding_standards.py` — unit tests for the loader,
independent of any API/DB setup (the loader takes plain strings, no session needed):

```python
from migrations_engine.codegen.coding_standards import render_coding_standards_template


def test_mssql_standards_include_engine_specific_block():
    result = render_coding_standards_template(
        db_engine="mssql", staging_schema="stg", destination_schema="cxp"
    )
    assert '"cxp" schema' in result
    assert '"stg" schema' in result
    assert "Database Engine Conventions (mssql)" in result
    assert "SET XACT_ABORT ON immediately after SET NOCOUNT ON" in result
    assert "General Best Practices" in result


def test_sqlserver_alias_resolves_to_mssql_block():
    result = render_coding_standards_template(
        db_engine="sqlserver", staging_schema="stg", destination_schema="cxp"
    )
    assert "SET XACT_ABORT ON immediately after SET NOCOUNT ON" in result


def test_postgresql_standards_include_engine_specific_block():
    result = render_coding_standards_template(
        db_engine="postgresql", staging_schema="stg", destination_schema="cxp"
    )
    assert "PL/pgSQL using dollar-quoting" in result
    assert "SET XACT_ABORT" not in result


def test_mysql_standards_include_engine_specific_block():
    result = render_coding_standards_template(
        db_engine="mysql", staging_schema="stg", destination_schema="cxp"
    )
    assert "DELIMITER declarations" in result


def test_oracle_standards_include_engine_specific_block():
    result = render_coding_standards_template(
        db_engine="oracle", staging_schema="stg", destination_schema="cxp"
    )
    assert "Oracle length limits" in result


def test_unrecognized_engine_falls_back_to_shared_sections_only():
    result = render_coding_standards_template(
        db_engine="sqlite", staging_schema="stg", destination_schema="cxp"
    )
    assert "Database Engine Conventions (sqlite)" in result
    assert "General Best Practices" in result
    assert "SET XACT_ABORT" not in result
    assert "PL/pgSQL" not in result


def test_missing_config_falls_back_to_default_placeholder_names():
    result = render_coding_standards_template(
        db_engine=None, staging_schema=None, destination_schema=None
    )
    assert '"destination" schema' in result
    assert '"staging" schema' in result
    assert "Database Engine Conventions (target database)" in result
```

Add to `engine/tests/test_project_crud_api.py` (confirmed the right file — no existing test in
this codebase currently exercises `/codegen-instructions` or any other `/{project_id}/codegen-*`
route at all: `grep -rln "codegen-instructions\|codegen_instructions" engine/tests/*.py` returns
nothing). Use the file's own `_create_project(token, body)` helper (defined at line 95 as of this
writing: `response = client.post("/projects", ..., json=body); return response.json()`) — it
returns the created project's JSON, including `project["project_id"]`:

```python
def test_get_codegen_coding_standards_template(admin_token: str) -> None:
    project = _create_project(
        admin_token,
        {
            "name": "Codegen Standards Test",
            "domain_config": {
                "target_db_engine": "postgresql",
                "staging_schema": "stg",
                "destination_schema": "cxp",
            },
        },
    )

    response = client.get(
        f"/projects/{project['project_id']}/codegen-coding-standards-template",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200, response.text
    assert "PL/pgSQL using dollar-quoting" in response.json()["template"]
    assert '"cxp" schema' in response.json()["template"]
```

## Verification

```bash
cd /Users/vjkotra/projects/katana
.venv/bin/ruff check engine/src/migrations_engine/codegen/coding_standards.py engine/src/migrations_engine/routes/projects.py engine/src/migrations_engine/api/schemas.py engine/tests/test_codegen_coding_standards.py
```
Expect: `All checks passed!`

```bash
.venv/bin/python -m mypy engine/src/migrations_engine/codegen/coding_standards.py engine/src/migrations_engine/routes/projects.py --strict
```
Expect: no new errors versus the pre-existing baseline (compare via `git checkout HEAD~1 -- <file>`
+ rerun + `git checkout HEAD -- <file>`, as done for every prior task this session).

```bash
.venv/bin/pytest engine/tests/test_codegen_coding_standards.py -q
```
Expect: all 7 tests pass.

```bash
.venv/bin/pytest engine/tests -q
```
Expect: full suite passes, same count as before plus the new tests.

## Pitfalls

- **YAML indentation must be exact.** A block scalar's content is everything indented deeper than
  the key line; get the relative indentation wrong and the mssql block's nested numbered items
  (which have their own extra indentation in the original JS) will load with wrong/missing
  whitespace. Verify with the `yaml.safe_load` spot-check command given in step 1 before moving on.
- **The `sqlserver` alias.** The original JS treats `"mssql"` and `"sqlserver"` as the same engine
  (`lowerEngine === "mssql" || lowerEngine === "sqlserver"`) even though `sqlserver` isn't a valid
  `TargetDbEngine` value in the schema (`Literal["mssql", "oracle", "postgresql", "mysql"]`) — it's
  legacy defensiveness. Preserve it anyway (the loader code above already does, via `engine_key =
  "mssql" if lower_engine == "sqlserver" else lower_engine`) since some already-stored project data
  might still have that value.
- **Do not touch `page.tsx`.** This task is backend-only — `generateCodingStandardsTemplate` still
  exists and is still called by the button until `001es` lands. Leave it alone.
- **The endpoint reads `domain_config` via `get_project`'s already-validated
  `MigrationProjectConfig`**, not raw `ProjectDefinition.domain_config` dict access — this matches
  how `codegen/service.py` already validates domain_config elsewhere
  (`MigrationProjectConfig.model_validate(project_definition.domain_config or {})`) rather than
  reading raw dict keys with manual `.get()` calls.

## Commit

Own commit, before `001es`. Suggested message: `feat: extract codegen coding standards template
into a backend prompt file (001er)`.
