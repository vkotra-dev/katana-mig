# 001aq — Delivery Bundle 0000/0001+ Sequencing

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** When a lookup fiber reaches `operator_triggered`, generate a SQL UPSERT artifact (`destination_object_name = "0000_{fiber_key}"`) so the delivery bundle places all lookup reference table scripts before numbered domain object scripts. Also fix `build_delivery_bundle_text` so that when schema analysis exists, `0000_`-prefixed artifacts are pinned first rather than appended at position `len(sequence)`.

**Architecture:** Three focused changes:
1. New pure module `codegen/lookup_upsert.py` — engine-aware SQL generator (no DB dependency).
2. `management/fibers.py` `trigger_fiber` — when `fiber.fiber_type == "lookup"`, resolve the approved `LookupSnapshot`, generate UPSERT SQL, create `CodeGenerationArtifact`, update fiber fields.
3. `codegen/service.py` `build_delivery_bundle_text` — split artifacts into two lists (`lookup_artifacts` with `0000_` prefix, `domain_artifacts` without), always emit lookup list first with plain headings, then emit domain list with `-- [NN]` headings (or plain headings when no schema analysis exists).

**Tech Stack:** FastAPI, SQLAlchemy 2, Pydantic v2, pytest; Python 3.12

## Global Constraints

- **Prerequisites:** 001ah must be complete (`ProjectSchemaAnalysis` model exists; `codegen/schema_analysis.py` with `get_schema_analysis()` is imported into `codegen/service.py` at module level; `build_delivery_bundle_text` already uses `-- [NN]` headings when analysis exists). 001ak must be complete (`ProjectFiber` ORM model exists in `db/models.py` with fields `fiber_id`, `project_id`, `fiber_type`, `fiber_key`, `status`, `output_sql`). 001an must be complete (`management/fibers.py` exists with `trigger_fiber(db, *, project_id, fiber_id, actor)` that currently sets `fiber.status = "operator_triggered"` and logs "codegen queued" but does not generate any artifact).
- `destination_object_name` for lookup artifacts: `f"0000_{fiber.fiber_key}"` — the `0000_` prefix guarantees these sort before any alphabetic table name.
- Lookup artifact headings in bundle: `-- {artifact.destination_object_name}` (plain, no `[NN]`).
- Domain artifact headings when schema analysis exists: `-- [{idx:02d}] {artifact.destination_object_name}`.
- All headings plain (`-- {name}`) when no schema analysis exists; `0000_` artifacts still appear first because ASCII `"0" < "a"`.
- When no approved `LookupSnapshot` exists at trigger time: set `fiber.status = "operator_triggered"` (not `codegen_complete`), skip artifact creation, return fiber normally.
- `target_db_engine` is read from `ProjectRegistry → ProjectDefinition.domain_config.target_db_engine`. If absent, default to PostgreSQL syntax.
- Single-quote characters in value_map keys or values must be escaped (`'` → `''`) in generated SQL.
- Test file: `engine/tests/test_bundle_sequencing.py` (new) — all tests for all three tasks.
- Do NOT modify any Alembic migration files; no new DB columns are required.

## Objective

Generate lookup upsert SQL, sequence trigger-fiber code generation, and order the delivery bundle so reference data runs before dependent domain object SQL.

## Out of Scope

- No schema-analysis UI changes
- No unrelated codegen artifact model changes
- No feed rename behavior changes

## File Changes

- See the blast radius table above for the exact backend files and any codegen page updates.

## Verification

- Run the new bundle sequencing tests
- Run the existing codegen tests
- Run the relevant backend suite for delivery bundle generation

## Pitfalls

- Keep lookup bundles ahead of dependent domain object bundles
- Preserve deterministic ordering across runs
- Do not let lookup sequencing regress the existing codegen download contract

## Commit

- `feat(001aq): sequence delivery bundle SQL`


---

## Blast Radius

| File | Change |
|---|---|
| `engine/src/migrations_engine/codegen/lookup_upsert.py` | Create — `generate_lookup_upsert_sql` |
| `engine/src/migrations_engine/management/fibers.py` | Modify — `trigger_fiber` generates artifact for lookup fibers |
| `engine/src/migrations_engine/codegen/service.py` | Modify — `build_delivery_bundle_text` splits `0000_`/domain |
| `engine/tests/test_bundle_sequencing.py` | Create — all tests for all three tasks |

---

### Task 1: UPSERT SQL generator (`codegen/lookup_upsert.py`)

**Files:**
- Create: `engine/src/migrations_engine/codegen/lookup_upsert.py`

**Interfaces:**
- Produces: `generate_lookup_upsert_sql(lookup_name: str, value_map: dict[str, str], target_db_engine: str | None) -> str`
- Pure function — no DB, no imports outside stdlib and `__future__`.

- [ ] **Step 1: Write the failing tests**

Create `engine/tests/test_bundle_sequencing.py`:

```python
from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import select

from sqlite_test_support import Base, SessionLocal, TEST_ENGINE
from migrations_engine.db.models import (
    CodeGenerationArtifact,
    LookupSnapshot,
    ProjectDefinition,
    ProjectFiber,
    ProjectRegistry,
    User,
)
import migrations_engine.codegen.service as codegen_service_module


@pytest.fixture(scope="module", autouse=True)
def _setup_db() -> None:
    Base.metadata.create_all(bind=TEST_ENGINE)


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _new_project(db, *, domain_config: dict | None = None) -> str:
    project_id = str(uuid.uuid4())
    definition_id = str(uuid.uuid4())
    db.add(ProjectDefinition(
        definition_id=definition_id,
        project_id=project_id,
        name="Test Project",
        domain_config=domain_config or {},
        status="active",
    ))
    db.add(ProjectRegistry(
        project_id=project_id,
        name="Test Project",
        definition_id=definition_id,
        status="active",
    ))
    db.flush()
    return project_id


def _new_lookup_fiber(
    db,
    *,
    project_id: str,
    fiber_key: str,
    status: str = "business_approved",
    fiber_type: str = "lookup",
) -> ProjectFiber:
    fiber = ProjectFiber(
        fiber_id=str(uuid.uuid4()),
        feed_id=str(uuid.uuid4()),
        project_id=project_id,
        fiber_type=fiber_type,
        fiber_key=fiber_key,
        status=status,
        source="manual",
    )
    db.add(fiber)
    db.flush()
    return fiber


def _new_lookup_snapshot(
    db,
    *,
    project_id: str,
    lookup_name: str,
    value_map: dict[str, str],
) -> LookupSnapshot:
    snapshot = LookupSnapshot(
        lookup_snapshot_id=str(uuid.uuid4()),
        project_id=project_id,
        lookup_name=lookup_name,
        lookup_snapshot_version=str(uuid.uuid4()),
        value_map=value_map,
        status="approved",
        approved_at=datetime.now(UTC),
    )
    db.add(snapshot)
    db.flush()
    return snapshot


def _new_user(db) -> User:
    user = User(
        user_id=str(uuid.uuid4()),
        email=f"test-{uuid.uuid4()}@example.com",
        password_hash="x",
        role="central_team",
        status="active",
    )
    db.add(user)
    db.flush()
    return user


# ===========================================================================
# Task 1 tests — generate_lookup_upsert_sql (pure function, no DB)
# ===========================================================================

VALUE_MAP = {"DB": "Database Account", "SAV": "Savings Account"}


def test_postgresql_generates_on_conflict() -> None:
    from migrations_engine.codegen.lookup_upsert import generate_lookup_upsert_sql
    sql = generate_lookup_upsert_sql("account_type", VALUE_MAP, "postgresql")
    assert "CREATE TABLE IF NOT EXISTS account_type_ref" in sql
    assert "ON CONFLICT (source_val) DO UPDATE SET dest_val = EXCLUDED.dest_val" in sql
    assert "'DB'" in sql
    assert "'Savings Account'" in sql


def test_mysql_generates_on_duplicate_key() -> None:
    from migrations_engine.codegen.lookup_upsert import generate_lookup_upsert_sql
    sql = generate_lookup_upsert_sql("account_type", VALUE_MAP, "mysql")
    assert "CREATE TABLE IF NOT EXISTS account_type_ref" in sql
    assert "ON DUPLICATE KEY UPDATE dest_val = VALUES(dest_val)" in sql


def test_mssql_generates_merge() -> None:
    from migrations_engine.codegen.lookup_upsert import generate_lookup_upsert_sql
    sql = generate_lookup_upsert_sql("account_type", VALUE_MAP, "mssql")
    assert "IF OBJECT_ID('account_type_ref', 'U') IS NULL" in sql
    assert "MERGE account_type_ref AS target" in sql
    assert "WHEN MATCHED THEN UPDATE SET target.dest_val = source.dest_val" in sql
    assert "WHEN NOT MATCHED THEN INSERT" in sql


def test_oracle_generates_merge() -> None:
    from migrations_engine.codegen.lookup_upsert import generate_lookup_upsert_sql
    sql = generate_lookup_upsert_sql("account_type", VALUE_MAP, "oracle")
    assert "MERGE" in sql
    assert "WHEN MATCHED THEN UPDATE SET" in sql


def test_none_engine_defaults_to_pg_syntax() -> None:
    from migrations_engine.codegen.lookup_upsert import generate_lookup_upsert_sql
    sql = generate_lookup_upsert_sql("account_type", VALUE_MAP, None)
    assert "ON CONFLICT" in sql


def test_unknown_engine_defaults_to_pg_syntax() -> None:
    from migrations_engine.codegen.lookup_upsert import generate_lookup_upsert_sql
    sql = generate_lookup_upsert_sql("account_type", VALUE_MAP, "redshift")
    assert "ON CONFLICT" in sql


def test_empty_value_map_omits_upsert_dml() -> None:
    from migrations_engine.codegen.lookup_upsert import generate_lookup_upsert_sql
    sql = generate_lookup_upsert_sql("account_type", {}, "postgresql")
    assert "account_type_ref" in sql
    # No rows to insert, so no INSERT/MERGE statement
    assert "ON CONFLICT" not in sql


def test_single_quotes_in_values_are_escaped() -> None:
    from migrations_engine.codegen.lookup_upsert import generate_lookup_upsert_sql
    sql = generate_lookup_upsert_sql("test_lookup", {"O'Brien": "John O'Brien"}, "postgresql")
    assert "O''Brien" in sql


def test_ref_table_name_has_no_double_suffix() -> None:
    from migrations_engine.codegen.lookup_upsert import generate_lookup_upsert_sql
    sql = generate_lookup_upsert_sql("product_type", VALUE_MAP, "postgresql")
    assert "product_type_ref" in sql
    assert "product_type_ref_ref" not in sql


def test_sql_includes_comment_header() -> None:
    from migrations_engine.codegen.lookup_upsert import generate_lookup_upsert_sql
    sql = generate_lookup_upsert_sql("account_type", VALUE_MAP, "postgresql")
    assert "-- Lookup reference table: account_type" in sql


def test_values_sorted_for_deterministic_output() -> None:
    from migrations_engine.codegen.lookup_upsert import generate_lookup_upsert_sql
    sql_a = generate_lookup_upsert_sql("t", {"Z": "z", "A": "a"}, "postgresql")
    sql_b = generate_lookup_upsert_sql("t", {"A": "a", "Z": "z"}, "postgresql")
    assert sql_a == sql_b
```

- [ ] **Step 2: Run to verify tests fail**

```bash
cd /Users/vjkotra/projects/katana/engine/tests
python -m pytest test_bundle_sequencing.py::test_postgresql_generates_on_conflict -v
```

Expected: `ImportError: cannot import name 'generate_lookup_upsert_sql'` (module does not exist yet).

- [ ] **Step 3: Create `engine/src/migrations_engine/codegen/lookup_upsert.py`**

```python
from __future__ import annotations

"""Engine-aware SQL UPSERT generator for lookup reference tables.

Table name convention: ``{lookup_name}_ref``
Engines:
  - postgresql (default / unknown):  CREATE TABLE IF NOT EXISTS + INSERT ... ON CONFLICT
  - mysql:                           CREATE TABLE IF NOT EXISTS + INSERT ... ON DUPLICATE KEY UPDATE
  - mssql:                           IF OBJECT_ID check + MERGE statement
  - oracle:                          IF OBJECT_ID check + MERGE statement
"""


def _escape(value: str) -> str:
    """Escape single quotes for use inside SQL string literals."""
    return value.replace("'", "''")


def _values_clause(value_map: dict[str, str]) -> str:
    """Return comma-separated SQL row tuples ordered by source_val for determinism."""
    rows = [
        f"('{_escape(src)}', '{_escape(dst)}')"
        for src, dst in sorted(value_map.items())
    ]
    return ", ".join(rows)


def _pg_sql(lookup_name: str, ref_table: str, value_map: dict[str, str]) -> str:
    header = f"-- Lookup reference table: {lookup_name}"
    ddl = (
        f"CREATE TABLE IF NOT EXISTS {ref_table} (\n"
        f"    source_val VARCHAR(255) PRIMARY KEY,\n"
        f"    dest_val VARCHAR(255) NOT NULL\n"
        f");"
    )
    if not value_map:
        return f"{header}\n{ddl}"
    values = _values_clause(value_map)
    dml = (
        f"INSERT INTO {ref_table} (source_val, dest_val)\n"
        f"VALUES {values}\n"
        f"ON CONFLICT (source_val) DO UPDATE SET dest_val = EXCLUDED.dest_val;"
    )
    return f"{header}\n{ddl}\n{dml}"


def _mysql_sql(lookup_name: str, ref_table: str, value_map: dict[str, str]) -> str:
    header = f"-- Lookup reference table: {lookup_name}"
    ddl = (
        f"CREATE TABLE IF NOT EXISTS {ref_table} (\n"
        f"    source_val VARCHAR(255) PRIMARY KEY,\n"
        f"    dest_val VARCHAR(255) NOT NULL\n"
        f");"
    )
    if not value_map:
        return f"{header}\n{ddl}"
    values = _values_clause(value_map)
    dml = (
        f"INSERT INTO {ref_table} (source_val, dest_val)\n"
        f"VALUES {values}\n"
        f"ON DUPLICATE KEY UPDATE dest_val = VALUES(dest_val);"
    )
    return f"{header}\n{ddl}\n{dml}"


def _mssql_sql(lookup_name: str, ref_table: str, value_map: dict[str, str]) -> str:
    header = f"-- Lookup reference table: {lookup_name}"
    ddl = (
        f"IF OBJECT_ID('{ref_table}', 'U') IS NULL\n"
        f"CREATE TABLE {ref_table} ("
        f"source_val NVARCHAR(255) PRIMARY KEY, dest_val NVARCHAR(255) NOT NULL);"
    )
    if not value_map:
        return f"{header}\n{ddl}"
    values = _values_clause(value_map)
    merge = (
        f"MERGE {ref_table} AS target\n"
        f"USING (VALUES {values}) AS source (source_val, dest_val)\n"
        f"ON target.source_val = source.source_val\n"
        f"WHEN MATCHED THEN UPDATE SET target.dest_val = source.dest_val\n"
        f"WHEN NOT MATCHED THEN INSERT (source_val, dest_val)"
        f" VALUES (source.source_val, source.dest_val);"
    )
    return f"{header}\n{ddl}\n\n{merge}"


def _oracle_sql(lookup_name: str, ref_table: str, value_map: dict[str, str]) -> str:
    header = f"-- Lookup reference table: {lookup_name}"
    ddl = (
        f"IF OBJECT_ID('{ref_table}', 'U') IS NULL\n"
        f"CREATE TABLE {ref_table} ("
        f"source_val NVARCHAR(255) PRIMARY KEY, dest_val NVARCHAR(255) NOT NULL);"
    )
    if not value_map:
        return f"{header}\n{ddl}"
    values = _values_clause(value_map)
    merge = (
        f"MERGE {ref_table} AS target\n"
        f"USING (VALUES {values}) AS source (source_val, dest_val)\n"
        f"ON target.source_val = source.source_val\n"
        f"WHEN MATCHED THEN UPDATE SET target.dest_val = source.dest_val\n"
        f"WHEN NOT MATCHED THEN INSERT (source_val, dest_val)"
        f" VALUES (source.source_val, source.dest_val);"
    )
    return f"{header}\n{ddl}\n\n{merge}"


def generate_lookup_upsert_sql(
    lookup_name: str,
    value_map: dict[str, str],
    target_db_engine: str | None,
) -> str:
    """Generate CREATE TABLE + UPSERT SQL for a lookup reference table.

    Args:
        lookup_name:       The lookup name (e.g. ``"account_type"``). The reference
                           table will be named ``{lookup_name}_ref``.
        value_map:         Mapping of source values to destination values.
        target_db_engine:  One of ``"postgresql"``, ``"mysql"``, ``"mssql"``,
                           ``"oracle"`` (case-insensitive). ``None`` or any other
                           string defaults to PostgreSQL syntax.

    Returns:
        SQL string containing DDL + UPSERT DML ready to embed in a delivery bundle.
    """
    ref_table = f"{lookup_name}_ref"
    engine = (target_db_engine or "").lower()

    if engine == "mysql":
        return _mysql_sql(lookup_name, ref_table, value_map)
    if engine == "mssql":
        return _mssql_sql(lookup_name, ref_table, value_map)
    if engine == "oracle":
        return _oracle_sql(lookup_name, ref_table, value_map)
    # postgresql or any unrecognised engine
    return _pg_sql(lookup_name, ref_table, value_map)
```

- [ ] **Step 4: Run Task 1 tests to confirm they pass**

```bash
cd /Users/vjkotra/projects/katana/engine/tests
python -m pytest test_bundle_sequencing.py -k "test_postgresql or test_mysql or test_mssql or test_oracle or test_none_engine or test_unknown_engine or test_empty_value or test_single_quote or test_ref_table or test_sql_includes or test_values_sorted" -v
```

Expected: all 11 Task 1 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add engine/src/migrations_engine/codegen/lookup_upsert.py \
        engine/tests/test_bundle_sequencing.py
git commit -m "feat(001aq): add engine-aware lookup UPSERT SQL generator"
```

---

### Task 2: Lookup fiber artifact generation (`management/fibers.py`)

**Files:**
- Modify: `engine/src/migrations_engine/management/fibers.py`

**Interfaces:**
- Consumes: `generate_lookup_upsert_sql` from `codegen.lookup_upsert`; `select_latest_approved_lookup_snapshot` from `mapping.snapshots`; `SnapshotNotFoundError` from `mapping.exceptions`; `CodeGenerationArtifact`, `ProjectDefinition`, `ProjectRegistry` from `db.models`
- Produces: When `fiber.fiber_type == "lookup"` and an approved snapshot exists, `trigger_fiber` creates a `CodeGenerationArtifact` with `destination_object_name = f"0000_{fiber.fiber_key}"` and sets `fiber.status = "codegen_complete"` and `fiber.output_sql`. When no snapshot exists: `fiber.status = "operator_triggered"`, no artifact. For all other `fiber_type` values: `fiber.status = "operator_triggered"`, no artifact (existing behavior).

**Current state of `trigger_fiber` (from 001an — do not lose this behavior for non-lookup fibers):**

```python
def trigger_fiber(
    db: Session,
    *,
    project_id: str,
    fiber_id: str,
    actor: User,
) -> ProjectFiber:
    fiber = _get_fiber(db, project_id=project_id, fiber_id=fiber_id)
    if fiber.status != "business_approved":
        raise AuthApiError(
            "invalid_status",
            f"Fiber must be 'business_approved' to trigger, got '{fiber.status}'.",
            409,
        )
    fiber.status = "operator_triggered"
    logger.info("codegen queued for fiber %s", fiber_id)
    db.commit()
    db.refresh(fiber)
    return fiber
```

- [ ] **Step 1: Add Task 2 failing tests to `test_bundle_sequencing.py`**

Append the following to `engine/tests/test_bundle_sequencing.py`:

```python
# ===========================================================================
# Task 2 tests — trigger_fiber generates UPSERT artifact for lookup fibers
# ===========================================================================

def test_trigger_fiber_lookup_creates_active_artifact() -> None:
    from migrations_engine.management.fibers import trigger_fiber
    with SessionLocal() as db:
        project_id = _new_project(db, domain_config={"target_db_engine": "postgresql"})
        _new_lookup_snapshot(
            db, project_id=project_id, lookup_name="acct_type",
            value_map={"A": "Alpha", "B": "Beta"},
        )
        fiber = _new_lookup_fiber(db, project_id=project_id, fiber_key="acct_type")
        actor = _new_user(db)
        db.commit()

        result = trigger_fiber(db, project_id=project_id, fiber_id=fiber.fiber_id, actor=actor)

    assert result.status == "codegen_complete"

    with SessionLocal() as db:
        artifact = db.scalar(
            select(CodeGenerationArtifact).where(
                CodeGenerationArtifact.project_id == project_id,
                CodeGenerationArtifact.destination_object_name == "0000_acct_type",
                CodeGenerationArtifact.status == "active",
            )
        )
    assert artifact is not None


def test_trigger_fiber_lookup_destination_name_has_0000_prefix() -> None:
    from migrations_engine.management.fibers import trigger_fiber
    with SessionLocal() as db:
        project_id = _new_project(db, domain_config={"target_db_engine": "postgresql"})
        _new_lookup_snapshot(
            db, project_id=project_id, lookup_name="prod_type",
            value_map={"X": "Y"},
        )
        fiber = _new_lookup_fiber(db, project_id=project_id, fiber_key="prod_type")
        actor = _new_user(db)
        db.commit()

        trigger_fiber(db, project_id=project_id, fiber_id=fiber.fiber_id, actor=actor)

    with SessionLocal() as db:
        artifact = db.scalar(
            select(CodeGenerationArtifact).where(
                CodeGenerationArtifact.project_id == project_id,
                CodeGenerationArtifact.status == "active",
            )
        )
    assert artifact is not None
    assert artifact.destination_object_name == "0000_prod_type"


def test_trigger_fiber_lookup_sets_output_sql_with_pg_syntax() -> None:
    from migrations_engine.management.fibers import trigger_fiber
    with SessionLocal() as db:
        project_id = _new_project(db, domain_config={"target_db_engine": "postgresql"})
        _new_lookup_snapshot(
            db, project_id=project_id, lookup_name="cust_type",
            value_map={"P": "Premium"},
        )
        fiber = _new_lookup_fiber(db, project_id=project_id, fiber_key="cust_type")
        actor = _new_user(db)
        db.commit()

        result = trigger_fiber(db, project_id=project_id, fiber_id=fiber.fiber_id, actor=actor)

    assert result.output_sql is not None
    assert "cust_type_ref" in result.output_sql
    assert "ON CONFLICT" in result.output_sql


def test_trigger_fiber_lookup_supersedes_previous_artifact() -> None:
    from migrations_engine.management.fibers import trigger_fiber
    with SessionLocal() as db:
        project_id = _new_project(db, domain_config={"target_db_engine": "postgresql"})
        _new_lookup_snapshot(
            db, project_id=project_id, lookup_name="sup_type",
            value_map={"A": "Alpha"},
        )
        fiber = _new_lookup_fiber(db, project_id=project_id, fiber_key="sup_type")
        actor = _new_user(db)
        # Pre-existing active artifact that should be superseded
        db.add(CodeGenerationArtifact(
            codegen_artifact_id=str(uuid.uuid4()),
            project_id=project_id,
            destination_object_name="0000_sup_type",
            sql_bundle="-- old SQL",
            status="active",
        ))
        db.commit()

        trigger_fiber(db, project_id=project_id, fiber_id=fiber.fiber_id, actor=actor)

    with SessionLocal() as db:
        active = list(db.scalars(
            select(CodeGenerationArtifact).where(
                CodeGenerationArtifact.project_id == project_id,
                CodeGenerationArtifact.destination_object_name == "0000_sup_type",
                CodeGenerationArtifact.status == "active",
            )
        ))
        superseded = list(db.scalars(
            select(CodeGenerationArtifact).where(
                CodeGenerationArtifact.project_id == project_id,
                CodeGenerationArtifact.destination_object_name == "0000_sup_type",
                CodeGenerationArtifact.status == "superseded",
            )
        ))
    assert len(active) == 1
    assert len(superseded) == 1
    assert "old SQL" in (superseded[0].sql_bundle or "")


def test_trigger_fiber_lookup_skips_artifact_when_no_snapshot() -> None:
    from migrations_engine.management.fibers import trigger_fiber
    with SessionLocal() as db:
        project_id = _new_project(db, domain_config={"target_db_engine": "postgresql"})
        # Intentionally no LookupSnapshot for "missing_type"
        fiber = _new_lookup_fiber(db, project_id=project_id, fiber_key="missing_type")
        actor = _new_user(db)
        db.commit()

        result = trigger_fiber(db, project_id=project_id, fiber_id=fiber.fiber_id, actor=actor)

    # Fiber transitions to operator_triggered (not codegen_complete) when snapshot absent
    assert result.status == "operator_triggered"

    with SessionLocal() as db:
        artifacts = list(db.scalars(
            select(CodeGenerationArtifact).where(
                CodeGenerationArtifact.project_id == project_id,
            )
        ))
    assert artifacts == []


def test_trigger_fiber_domain_object_does_not_create_artifact() -> None:
    from migrations_engine.management.fibers import trigger_fiber
    with SessionLocal() as db:
        project_id = _new_project(db)
        fiber = _new_lookup_fiber(
            db, project_id=project_id, fiber_key="customers", fiber_type="domain_object"
        )
        actor = _new_user(db)
        db.commit()

        result = trigger_fiber(db, project_id=project_id, fiber_id=fiber.fiber_id, actor=actor)

    assert result.status == "operator_triggered"

    with SessionLocal() as db:
        artifacts = list(db.scalars(
            select(CodeGenerationArtifact).where(
                CodeGenerationArtifact.project_id == project_id,
            )
        ))
    assert artifacts == []


def test_trigger_fiber_mssql_creates_merge_artifact() -> None:
    from migrations_engine.management.fibers import trigger_fiber
    with SessionLocal() as db:
        project_id = _new_project(db, domain_config={"target_db_engine": "mssql"})
        _new_lookup_snapshot(
            db, project_id=project_id, lookup_name="mssql_type",
            value_map={"A": "Alpha"},
        )
        fiber = _new_lookup_fiber(db, project_id=project_id, fiber_key="mssql_type")
        actor = _new_user(db)
        db.commit()

        trigger_fiber(db, project_id=project_id, fiber_id=fiber.fiber_id, actor=actor)

    with SessionLocal() as db:
        artifact = db.scalar(
            select(CodeGenerationArtifact).where(
                CodeGenerationArtifact.project_id == project_id,
                CodeGenerationArtifact.status == "active",
            )
        )
    assert artifact is not None
    assert "MERGE" in (artifact.sql_bundle or "")


def test_trigger_fiber_artifact_stores_snapshot_version() -> None:
    from migrations_engine.management.fibers import trigger_fiber
    with SessionLocal() as db:
        project_id = _new_project(db, domain_config={"target_db_engine": "postgresql"})
        snapshot = _new_lookup_snapshot(
            db, project_id=project_id, lookup_name="ver_type",
            value_map={"V": "Value"},
        )
        snapshot_version = snapshot.lookup_snapshot_version
        fiber = _new_lookup_fiber(db, project_id=project_id, fiber_key="ver_type")
        actor = _new_user(db)
        db.commit()

        trigger_fiber(db, project_id=project_id, fiber_id=fiber.fiber_id, actor=actor)

    with SessionLocal() as db:
        artifact = db.scalar(
            select(CodeGenerationArtifact).where(
                CodeGenerationArtifact.project_id == project_id,
                CodeGenerationArtifact.destination_object_name == "0000_ver_type",
            )
        )
    assert artifact is not None
    assert artifact.lookup_snapshot_version == snapshot_version
```

- [ ] **Step 2: Run Task 2 tests to verify they fail**

```bash
cd /Users/vjkotra/projects/katana/engine/tests
python -m pytest test_bundle_sequencing.py -k "test_trigger_fiber" -v
```

Expected: FAIL — either `ImportError` (if `management/fibers.py` does not yet have the codegen logic) or assertion failures showing no artifact was created.

- [ ] **Step 3: Modify `trigger_fiber` in `engine/src/migrations_engine/management/fibers.py`**

Add the following imports to the existing imports at the top of the file (add, do not replace existing imports):

```python
from datetime import UTC, datetime

from sqlalchemy import update

from ..codegen.lookup_upsert import generate_lookup_upsert_sql
from ..db.models import (
    CodeGenerationArtifact,
    ProjectDefinition,
    ProjectRegistry,
    new_id,
)
from ..mapping.exceptions import SnapshotNotFoundError
from ..mapping.snapshots import select_latest_approved_lookup_snapshot
```

Add the following two private helpers after the existing `_get_fiber` helper and before `trigger_fiber`:

```python
def _get_target_db_engine(db: Session, *, project_id: str) -> str | None:
    registry = db.get(ProjectRegistry, project_id)
    if registry is None:
        return None
    definition = db.get(ProjectDefinition, registry.definition_id)
    if definition is None:
        return None
    return (definition.domain_config or {}).get("target_db_engine")


def _supersede_lookup_artifact(
    db: Session,
    *,
    project_id: str,
    destination_object_name: str,
) -> None:
    now = datetime.now(UTC)
    db.execute(
        update(CodeGenerationArtifact)
        .where(
            CodeGenerationArtifact.project_id == project_id,
            CodeGenerationArtifact.destination_object_name == destination_object_name,
            CodeGenerationArtifact.status == "active",
        )
        .values(status="superseded", superseded_at=now)
    )
```

Replace the body of `trigger_fiber` with the following (keep the function signature unchanged):

```python
def trigger_fiber(
    db: Session,
    *,
    project_id: str,
    fiber_id: str,
    actor: User,
) -> ProjectFiber:
    fiber = _get_fiber(db, project_id=project_id, fiber_id=fiber_id)
    if fiber.status != "business_approved":
        raise AuthApiError(
            "invalid_status",
            f"Fiber must be 'business_approved' to trigger, got '{fiber.status}'.",
            409,
        )

    if fiber.fiber_type == "lookup":
        try:
            snapshot = select_latest_approved_lookup_snapshot(
                db,
                project_id=project_id,
                lookup_name=fiber.fiber_key,
            )
        except SnapshotNotFoundError:
            logger.warning(
                "No approved lookup snapshot for fiber %s (lookup_name=%r) — skipping codegen",
                fiber_id,
                fiber.fiber_key,
            )
            fiber.status = "operator_triggered"
            db.commit()
            db.refresh(fiber)
            return fiber

        target_db_engine = _get_target_db_engine(db, project_id=project_id)
        sql = generate_lookup_upsert_sql(
            lookup_name=fiber.fiber_key,
            value_map=snapshot.value_map,
            target_db_engine=target_db_engine,
        )
        destination_object_name = f"0000_{fiber.fiber_key}"

        _supersede_lookup_artifact(
            db,
            project_id=project_id,
            destination_object_name=destination_object_name,
        )

        db.add(CodeGenerationArtifact(
            codegen_artifact_id=new_id(),
            project_id=project_id,
            destination_object_name=destination_object_name,
            run_id=None,
            source_slice_version=None,
            mapping_snapshot_version=None,
            lookup_snapshot_version=snapshot.lookup_snapshot_version,
            sql_bundle=sql,
            status="active",
        ))

        fiber.output_sql = sql
        fiber.status = "codegen_complete"
    else:
        fiber.status = "operator_triggered"
        logger.info("codegen queued for fiber %s", fiber_id)

    db.commit()
    db.refresh(fiber)
    return fiber
```

- [ ] **Step 4: Run Task 2 tests to confirm they pass**

```bash
cd /Users/vjkotra/projects/katana/engine/tests
python -m pytest test_bundle_sequencing.py -k "test_trigger_fiber" -v
```

Expected: all 8 Task 2 tests PASS.

- [ ] **Step 5: Run the full engine test suite**

```bash
cd /Users/vjkotra/projects/katana/engine/tests
python -m pytest -v
```

Expected: all tests PASS (existing tests must not regress).

- [ ] **Step 6: Commit**

```bash
git add engine/src/migrations_engine/management/fibers.py \
        engine/tests/test_bundle_sequencing.py
git commit -m "feat(001aq): trigger_fiber generates UPSERT artifact for lookup fibers"
```

---

### Task 3: Bundle 0000_/domain split in `build_delivery_bundle_text`

**Files:**
- Modify: `engine/src/migrations_engine/codegen/service.py`

**Interfaces:**
- Consumes: `get_schema_analysis` (already imported at module level after 001ah); `CodeGenerationArtifact` records from DB
- Produces: When schema analysis exists, lookup artifacts (`destination_object_name.startswith("0000_")`) are placed first with plain `-- {name}` headings; domain artifacts follow with `-- [{idx:02d}] {name}` headings. When no schema analysis exists, all artifacts are sorted alphabetically with plain `-- {name}` headings (`0000_` artifacts naturally appear first because `"0" < "a"`).

**Problem being fixed:** After 001ah, `build_delivery_bundle_text` computes `position = {name: i for i, name in enumerate(sequence)}`. Any artifact whose name is not in the sequence gets `position.get(name, len(sequence))`, sending it to the end of the bundle. Lookup artifacts with `0000_` names are never in the schema analysis sequence, so they end up last. This task explicitly partitions the two groups.

**Current state of `build_delivery_bundle_text` (after 001ah, before 001aq):**

```python
def build_delivery_bundle_text(db, *, project_id):
    analysis = get_schema_analysis(db, project_id=project_id)
    sequence = analysis.destination_object_sequence if analysis else None

    artifacts = db.scalars(
        select(CodeGenerationArtifact)
        .where(
            CodeGenerationArtifact.project_id == project_id,
            CodeGenerationArtifact.status == "active",
        )
        .order_by(
            CodeGenerationArtifact.destination_object_name.asc(),
            CodeGenerationArtifact.created_at.desc(),
        )
    ).all()

    if sequence:
        position = {name: i for i, name in enumerate(sequence)}
        artifacts = sorted(
            artifacts,
            key=lambda a: position.get(a.destination_object_name, len(sequence)),
        )

    bundle_parts: list[str] = []
    for idx, artifact in enumerate(artifacts, start=1):
        if sequence:
            heading = f"-- [{idx:02d}] {artifact.destination_object_name}"
        else:
            heading = f"-- {artifact.destination_object_name}"
        bundle_parts.append(heading)
        if artifact.sql_bundle:
            bundle_parts.append(artifact.sql_bundle.strip())

    return DeliveryBundleResponse(
        sql_bundle="\n\n".join(bundle_parts).strip(),
        artifact_count=len(artifacts),
    )
```

- [ ] **Step 1: Add Task 3 failing tests to `test_bundle_sequencing.py`**

Append the following to `engine/tests/test_bundle_sequencing.py`:

```python
# ===========================================================================
# Task 3 tests — build_delivery_bundle_text 0000_/domain split
# ===========================================================================

class _FakeAnalysis:
    """Minimal stand-in for ProjectSchemaAnalysisResponse."""

    def __init__(self, sequence: list[str]) -> None:
        self.destination_object_sequence = sequence


def test_lookup_artifacts_placed_before_domain_when_schema_analysis_exists(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from migrations_engine.codegen.service import build_delivery_bundle_text
    monkeypatch.setattr(
        codegen_service_module,
        "get_schema_analysis",
        lambda db, project_id: _FakeAnalysis(["customers", "accounts"]),
    )
    with SessionLocal() as db:
        project_id = _new_project(db)
        db.add(CodeGenerationArtifact(
            codegen_artifact_id=str(uuid.uuid4()),
            project_id=project_id,
            destination_object_name="0000_account_type",
            status="active",
            sql_bundle="-- UPSERT SQL",
        ))
        db.add(CodeGenerationArtifact(
            codegen_artifact_id=str(uuid.uuid4()),
            project_id=project_id,
            destination_object_name="customers",
            status="active",
            sql_bundle="-- customers DDL",
        ))
        db.add(CodeGenerationArtifact(
            codegen_artifact_id=str(uuid.uuid4()),
            project_id=project_id,
            destination_object_name="accounts",
            status="active",
            sql_bundle="-- accounts DDL",
        ))
        db.commit()
        result = build_delivery_bundle_text(db, project_id=project_id)

    assert result.artifact_count == 3
    # Lookup block appears before the first domain block
    assert result.sql_bundle.index("-- 0000_account_type") < result.sql_bundle.index("-- [01] customers")


def test_lookup_heading_has_no_nn_bracket_prefix(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from migrations_engine.codegen.service import build_delivery_bundle_text
    monkeypatch.setattr(
        codegen_service_module,
        "get_schema_analysis",
        lambda db, project_id: _FakeAnalysis(["customers"]),
    )
    with SessionLocal() as db:
        project_id = _new_project(db)
        db.add(CodeGenerationArtifact(
            codegen_artifact_id=str(uuid.uuid4()),
            project_id=project_id,
            destination_object_name="0000_lookup_x",
            status="active",
            sql_bundle="-- SQL",
        ))
        db.add(CodeGenerationArtifact(
            codegen_artifact_id=str(uuid.uuid4()),
            project_id=project_id,
            destination_object_name="customers",
            status="active",
            sql_bundle="-- DDL",
        ))
        db.commit()
        result = build_delivery_bundle_text(db, project_id=project_id)

    # Lookup heading is plain, no [NN] brackets
    assert "-- 0000_lookup_x" in result.sql_bundle
    lookup_idx = result.sql_bundle.index("-- 0000_lookup_x")
    # Everything before the lookup heading contains no [NN] marker
    assert "-- [" not in result.sql_bundle[:lookup_idx]
    # Domain heading has [NN] marker
    assert "-- [01] customers" in result.sql_bundle


def test_domain_artifacts_numbered_independently_of_lookup_count(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Domain [NN] index starts at 01 regardless of how many lookup artifacts precede."""
    from migrations_engine.codegen.service import build_delivery_bundle_text
    monkeypatch.setattr(
        codegen_service_module,
        "get_schema_analysis",
        lambda db, project_id: _FakeAnalysis(["customers", "orders"]),
    )
    with SessionLocal() as db:
        project_id = _new_project(db)
        for name in ("0000_type_a", "0000_type_b"):
            db.add(CodeGenerationArtifact(
                codegen_artifact_id=str(uuid.uuid4()),
                project_id=project_id,
                destination_object_name=name,
                status="active",
                sql_bundle="-- UPSERT",
            ))
        for name in ("customers", "orders"):
            db.add(CodeGenerationArtifact(
                codegen_artifact_id=str(uuid.uuid4()),
                project_id=project_id,
                destination_object_name=name,
                status="active",
                sql_bundle="-- DDL",
            ))
        db.commit()
        result = build_delivery_bundle_text(db, project_id=project_id)

    # Domain numbering is 01, 02 — not 03, 04 (no offset from lookup count)
    assert "-- [01] customers" in result.sql_bundle
    assert "-- [02] orders" in result.sql_bundle
    assert "-- [03]" not in result.sql_bundle


def test_multiple_lookup_artifacts_sorted_alphabetically(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from migrations_engine.codegen.service import build_delivery_bundle_text
    monkeypatch.setattr(
        codegen_service_module,
        "get_schema_analysis",
        lambda db, project_id: _FakeAnalysis(["customers"]),
    )
    with SessionLocal() as db:
        project_id = _new_project(db)
        db.add(CodeGenerationArtifact(
            codegen_artifact_id=str(uuid.uuid4()),
            project_id=project_id,
            destination_object_name="0000_zone_type",
            status="active",
            sql_bundle="-- SQL zone",
        ))
        db.add(CodeGenerationArtifact(
            codegen_artifact_id=str(uuid.uuid4()),
            project_id=project_id,
            destination_object_name="0000_acct_type",
            status="active",
            sql_bundle="-- SQL acct",
        ))
        db.add(CodeGenerationArtifact(
            codegen_artifact_id=str(uuid.uuid4()),
            project_id=project_id,
            destination_object_name="customers",
            status="active",
            sql_bundle="-- DDL",
        ))
        db.commit()
        result = build_delivery_bundle_text(db, project_id=project_id)

    # Alphabetical among lookup: acct < zone
    assert result.sql_bundle.index("0000_acct_type") < result.sql_bundle.index("0000_zone_type")
    # Both lookup items before domain items
    assert result.sql_bundle.index("0000_zone_type") < result.sql_bundle.index("-- [01] customers")


def test_no_schema_analysis_all_artifacts_alphabetical_no_nn_prefix(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from migrations_engine.codegen.service import build_delivery_bundle_text
    monkeypatch.setattr(
        codegen_service_module,
        "get_schema_analysis",
        lambda db, project_id: None,
    )
    with SessionLocal() as db:
        project_id = _new_project(db)
        db.add(CodeGenerationArtifact(
            codegen_artifact_id=str(uuid.uuid4()),
            project_id=project_id,
            destination_object_name="0000_acct_type",
            status="active",
            sql_bundle="-- UPSERT",
        ))
        db.add(CodeGenerationArtifact(
            codegen_artifact_id=str(uuid.uuid4()),
            project_id=project_id,
            destination_object_name="customers",
            status="active",
            sql_bundle="-- DDL",
        ))
        db.commit()
        result = build_delivery_bundle_text(db, project_id=project_id)

    # No [NN] prefix on any heading
    assert "-- [" not in result.sql_bundle
    # 0000_ sorts before alphabetic names naturally
    assert result.sql_bundle.index("-- 0000_acct_type") < result.sql_bundle.index("-- customers")


def test_only_lookup_artifacts_no_domain_artifacts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from migrations_engine.codegen.service import build_delivery_bundle_text
    monkeypatch.setattr(
        codegen_service_module,
        "get_schema_analysis",
        lambda db, project_id: _FakeAnalysis([]),
    )
    with SessionLocal() as db:
        project_id = _new_project(db)
        db.add(CodeGenerationArtifact(
            codegen_artifact_id=str(uuid.uuid4()),
            project_id=project_id,
            destination_object_name="0000_acct_type",
            status="active",
            sql_bundle="-- UPSERT",
        ))
        db.commit()
        result = build_delivery_bundle_text(db, project_id=project_id)

    assert result.artifact_count == 1
    assert "-- 0000_acct_type" in result.sql_bundle
    assert "-- [" not in result.sql_bundle


def test_only_domain_artifacts_no_lookup_artifacts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from migrations_engine.codegen.service import build_delivery_bundle_text
    monkeypatch.setattr(
        codegen_service_module,
        "get_schema_analysis",
        lambda db, project_id: _FakeAnalysis(["customers", "orders"]),
    )
    with SessionLocal() as db:
        project_id = _new_project(db)
        for name in ("orders", "customers"):
            db.add(CodeGenerationArtifact(
                codegen_artifact_id=str(uuid.uuid4()),
                project_id=project_id,
                destination_object_name=name,
                status="active",
                sql_bundle=f"-- {name} DDL",
            ))
        db.commit()
        result = build_delivery_bundle_text(db, project_id=project_id)

    assert result.artifact_count == 2
    # Schema-analysis order: customers (pos 0) before orders (pos 1)
    assert result.sql_bundle.index("-- [01] customers") < result.sql_bundle.index("-- [02] orders")
```

- [ ] **Step 2: Run Task 3 tests to verify they fail**

```bash
cd /Users/vjkotra/projects/katana/engine/tests
python -m pytest test_bundle_sequencing.py -k "test_lookup_artifacts_placed or test_lookup_heading or test_domain_artifacts_numbered or test_multiple_lookup or test_no_schema_analysis or test_only_lookup or test_only_domain" -v
```

Expected: FAIL — the current `build_delivery_bundle_text` (from 001ah) sends `0000_` artifacts to position `len(sequence)` instead of the front.

- [ ] **Step 3: Update `build_delivery_bundle_text` in `engine/src/migrations_engine/codegen/service.py`**

Replace the entire `build_delivery_bundle_text` function with the following (the `from .schema_analysis import get_schema_analysis` import at the top of the module is already present from 001ah — do not add it again):

```python
def build_delivery_bundle_text(
    db: Session,
    *,
    project_id: str,
) -> DeliveryBundleResponse:
    analysis = get_schema_analysis(db, project_id=project_id)
    sequence = analysis.destination_object_sequence if analysis else None

    # Fetch all active artifacts sorted alphabetically (stable base order)
    all_artifacts = db.scalars(
        select(CodeGenerationArtifact)
        .where(
            CodeGenerationArtifact.project_id == project_id,
            CodeGenerationArtifact.status == "active",
        )
        .order_by(
            CodeGenerationArtifact.destination_object_name.asc(),
            CodeGenerationArtifact.created_at.desc(),
        )
    ).all()

    bundle_parts: list[str] = []

    if sequence:
        # Split: lookup artifacts (0000_ prefix) always come first with plain headings.
        # Domain artifacts follow in schema-analysis dependency order with [NN] headings.
        lookup_artifacts = sorted(
            [a for a in all_artifacts if a.destination_object_name.startswith("0000_")],
            key=lambda a: a.destination_object_name,
        )
        domain_artifacts = [
            a for a in all_artifacts if not a.destination_object_name.startswith("0000_")
        ]
        position = {name: i for i, name in enumerate(sequence)}
        sorted_domain = sorted(
            domain_artifacts,
            key=lambda a: position.get(a.destination_object_name, len(sequence)),
        )

        for artifact in lookup_artifacts:
            bundle_parts.append(f"-- {artifact.destination_object_name}")
            if artifact.sql_bundle:
                bundle_parts.append(artifact.sql_bundle.strip())

        for idx, artifact in enumerate(sorted_domain, start=1):
            bundle_parts.append(f"-- [{idx:02d}] {artifact.destination_object_name}")
            if artifact.sql_bundle:
                bundle_parts.append(artifact.sql_bundle.strip())
    else:
        # No schema analysis: pure alphabetical order.
        # "0000_" prefix ensures lookup artifacts sort before any alphabetic table name.
        for artifact in all_artifacts:
            bundle_parts.append(f"-- {artifact.destination_object_name}")
            if artifact.sql_bundle:
                bundle_parts.append(artifact.sql_bundle.strip())

    return DeliveryBundleResponse(
        sql_bundle="\n\n".join(bundle_parts).strip(),
        artifact_count=len(all_artifacts),
    )
```

- [ ] **Step 4: Run all Task 3 tests to confirm they pass**

```bash
cd /Users/vjkotra/projects/katana/engine/tests
python -m pytest test_bundle_sequencing.py -k "test_lookup_artifacts_placed or test_lookup_heading or test_domain_artifacts_numbered or test_multiple_lookup or test_no_schema_analysis or test_only_lookup or test_only_domain" -v
```

Expected: all 7 Task 3 tests PASS.

- [ ] **Step 5: Run the full `test_bundle_sequencing.py` suite**

```bash
cd /Users/vjkotra/projects/katana/engine/tests
python -m pytest test_bundle_sequencing.py -v
```

Expected: all 26 tests PASS (11 Task 1 + 8 Task 2 + 7 Task 3).

- [ ] **Step 6: Run the full engine test suite to check for regressions**

```bash
cd /Users/vjkotra/projects/katana/engine/tests
python -m pytest -v
```

Expected: all tests PASS. Pay particular attention to `test_codegen_service_api.py::test_delivery_bundle_returns_active_artifacts` — that test's existing assertion `response.text.startswith("-- Customer")` must still pass (no schema analysis in that test means alphabetical + plain headings, unaffected by this change).

- [ ] **Step 7: Commit**

```bash
git add engine/src/migrations_engine/codegen/service.py \
        engine/tests/test_bundle_sequencing.py
git commit -m "feat(001aq): pin 0000_ lookup artifacts first in delivery bundle"
```
