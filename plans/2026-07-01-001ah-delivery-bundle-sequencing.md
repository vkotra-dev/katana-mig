Task: tasks/001ah-delivery-bundle-sequencing.md
Spec: docs/superpowers/specs/2026-07-01-delivery-bundle-sequencing-design.md
Domain: docs/domain/ui.md (authoritative), docs/domain/api.md

## Source of truth

`docs/superpowers/specs/2026-07-01-delivery-bundle-sequencing-design.md` defines what to build.
Mockmigration (if referenced) is for styling patterns only — not content authority.
`docs/domain/ui.md` governs role-based visibility rules.

## Current state

| File | What exists |
|---|---|
| `engine/src/migrations_engine/ai/config.py` | `MigrationModelConfig` with 4 slots: `pii_review`, `field_mapping`, `script_generation`, `script_correction` |
| `engine/config/engine.yaml` | `migration.models` has the same 4 keys |
| `engine/src/migrations_engine/ai/factory.py` | `_SLOT_MAP` with 7 entries |
| `engine/src/migrations_engine/db/models.py` | No `ProjectSchemaAnalysis` model |
| `engine/src/migrations_engine/codegen/service.py` | `build_delivery_bundle_text` sorts alphabetically, no sequencing |
| `engine/src/migrations_engine/routes/codegen.py` | No schema-analysis routes |
| `web/lib/codegen-api.ts` | No `SchemaAnalysisRecord` type or `getSchemaAnalysis`/`triggerSchemaAnalysis` helpers |
| `web/components/projects/SourceList.tsx` | No analysis prompt banner |
| `web/app/projects/[id]/codegen/page.tsx` | No schema analysis report panel |

## Blast radius

| File | Action |
|---|---|
| `engine/config/engine.yaml` | modify — add `schema_dependency` key under `migration.models` |
| `engine/src/migrations_engine/ai/config.py` | modify — add `schema_dependency` field to `MigrationModelConfig` |
| `engine/src/migrations_engine/ai/factory.py` | modify — add `schema_dependency` to `_SLOT_MAP` |
| `engine/src/migrations_engine/db/models.py` | modify — add `ProjectSchemaAnalysis` model |
| `engine/migrations/versions/0016_project_schema_analysis.py` | create — migration |
| `engine/src/migrations_engine/codegen/schema_analysis.py` | create — AI call, topological sort, service functions |
| `engine/src/migrations_engine/api/schemas.py` | modify — add `ProjectSchemaAnalysisResponse` |
| `engine/src/migrations_engine/routes/codegen.py` | modify — add `POST` and `GET` schema-analysis routes |
| `engine/src/migrations_engine/codegen/service.py` | modify — use sequence in `build_delivery_bundle_text` |
| `engine/src/migrations_engine/codegen/__init__.py` | modify — export new functions |
| `engine/tests/test_schema_analysis_api.py` | create — service + route tests |
| `web/lib/codegen-api.ts` | modify — add `SchemaAnalysisRecord`, `getSchemaAnalysis`, `triggerSchemaAnalysis` |
| `web/components/projects/SourceList.tsx` | modify — fetch analysis on mount; show banner if null + source count > 0 |
| `web/app/projects/[id]/codegen/page.tsx` | modify — fetch analysis; show report panel |
| `web/app/projects/[id]/codegen/page.test.tsx` | create — report panel tests |
| `web/components/projects/SourceList.test.tsx` | create (or modify if exists) — banner tests |

---

# Delivery Bundle Sequencing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Use AI to analyse the project's `destination_schema_ddl` once, produce a FK-dependency-ordered sequence of destination objects, store it on the project, and use it to order (and number) the delivery bundle SQL output. Surface a prompt banner in the Sources tab and a report panel in the codegen page.

**Architecture:** New AI task slot `schema_dependency` → new service `codegen/schema_analysis.py` calls AI with the DDL, topological-sorts the result, persists to `ProjectSchemaAnalysis` (one record per project, upserted). `build_delivery_bundle_text` reads the sequence to sort artifacts and prefix blocks with `-- [01]` numbering. Two new routes on the `codegen.py` router. Two UI surfaces: banner in `SourceList` (shown when first source exists but no analysis), report panel in codegen page.

**Tech Stack:** FastAPI, SQLAlchemy 2, Alembic, Pydantic v2, pytest; Next.js App Router, React, TypeScript, Vitest + Testing Library

## Global Constraints

- Revision ID `"0016_project_schema_analysis"` is 26 chars — within the 32-char `alembic_version` limit
- `down_revision = "0015_reconciliation_tables"` — do not change the chain
- Route auth: `require_project_access(db, user=actor, project_id=project_id)` — all roles read; no write-gate beyond project membership
- Styling follows mockmigration patterns; spec is content authority
- Cycle-breaking in topological sort: alphabetical insertion of remaining nodes — no hard failure

---

### Task 1: AI config — add `schema_dependency` slot

**Files:**
- Modify: `engine/config/engine.yaml`
- Modify: `engine/src/migrations_engine/ai/config.py`
- Modify: `engine/src/migrations_engine/ai/factory.py`

**Interfaces:**
- Produces: `get_adapter("schema_dependency")` returns an `AIAdapter` instance

- [ ] **Step 1: Write the failing test**

Create `engine/tests/test_schema_dependency_slot.py`:

```python
from __future__ import annotations

import os
import pytest
from pathlib import Path


def test_schema_dependency_slot_in_slot_map() -> None:
    from migrations_engine.ai.factory import _SLOT_MAP
    assert "schema_dependency" in _SLOT_MAP


def test_migration_model_config_has_schema_dependency() -> None:
    from migrations_engine.ai.config import MigrationModelConfig
    import dataclasses
    fields = {f.name for f in dataclasses.fields(MigrationModelConfig)}
    assert "schema_dependency" in fields
```

- [ ] **Step 2: Run to verify it fails**

```bash
cd /Users/vjkotra/projects/katana/engine/tests
python -m pytest test_schema_dependency_slot.py -v
```

Expected: FAIL — `schema_dependency` not in `_SLOT_MAP`.

- [ ] **Step 3: Add `schema_dependency` to engine.yaml**

Open `engine/config/engine.yaml`. Under `migration: models:`, add:

```yaml
migration:
  models:
    pii_review: ${MODEL_PII_REVIEW}
    field_mapping: ${MODEL_FIELD_MAPPING}
    script_generation: ${MODEL_SCRIPT_GENERATION}
    script_correction: ${MODEL_SCRIPT_CORRECTION}
    schema_dependency: ${MODEL_SCHEMA_DEPENDENCY}
```

- [ ] **Step 4: Add field to `MigrationModelConfig`**

Open `engine/src/migrations_engine/ai/config.py`. Add `schema_dependency: str` to the `MigrationModelConfig` dataclass:

```python
@dataclass(frozen=True)
class MigrationModelConfig:
    pii_review: str
    field_mapping: str
    script_generation: str
    script_correction: str
    schema_dependency: str
```

In `_parse_config`, inside the `MigrationModelConfig(...)` call, add:

```python
schema_dependency=_require_str(migration_models, "schema_dependency", "migration.models.schema_dependency"),
```

- [ ] **Step 5: Add to `_SLOT_MAP` in factory.py**

Open `engine/src/migrations_engine/ai/factory.py`. Add to `_SLOT_MAP`:

```python
"schema_dependency": lambda config: config.migration_models.schema_dependency,
```

- [ ] **Step 6: Run the test to verify it passes**

```bash
cd /Users/vjkotra/projects/katana/engine/tests
python -m pytest test_schema_dependency_slot.py -v
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add engine/config/engine.yaml \
        engine/src/migrations_engine/ai/config.py \
        engine/src/migrations_engine/ai/factory.py \
        engine/tests/test_schema_dependency_slot.py
git commit -m "feat(001ah): add schema_dependency AI task slot"
```

---

### Task 2: DB model + migration

**Files:**
- Modify: `engine/src/migrations_engine/db/models.py`
- Create: `engine/migrations/versions/0016_project_schema_analysis.py`

**Interfaces:**
- Produces: `ProjectSchemaAnalysis` ORM class with fields: `analysis_id: str`, `project_id: str`, `destination_object_sequence: list[str]`, `identified_count: int`, `analyzed_at: datetime`

- [ ] **Step 1: Write the failing test**

Add to `engine/tests/test_schema_dependency_slot.py`:

```python
def test_project_schema_analysis_model_exists() -> None:
    from migrations_engine.db.models import ProjectSchemaAnalysis
    assert ProjectSchemaAnalysis.__tablename__ == "project_schema_analyses"
```

- [ ] **Step 2: Run to verify it fails**

```bash
cd /Users/vjkotra/projects/katana/engine/tests
python -m pytest test_schema_dependency_slot.py::test_project_schema_analysis_model_exists -v
```

Expected: FAIL — `ImportError: cannot import name 'ProjectSchemaAnalysis'`.

- [ ] **Step 3: Add `ProjectSchemaAnalysis` model to models.py**

Open `engine/src/migrations_engine/db/models.py`. Add after the `ReconciliationLineageRow` class and before `CodeGenerationArtifact`:

```python
class ProjectSchemaAnalysis(Base):
    __tablename__ = "project_schema_analyses"

    analysis_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("project_definitions.project_id"), nullable=False, unique=True
    )
    destination_object_sequence: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    identified_count: Mapped[int] = mapped_column(Integer, nullable=False)
    analyzed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
```

`unique=True` on `project_id` enforces one analysis record per project (upsert pattern).

- [ ] **Step 4: Create migration 0016**

Create `engine/migrations/versions/0016_project_schema_analysis.py`:

```python
"""add project schema analysis table

Revision ID: 0016_project_schema_analysis
Revises: 0015_reconciliation_tables
Create Date: 2026-07-01
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0016_project_schema_analysis"
down_revision = "0015_reconciliation_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "project_schema_analyses",
        sa.Column("analysis_id", sa.String(36), primary_key=True),
        sa.Column(
            "project_id",
            sa.String(36),
            sa.ForeignKey("project_definitions.project_id"),
            nullable=False,
            unique=True,
        ),
        sa.Column("destination_object_sequence", sa.JSON(), nullable=False),
        sa.Column("identified_count", sa.Integer(), nullable=False),
        sa.Column("analyzed_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_project_schema_analyses_project_id",
        "project_schema_analyses",
        ["project_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_project_schema_analyses_project_id", table_name="project_schema_analyses")
    op.drop_table("project_schema_analyses")
```

- [ ] **Step 5: Run the test to verify it passes**

```bash
cd /Users/vjkotra/projects/katana/engine/tests
python -m pytest test_schema_dependency_slot.py -v
```

Expected: all 3 tests PASS.

- [ ] **Step 6: Commit**

```bash
git add engine/src/migrations_engine/db/models.py \
        engine/migrations/versions/0016_project_schema_analysis.py \
        engine/tests/test_schema_dependency_slot.py
git commit -m "feat(001ah): add ProjectSchemaAnalysis model and migration 0016"
```

---

### Task 3: Schema analysis service

**Files:**
- Create: `engine/src/migrations_engine/codegen/schema_analysis.py`
- Modify: `engine/src/migrations_engine/codegen/__init__.py`
- Create: `engine/tests/test_schema_analysis_api.py`

**Interfaces:**
- Consumes: `get_adapter("schema_dependency")`, `ProjectSchemaAnalysis` ORM model, `ProjectDefinition` ORM model
- Produces:
  - `run_schema_analysis(db, project_id=str) -> ProjectSchemaAnalysisResponse` — AI call, upsert, return
  - `get_schema_analysis(db, project_id=str) -> ProjectSchemaAnalysisResponse | None` — read only
  - `ProjectSchemaAnalysisResponse` Pydantic model (also added to `api/schemas.py` in Task 4)

- [ ] **Step 1: Write the failing tests**

Create `engine/tests/test_schema_analysis_api.py`:

```python
from __future__ import annotations

import uuid
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from sqlite_test_support import Base, SessionLocal, TEST_ENGINE
from migrations_engine.app import app
from migrations_engine.auth.passwords import hash_password
from migrations_engine.config import get_settings
from migrations_engine.db.models import (
    ProjectDefinition,
    ProjectRegistry,
    ProjectSchemaAnalysis,
    User,
)
from migrations_engine.roles import CENTRAL_TEAM_ROLE
import migrations_engine.codegen.schema_analysis as sa_module

client = TestClient(app)

DDL = """
CREATE TABLE customers (
    customer_id INT PRIMARY KEY
);
CREATE TABLE orders (
    order_id INT PRIMARY KEY,
    customer_id INT REFERENCES customers(customer_id)
);
CREATE TABLE order_items (
    item_id INT PRIMARY KEY,
    order_id INT REFERENCES orders(order_id)
);
"""


class FakeSchemaAdapter:
    model_id = "gpt-4o-mini"

    def call(self, system: str, user: str, response_model: type[object]):
        return response_model(
            objects=[
                {"name": "customers", "depends_on": []},
                {"name": "orders", "depends_on": ["customers"]},
                {"name": "order_items", "depends_on": ["orders"]},
            ]
        )


@pytest.fixture(scope="module", autouse=True)
def _setup_db() -> None:
    Base.metadata.create_all(bind=TEST_ENGINE)
    settings = get_settings()
    if not settings.bootstrap_admin_email or not settings.bootstrap_admin_password:
        pytest.skip("bootstrap credentials not configured")
    with SessionLocal() as db:
        if db.scalar(select(User).where(User.email == settings.bootstrap_admin_email.strip().lower())) is None:
            db.add(
                User(
                    user_id=str(uuid.uuid4()),
                    email=settings.bootstrap_admin_email.strip().lower(),
                    display_name="Admin",
                    password_hash=hash_password(settings.bootstrap_admin_password),
                    role=CENTRAL_TEAM_ROLE,
                    status="active",
                )
            )
        db.commit()


@pytest.fixture(autouse=True)
def _clear_caches() -> None:
    get_settings.cache_clear()


def _login() -> str:
    settings = get_settings()
    r = client.post("/auth/login", json={
        "email": settings.bootstrap_admin_email,
        "password": settings.bootstrap_admin_password,
    })
    assert r.status_code == 200
    return r.json()["access_token"]


@pytest.fixture
def project_with_ddl() -> str:
    with SessionLocal() as db:
        pid = str(uuid.uuid4())
        db.add(ProjectDefinition(
            project_id=pid,
            name="Schema Test",
            domain_config={"destination_schema_ddl": DDL},
        ))
        db.add(ProjectRegistry(project_id=pid, status="active"))
        db.commit()
    return pid


@pytest.fixture
def project_no_ddl() -> str:
    with SessionLocal() as db:
        pid = str(uuid.uuid4())
        db.add(ProjectDefinition(project_id=pid, name="No DDL Project", domain_config={}))
        db.add(ProjectRegistry(project_id=pid, status="active"))
        db.commit()
    return pid


def test_topological_sort_orders_by_dependency() -> None:
    from migrations_engine.codegen.schema_analysis import _topological_sort, _ObjectDependency
    objects = [
        _ObjectDependency(name="order_items", depends_on=["orders"]),
        _ObjectDependency(name="orders", depends_on=["customers"]),
        _ObjectDependency(name="customers", depends_on=[]),
    ]
    result = _topological_sort(objects)
    assert result.index("customers") < result.index("orders")
    assert result.index("orders") < result.index("order_items")


def test_topological_sort_cycle_does_not_raise() -> None:
    from migrations_engine.codegen.schema_analysis import _topological_sort, _ObjectDependency
    objects = [
        _ObjectDependency(name="a", depends_on=["b"]),
        _ObjectDependency(name="b", depends_on=["a"]),
    ]
    result = _topological_sort(objects)
    assert set(result) == {"a", "b"}


def test_get_schema_analysis_returns_none_when_absent(project_with_ddl: str) -> None:
    with SessionLocal() as db:
        from migrations_engine.codegen.schema_analysis import get_schema_analysis
        result = get_schema_analysis(db, project_id=project_with_ddl)
    assert result is None


def test_run_schema_analysis_creates_record(project_with_ddl: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sa_module, "get_adapter", lambda task: FakeSchemaAdapter())
    with SessionLocal() as db:
        from migrations_engine.codegen.schema_analysis import run_schema_analysis
        result = run_schema_analysis(db, project_id=project_with_ddl)
    assert result.identified_count == 3
    assert result.destination_object_sequence[0] == "customers"
    assert result.processed_count == 0  # no active artifacts yet


def test_run_schema_analysis_upserts_on_rerun(project_with_ddl: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sa_module, "get_adapter", lambda task: FakeSchemaAdapter())
    with SessionLocal() as db:
        from migrations_engine.codegen.schema_analysis import run_schema_analysis
        run_schema_analysis(db, project_id=project_with_ddl)
        run_schema_analysis(db, project_id=project_with_ddl)
    with SessionLocal() as db:
        count = db.query(ProjectSchemaAnalysis).filter_by(project_id=project_with_ddl).count()
    assert count == 1  # not 2


def test_run_schema_analysis_raises_422_when_no_ddl(project_no_ddl: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sa_module, "get_adapter", lambda task: FakeSchemaAdapter())
    with SessionLocal() as db:
        from migrations_engine.codegen.schema_analysis import run_schema_analysis
        from migrations_engine.api.deps import AuthApiError
        with pytest.raises(AuthApiError) as exc_info:
            run_schema_analysis(db, project_id=project_no_ddl)
    assert exc_info.value.status_code == 422


def test_post_schema_analysis_route(project_with_ddl: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sa_module, "get_adapter", lambda task: FakeSchemaAdapter())
    token = _login()
    r = client.post(
        f"/projects/{project_with_ddl}/schema-analysis",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["identified_count"] == 3
    assert "destination_object_sequence" in body


def test_get_schema_analysis_route(project_with_ddl: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sa_module, "get_adapter", lambda task: FakeSchemaAdapter())
    token = _login()
    # trigger first
    client.post(
        f"/projects/{project_with_ddl}/schema-analysis",
        headers={"Authorization": f"Bearer {token}"},
    )
    r = client.get(
        f"/projects/{project_with_ddl}/schema-analysis",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    assert r.json()["identified_count"] == 3


def test_get_schema_analysis_route_returns_null_when_absent(project_with_ddl: str) -> None:
    # fresh project, no POST yet
    with SessionLocal() as db:
        pid = str(uuid.uuid4())
        db.add(ProjectDefinition(
            project_id=pid,
            name="Fresh",
            domain_config={"destination_schema_ddl": DDL},
        ))
        db.add(ProjectRegistry(project_id=pid, status="active"))
        db.commit()
    token = _login()
    r = client.get(
        f"/projects/{pid}/schema-analysis",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    assert r.json() is None
```

- [ ] **Step 2: Run to verify tests fail**

```bash
cd /Users/vjkotra/projects/katana/engine/tests
python -m pytest test_schema_analysis_api.py -v
```

Expected: FAIL — `ImportError: cannot import name 'schema_analysis'`.

- [ ] **Step 3: Create `engine/src/migrations_engine/codegen/schema_analysis.py`**

```python
from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..api.deps import AuthApiError
from ..db.models import CodeGenerationArtifact, ProjectDefinition, ProjectSchemaAnalysis

try:
    from ..ai.factory import get_adapter
except ModuleNotFoundError:  # pragma: no cover
    get_adapter = None  # type: ignore[assignment]


SYSTEM_PROMPT = (
    "You are a SQL DDL analyst. Given a multi-table DDL script, identify all destination "
    "objects (tables/views) and their dependency relationships based on FOREIGN KEY / "
    "REFERENCES clauses. Return a JSON object matching the schema below."
)


class _ObjectDependency(BaseModel):
    name: str
    depends_on: list[str]


class _DDLAnalysisResult(BaseModel):
    objects: list[_ObjectDependency]


def _topological_sort(objects: list[_ObjectDependency]) -> list[str]:
    """Kahn's algorithm. Cycles are broken by appending remaining nodes alphabetically."""
    all_names = {obj.name for obj in objects}
    # successors[X] = nodes that must come AFTER X (because they depend on X)
    successors: dict[str, list[str]] = {obj.name: [] for obj in objects}
    in_degree: dict[str, int] = {obj.name: 0 for obj in objects}
    for obj in objects:
        for dep in obj.depends_on:
            if dep in all_names:
                successors[dep].append(obj.name)
                in_degree[obj.name] += 1
    queue = sorted(name for name, deg in in_degree.items() if deg == 0)
    result: list[str] = []
    while queue:
        node = queue.pop(0)
        result.append(node)
        for successor in sorted(successors[node]):
            in_degree[successor] -= 1
            if in_degree[successor] == 0:
                queue.append(successor)
    # cycle fallback: remaining nodes in alphabetical order
    remaining = sorted(name for name in all_names if name not in result)
    result.extend(remaining)
    return result


def _processed_count(db: Session, project_id: str, sequence: list[str]) -> int:
    active_names = set(
        db.scalars(
            select(CodeGenerationArtifact.destination_object_name)
            .where(
                CodeGenerationArtifact.project_id == project_id,
                CodeGenerationArtifact.status == "active",
            )
        ).all()
    )
    return sum(1 for name in sequence if name in active_names)


def _to_response(
    db: Session,
    record: ProjectSchemaAnalysis,
) -> "ProjectSchemaAnalysisResponse":
    from ..api.schemas import ProjectSchemaAnalysisResponse
    sequence = record.destination_object_sequence
    return ProjectSchemaAnalysisResponse(
        analysis_id=record.analysis_id,
        project_id=record.project_id,
        destination_object_sequence=sequence,
        identified_count=record.identified_count,
        processed_count=_processed_count(db, record.project_id, sequence),
        analyzed_at=record.analyzed_at.isoformat(),
    )


def run_schema_analysis(db: Session, *, project_id: str) -> "ProjectSchemaAnalysisResponse":
    project = db.get(ProjectDefinition, project_id)
    if project is None:
        raise AuthApiError("not_found", "Project not found.", 404)

    ddl = (project.domain_config or {}).get("destination_schema_ddl")
    if not ddl:
        raise AuthApiError("missing_ddl", "Project has no destination_schema_ddl set.", 422)

    adapter = get_adapter("schema_dependency")
    result = adapter.call(SYSTEM_PROMPT, ddl, _DDLAnalysisResult)
    sequence = _topological_sort(result.objects)

    existing = db.scalars(
        select(ProjectSchemaAnalysis).where(ProjectSchemaAnalysis.project_id == project_id)
    ).first()

    now = datetime.now(UTC)
    if existing:
        existing.destination_object_sequence = sequence
        existing.identified_count = len(sequence)
        existing.analyzed_at = now
        db.flush()
        record = existing
    else:
        record = ProjectSchemaAnalysis(
            project_id=project_id,
            destination_object_sequence=sequence,
            identified_count=len(sequence),
            analyzed_at=now,
        )
        db.add(record)
        db.flush()

    db.commit()
    db.refresh(record)
    return _to_response(db, record)


def get_schema_analysis(db: Session, *, project_id: str) -> "ProjectSchemaAnalysisResponse | None":
    record = db.scalars(
        select(ProjectSchemaAnalysis).where(ProjectSchemaAnalysis.project_id == project_id)
    ).first()
    if record is None:
        return None
    return _to_response(db, record)
```

- [ ] **Step 4: Add `ProjectSchemaAnalysisResponse` to `engine/src/migrations_engine/api/schemas.py`**

Open `engine/src/migrations_engine/api/schemas.py`. Add after the reconciliation schemas:

```python
class ProjectSchemaAnalysisResponse(BaseModel):
    analysis_id: str
    project_id: str
    destination_object_sequence: list[str]
    identified_count: int
    processed_count: int
    analyzed_at: str
```

- [ ] **Step 5: Export from `engine/src/migrations_engine/codegen/__init__.py`**

Open `engine/src/migrations_engine/codegen/__init__.py`. Add the new exports:

```python
from .schema_analysis import get_schema_analysis, run_schema_analysis

__all__ = [
    ...,  # existing exports
    "get_schema_analysis",
    "run_schema_analysis",
]
```

- [ ] **Step 6: Run the tests to verify they pass**

```bash
cd /Users/vjkotra/projects/katana/engine/tests
python -m pytest test_schema_analysis_api.py -v
```

Expected: all tests PASS.

- [ ] **Step 7: Commit**

```bash
git add engine/src/migrations_engine/codegen/schema_analysis.py \
        engine/src/migrations_engine/codegen/__init__.py \
        engine/src/migrations_engine/api/schemas.py \
        engine/tests/test_schema_analysis_api.py
git commit -m "feat(001ah): add schema analysis service with AI DDL parsing and topological sort"
```

---

### Task 4: API routes

**Files:**
- Modify: `engine/src/migrations_engine/routes/codegen.py`

**Interfaces:**
- Consumes: `run_schema_analysis`, `get_schema_analysis` from `codegen.schema_analysis`; `ProjectSchemaAnalysisResponse` from `api.schemas`; `require_project_access` from `management.access`
- Produces:
  - `POST /projects/{project_id}/schema-analysis` → `ProjectSchemaAnalysisResponse`
  - `GET /projects/{project_id}/schema-analysis` → `ProjectSchemaAnalysisResponse | None`

- [ ] **Step 1: The tests for the routes are already in `test_schema_analysis_api.py` (Task 3). Run them to confirm they fail on the route before implementation**

```bash
cd /Users/vjkotra/projects/katana/engine/tests
python -m pytest test_schema_analysis_api.py::test_post_schema_analysis_route test_schema_analysis_api.py::test_get_schema_analysis_route -v
```

Expected: FAIL — 404 (routes not registered yet).

- [ ] **Step 2: Add routes to `engine/src/migrations_engine/routes/codegen.py`**

Open `engine/src/migrations_engine/routes/codegen.py`. Add these imports at the top (with existing imports):

```python
from ..codegen.schema_analysis import get_schema_analysis as _get_schema_analysis
from ..codegen.schema_analysis import run_schema_analysis as _run_schema_analysis
from ..api.schemas import ProjectSchemaAnalysisResponse
```

Add these two routes after the existing `download_delivery_bundle` route:

```python
@router.post("/projects/{project_id}/schema-analysis", response_model=ProjectSchemaAnalysisResponse)
def trigger_schema_analysis(
    project_id: str,
    actor: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ProjectSchemaAnalysisResponse:
    require_project_access(db, user=actor, project_id=project_id)
    return _run_schema_analysis(db, project_id=project_id)


@router.get("/projects/{project_id}/schema-analysis", response_model=ProjectSchemaAnalysisResponse | None)
def get_schema_analysis_route(
    project_id: str,
    actor: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ProjectSchemaAnalysisResponse | None:
    require_project_access(db, user=actor, project_id=project_id)
    return _get_schema_analysis(db, project_id=project_id)
```

- [ ] **Step 3: Run the route tests**

```bash
cd /Users/vjkotra/projects/katana/engine/tests
python -m pytest test_schema_analysis_api.py -v
```

Expected: all tests PASS.

- [ ] **Step 4: Commit**

```bash
git add engine/src/migrations_engine/routes/codegen.py
git commit -m "feat(001ah): add POST/GET schema-analysis routes"
```

---

### Task 5: Sequenced delivery bundle output

**Files:**
- Modify: `engine/src/migrations_engine/codegen/service.py`

**Interfaces:**
- Consumes: `get_schema_analysis(db, project_id=str)` from `codegen.schema_analysis`
- Produces: `build_delivery_bundle_text` now prefixes SQL blocks with `-- [01] table_name` when analysis exists; falls back to `-- table_name` when absent

- [ ] **Step 1: Write the failing test**

Add to `engine/tests/test_schema_analysis_api.py`:

```python
def test_bundle_uses_sequence_ordering(project_with_ddl: str, monkeypatch: pytest.MonkeyPatch) -> None:
    from migrations_engine.codegen.schema_analysis import run_schema_analysis
    from migrations_engine.codegen.service import build_delivery_bundle_text
    monkeypatch.setattr(sa_module, "get_adapter", lambda task: FakeSchemaAdapter())

    # Create active artifacts in reverse order
    with SessionLocal() as db:
        run_schema_analysis(db, project_id=project_with_ddl)
        for name in ["order_items", "orders", "customers"]:
            db.add(CodeGenerationArtifact(
                codegen_artifact_id=str(uuid.uuid4()),
                project_id=project_with_ddl,
                destination_object_name=name,
                status="active",
                sql_bundle=f"-- SQL for {name}",
            ))
        db.commit()

    with SessionLocal() as db:
        result = build_delivery_bundle_text(db, project_id=project_with_ddl)

    lines = result.sql_bundle.splitlines()
    heading_lines = [l for l in lines if l.startswith("-- [")]
    assert heading_lines[0] == "-- [01] customers"
    assert heading_lines[1] == "-- [02] orders"
    assert heading_lines[2] == "-- [03] order_items"


def test_bundle_falls_back_to_alphabetical_when_no_analysis() -> None:
    from migrations_engine.codegen.service import build_delivery_bundle_text
    with SessionLocal() as db:
        pid = str(uuid.uuid4())
        db.add(ProjectDefinition(project_id=pid, name="No Analysis", domain_config={}))
        db.add(ProjectRegistry(project_id=pid, status="active"))
        for name in ["zebra", "alpha"]:
            db.add(CodeGenerationArtifact(
                codegen_artifact_id=str(uuid.uuid4()),
                project_id=pid,
                destination_object_name=name,
                status="active",
                sql_bundle="SELECT 1",
            ))
        db.commit()
        result = build_delivery_bundle_text(db, project_id=pid)

    assert "-- [" not in result.sql_bundle        # no sequence prefixes
    assert "-- alpha" in result.sql_bundle         # plain heading
    assert result.sql_bundle.index("-- alpha") < result.sql_bundle.index("-- zebra")
```

- [ ] **Step 2: Run to verify tests fail**

```bash
cd /Users/vjkotra/projects/katana/engine/tests
python -m pytest test_schema_analysis_api.py::test_bundle_uses_sequence_ordering test_schema_analysis_api.py::test_bundle_falls_back_to_alphabetical_when_no_analysis -v
```

Expected: FAIL.

- [ ] **Step 3: Update `build_delivery_bundle_text` in `engine/src/migrations_engine/codegen/service.py`**

Open `engine/src/migrations_engine/codegen/service.py`. Add this import at the top:

```python
from .schema_analysis import get_schema_analysis
```

Replace the entire `build_delivery_bundle_text` function with:

```python
def build_delivery_bundle_text(
    db: Session,
    *,
    project_id: str,
) -> DeliveryBundleResponse:
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

- [ ] **Step 4: Run all schema analysis tests**

```bash
cd /Users/vjkotra/projects/katana/engine/tests
python -m pytest test_schema_analysis_api.py -v
```

Expected: all tests PASS.

- [ ] **Step 5: Run the full engine test suite**

```bash
cd /Users/vjkotra/projects/katana/engine/tests
python -m pytest -v
```

Expected: all tests PASS (including pre-existing codegen tests).

- [ ] **Step 6: Commit**

```bash
git add engine/src/migrations_engine/codegen/service.py \
        engine/tests/test_schema_analysis_api.py
git commit -m "feat(001ah): sequence delivery bundle by FK dependency order"
```

---

### Task 6: Frontend API helpers

**Files:**
- Modify: `web/lib/codegen-api.ts`

**Interfaces:**
- Produces:
  - `SchemaAnalysisRecord` TypeScript interface
  - `getSchemaAnalysis(token, projectId): Promise<SchemaAnalysisRecord | null>`
  - `triggerSchemaAnalysis(token, projectId): Promise<SchemaAnalysisRecord>`

- [ ] **Step 1: Write the failing test**

Create `web/lib/__tests__/codegen-api.schema-analysis.test.ts` (create the `__tests__` directory if it doesn't exist: `mkdir -p web/lib/__tests__`):

```typescript
import { describe, expect, it, vi, beforeEach } from "vitest";
import { getSchemaAnalysis, triggerSchemaAnalysis } from "../codegen-api";

const fetchMock = vi.fn();
vi.stubGlobal("fetch", fetchMock);

const ANALYSIS = {
  analysis_id: "a-1",
  project_id: "p-1",
  destination_object_sequence: ["customers", "orders"],
  identified_count: 2,
  processed_count: 1,
  analyzed_at: "2026-07-01T00:00:00Z",
};

beforeEach(() => {
  vi.clearAllMocks();
});

describe("getSchemaAnalysis", () => {
  it("returns mapped record when analysis exists", async () => {
    fetchMock.mockResolvedValue({ ok: true, status: 200, json: async () => ANALYSIS });
    const result = await getSchemaAnalysis("tok", "p-1");
    expect(result).not.toBeNull();
    expect(result?.analysisId).toBe("a-1");
    expect(result?.destinationObjectSequence).toEqual(["customers", "orders"]);
    expect(result?.processedCount).toBe(1);
  });

  it("returns null when server responds with null", async () => {
    fetchMock.mockResolvedValue({ ok: true, status: 200, json: async () => null });
    const result = await getSchemaAnalysis("tok", "p-1");
    expect(result).toBeNull();
  });
});

describe("triggerSchemaAnalysis", () => {
  it("posts and returns mapped record", async () => {
    fetchMock.mockResolvedValue({ ok: true, status: 200, json: async () => ANALYSIS });
    const result = await triggerSchemaAnalysis("tok", "p-1");
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/projects/p-1/schema-analysis"),
      expect.objectContaining({ method: "POST" }),
    );
    expect(result.identifiedCount).toBe(2);
  });
});
```

- [ ] **Step 2: Run to verify tests fail**

```bash
cd /Users/vjkotra/projects/katana/web
npm test -- lib/__tests__/codegen-api.schema-analysis.test.ts
```

Expected: FAIL — `getSchemaAnalysis` not exported.

- [ ] **Step 3: Add types and helpers to `web/lib/codegen-api.ts`**

Open `web/lib/codegen-api.ts`. Add after the existing interfaces (after `DeliveryBundleRecord`):

```typescript
export interface SchemaAnalysisRecord {
  analysisId: string;
  projectId: string;
  destinationObjectSequence: string[];
  identifiedCount: number;
  processedCount: number;
  analyzedAt: string;
}
```

Add a private mapper after the existing `mapArtifactResponse` function:

```typescript
function mapSchemaAnalysisResponse(r: {
  analysis_id: string;
  project_id: string;
  destination_object_sequence: string[];
  identified_count: number;
  processed_count: number;
  analyzed_at: string;
}): SchemaAnalysisRecord {
  return {
    analysisId: r.analysis_id,
    projectId: r.project_id,
    destinationObjectSequence: r.destination_object_sequence,
    identifiedCount: r.identified_count,
    processedCount: r.processed_count,
    analyzedAt: r.analyzed_at,
  };
}
```

Add the two exported functions at the end of the file:

```typescript
export async function getSchemaAnalysis(
  token: string,
  projectId: string,
): Promise<SchemaAnalysisRecord | null> {
  const raw = await requestJson<Parameters<typeof mapSchemaAnalysisResponse>[0] | null>(
    `/projects/${projectId}/schema-analysis`,
    { method: "GET", token },
  );
  return raw ? mapSchemaAnalysisResponse(raw) : null;
}

export async function triggerSchemaAnalysis(
  token: string,
  projectId: string,
): Promise<SchemaAnalysisRecord> {
  const raw = await requestJson<Parameters<typeof mapSchemaAnalysisResponse>[0]>(
    `/projects/${projectId}/schema-analysis`,
    { method: "POST", token },
  );
  return mapSchemaAnalysisResponse(raw);
}
```

- [ ] **Step 4: Run the tests to verify they pass**

```bash
cd /Users/vjkotra/projects/katana/web
npm test -- lib/__tests__/codegen-api.schema-analysis.test.ts
```

Expected: all tests PASS.

- [ ] **Step 5: Commit**

```bash
git add web/lib/codegen-api.ts web/lib/__tests__/codegen-api.schema-analysis.test.ts
git commit -m "feat(001ah): add getSchemaAnalysis and triggerSchemaAnalysis API helpers"
```

---

### Task 7: SourceList analysis prompt banner

**Files:**
- Modify: `web/components/projects/SourceList.tsx`
- Create: `web/components/projects/__tests__/SourceList.schema-analysis.test.tsx`

**Interfaces:**
- Consumes: `getSchemaAnalysis`, `triggerSchemaAnalysis` from `../../lib/codegen-api`; `ProjectRecord` from `../../lib/projects-api` (for `domainConfig.destinationSchemaDdl`)
- `SourceList` props currently: `{ projectId: string; token: string; role: SessionRole }` — add `project: ProjectRecord`

- [ ] **Step 1: Write the failing tests**

Create `web/components/projects/__tests__/SourceList.schema-analysis.test.tsx`:

```tsx
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { SourceList } from "../SourceList";

const { listSourceContractsMock, getSchemaAnalysisMock, triggerSchemaAnalysisMock } = vi.hoisted(() => ({
  listSourceContractsMock: vi.fn(),
  getSchemaAnalysisMock: vi.fn(),
  triggerSchemaAnalysisMock: vi.fn(),
}));

vi.mock("../../../lib/sources-api", () => ({
  listSourceContracts: listSourceContractsMock,
  addSourceContract: vi.fn(),
}));

vi.mock("../../../lib/codegen-api", () => ({
  getSchemaAnalysis: getSchemaAnalysisMock,
  triggerSchemaAnalysis: triggerSchemaAnalysisMock,
}));

vi.mock("../AddSourceDialog", () => ({
  AddSourceDialog: () => null,
}));

const PROJECT_WITH_DDL = {
  projectId: "p-1",
  domainConfig: { destinationSchemaDdl: "CREATE TABLE t (id INT);" },
};

const PROJECT_NO_DDL = {
  projectId: "p-2",
  domainConfig: null,
};

const SOURCE = {
  sourceDefinitionId: "s-1",
  projectId: "p-1",
  label: "Customers",
  sourceType: "csv",
  encoding: "utf-8",
  status: "active",
  destinationObjectReferences: ["customers"],
  createdAt: "2026-07-01T00:00:00Z",
  updatedAt: "2026-07-01T00:00:00Z",
};

describe("SourceList — schema analysis banner", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    listSourceContractsMock.mockResolvedValue([SOURCE]);
  });

  it("shows banner when sources exist and no analysis", async () => {
    getSchemaAnalysisMock.mockResolvedValue(null);
    render(
      <SourceList
        projectId="p-1"
        token="tok"
        role="central_team"
        project={PROJECT_WITH_DDL as never}
      />
    );
    expect(await screen.findByText(/Analyze your destination schema/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Analyze DDL/i })).toBeInTheDocument();
  });

  it("hides banner when analysis already exists", async () => {
    getSchemaAnalysisMock.mockResolvedValue({
      analysisId: "a-1",
      projectId: "p-1",
      destinationObjectSequence: ["customers"],
      identifiedCount: 1,
      processedCount: 0,
      analyzedAt: "2026-07-01T00:00:00Z",
    });
    render(
      <SourceList
        projectId="p-1"
        token="tok"
        role="central_team"
        project={PROJECT_WITH_DDL as never}
      />
    );
    await screen.findByText("Customers");
    expect(screen.queryByText(/Analyze your destination schema/i)).not.toBeInTheDocument();
  });

  it("disables Analyze DDL button when project has no destinationSchemaDdl", async () => {
    getSchemaAnalysisMock.mockResolvedValue(null);
    render(
      <SourceList
        projectId="p-2"
        token="tok"
        role="central_team"
        project={PROJECT_NO_DDL as never}
      />
    );
    const btn = await screen.findByRole("button", { name: /Analyze DDL/i });
    expect(btn).toBeDisabled();
  });

  it("calls triggerSchemaAnalysis and hides banner on success", async () => {
    getSchemaAnalysisMock.mockResolvedValue(null);
    triggerSchemaAnalysisMock.mockResolvedValue({
      analysisId: "a-1",
      projectId: "p-1",
      destinationObjectSequence: ["customers"],
      identifiedCount: 1,
      processedCount: 0,
      analyzedAt: "2026-07-01T00:00:00Z",
    });
    render(
      <SourceList
        projectId="p-1"
        token="tok"
        role="central_team"
        project={PROJECT_WITH_DDL as never}
      />
    );
    const btn = await screen.findByRole("button", { name: /Analyze DDL/i });
    fireEvent.click(btn);
    await waitFor(() =>
      expect(screen.queryByText(/Analyze your destination schema/i)).not.toBeInTheDocument()
    );
  });
});
```

- [ ] **Step 2: Run to verify tests fail**

```bash
cd /Users/vjkotra/projects/katana/web
npm test -- components/projects/__tests__/SourceList.schema-analysis.test.tsx
```

Expected: FAIL.

- [ ] **Step 3: Update `SourceList` to accept `project` prop and fetch analysis**

Open `web/components/projects/SourceList.tsx`. The component currently has props `{ projectId, token, role }`. Make the following changes:

**Add imports at top:**
```tsx
import { getSchemaAnalysis, triggerSchemaAnalysis, type SchemaAnalysisRecord } from "../../lib/codegen-api";
import type { ProjectRecord } from "../../lib/projects-api";
```

**Update the props interface:**
```tsx
export interface SourceListProps {
  projectId: string;
  token: string;
  role: SessionRole;
  project: ProjectRecord;
}
```

**Add state inside the component (alongside existing state):**
```tsx
const [schemaAnalysis, setSchemaAnalysis] = useState<SchemaAnalysisRecord | null | undefined>(undefined);
const [analysisLoading, setAnalysisLoading] = useState(false);
```

**Add a `useEffect` to fetch the analysis (after sources load):**
```tsx
useEffect(() => {
  if (sources.length === 0) return;
  let active = true;
  void getSchemaAnalysis(token, projectId).then((result) => {
    if (active) setSchemaAnalysis(result);
  });
  return () => { active = false; };
}, [sources, token, projectId]);
```

**Add the handler:**
```tsx
const handleAnalyzeDdl = async (): Promise<void> => {
  setAnalysisLoading(true);
  try {
    const result = await triggerSchemaAnalysis(token, projectId);
    setSchemaAnalysis(result);
  } finally {
    setAnalysisLoading(false);
  }
};
```

**Add the banner in the JSX, immediately above the source table (inside the non-loading, non-error branch):**
```tsx
{schemaAnalysis === null && sources.length > 0 && (
  <div className="flex items-center justify-between gap-4 rounded-xl border border-primary/30 bg-primary/5 px-4 py-3 text-sm text-slate-700">
    <span>Analyze your destination schema to enable dependency-ordered SQL delivery.</span>
    <button
      className="rounded-full bg-primary px-4 py-2 text-sm font-semibold text-white disabled:opacity-60"
      disabled={analysisLoading || !project.domainConfig?.destinationSchemaDdl}
      onClick={() => void handleAnalyzeDdl()}
      title={!project.domainConfig?.destinationSchemaDdl ? "Set destination_schema_ddl on the project first" : undefined}
      type="button"
    >
      {analysisLoading ? "Analyzing…" : "Analyze DDL"}
    </button>
  </div>
)}
```

- [ ] **Step 4: Update the call site in `web/app/projects/[id]/page.tsx`**

The `SourceList` now requires a `project` prop. In `web/app/projects/[id]/page.tsx`, find the `<SourceList ...>` render and add `project={project}`:

```tsx
<SourceList projectId={id} role={role} token={session.accessToken} project={project} />
```

- [ ] **Step 5: Run the tests**

```bash
cd /Users/vjkotra/projects/katana/web
npm test -- components/projects/__tests__/SourceList.schema-analysis.test.tsx
```

Expected: all tests PASS.

- [ ] **Step 6: Run full web test suite**

```bash
cd /Users/vjkotra/projects/katana/web
npm test
```

Expected: all tests PASS (including existing SourceList tests if any).

- [ ] **Step 7: Commit**

```bash
git add web/components/projects/SourceList.tsx \
        web/components/projects/__tests__/SourceList.schema-analysis.test.tsx \
        web/app/projects/\[id\]/page.tsx
git commit -m "feat(001ah): add DDL analysis prompt banner to SourceList"
```

---

### Task 8: Codegen page — schema analysis report panel

**Files:**
- Modify: `web/app/projects/[id]/codegen/page.tsx`
- Create: `web/app/projects/[id]/codegen/page.test.tsx`

**Interfaces:**
- Consumes: `getSchemaAnalysis`, `triggerSchemaAnalysis`, `SchemaAnalysisRecord` from `../../../../lib/codegen-api`

- [ ] **Step 1: Write the failing tests**

Create `web/app/projects/[id]/codegen/page.test.tsx`:

```tsx
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import CodegenPage from "./page";

const {
  loadUiSessionMock,
  listSourceContractsMock,
  listCodegenArtifactsMock,
  getSchemaAnalysisMock,
  triggerSchemaAnalysisMock,
  routerPushMock,
} = vi.hoisted(() => ({
  loadUiSessionMock: vi.fn(),
  listSourceContractsMock: vi.fn(),
  listCodegenArtifactsMock: vi.fn(),
  getSchemaAnalysisMock: vi.fn(),
  triggerSchemaAnalysisMock: vi.fn(),
  routerPushMock: vi.fn(),
}));

vi.mock("../../../../lib/session", () => ({ loadUiSession: loadUiSessionMock }));
vi.mock("../../../../lib/sources-api", () => ({ listSourceContracts: listSourceContractsMock }));
vi.mock("../../../../lib/codegen-api", () => ({
  listCodegenArtifacts: listCodegenArtifactsMock,
  triggerCodegen: vi.fn(),
  downloadCodegenDeliveryBundle: vi.fn(),
  getSchemaAnalysis: getSchemaAnalysisMock,
  triggerSchemaAnalysis: triggerSchemaAnalysisMock,
}));
vi.mock("../../../../components/Topbar", () => ({ Topbar: () => <nav>Topbar</nav> }));
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: routerPushMock }),
}));

const SESSION = {
  accessToken: "tok",
  expiresAt: "2027-01-01T00:00:00Z",
  role: "central_team" as const,
  sessionVersion: 1,
  userId: "u-1",
};

const ANALYSIS = {
  analysisId: "a-1",
  projectId: "p-1",
  destinationObjectSequence: ["customers", "orders", "order_items"],
  identifiedCount: 3,
  processedCount: 2,
  analyzedAt: "2026-07-01T12:00:00Z",
};

describe("CodegenPage — schema analysis report", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    loadUiSessionMock.mockReturnValue(SESSION);
    listSourceContractsMock.mockResolvedValue([]);
    listCodegenArtifactsMock.mockResolvedValue([]);
  });

  it("shows identified / processed / pending counts when analysis exists", async () => {
    getSchemaAnalysisMock.mockResolvedValue(ANALYSIS);
    render(<CodegenPage params={Promise.resolve({ id: "p-1" })} />);
    expect(await screen.findByText("3")).toBeInTheDocument(); // identified
    expect(screen.getByText("2")).toBeInTheDocument();        // processed
    expect(screen.getByText("1")).toBeInTheDocument();        // pending (3 - 2)
  });

  it("shows empty state when no analysis exists", async () => {
    getSchemaAnalysisMock.mockResolvedValue(null);
    render(<CodegenPage params={Promise.resolve({ id: "p-1" })} />);
    expect(await screen.findByText(/No schema analysis yet/i)).toBeInTheDocument();
  });

  it("calls triggerSchemaAnalysis and refreshes on Re-analyze click", async () => {
    getSchemaAnalysisMock.mockResolvedValue(ANALYSIS);
    const updated = { ...ANALYSIS, identifiedCount: 4, processedCount: 3 };
    triggerSchemaAnalysisMock.mockResolvedValue(updated);
    render(<CodegenPage params={Promise.resolve({ id: "p-1" })} />);
    const btn = await screen.findByRole("button", { name: /Re-analyze DDL/i });
    fireEvent.click(btn);
    await waitFor(() => expect(screen.getByText("4")).toBeInTheDocument());
  });
});
```

- [ ] **Step 2: Run to verify tests fail**

```bash
cd /Users/vjkotra/projects/katana/web
npm test -- app/projects/\\[id\\]/codegen/page.test.tsx
```

Expected: FAIL.

- [ ] **Step 3: Update `web/app/projects/[id]/codegen/page.tsx`**

**Add imports:**
```tsx
import {
  ...,  // existing
  getSchemaAnalysis,
  triggerSchemaAnalysis,
  type SchemaAnalysisRecord,
} from "../../../../lib/codegen-api";
```

**Add state:**
```tsx
const [schemaAnalysis, setSchemaAnalysis] = useState<SchemaAnalysisRecord | null>(null);
const [analysisLoaded, setAnalysisLoaded] = useState(false);
const [analysisLoading, setAnalysisLoading] = useState(false);
```

**In the existing `useEffect` that fetches sources and artifacts, add the analysis fetch:**
```tsx
void Promise.all([
  listSourceContracts(session.accessToken, routeParams.id),
  listCodegenArtifacts(session.accessToken, routeParams.id),
  getSchemaAnalysis(session.accessToken, routeParams.id),
])
  .then(([sourceResponse, artifactResponse, analysisResponse]) => {
    if (!active) return;
    setSources(sourceResponse);
    setArtifacts(artifactResponse);
    setSchemaAnalysis(analysisResponse);
    setAnalysisLoaded(true);
  })
  ...
```

**Add the re-analyze handler:**
```tsx
const handleReanalyze = async (): Promise<void> => {
  if (!session || !routeParams) return;
  setAnalysisLoading(true);
  try {
    const result = await triggerSchemaAnalysis(session.accessToken, routeParams.id);
    setSchemaAnalysis(result);
  } finally {
    setAnalysisLoading(false);
  }
};
```

**Add the report panel in the JSX, inside the existing `<section className="grid gap-6 lg:grid-cols-[1.35fr_0.85fr]">` — add a third panel below the "Delivery bundle" sidebar panel:**

```tsx
<div className="space-y-4 rounded-2xl border border-outline-variant bg-surface-container p-6 shadow-sm">
  <div>
    <h2 className="text-xl font-semibold text-slate-900">Schema dependency analysis</h2>
    <p className="text-sm text-slate-600">FK-ordered execution sequence for the delivery bundle.</p>
  </div>

  {!analysisLoaded ? (
    <div className="text-sm text-slate-500">Loading…</div>
  ) : schemaAnalysis ? (
    <>
      <div className="grid grid-cols-3 gap-3 text-center">
        <div className="rounded-xl border border-outline-variant bg-surface px-3 py-3">
          <div className="text-2xl font-semibold text-slate-900">{schemaAnalysis.identifiedCount}</div>
          <div className="text-xs text-slate-500 mt-1">Identified</div>
        </div>
        <div className="rounded-xl border border-outline-variant bg-surface px-3 py-3">
          <div className="text-2xl font-semibold text-emerald-700">{schemaAnalysis.processedCount}</div>
          <div className="text-xs text-slate-500 mt-1">Processed</div>
        </div>
        <div className="rounded-xl border border-outline-variant bg-surface px-3 py-3">
          <div className="text-2xl font-semibold text-amber-600">
            {schemaAnalysis.identifiedCount - schemaAnalysis.processedCount}
          </div>
          <div className="text-xs text-slate-500 mt-1">Pending</div>
        </div>
      </div>
      <button
        className="rounded-full border border-outline-variant px-4 py-2 text-sm font-semibold text-slate-700 disabled:opacity-60"
        disabled={analysisLoading}
        onClick={() => void handleReanalyze()}
        type="button"
      >
        {analysisLoading ? "Re-analyzing…" : "Re-analyze DDL"}
      </button>
      <div className="text-xs text-slate-400">
        Analyzed {schemaAnalysis.analyzedAt.slice(0, 16).replace("T", " ")}
      </div>
    </>
  ) : (
    <div className="rounded-xl border border-dashed border-outline-variant bg-surface px-4 py-6 text-sm text-slate-500">
      No schema analysis yet. Add a source and click "Analyze DDL" to begin.
    </div>
  )}
</div>
```

- [ ] **Step 4: Run the tests**

```bash
cd /Users/vjkotra/projects/katana/web
npm test -- app/projects/\\[id\\]/codegen/page.test.tsx
```

Expected: all tests PASS.

- [ ] **Step 5: Run full web test suite**

```bash
cd /Users/vjkotra/projects/katana/web
npm test
```

Expected: all tests PASS.

- [ ] **Step 6: Commit**

```bash
git add web/app/projects/\[id\]/codegen/page.tsx \
        web/app/projects/\[id\]/codegen/page.test.tsx
git commit -m "feat(001ah): add schema analysis report panel to codegen page"
```
