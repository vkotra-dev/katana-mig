# Plan: 001eu — Make mig_upsert_log DDL Injection Engine-Aware

## Task and Domain links

- Task: `tasks/001eu-engine-aware-mig-upsert-log-ddl.md`
- Domain: no `docs/domain/` page documents this — no update required.

## Audience note

Written for an agent with no prior context. Every edit gives exact current text and exact
replacement. Re-read `engine/src/migrations_engine/codegen/service.py` lines 449-474 and
`engine/tests/codegen/test_bundle_logging.py` in full immediately before starting to confirm they
still match what's quoted below.

## Current State (verbatim)

`engine/src/migrations_engine/codegen/service.py`, lines 449-474 (`_mig_upsert_log_ddl` and
`_assemble_sql_bundle`, in full — this is the only place either function is defined, and each has
exactly one caller: `_assemble_sql_bundle` is called once at line 185; `_mig_upsert_log_ddl` is
called once, from inside `_assemble_sql_bundle` — confirmed via
`grep -rn "_assemble_sql_bundle\|_mig_upsert_log_ddl" engine/src engine/tests`):

```python
def _mig_upsert_log_ddl(staging_schema: str) -> str:
    return (
        f"IF OBJECT_ID(N'[{staging_schema}].[mig_upsert_log]', N'U') IS NULL\n"
        f"BEGIN\n"
        f"    CREATE TABLE [{staging_schema}].[mig_upsert_log] (\n"
        f"        [log_id]         BIGINT IDENTITY(1,1) PRIMARY KEY,\n"
        f"        [run_ref]        NVARCHAR(255) NOT NULL,\n"
        f"        [dest_table]     NVARCHAR(255) NOT NULL,\n"
        f"        [source_row_num] BIGINT        NULL,\n"
        f"        [dest_row_id]    NVARCHAR(255) NULL,\n"
        f"        [action]         NVARCHAR(10)  NOT NULL,\n"
        f"        [logged_at]      DATETIME2(0)  NOT NULL DEFAULT GETDATE()\n"
        f"    );\n"
        f"END;"
    )


def _assemble_sql_bundle(generated_sql: GeneratedSQL, *, staging_schema: str | None = None) -> str:
    parts: list[str] = []
    if staging_schema:
        parts.append(_mig_upsert_log_ddl(staging_schema))
    parts.append(generated_sql.staging_ddl.strip())
    parts.extend(s.strip() for s in generated_sql.lookup_ddl if s.strip())
    parts.extend(s.strip() for s in generated_sql.seed_data if s.strip())
    parts.extend(s.strip() for s in generated_sql.stored_procedures if s.strip())
    return "\n\nGO\n\n".join(parts).strip()
```

The single call site, `service.py:185` (1 line, inside `generate_codegen_artifact` — `project_config`,
a `MigrationProjectConfig` with `.target_db_engine`, is already in scope at this point in the
function, confirmed by reading the surrounding function body):

```python
    sql_bundle = _assemble_sql_bundle(generated_sql, staging_schema=project_config.staging_schema)
```

`engine/tests/codegen/test_bundle_logging.py`, in full (post-`001et`'s cleanup — 3 tests, none
currently pass an engine, all assert MSSQL-specific syntax):

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

## Objective

1. `_mig_upsert_log_ddl` produces correct, idiomatic DDL for whichever engine is passed in
   (mssql/postgresql/mysql/oracle), defaulting to mssql when the engine is `None` or unrecognized
   — this preserves exact backward-compatible behavior for any existing project that hasn't set
   `target_db_engine` yet, since the function's only historical behavior was MSSQL-shaped SQL.
2. `_assemble_sql_bundle` accepts and forwards the engine.
3. The call site passes `project_config.target_db_engine` through.
4. Existing 3 tests updated to explicitly pass `db_engine="mssql"` (matching what they actually
   assert), plus new tests for postgresql/mysql/oracle and the None-defaults-to-mssql case.

## File Changes

### `engine/src/migrations_engine/codegen/service.py`

Find the exact block quoted above under "Current State" (`_mig_upsert_log_ddl` and
`_assemble_sql_bundle` together) and replace it with:

```python
def _mig_upsert_log_ddl(staging_schema: str, db_engine: str | None = None) -> str:
    lower_engine = (db_engine or "").lower()
    engine_key = "mssql" if lower_engine == "sqlserver" else lower_engine

    if engine_key == "postgresql":
        return (
            f"CREATE TABLE IF NOT EXISTS {staging_schema}.mig_upsert_log (\n"
            f"    log_id         BIGSERIAL PRIMARY KEY,\n"
            f"    run_ref        VARCHAR(255) NOT NULL,\n"
            f"    dest_table     VARCHAR(255) NOT NULL,\n"
            f"    source_row_num BIGINT,\n"
            f"    dest_row_id    VARCHAR(255),\n"
            f"    action         VARCHAR(10) NOT NULL,\n"
            f"    logged_at      TIMESTAMP NOT NULL DEFAULT clock_timestamp()\n"
            f");"
        )
    if engine_key == "mysql":
        return (
            f"CREATE TABLE IF NOT EXISTS {staging_schema}.mig_upsert_log (\n"
            f"    log_id         BIGINT AUTO_INCREMENT PRIMARY KEY,\n"
            f"    run_ref        VARCHAR(255) NOT NULL,\n"
            f"    dest_table     VARCHAR(255) NOT NULL,\n"
            f"    source_row_num BIGINT,\n"
            f"    dest_row_id    VARCHAR(255),\n"
            f"    action         VARCHAR(10) NOT NULL,\n"
            f"    logged_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP\n"
            f");"
        )
    if engine_key == "oracle":
        return (
            f"BEGIN\n"
            f"    EXECUTE IMMEDIATE 'CREATE TABLE {staging_schema}.mig_upsert_log (\n"
            f"        log_id         NUMBER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,\n"
            f"        run_ref        VARCHAR2(255) NOT NULL,\n"
            f"        dest_table     VARCHAR2(255) NOT NULL,\n"
            f"        source_row_num NUMBER,\n"
            f"        dest_row_id    VARCHAR2(255),\n"
            f"        action         VARCHAR2(10) NOT NULL,\n"
            f"        logged_at      TIMESTAMP DEFAULT SYSTIMESTAMP NOT NULL\n"
            f"    )';\n"
            f"EXCEPTION\n"
            f"    WHEN OTHERS THEN\n"
            f"        IF SQLCODE != -955 THEN RAISE; END IF; -- ORA-00955: name already used by an existing object\n"
            f"END;"
        )
    # mssql, and the default for None/unrecognized engines (preserves this function's original,
    # only-ever-MSSQL behavior for any project that hasn't set target_db_engine yet).
    return (
        f"IF OBJECT_ID(N'[{staging_schema}].[mig_upsert_log]', N'U') IS NULL\n"
        f"BEGIN\n"
        f"    CREATE TABLE [{staging_schema}].[mig_upsert_log] (\n"
        f"        [log_id]         BIGINT IDENTITY(1,1) PRIMARY KEY,\n"
        f"        [run_ref]        NVARCHAR(255) NOT NULL,\n"
        f"        [dest_table]     NVARCHAR(255) NOT NULL,\n"
        f"        [source_row_num] BIGINT        NULL,\n"
        f"        [dest_row_id]    NVARCHAR(255) NULL,\n"
        f"        [action]         NVARCHAR(10)  NOT NULL,\n"
        f"        [logged_at]      DATETIME2(0)  NOT NULL DEFAULT GETDATE()\n"
        f"    );\n"
        f"END;"
    )


def _assemble_sql_bundle(
    generated_sql: GeneratedSQL, *, staging_schema: str | None = None, db_engine: str | None = None
) -> str:
    parts: list[str] = []
    if staging_schema:
        parts.append(_mig_upsert_log_ddl(staging_schema, db_engine))
    parts.append(generated_sql.staging_ddl.strip())
    parts.extend(s.strip() for s in generated_sql.lookup_ddl if s.strip())
    parts.extend(s.strip() for s in generated_sql.seed_data if s.strip())
    parts.extend(s.strip() for s in generated_sql.stored_procedures if s.strip())
    return "\n\nGO\n\n".join(parts).strip()
```

Find the exact call site quoted above under "Current State":

```python
    sql_bundle = _assemble_sql_bundle(generated_sql, staging_schema=project_config.staging_schema)
```

Replace with:

```python
    sql_bundle = _assemble_sql_bundle(
        generated_sql, staging_schema=project_config.staging_schema, db_engine=project_config.target_db_engine
    )
```

## Tests

Replace `engine/tests/codegen/test_bundle_logging.py` in full (find the exact current content
quoted above under "Current State" and replace it with):

```python
from migrations_engine.codegen.service import _assemble_sql_bundle, GeneratedSQL


def make_sql(ddl="CREATE TABLE [stg].[t] ([id] INT);", views=None):
    return GeneratedSQL(staging_ddl=ddl, lookup_ddl=[], seed_data=[], stored_procedures=[], views=views or [])


def test_log_table_prepended_when_staging_schema_set():
    bundle = _assemble_sql_bundle(make_sql(), staging_schema="oc_stag", db_engine="mssql")
    assert "mig_upsert_log" in bundle
    assert bundle.index("mig_upsert_log") < bundle.index("CREATE TABLE [stg].[t]")


def test_log_table_omitted_when_staging_schema_none():
    bundle = _assemble_sql_bundle(make_sql(), staging_schema=None, db_engine="mssql")
    assert "mig_upsert_log" not in bundle


def test_if_not_exists_guard_present():
    bundle = _assemble_sql_bundle(make_sql(), staging_schema="oc_stag", db_engine="mssql")
    assert "IF OBJECT_ID" in bundle
    assert "IS NULL" in bundle


def test_unset_engine_defaults_to_mssql_ddl():
    bundle = _assemble_sql_bundle(make_sql(), staging_schema="oc_stag", db_engine=None)
    assert "IF OBJECT_ID" in bundle
    assert "IDENTITY(1,1)" in bundle


def test_postgresql_uses_create_table_if_not_exists():
    bundle = _assemble_sql_bundle(make_sql(), staging_schema="stg", db_engine="postgresql")
    assert "CREATE TABLE IF NOT EXISTS stg.mig_upsert_log" in bundle
    assert "BIGSERIAL" in bundle
    assert "IF OBJECT_ID" not in bundle


def test_mysql_uses_create_table_if_not_exists():
    bundle = _assemble_sql_bundle(make_sql(), staging_schema="stg", db_engine="mysql")
    assert "CREATE TABLE IF NOT EXISTS stg.mig_upsert_log" in bundle
    assert "AUTO_INCREMENT" in bundle
    assert "IF OBJECT_ID" not in bundle


def test_oracle_uses_execute_immediate_guard():
    bundle = _assemble_sql_bundle(make_sql(), staging_schema="stg", db_engine="oracle")
    assert "EXECUTE IMMEDIATE" in bundle
    assert "GENERATED ALWAYS AS IDENTITY" in bundle
    assert "ORA-00955" in bundle
    assert "IF OBJECT_ID" not in bundle


def test_sqlserver_alias_resolves_to_mssql_ddl():
    bundle = _assemble_sql_bundle(make_sql(), staging_schema="oc_stag", db_engine="sqlserver")
    assert "IF OBJECT_ID" in bundle
```

## Verification

```bash
cd /Users/vjkotra/projects/katana
.venv/bin/ruff check engine/src/migrations_engine/codegen/service.py engine/tests/codegen/test_bundle_logging.py
```
Expect: `All checks passed!`

```bash
.venv/bin/python -m mypy engine/src/migrations_engine/codegen/service.py --strict
```
Expect: no new errors versus the pre-existing baseline (the two `Row[tuple[...]]` errors on
`_build_user_prompt`'s call are pre-existing, confirmed multiple times already this session via
`git checkout HEAD~1` comparison — not something to fix here).

```bash
.venv/bin/pytest engine/tests/codegen/test_bundle_logging.py -q
```
Expect: all 8 tests pass.

```bash
.venv/bin/pytest engine/tests -q
```
Expect: full suite passes, same count as before plus the 5 new tests, zero failures.

## Pitfalls

- **Default to mssql when `db_engine` is `None` or unrecognized — do not default to "no DDL" or
  raise an error.** This function's entire historical behavior was unconditionally MSSQL-shaped;
  any existing project that hasn't set `target_db_engine` must keep getting the same DDL it always
  got. Changing this default would silently break codegen for those projects.
- **Oracle's guard uses `EXECUTE IMMEDIATE` + a `SQLCODE != -955` check, matching the identical
  pattern already established in `001et`'s coding-standards YAML content for Oracle's idempotent
  `CREATE TABLE`** — reuse this exact pattern rather than inventing a different one, for
  consistency between what the AI is told to do (in the coding standards) and what the code
  actually does here.
- **`_mig_upsert_log_ddl`'s `db_engine` parameter has a default of `None`** so any other future
  caller that doesn't pass it explicitly still gets the safe mssql fallback rather than a
  `TypeError` for a missing required argument.
- **Do not change the column names/types within an engine's DDL** beyond what's needed for that
  engine's actual valid syntax — the column set (`log_id`, `run_ref`, `dest_table`,
  `source_row_num`, `dest_row_id`, `action`, `logged_at`) must stay consistent across all four
  engines, matching the same conceptual audit table described in `001et`'s coding standards content
  for each engine.

## Commit

Own commit. Suggested message: `fix: make mig_upsert_log DDL injection engine-aware, not
MSSQL-only (001eu)`.
