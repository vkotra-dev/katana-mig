# Fiber + Lookup Entity Models Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create the five new DB models (`ProjectFiber`, `LookupSourceEntry`, `LookupDestFeed`, `LookupDestEntry`, `LookupMapping`), a single migration, Pydantic schemas, and the basic fiber CRUD endpoints (create manual, list, get) that all Wave 4 tasks build on.

**Architecture:** One new router `routes/fibers.py` with the three foundational endpoints (POST/GET list/GET one). Lookup-specific endpoints (source-entries, dest-feed, mappings, lookup-inputs) are added in task 001al. Approval chain endpoints (assign, approve, trigger) are added in task 001an. All five models live in the existing `db/models.py`. Migration `0019_fiber_models` creates five tables in one operation.

**Tech Stack:** FastAPI, SQLAlchemy 2, Alembic, Pydantic v2, pytest; no new frontend in this task

## Global Constraints

- Migration revision `"0019_fiber_models"` — `down_revision = "0018_feed_rename"` (001aj migration)
- `fiber_type` values: `"lookup"` | `"domain_object"`
- `source` values: `"auto"` | `"manual"` (how the fiber was created)
- Lookup fiber status lifecycle: `created → deferred → inputs_ready → ai_running → mapped → operator_assigned → business_approved → operator_triggered → codegen_complete`
- Mapping fiber status lifecycle: `created → ai_running → mapped → operator_assigned → business_approved → operator_triggered → codegen_complete`
- `LookupMapping.status`: `"proposed"` | `"confirmed"` | `"overridden"`
- `LookupMapping.mapped_by`: `"ai"` | `"operator"` | `"business"`
- `LookupDestFeed` is unique per fiber (one destination reference set per lookup fiber)
- Route: `router = APIRouter(prefix="/projects/{project_id}/feeds/{feed_id}/fibers", tags=["fibers"])`
- Auth: list/get = any project member; create = `central_team` only

## Objective

Add the `ProjectFiber` model and the four lookup entity models needed for the fiber-based migration domain, together with the 0019 migration.

## Out of Scope

- No AI proposal flows
- No approval-chain UI or route work
- No fiber execution engine changes beyond what the new models require

## File Changes

- See the blast radius table above for the exact backend and migration files.

## Verification

- Run the fiber model tests
- Run `alembic upgrade head`
- Run the focused backend test subset that exercises the new tables

## Pitfalls

- Keep foreign keys and uniqueness rules aligned with the fiber domain
- Do not break the migration revision chain
- Make sure the model names match the task vocabulary exactly

## Commit

- `feat(001ak): add fiber models and migration`


---

## Blast radius

| File | Change |
|---|---|
| `engine/src/migrations_engine/db/models.py` | Add 5 new model classes |
| `engine/migrations/versions/0019_fiber_models.py` | Create — 5 new tables |
| `engine/src/migrations_engine/api/schemas.py` | Add `FiberResponse`, `FiberCreateRequest`, `LookupSourceEntryResponse`, `LookupDestFeedResponse`, `LookupDestEntryResponse`, `LookupMappingResponse` |
| `engine/src/migrations_engine/management/fibers.py` | Create — service: `create_fiber`, `list_fibers`, `get_fiber` |
| `engine/src/migrations_engine/routes/fibers.py` | Create — 3 routes: POST, GET list, GET one |
| `engine/src/migrations_engine/app.py` | Add `fibers_router` import + include |
| `engine/tests/test_fiber_models.py` | Create — model + route tests |

---

### Task 1: DB models + migration

**Files:**
- Modify: `engine/src/migrations_engine/db/models.py`
- Create: `engine/migrations/versions/0019_fiber_models.py`

**Interfaces:**
- Produces:
  - `ProjectFiber` with fields: `fiber_id`, `feed_id`, `project_id`, `fiber_type`, `fiber_key`, `status`, `source`, `proposed_mappings`, `field_bindings`, `output_sql`, `created_at`, `updated_at`
  - `LookupSourceEntry` with fields: `entry_id`, `fiber_id`, `lookup_name`, `source_value`, `discovery_type`, `created_at`
  - `LookupDestFeed` with fields: `dest_feed_id`, `fiber_id`, `lookup_name`, `columns`, `created_at`
  - `LookupDestEntry` with fields: `entry_id`, `dest_feed_id`, `row_data`, `created_at`
  - `LookupMapping` with fields: `mapping_id`, `fiber_id`, `lookup_name`, `source_entry_id`, `source_value`, `dest_entry_id`, `dest_row`, `confidence_score`, `status`, `mapped_by`, `created_at`, `updated_at`

- [ ] **Step 1: Write the failing test**

Create `engine/tests/test_fiber_models.py`:

```python
from __future__ import annotations


def test_project_fiber_model_exists() -> None:
    from migrations_engine.db.models import ProjectFiber
    assert ProjectFiber.__tablename__ == "project_fibers"


def test_lookup_source_entry_model_exists() -> None:
    from migrations_engine.db.models import LookupSourceEntry
    assert LookupSourceEntry.__tablename__ == "lookup_source_entries"


def test_lookup_dest_feed_model_exists() -> None:
    from migrations_engine.db.models import LookupDestFeed
    assert LookupDestFeed.__tablename__ == "lookup_dest_feeds"


def test_lookup_dest_entry_model_exists() -> None:
    from migrations_engine.db.models import LookupDestEntry
    assert LookupDestEntry.__tablename__ == "lookup_dest_entries"


def test_lookup_mapping_model_exists() -> None:
    from migrations_engine.db.models import LookupMapping
    assert LookupMapping.__tablename__ == "lookup_mappings"


def test_project_fiber_has_required_fields() -> None:
    from migrations_engine.db.models import ProjectFiber
    cols = {c.name for c in ProjectFiber.__table__.columns}
    assert {"fiber_id", "feed_id", "project_id", "fiber_type", "fiber_key",
            "status", "source", "created_at", "updated_at"}.issubset(cols)


def test_lookup_mapping_has_status_and_confidence() -> None:
    from migrations_engine.db.models import LookupMapping
    cols = {c.name for c in LookupMapping.__table__.columns}
    assert {"confidence_score", "status", "mapped_by"}.issubset(cols)
```

- [ ] **Step 2: Run to verify tests fail**

```bash
cd /Users/vjkotra/projects/katana/engine/tests
python -m pytest test_fiber_models.py -v
```

Expected: FAIL — `ImportError: cannot import name 'ProjectFiber'`

- [ ] **Step 3: Add the five model classes to `engine/src/migrations_engine/db/models.py`**

Add after the existing `LookupValueMap` class and before `MappingArtifact`:

```python
class ProjectFiber(Base):
    __tablename__ = "project_fibers"

    fiber_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    feed_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("feeds.source_definition_id"), nullable=False, index=True
    )
    project_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("project_registry.project_id"), nullable=False, index=True
    )
    fiber_type: Mapped[str] = mapped_column(String(32), nullable=False)
    fiber_key: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(64), nullable=False, default="created")
    source: Mapped[str] = mapped_column(String(16), nullable=False, default="auto")
    proposed_mappings: Mapped[list[dict[str, Any]] | None] = mapped_column(JSON)
    field_bindings: Mapped[list[dict[str, Any]] | None] = mapped_column(JSON)
    output_sql: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class LookupSourceEntry(Base):
    __tablename__ = "lookup_source_entries"

    entry_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    fiber_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("project_fibers.fiber_id"), nullable=False, index=True
    )
    lookup_name: Mapped[str] = mapped_column(String(128), nullable=False)
    source_value: Mapped[str] = mapped_column(String(512), nullable=False)
    discovery_type: Mapped[str] = mapped_column(String(16), nullable=False, default="sample")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class LookupDestFeed(Base):
    __tablename__ = "lookup_dest_feeds"

    dest_feed_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    fiber_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("project_fibers.fiber_id"), nullable=False, unique=True
    )
    lookup_name: Mapped[str] = mapped_column(String(128), nullable=False)
    columns: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class LookupDestEntry(Base):
    __tablename__ = "lookup_dest_entries"

    entry_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    dest_feed_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("lookup_dest_feeds.dest_feed_id"), nullable=False, index=True
    )
    row_data: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class LookupMapping(Base):
    __tablename__ = "lookup_mappings"

    mapping_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    fiber_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("project_fibers.fiber_id"), nullable=False, index=True
    )
    lookup_name: Mapped[str] = mapped_column(String(128), nullable=False)
    source_entry_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("lookup_source_entries.entry_id"), nullable=False
    )
    source_value: Mapped[str] = mapped_column(String(512), nullable=False)
    dest_entry_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("lookup_dest_entries.entry_id"), nullable=True
    )
    dest_row: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    confidence_score: Mapped[float | None] = mapped_column(nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="proposed")
    mapped_by: Mapped[str] = mapped_column(String(16), nullable=False, default="ai")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
```

- [ ] **Step 4: Create migration `engine/migrations/versions/0019_fiber_models.py`**

```python
"""add fiber and lookup entity tables

Revision ID: 0019_fiber_models
Revises: 0018_feed_rename
Create Date: 2026-07-01
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0019_fiber_models"
down_revision = "0018_feed_rename"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "project_fibers",
        sa.Column("fiber_id", sa.String(36), primary_key=True),
        sa.Column("feed_id", sa.String(36), sa.ForeignKey("feeds.source_definition_id"), nullable=False),
        sa.Column("project_id", sa.String(36), sa.ForeignKey("project_registry.project_id"), nullable=False),
        sa.Column("fiber_type", sa.String(32), nullable=False),
        sa.Column("fiber_key", sa.String(255), nullable=False),
        sa.Column("status", sa.String(64), nullable=False, server_default="created"),
        sa.Column("source", sa.String(16), nullable=False, server_default="auto"),
        sa.Column("proposed_mappings", sa.JSON()),
        sa.Column("field_bindings", sa.JSON()),
        sa.Column("output_sql", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_project_fibers_feed_id", "project_fibers", ["feed_id"])
    op.create_index("ix_project_fibers_project_id", "project_fibers", ["project_id"])

    op.create_table(
        "lookup_source_entries",
        sa.Column("entry_id", sa.String(36), primary_key=True),
        sa.Column("fiber_id", sa.String(36), sa.ForeignKey("project_fibers.fiber_id"), nullable=False),
        sa.Column("lookup_name", sa.String(128), nullable=False),
        sa.Column("source_value", sa.String(512), nullable=False),
        sa.Column("discovery_type", sa.String(16), nullable=False, server_default="sample"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_lookup_source_entries_fiber_id", "lookup_source_entries", ["fiber_id"])

    op.create_table(
        "lookup_dest_feeds",
        sa.Column("dest_feed_id", sa.String(36), primary_key=True),
        sa.Column("fiber_id", sa.String(36), sa.ForeignKey("project_fibers.fiber_id"), nullable=False, unique=True),
        sa.Column("lookup_name", sa.String(128), nullable=False),
        sa.Column("columns", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "lookup_dest_entries",
        sa.Column("entry_id", sa.String(36), primary_key=True),
        sa.Column("dest_feed_id", sa.String(36), sa.ForeignKey("lookup_dest_feeds.dest_feed_id"), nullable=False),
        sa.Column("row_data", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_lookup_dest_entries_dest_feed_id", "lookup_dest_entries", ["dest_feed_id"])

    op.create_table(
        "lookup_mappings",
        sa.Column("mapping_id", sa.String(36), primary_key=True),
        sa.Column("fiber_id", sa.String(36), sa.ForeignKey("project_fibers.fiber_id"), nullable=False),
        sa.Column("lookup_name", sa.String(128), nullable=False),
        sa.Column("source_entry_id", sa.String(36), sa.ForeignKey("lookup_source_entries.entry_id"), nullable=False),
        sa.Column("source_value", sa.String(512), nullable=False),
        sa.Column("dest_entry_id", sa.String(36), sa.ForeignKey("lookup_dest_entries.entry_id"), nullable=True),
        sa.Column("dest_row", sa.JSON()),
        sa.Column("confidence_score", sa.Float(), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="proposed"),
        sa.Column("mapped_by", sa.String(16), nullable=False, server_default="ai"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_lookup_mappings_fiber_id", "lookup_mappings", ["fiber_id"])


def downgrade() -> None:
    op.drop_index("ix_lookup_mappings_fiber_id", table_name="lookup_mappings")
    op.drop_table("lookup_mappings")
    op.drop_index("ix_lookup_dest_entries_dest_feed_id", table_name="lookup_dest_entries")
    op.drop_table("lookup_dest_entries")
    op.drop_table("lookup_dest_feeds")
    op.drop_index("ix_lookup_source_entries_fiber_id", table_name="lookup_source_entries")
    op.drop_table("lookup_source_entries")
    op.drop_index("ix_project_fibers_project_id", table_name="project_fibers")
    op.drop_index("ix_project_fibers_feed_id", table_name="project_fibers")
    op.drop_table("project_fibers")
```

- [ ] **Step 5: Run the failing tests — they should now pass**

```bash
cd /Users/vjkotra/projects/katana/engine/tests
python -m pytest test_fiber_models.py -v
```

Expected: all 7 tests PASS.

- [ ] **Step 6: Commit**

```bash
git add engine/src/migrations_engine/db/models.py \
        engine/migrations/versions/0019_fiber_models.py \
        engine/tests/test_fiber_models.py
git commit -m "feat(001ak): add ProjectFiber and lookup entity models with migration 0019"
```

---

### Task 2: Pydantic schemas

**Files:**
- Modify: `engine/src/migrations_engine/api/schemas.py`

**Interfaces:**
- Produces: `FiberCreateRequest`, `FiberResponse`, `LookupSourceEntryResponse`, `LookupDestFeedResponse`, `LookupDestEntryResponse`, `LookupMappingResponse`, `LookupMappingPatchRequest`

- [ ] **Step 1: Write the failing test**

Add to `engine/tests/test_fiber_models.py`:

```python
def test_fiber_response_schema_exists() -> None:
    from migrations_engine.api.schemas import FiberResponse
    assert "fiber_id" in FiberResponse.model_fields
    assert "fiber_type" in FiberResponse.model_fields
    assert "status" in FiberResponse.model_fields
    assert "proposed_mappings" in FiberResponse.model_fields
    assert "field_bindings" in FiberResponse.model_fields


def test_fiber_create_request_schema_exists() -> None:
    from migrations_engine.api.schemas import FiberCreateRequest
    assert "fiber_type" in FiberCreateRequest.model_fields
    assert "fiber_key" in FiberCreateRequest.model_fields


def test_lookup_mapping_response_schema_exists() -> None:
    from migrations_engine.api.schemas import LookupMappingResponse
    assert "mapping_id" in LookupMappingResponse.model_fields
    assert "confidence_score" in LookupMappingResponse.model_fields
    assert "status" in LookupMappingResponse.model_fields
```

- [ ] **Step 2: Run to verify tests fail**

```bash
cd /Users/vjkotra/projects/katana/engine/tests
python -m pytest test_fiber_models.py::test_fiber_response_schema_exists -v
```

Expected: FAIL — `ImportError: cannot import name 'FiberResponse'`

- [ ] **Step 3: Add schemas to `engine/src/migrations_engine/api/schemas.py`**

Add after the existing `LookupSnapshotResponse` class:

```python
class FiberCreateRequest(BaseModel):
    fiber_type: Literal["lookup", "domain_object"]
    fiber_key: str = Field(min_length=1, max_length=255)


class FiberResponse(BaseModel):
    fiber_id: str
    feed_id: str
    project_id: str
    fiber_type: Literal["lookup", "domain_object"]
    fiber_key: str
    status: str
    source: Literal["auto", "manual"]
    proposed_mappings: list[dict[str, Any]] | None
    field_bindings: list[dict[str, Any]] | None
    output_sql: str | None
    created_at: datetime
    updated_at: datetime


class LookupSourceEntryResponse(BaseModel):
    entry_id: str
    fiber_id: str
    lookup_name: str
    source_value: str
    discovery_type: Literal["sample", "delta"]
    created_at: datetime


class LookupDestFeedResponse(BaseModel):
    dest_feed_id: str
    fiber_id: str
    lookup_name: str
    columns: list[str]
    created_at: datetime


class LookupDestEntryResponse(BaseModel):
    entry_id: str
    dest_feed_id: str
    row_data: dict[str, Any]
    created_at: datetime


class LookupMappingResponse(BaseModel):
    mapping_id: str
    fiber_id: str
    lookup_name: str
    source_entry_id: str
    source_value: str
    dest_entry_id: str | None
    dest_row: dict[str, Any] | None
    confidence_score: float | None
    status: Literal["proposed", "confirmed", "overridden"]
    mapped_by: Literal["ai", "operator", "business"]
    created_at: datetime
    updated_at: datetime


class LookupMappingPatchRequest(BaseModel):
    dest_entry_id: str
    status: Literal["confirmed", "overridden"]


class LookupSourceEntriesCreateRequest(BaseModel):
    values: list[str] = Field(min_length=1)
    discovery_type: Literal["sample", "delta"] = "sample"


class LookupDestFeedCreateRequest(BaseModel):
    columns: list[str] = Field(min_length=1)
    rows: list[dict[str, Any]] = Field(min_length=1)
```

- [ ] **Step 4: Run tests**

```bash
cd /Users/vjkotra/projects/katana/engine/tests
python -m pytest test_fiber_models.py -v
```

Expected: all tests PASS.

- [ ] **Step 5: Commit**

```bash
git add engine/src/migrations_engine/api/schemas.py \
        engine/tests/test_fiber_models.py
git commit -m "feat(001ak): add Fiber and lookup entity Pydantic schemas"
```

---

### Task 3: Service + routes (create, list, get)

**Files:**
- Create: `engine/src/migrations_engine/management/fibers.py`
- Create: `engine/src/migrations_engine/routes/fibers.py`
- Modify: `engine/src/migrations_engine/app.py`

**Interfaces:**
- Consumes: `ProjectFiber` from `db.models`; `FiberResponse`, `FiberCreateRequest` from `api.schemas`; `require_project_access`, `get_central_team_user`, `get_current_user`, `get_db`
- Produces:
  - `create_fiber(db, *, feed_id, project_id, body: FiberCreateRequest, actor: User) -> FiberResponse`
  - `list_fibers(db, *, feed_id, project_id) -> list[FiberResponse]`
  - `get_fiber(db, *, feed_id, fiber_id, project_id) -> FiberResponse`
  - `POST /projects/{project_id}/feeds/{feed_id}/fibers` → `FiberResponse` 201
  - `GET /projects/{project_id}/feeds/{feed_id}/fibers` → `list[FiberResponse]` 200
  - `GET /projects/{project_id}/feeds/{feed_id}/fibers/{fiber_id}` → `FiberResponse` 200

- [ ] **Step 1: Write the failing tests**

Add to `engine/tests/test_fiber_models.py`:

```python
import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from sqlite_test_support import Base, SessionLocal, TEST_ENGINE
from migrations_engine.app import app
from migrations_engine.auth.passwords import hash_password
from migrations_engine.config import get_settings
from migrations_engine.db.models import (
    Feed,
    ProjectDefinition,
    ProjectFiber,
    ProjectRegistry,
    User,
)
from migrations_engine.roles import CENTRAL_TEAM_ROLE

client = TestClient(app)


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
def feed_id() -> str:
    with SessionLocal() as db:
        pid = str(uuid.uuid4())
        fid = str(uuid.uuid4())
        db.add(ProjectDefinition(project_id=pid, name="Fiber Test", domain_config={}))
        db.add(ProjectRegistry(project_id=pid, status="active"))
        db.add(Feed(
            source_definition_id=fid,
            project_id=pid,
            source_type="csv",
            source_contract_version="v1",
        ))
        db.commit()
        return fid


def _get_project_id(fid: str) -> str:
    with SessionLocal() as db:
        feed = db.get(Feed, fid)
        return feed.project_id


def test_create_fiber_lookup(feed_id: str) -> None:
    token = _login()
    pid = _get_project_id(feed_id)
    r = client.post(
        f"/projects/{pid}/feeds/{feed_id}/fibers",
        json={"fiber_type": "lookup", "fiber_key": "account_type"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 201
    body = r.json()
    assert body["fiber_type"] == "lookup"
    assert body["fiber_key"] == "account_type"
    assert body["status"] == "deferred"
    assert body["source"] == "manual"


def test_create_fiber_domain_object(feed_id: str) -> None:
    token = _login()
    pid = _get_project_id(feed_id)
    r = client.post(
        f"/projects/{pid}/feeds/{feed_id}/fibers",
        json={"fiber_type": "domain_object", "fiber_key": "customers"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 201
    body = r.json()
    assert body["status"] == "operator_assigned"


def test_list_fibers(feed_id: str) -> None:
    token = _login()
    pid = _get_project_id(feed_id)
    r = client.get(
        f"/projects/{pid}/feeds/{feed_id}/fibers",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_get_fiber(feed_id: str) -> None:
    token = _login()
    pid = _get_project_id(feed_id)
    create_r = client.post(
        f"/projects/{pid}/feeds/{feed_id}/fibers",
        json={"fiber_type": "lookup", "fiber_key": "status_code"},
        headers={"Authorization": f"Bearer {token}"},
    )
    fiber_id = create_r.json()["fiber_id"]
    r = client.get(
        f"/projects/{pid}/feeds/{feed_id}/fibers/{fiber_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    assert r.json()["fiber_id"] == fiber_id


def test_get_fiber_not_found(feed_id: str) -> None:
    token = _login()
    pid = _get_project_id(feed_id)
    r = client.get(
        f"/projects/{pid}/feeds/{feed_id}/fibers/nonexistent",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 404


def test_create_fiber_requires_central_team(feed_id: str) -> None:
    # unauthenticated
    pid = _get_project_id(feed_id)
    r = client.post(
        f"/projects/{pid}/feeds/{feed_id}/fibers",
        json={"fiber_type": "lookup", "fiber_key": "test"},
    )
    assert r.status_code == 401
```

- [ ] **Step 2: Run to verify tests fail**

```bash
cd /Users/vjkotra/projects/katana/engine/tests
python -m pytest test_fiber_models.py -k "test_create_fiber or test_list_fibers or test_get_fiber" -v
```

Expected: FAIL — 404 (routes not registered)

- [ ] **Step 3: Create `engine/src/migrations_engine/management/fibers.py`**

```python
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..api.deps import AuthApiError
from ..api.schemas import FiberCreateRequest, FiberResponse
from ..db.models import Feed, ProjectFiber, User


def _to_response(fiber: ProjectFiber) -> FiberResponse:
    return FiberResponse(
        fiber_id=fiber.fiber_id,
        feed_id=fiber.feed_id,
        project_id=fiber.project_id,
        fiber_type=fiber.fiber_type,
        fiber_key=fiber.fiber_key,
        status=fiber.status,
        source=fiber.source,
        proposed_mappings=fiber.proposed_mappings,
        field_bindings=fiber.field_bindings,
        output_sql=fiber.output_sql,
        created_at=fiber.created_at,
        updated_at=fiber.updated_at,
    )


def _require_feed(db: Session, *, feed_id: str, project_id: str) -> Feed:
    feed = db.get(Feed, feed_id)
    if feed is None or feed.project_id != project_id:
        raise AuthApiError("feed_not_found", "Feed not found.", 404)
    return feed


def create_fiber(
    db: Session,
    *,
    feed_id: str,
    project_id: str,
    body: FiberCreateRequest,
    actor: User,
) -> FiberResponse:
    _require_feed(db, feed_id=feed_id, project_id=project_id)
    initial_status = "deferred" if body.fiber_type == "lookup" else "operator_assigned"
    fiber = ProjectFiber(
        feed_id=feed_id,
        project_id=project_id,
        fiber_type=body.fiber_type,
        fiber_key=body.fiber_key,
        status=initial_status,
        source="manual",
    )
    db.add(fiber)
    db.commit()
    db.refresh(fiber)
    return _to_response(fiber)


def list_fibers(
    db: Session,
    *,
    feed_id: str,
    project_id: str,
) -> list[FiberResponse]:
    _require_feed(db, feed_id=feed_id, project_id=project_id)
    fibers = db.scalars(
        select(ProjectFiber)
        .where(
            ProjectFiber.feed_id == feed_id,
            ProjectFiber.project_id == project_id,
        )
        .order_by(ProjectFiber.created_at.asc())
    ).all()
    return [_to_response(f) for f in fibers]


def get_fiber(
    db: Session,
    *,
    feed_id: str,
    fiber_id: str,
    project_id: str,
) -> FiberResponse:
    _require_feed(db, feed_id=feed_id, project_id=project_id)
    fiber = db.scalars(
        select(ProjectFiber).where(
            ProjectFiber.fiber_id == fiber_id,
            ProjectFiber.feed_id == feed_id,
        )
    ).first()
    if fiber is None:
        raise AuthApiError("fiber_not_found", "Fiber not found.", 404)
    return _to_response(fiber)
```

- [ ] **Step 4: Create `engine/src/migrations_engine/routes/fibers.py`**

```python
from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from ..api.deps import get_central_team_user, get_current_user, get_db
from ..api.schemas import FiberCreateRequest, FiberResponse
from ..db.models import User
from ..management.access import require_project_access
from ..management.fibers import create_fiber, get_fiber, list_fibers

router = APIRouter(
    prefix="/projects/{project_id}/feeds/{feed_id}/fibers",
    tags=["fibers"],
)


@router.post("", response_model=FiberResponse, status_code=status.HTTP_201_CREATED)
def post_fiber(
    project_id: str,
    feed_id: str,
    body: FiberCreateRequest,
    actor: User = Depends(get_central_team_user),
    db: Session = Depends(get_db),
) -> FiberResponse:
    return create_fiber(db, feed_id=feed_id, project_id=project_id, body=body, actor=actor)


@router.get("", response_model=list[FiberResponse])
def get_fibers(
    project_id: str,
    feed_id: str,
    actor: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[FiberResponse]:
    require_project_access(db, user=actor, project_id=project_id)
    return list_fibers(db, feed_id=feed_id, project_id=project_id)


@router.get("/{fiber_id}", response_model=FiberResponse)
def get_fiber_by_id(
    project_id: str,
    feed_id: str,
    fiber_id: str,
    actor: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FiberResponse:
    require_project_access(db, user=actor, project_id=project_id)
    return get_fiber(db, feed_id=feed_id, fiber_id=fiber_id, project_id=project_id)
```

- [ ] **Step 5: Register the router in `engine/src/migrations_engine/app.py`**

Add to the imports:
```python
from .routes.fibers import router as fibers_router
```

Add to the `app.include_router(...)` calls (after `sources_router` or `feeds_router`):
```python
app.include_router(fibers_router)
```

- [ ] **Step 6: Run all fiber tests**

```bash
cd /Users/vjkotra/projects/katana/engine/tests
python -m pytest test_fiber_models.py -v
```

Expected: all tests PASS.

- [ ] **Step 7: Run the full engine test suite**

```bash
cd /Users/vjkotra/projects/katana/engine/tests
python -m pytest -v
```

Expected: all tests PASS.

- [ ] **Step 8: Commit**

```bash
git add engine/src/migrations_engine/management/fibers.py \
        engine/src/migrations_engine/routes/fibers.py \
        engine/src/migrations_engine/app.py \
        engine/tests/test_fiber_models.py
git commit -m "feat(001ak): add fiber CRUD endpoints (create, list, get)"
```
