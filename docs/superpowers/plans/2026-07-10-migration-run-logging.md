# Migration Run Logging — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Every SQL bundle includes a `mig_upsert_log` table in the staging schema. Every stored proc upsert writes a row to it via `MERGE … OUTPUT`, capturing source row number, destination row ID, destination table, and action — enabling row counts per table mapping fiber and full source→destination lineage.

**Architecture:** Two changes to `codegen/service.py`: (1) `_assemble_sql_bundle()` prepends a static `mig_upsert_log` CREATE block (IF NOT EXISTS, once per project); (2) `_build_system_prompt()` gains a logging instruction block telling the AI to add `_row_num IDENTITY` to staging tables and use `MERGE … OUTPUT` into `mig_upsert_log` for every upsert. No Alembic migration — `mig_upsert_log` lives in the destination SQL Server staging schema, not in Katana's MySQL DB.

**Tech Stack:** Python (codegen service), SQL Server T-SQL (generated bundle output).

## Global Constraints

- `mig_upsert_log` lives in `{staging_schema}` on the destination SQL Server — not in Katana's MySQL
- Table creation uses `IF OBJECT_ID(...) IS NULL` guard — append-only, never dropped
- `run_ref` is baked as a string literal at codegen time: `'{project_id}_{source_definition_id}'`
- `_row_num BIGINT IDENTITY(1,1)` must be the first column of every generated staging table
- The `OUTPUT` clause references `src._row_num` (from the MERGE source alias) and `inserted.<pk>` (destination PK)
- One `mig_upsert_log` table per project bundle — multiple procs (one per destination table) all write to the same table

---

## File Map

| File | Action | Purpose |
|---|---|---|
| `engine/src/migrations_engine/codegen/service.py` | Modify | Prepend log table DDL in bundle; add logging instructions to system prompt |
| `engine/tests/codegen/test_bundle_logging.py` | Create | Tests for log table presence and prompt instructions |

---

### Task 1: Prepend `mig_upsert_log` DDL to every bundle

**Files:**
- Modify: `engine/src/migrations_engine/codegen/service.py:381-388` (`_assemble_sql_bundle`)

**Interfaces:**
- Consumes: `project_config.staging_schema: str | None` (already available in `generate_codegen_artifact`)
- Produces: every bundle starts with `mig_upsert_log` CREATE block

- [ ] **Step 1: Add a helper that generates the log table DDL**

In `engine/src/migrations_engine/codegen/service.py`, add before `_assemble_sql_bundle`:

```python
def _mig_upsert_log_ddl(staging_schema: str) -> str:
    return f"""\
IF OBJECT_ID(N'[{staging_schema}].[mig_upsert_log]', N'U') IS NULL
BEGIN
    CREATE TABLE [{staging_schema}].[mig_upsert_log] (
        [log_id]         BIGINT IDENTITY(1,1) PRIMARY KEY,
        [run_ref]        NVARCHAR(255) NOT NULL,
        [dest_table]     NVARCHAR(255) NOT NULL,
        [source_row_num] BIGINT        NULL,
        [dest_row_id]    NVARCHAR(255) NULL,
        [action]         NVARCHAR(10)  NOT NULL,
        [logged_at]      DATETIME2(0)  NOT NULL DEFAULT GETDATE()
    );
END;
GO"""
```

- [ ] **Step 2: Update `_assemble_sql_bundle` to accept `staging_schema` and prepend the block**

Change the signature and body:

```python
def _assemble_sql_bundle(generated_sql: GeneratedSQL, *, staging_schema: str | None) -> str:
    bundle_parts = []
    if staging_schema:
        bundle_parts.append(_mig_upsert_log_ddl(staging_schema))
    bundle_parts.append(generated_sql.staging_table_ddl.strip())
    bundle_parts.extend(view.strip() for view in generated_sql.views if view.strip())
    return "\n\nGO\n\n".join(p for p in bundle_parts if p).strip()
```

- [ ] **Step 3: Update the call site in `generate_codegen_artifact`**

Find the call to `_assemble_sql_bundle` (currently `_assemble_sql_bundle(generated_sql)`). Pass `staging_schema`:

```python
sql_bundle = _assemble_sql_bundle(generated_sql, staging_schema=project_config.staging_schema)
```

- [ ] **Step 4: Write a test**

Create `engine/tests/codegen/test_bundle_logging.py`:

```python
from migrations_engine.codegen.service import _assemble_sql_bundle, GeneratedSQL


def make_sql(ddl="CREATE TABLE [stg].[t] ([id] INT);", views=None):
    return GeneratedSQL(staging_table_ddl=ddl, views=views or [])


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

- [ ] **Step 5: Run tests**

```bash
cd engine && python -m pytest tests/codegen/test_bundle_logging.py -v
```

Expected: all 3 tests pass.

- [ ] **Step 6: Commit**

```bash
git add engine/src/migrations_engine/codegen/service.py \
        engine/tests/codegen/test_bundle_logging.py
git commit -m "feat: prepend mig_upsert_log DDL to every generated SQL bundle"
```

---

### Task 2: Inject run logging instructions into the system prompt

**Files:**
- Modify: `engine/src/migrations_engine/codegen/service.py:387-393` (`_build_system_prompt`)

**Interfaces:**
- Consumes: `project_id: str`, `source_definition_id: str`, `project_config.staging_schema: str | None` — all already available in `generate_codegen_artifact`
- Produces: system prompt instructs AI to add `_row_num` to staging table and use MERGE+OUTPUT

- [ ] **Step 1: Extend `_build_system_prompt` signature**

`_build_system_prompt` currently receives `project_config` and `destination_object_name`. Add two more keyword-only params:

```python
def _build_system_prompt(
    *,
    project_config: MigrationProjectConfig,
    destination_object_name: str,
    codegen_instructions: str | None,       # already added by 001cn
    run_ref: str,                            # NEW: '{project_id}_{source_definition_id}'
) -> str:
```

- [ ] **Step 2: Append the run logging instruction block**

Inside `_build_system_prompt`, after the existing `GLOBAL CODING STANDARDS` block (from 001cn), append:

```python
    parts.append("")
    parts.append("RUN LOGGING REQUIREMENTS")
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
```

- [ ] **Step 3: Update the call site**

In `generate_codegen_artifact`, pass `run_ref` to `_build_system_prompt`:

```python
run_ref = f"{project_id}_{source_definition_id}"
system=_build_system_prompt(
    project_config=project_config,
    destination_object_name=destination_object_name,
    codegen_instructions=project_definition.codegen_instructions,
    run_ref=run_ref,
),
```

- [ ] **Step 4: Write a test**

In `engine/tests/codegen/test_bundle_logging.py`, add:

```python
from migrations_engine.codegen.service import _build_system_prompt
from migrations_engine.api.schemas import MigrationProjectConfig


def test_system_prompt_includes_run_logging_block():
    config = MigrationProjectConfig(
        target_db_engine="sqlserver",
        staging_schema="oc_stag",
        destination_schema="dbo",
    )
    prompt = _build_system_prompt(
        project_config=config,
        destination_object_name="policy_claims",
        codegen_instructions=None,
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
        codegen_instructions=None,
        run_ref="myproject_myfeed",
    )
    assert "'myproject_myfeed'" in prompt
```

- [ ] **Step 5: Run all codegen tests**

```bash
cd engine && python -m pytest tests/codegen/ -v
```

Expected: all tests pass including the 001cn prompt tests and the new logging tests.

- [ ] **Step 6: Commit**

```bash
git add engine/src/migrations_engine/codegen/service.py \
        engine/tests/codegen/test_bundle_logging.py
git commit -m "feat: inject run logging instructions into codegen system prompt"
```

---

## Verification

1. Click Generate SQL on the codegen page for any feed
2. Download the delivery bundle — first block is `mig_upsert_log` CREATE with `IF OBJECT_ID` guard
3. Staging table DDL has `[_row_num] BIGINT IDENTITY(1,1) NOT NULL` as first column
4. Generated stored proc uses `MERGE` with `OUTPUT ... INTO [staging_schema].[mig_upsert_log]`
5. `run_ref` in the OUTPUT clause matches `'{project_id}_{source_definition_id}'` for that feed
6. No `mig_upsert_log` block when `staging_schema` is null on the project
7. Run the bundle on SQL Server: after proc executes, `SELECT * FROM [stg].[mig_upsert_log]` shows one row per upserted row with correct `dest_table`, `source_row_num`, `dest_row_id`, `action`
8. For a feed that writes to two destination tables: `GROUP BY dest_table, action` shows correct row counts per fiber
