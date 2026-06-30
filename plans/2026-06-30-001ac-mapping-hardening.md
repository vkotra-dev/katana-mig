# Mapping Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make mapping snapshot creation and parsing fail deterministically, and remove the transient lookup-value-map migration inconsistency.

**Architecture:** Keep the fix narrow: the mapping snapshot helper should preflight conflicts before insert, the field-binding parser should reject unsupported multi-binding snapshots, and the lookup-value-map migrations should describe the final table shape from the start. The domain page gets a short contract note so the code and docs agree on what is supported today.

**Tech Stack:** Python 3.14, FastAPI, SQLAlchemy 2.x ORM, Alembic, Pytest, SQLite test fixtures.

## Global Constraints

- Source contracts are declared, not inferred from runtime connection strings.
- Source-type-specific structure must be preserved.
- A source slice is approved, immutable, and versioned before downstream use.
- Every DDL change ships with a hand-written Alembic migration in the same commit.
- Migration files follow the `NNNN_<description>.py` naming convention; inspect the current chain to get the next number before writing the file.
- The `down_revision` in the new file must match the `revision` of the latest existing migration — never guess the number; read it from the file.
- `alembic upgrade head` must run cleanly locally before the change is committed.

---

### Task 1: Mapping snapshot conflict guard and single-binding rejection

**Files:**
- Modify: `docs/domain/source-model.md`
- Modify: `engine/src/migrations_engine/mapping/exceptions.py`
- Modify: `engine/src/migrations_engine/mapping/__init__.py`
- Modify: `engine/src/migrations_engine/mapping/snapshots.py`
- Modify: `engine/tests/test_mapping_slice.py`

**Interfaces:**
- Consumes: `MappingSnapshot`, `FieldBinding`, `SnapshotNotFoundError`, `SnapshotImmutableError`
- Produces: a governed conflict exception for duplicate mapping snapshot versions and an explicit error for multi-binding snapshots

- [ ] **Step 1: Write the failing regression tests**

```python
def test_create_approved_mapping_snapshot_rejects_duplicate_version() -> None:
    Base.metadata.create_all(bind=TEST_ENGINE)

    with SessionLocal() as db:
        project_id = str(uuid.uuid4())
        destination_object_name = "Customer"
        # seed project_registry row here
        create_approved_mapping_snapshot(
            db,
            project_id=project_id,
            destination_object_name=destination_object_name,
            mapping_snapshot_version="v1",
            field_bindings=[
                FieldBinding(
                    source_field="src_status",
                    destination_field="status",
                    lookup_name="status_code",
                ),
            ],
        )
        db.commit()

        with pytest.raises(SnapshotVersionConflictError):
            create_approved_mapping_snapshot(
                db,
                project_id=project_id,
                destination_object_name=destination_object_name,
                mapping_snapshot_version="v1",
                field_bindings=[
                    FieldBinding(
                        source_field="src_status",
                        destination_field="status",
                        lookup_name="status_code",
                    ),
                ],
            )
```

```python
def test_parse_primary_field_binding_rejects_multiple_bindings() -> None:
    snapshot = MappingSnapshot(
        mapping_snapshot_id="mapping-1",
        project_id="project-1",
        destination_object_name="Customer",
        mapping_snapshot_version="v1",
        field_bindings=[
            {"source_field": "src_status", "destination_field": "status", "lookup_name": "status_code"},
            {"source_field": "src_type", "destination_field": "type", "lookup_name": "type_code"},
        ],
        status="approved",
    )

    with pytest.raises(MappingError, match="single-field binding is supported"):
        parse_primary_field_binding(snapshot)
```

- [ ] **Step 2: Run the tests and confirm they fail before implementation**

Run:

```bash
cd engine && PYTHONPATH=src pytest tests/test_mapping_slice.py -q
```

Expected:

- duplicate mapping snapshot version currently raises `IntegrityError` or equivalent database failure
- multi-binding snapshot currently truncates to the first binding instead of raising

- [ ] **Step 3: Implement the conflict guard and parser guard**

```python
class SnapshotVersionConflictError(MappingError):
    """Raised when an approved snapshot version already exists for the scope."""


def create_approved_mapping_snapshot(...):
    existing = db.scalar(
        select(MappingSnapshot).where(
            MappingSnapshot.project_id == project_id,
            MappingSnapshot.destination_object_name == destination_object_name,
            MappingSnapshot.mapping_snapshot_version == mapping_snapshot_version,
        )
    )
    if existing is not None:
        raise SnapshotVersionConflictError(
            f"Mapping snapshot version {mapping_snapshot_version!r} already exists for "
            f"{destination_object_name!r} in project {project_id}."
        )
    ...


def parse_primary_field_binding(snapshot: MappingSnapshot) -> FieldBinding:
    if not snapshot.field_bindings:
        raise SnapshotNotFoundError("Mapping snapshot has no field bindings.")
    if len(snapshot.field_bindings) > 1:
        raise MappingError("Only single-field binding is supported.")
    binding = snapshot.field_bindings[0]
    ...
```

```python
from .exceptions import (
    LookupDeltaCRError,
    MappingError,
    SnapshotImmutableError,
    SnapshotNotFoundError,
    SnapshotVersionConflictError,
    UnmappedLookupValueError,
)
```

- [ ] **Step 4: Update the source-model page and rerun tests**

Run:

```bash
cd engine && PYTHONPATH=src pytest tests/test_mapping_slice.py -q
```

Expected:

- tests pass
- source-model page now states that unsupported multi-binding snapshots are rejected explicitly

- [ ] **Step 5: Commit**

```bash
git add docs/domain/source-model.md engine/src/migrations_engine/mapping/exceptions.py engine/src/migrations_engine/mapping/__init__.py engine/src/migrations_engine/mapping/snapshots.py engine/tests/test_mapping_slice.py
git commit -m "fix(mapping): guard duplicate mapping versions and single-field binding"
```

### Task 2: Lookup value map migration chain cleanup

**Files:**
- Modify: `engine/migrations/versions/0012_lookup_value_maps.py`
- Modify: `engine/migrations/versions/0013_lookup_value_map_source_value_map.py`
- Modify: `engine/tests/test_lookup_mapping_models.py`

**Interfaces:**
- Consumes: existing Alembic chain ending at `0014_run_record_lookup_snapshot_versions`
- Produces: a clean fresh-install path for `lookup_value_maps` without the transient unique constraint window

- [ ] **Step 1: Write the regression test that inspects migration shape**

```python
def test_lookup_value_map_migrations_produce_final_shape() -> None:
    Base.metadata.create_all(bind=TEST_ENGINE)

    with SessionLocal() as db:
        source_definition_id = _seed_source_definition(db)
        db.add(
            LookupValueMap(
                source_definition_id=source_definition_id,
                lookup_name="status_code",
                destination_table=[{"id": "ACTIVE", "label": "Active"}],
                source_value_map={"A": "ACTIVE"},
                status="draft",
            )
        )
        db.commit()
```

This test should continue to prove that a fresh install allows multiple drafts for the same
lookup without a transient unique-constraint failure.

- [ ] **Step 2: Run the model test and confirm the current chain still reflects the problem**

Run:

```bash
cd engine && PYTHONPATH=src pytest tests/test_lookup_mapping_models.py -q
```

Expected:

- current migration chain still carries the transient `0012`/`0013` inconsistency

- [ ] **Step 3: Rewrite the migrations to the final table shape**

```python
# engine/migrations/versions/0012_lookup_value_maps.py
def upgrade() -> None:
    op.create_table(
        "lookup_value_maps",
        sa.Column("lookup_value_map_id", sa.String(length=36), primary_key=True),
        sa.Column("source_definition_id", sa.String(length=36), nullable=False),
        sa.Column("lookup_name", sa.String(length=128), nullable=False),
        sa.Column("destination_table", sa.JSON(), nullable=False),
        sa.Column("source_value_map", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False, server_default=sa.text("'draft'")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["source_definition_id"], ["source_definitions.source_definition_id"]),
    )
```

```python
# engine/migrations/versions/0013_lookup_value_map_source_value_map.py
def upgrade() -> None:
    # Final table shape already includes source_value_map in 0012.
    pass
```

- [ ] **Step 4: Run Alembic and the model test**

Run:

```bash
cd engine && source ../.venv/bin/activate && PYTHONPATH=src python -m alembic upgrade head && PYTHONPATH=src pytest tests/test_lookup_mapping_models.py -q
```

Expected:

- Alembic applies cleanly from a fresh database
- the model test still passes

- [ ] **Step 5: Commit**

```bash
git add engine/migrations/versions/0012_lookup_value_maps.py engine/migrations/versions/0013_lookup_value_map_source_value_map.py engine/tests/test_lookup_mapping_models.py
git commit -m "fix(migrations): remove transient lookup value map constraint window"
```
