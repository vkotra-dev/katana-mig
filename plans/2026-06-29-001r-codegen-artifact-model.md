# CodeGenerationArtifact Model and Migration — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the `CodeGenerationArtifact` ORM model to `models.py` and ship migration `0009`. No routes or UI — this plan exists so the model is importable before the code generation service (001y) needs it.

**Architecture:** One new table `code_generation_artifacts`. Supersession handled by a helper that marks previous `active` rows for the same `(project_id, destination_object_name)` as `superseded` before inserting a new `active` artifact.

**Depends on:** 001q (migration 0008 must exist before reading its revision for `down_revision`).

**Tech Stack:** Python ≥ 3.11, SQLAlchemy 2.x sync ORM, Alembic, pytest.

## Global Constraints

- `from __future__ import annotations` at top of every file
- All IDs: UUID4 via `new_id()` from `db.models`
- I18: read `down_revision` from `0008_source_intake_fields.py` before writing migration — never guess

---

## File Structure

| File | Action | Role |
|---|---|---|
| `engine/src/migrations_engine/db/models.py` | Modify | Add `CodeGenerationArtifact` class |
| `engine/migrations/versions/0009_codegen_artifact.py` | Create | CREATE TABLE code_generation_artifacts |
| `engine/tests/test_codegen_artifact_model.py` | Create | Insertion + supersession tests |

---

### Task 1 — Model and migration

- [ ] **Step 1: Read `down_revision` from 0008**

```bash
head -15 engine/migrations/versions/0008_source_intake_fields.py
```

Copy the `revision` value — that becomes the `down_revision` for 0009.

- [ ] **Step 2: Add `CodeGenerationArtifact` to `models.py`**

Append after `MappingArtifact`:

```python
class CodeGenerationArtifact(Base):
    __tablename__ = "code_generation_artifacts"

    codegen_artifact_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("project_registry.project_id"), nullable=False, index=True
    )
    destination_object_name: Mapped[str] = mapped_column(String(255), nullable=False)
    run_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("run_records.run_id"), nullable=True, index=True
    )
    source_slice_version: Mapped[str | None] = mapped_column(String(255))
    mapping_snapshot_version: Mapped[str | None] = mapped_column(String(255))
    lookup_snapshot_version: Mapped[str | None] = mapped_column(String(255))
    sql_bundle: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    superseded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
```

- [ ] **Step 3: Write `engine/migrations/versions/0009_codegen_artifact.py`**

```python
"""add code_generation_artifacts table

Revision ID: 0009_codegen_artifact
Revises: <paste revision from 0008 here>
Create Date: 2026-06-29
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0009_codegen_artifact"
down_revision = "<paste revision from 0008 here>"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "code_generation_artifacts",
        sa.Column("codegen_artifact_id", sa.String(length=36), primary_key=True),
        sa.Column("project_id", sa.String(length=36), nullable=False),
        sa.Column("destination_object_name", sa.String(length=255), nullable=False),
        sa.Column("run_id", sa.String(length=36), nullable=True),
        sa.Column("source_slice_version", sa.String(length=255), nullable=True),
        sa.Column("mapping_snapshot_version", sa.String(length=255), nullable=True),
        sa.Column("lookup_snapshot_version", sa.String(length=255), nullable=True),
        sa.Column("sql_bundle", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("superseded_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["project_id"], ["project_registry.project_id"]),
        sa.ForeignKeyConstraint(["run_id"], ["run_records.run_id"]),
    )
    op.create_index("ix_codegen_artifacts_project_id", "code_generation_artifacts", ["project_id"])
    op.create_index("ix_codegen_artifacts_run_id", "code_generation_artifacts", ["run_id"])


def downgrade() -> None:
    op.drop_index("ix_codegen_artifacts_run_id", table_name="code_generation_artifacts")
    op.drop_index("ix_codegen_artifacts_project_id", table_name="code_generation_artifacts")
    op.drop_table("code_generation_artifacts")
```

- [ ] **Step 4: Run migration**

```bash
cd engine && alembic upgrade head
```

Expected: `Running upgrade ... -> 0009_codegen_artifact`

- [ ] **Step 5: Write failing tests**

Create `engine/tests/test_codegen_artifact_model.py`:

```python
from __future__ import annotations

from datetime import UTC, datetime

import pytest
from migrations_engine.db.models import CodeGenerationArtifact, ProjectRegistry, ProjectDefinition, new_id
from migrations_engine.db.session import SessionLocal


def _make_project(db) -> str:
    pid = new_id()
    defn = ProjectDefinition(
        definition_id=new_id(), project_id=pid, name="Test", status="active", domain_config=None,
    )
    db.add(defn)
    reg = ProjectRegistry(project_id=pid, name="Test", definition_id=defn.definition_id, status="active")
    db.add(reg)
    db.flush()
    return pid


def test_insert_active_artifact() -> None:
    with SessionLocal() as db:
        pid = _make_project(db)
        art = CodeGenerationArtifact(
            codegen_artifact_id=new_id(),
            project_id=pid,
            destination_object_name="Customer",
            sql_bundle="CREATE TABLE stg_customer (id INT);",
            status="active",
        )
        db.add(art)
        db.commit()
        fetched = db.get(CodeGenerationArtifact, art.codegen_artifact_id)
        assert fetched.status == "active"
        assert fetched.sql_bundle is not None


def test_supersession_marks_old_artifact() -> None:
    with SessionLocal() as db:
        pid = _make_project(db)

        first = CodeGenerationArtifact(
            codegen_artifact_id=new_id(), project_id=pid,
            destination_object_name="Customer", status="active",
            sql_bundle="-- v1",
        )
        db.add(first)
        db.flush()

        # Supersede first before inserting second
        first.status = "superseded"
        first.superseded_at = datetime.now(UTC)

        second = CodeGenerationArtifact(
            codegen_artifact_id=new_id(), project_id=pid,
            destination_object_name="Customer", status="active",
            sql_bundle="-- v2",
        )
        db.add(second)
        db.commit()

        active = (
            db.query(CodeGenerationArtifact)
            .filter_by(project_id=pid, destination_object_name="Customer", status="active")
            .all()
        )
        superseded = (
            db.query(CodeGenerationArtifact)
            .filter_by(project_id=pid, destination_object_name="Customer", status="superseded")
            .all()
        )
        assert len(active) == 1
        assert active[0].sql_bundle == "-- v2"
        assert len(superseded) == 1
        assert superseded[0].superseded_at is not None


def test_delivery_bundle_query() -> None:
    """Active artifacts per project assemble the delivery bundle."""
    with SessionLocal() as db:
        pid = _make_project(db)
        for obj in ("Customer", "Account", "Address"):
            db.add(CodeGenerationArtifact(
                codegen_artifact_id=new_id(), project_id=pid,
                destination_object_name=obj, status="active", sql_bundle=f"-- {obj}",
            ))
        db.commit()

        bundle = (
            db.query(CodeGenerationArtifact)
            .filter_by(project_id=pid, status="active")
            .order_by(CodeGenerationArtifact.destination_object_name)
            .all()
        )
        assert [a.destination_object_name for a in bundle] == ["Account", "Address", "Customer"]
```

- [ ] **Step 6: Run tests — confirm they pass**

```bash
cd engine && python -m pytest tests/test_codegen_artifact_model.py -v
```

Expected: all pass.

- [ ] **Step 7: Commit**

```bash
git add engine/src/migrations_engine/db/models.py \
        engine/migrations/versions/0009_codegen_artifact.py \
        engine/tests/test_codegen_artifact_model.py
git commit -m "feat: add CodeGenerationArtifact model and migration 0009"
```
