# Plan: Task 002b8 — Version History Backend

- **Task**: [002b8-version-history-backend.md](./002b8-version-history-backend.md)
- **Domain**: `docs/domain/source-model.md`, `docs/domain/api.md`

---

## Current State

- No `version_history` table in the database.
- No `VersionHistory` SQLAlchemy model.
- No version history API endpoints.
- Existing PATCH handlers for hints/transformation/codegen do not capture version snapshots.
- All routes are prefixed `/projects/{project_id}/` and use `require_project_access` for isolation (I15/I21).
- Migration chain ends at `0042_add_source_ddl_to_source_schema_artifact.py` (revision "0042").
- Codebase uses `from datetime import UTC, datetime` and `datetime.now(UTC)` for timezone-aware timestamps (e.g., codegen/service.py:3,3).

## Objective

1. Create migration `0043_add_version_history.py` (down_revision = "0042").
2. Add `VersionHistory` SQLAlchemy model to `db/models.py`.
3. Add `VersionHistoryResponse` + `VersionHistoryCreateRequest` schemas.
4. Create `routes/versions.py` with `GET /projects/{project_id}/versions/{entity_type}`, scoped by `project_id`, guarded by `require_project_access`.
5. Register the router in `app.py`.
6. Add version capture hooks in existing PATCH handlers.
7. Add tests in `tests/test_version_history.py`.

## Out of Scope

- No frontend UI — handled in follow-up task [[002b9]].
- No diff-generation — `old_value` and `new_value` stored as full text.
- No notification or pagination UI.

## Step-by-Step Build Instructions

---

### Step 1: Migration — `engine/migrations/versions/0043_add_version_history.py`

**File**: `engine/migrations/versions/0043_add_version_history.py` (new)

Read the latest migration to confirm `down_revision = "0042"`. Create:

```python
"""add version_history table

Revision ID: 0043
Revises: 0042
"""
from alembic import op
import sqlalchemy as sa

revision = "0043"
down_revision = "0042"


def upgrade() -> None:
    op.create_table(
        "version_history",
        sa.Column("version_id", sa.String(36), nullable=False),
        sa.Column("entity_type", sa.String(64), nullable=False, index=True),
        sa.Column("entity_id", sa.String(36), nullable=False, index=True),
        sa.Column("field_name", sa.String(128), nullable=False),
        sa.Column("old_value", sa.Text(), nullable=True),
        sa.Column("new_value", sa.Text(), nullable=True),
        sa.Column("changed_by", sa.String(36), nullable=True, index=True),
        sa.Column("changed_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("version_id"),
    )
    op.create_index(
        "ix_version_history_entity",
        "version_history",
        ["entity_type", "entity_id", "field_name"],
    )


def downgrade() -> None:
    op.drop_index("ix_version_history_entity", table_name="version_history")
    op.drop_table("version_history")
```

---

### Step 2: Model — `engine/src/migrations_engine/db/models.py`

**File**: `engine/src/migrations_engine/db/models.py`

Append after the `AICallLog` class at end of file:

```python
class VersionHistory(Base):
    __tablename__ = "version_history"

    version_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    entity_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    entity_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    field_name: Mapped[str] = mapped_column(String(128), nullable=False)
    old_value: Mapped[str | None] = mapped_column(Text)
    new_value: Mapped[str | None] = mapped_column(Text)
    changed_by: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        sa.Index("ix_version_history_entity", "entity_type", "entity_id", "field_name"),
    )
```

---

### Step 3: Schemas — `engine/src/migrations_engine/api/schemas.py`

**File**: `engine/src/migrations_engine/api/schemas.py`

Append after `AICallLogResponse` at end of file:

```python
class VersionHistoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    version_id: str
    field_name: str
    old_value: str | None
    new_value: str | None
    changed_by: str | None
    changed_at: datetime


class VersionHistoryCreateRequest(BaseModel):
    field_name: str
    old_value: str | None = None
    new_value: str | None = None
```

---

### Step 4: API Routes — `engine/src/migrations_engine/routes/versions.py` (new)

**File**: `engine/src/migrations_engine/routes/versions.py` (new)

```python
"""Version history endpoints — scoped per project."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..api.deps import get_current_user, get_db
from ..api.schemas import VersionHistoryResponse
from ..db.models import User, VersionHistory
from ..management.access import require_project_access

router = APIRouter(prefix="/projects/{project_id}/versions", tags=["versions"])


def _entity_router(entity_type: str) -> APIRouter:
    r = APIRouter(prefix=f"/{entity_type}")

    @r.get("/versions", response_model=list[VersionHistoryResponse])
    def get_entity_versions(
        project_id: str,
        actor: User = Depends(get_current_user),
        db: Session = Depends(get_db),
        limit: int = Query(default=50, le=200),
        offset: int = Query(default=0, ge=0),
    ) -> list[VersionHistoryResponse]:
        require_project_access(db, user=actor, project_id=project_id)
        rows = (
            db.execute(
                select(VersionHistory)
                .where(VersionHistory.entity_type == entity_type)
                .order_by(VersionHistory.changed_at.desc())
                .limit(limit)
                .offset(offset)
            )
            .scalars()
            .all()
        )
        return rows

    return r


router.include_router(_entity_router("hints"))
router.include_router(_entity_router("codegen"))
router.include_router(_entity_router("transformation"))
router.include_router(_entity_router("sql"))
```

**Register in `engine/src/migrations_engine/app.py`**:
```python
from .routes.versions import router as versions_router
# ... then add to app.include_router() calls:
app.include_router(versions_router)
```

---

### Step 5: Patch Hooks — Capture Versions

**File**: `engine/src/migrations_engine/routes/feeds.py`

Imports — add `VersionHistory` to the existing model import and add `datetime` import:
```python
from datetime import UTC, datetime as _dt
from ..db.models import User, Feed, VersionHistory
```
(Remove existing `from ..api.schemas import` line that has `FeedMappingHintsRequest, TransformationInstructionsRequest` if `VersionHistory` is not already imported — or just add `VersionHistory` to the existing model import line.)

In `patch_source_hints` (line ~151):
```python
    feed = db.get(Feed, source_definition_id)
    if feed is None or feed.project_id != project_id:
        raise AuthApiError("feed_not_found", "Feed not found.", 404)
    _old = feed.mapping_hints
    feed.mapping_hints = body.mapping_hints
    db.add(VersionHistory(
        entity_type="hints",
        entity_id=source_definition_id,
        field_name="mapping_hints",
        old_value=_old,
        new_value=body.mapping_hints,
        changed_by=actor.user_id,
        changed_at=_dt.now(UTC),
    ))
    db.commit()
```

In `patch_source_transformation_instructions` (line ~180):
```python
    feed = db.get(Feed, source_definition_id)
    if feed is None or feed.project_id != project_id:
        raise AuthApiError("feed_not_found", "Feed not found.", 404)
    _old = feed.transformation_instructions
    feed.transformation_instructions = body.transformation_instructions
    db.add(VersionHistory(
        entity_type="transformation",
        entity_id=source_definition_id,
        field_name="transformation_instructions",
        old_value=_old,
        new_value=body.transformation_instructions,
        changed_by=actor.user_id,
        changed_at=_dt.now(UTC),
    ))
    db.commit()
```

**File**: `engine/src/migrations_engine/routes/projects.py`

Import `VersionHistory` and `datetime`:
```python
from ..db.models import User, VersionHistory
from datetime import UTC
```

In `patch_codegen_instructions`:
```python
@router.patch("/{project_id}/codegen-instructions", response_model=ProjectResponse)
def patch_codegen_instructions(
    project_id: str,
    body: CodegenInstructionsRequest,
    actor: User = Depends(get_central_team_user),
    db: Session = Depends(get_db),
) -> ProjectResponse:
    require_project_access(db, user=actor, project_id=project_id)
    # Capture version snapshot before update
    current_def = db.get(ProjectDefinition, db.get(ProjectRegistry, project_id).definition_id) if db.get(ProjectRegistry, project_id) else None
    _old_val = current_def.codegen_instructions if current_def else None
    if body.codegen_instructions is not None:
        db.add(VersionHistory(
            entity_type="codegen",
            entity_id=project_id,
            field_name="codegen_instructions",
            old_value=_old_val,
            new_value=body.codegen_instructions,
            changed_by=actor.user_id,
            changed_at=UTC,
        ))
        db.commit()
    return update_project(
        db,
        actor=actor,
        project_id=project_id,
        body=ProjectUpdateRequest(codegen_instructions=body.codegen_instructions),
    )
```
Add imports for `ProjectDefinition` and `ProjectRegistry` at the top of `routes/projects.py` if not already present (check the existing `from ..management.projects import ...` line).

**File**: `engine/src/migrations_engine/codegen/service.py`

Import `VersionHistory`:
```python
from ..db.models import (
    CodeGenerationArtifact,
    LookupSnapshot,
    MappingSnapshot,
    ProjectDefinition,
    ProjectRegistry,
    Feed,
    FeedSlice,
    FeedComment,
    User,
    new_id,
    VersionHistory,
)
```

After `db.add(artifact)` (line ~199), before `record_management_audit`:
```python
    db.add(VersionHistory(
        entity_type="sql",
        entity_id=artifact.codegen_artifact_id,
        field_name="sql_bundle",
        old_value=None,
        new_value=sql_bundle,
        changed_by=actor.user_id,
        changed_at=datetime.now(UTC),
    ))
```

---

### Step 6: Tests — `engine/tests/test_version_history.py`

**File**: `engine/tests/test_version_history.py` (new)

```python
from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from sqlite_test_support import Base, SessionLocal, TEST_ENGINE
from migrations_engine.app import app
from migrations_engine.auth.passwords import hash_password
from migrations_engine.config import get_settings
from migrations_engine.db.models import (
    FeedSlice,
    ProjectDefinition,
    ProjectMembership,
    ProjectRegistry,
    SourceDefinition,
    SourceSlice,
    User,
    VersionHistory,
)
from migrations_engine.roles import CENTRAL_TEAM_ROLE, PROJECT_STAKEHOLDER_ROLE

client = TestClient(app)


@pytest.fixture(scope="module", autouse=True)
def _setup_sqlite_db() -> None:
    Base.metadata.create_all(bind=TEST_ENGINE)
    settings = get_settings()
    if not settings.bootstrap_admin_email or not settings.bootstrap_admin_password:
        pytest.skip("bootstrap credentials not configured")

    with SessionLocal() as db:
        if db.scalar(select(User).where(User.email == settings.bootstrap_admin_email.strip().lower())) is None:
            db.add(User(
                user_id=str(uuid.uuid4()),
                email=settings.bootstrap_admin_email.strip().lower(),
                display_name="Admin",
                password_hash=hash_password(settings.bootstrap_admin_password),
                role=CENTRAL_TEAM_ROLE,
                status="active",
            ))
        if db.scalar(select(User).where(User.email == "stakeholder@example.com")) is None:
            db.add(User(
                user_id=str(uuid.uuid4()),
                email="stakeholder@example.com",
                display_name="Stakeholder",
                password_hash=hash_password("stakeholder-password"),
                role=PROJECT_STAKEHOLDER_ROLE,
                status="active",
            ))
        db.commit()


@pytest.fixture(autouse=True)
def _clear_settings_cache() -> None:
    get_settings.cache_clear()


def _login(email: str, password: str) -> str:
    resp = client.post("/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200
    return resp.json()["access_token"]


@pytest.fixture
def admin_token() -> str:
    settings = get_settings()
    if not settings.bootstrap_admin_email or not settings.bootstrap_admin_password:
        pytest.skip("bootstrap credentials not configured")
    return _login(settings.bootstrap_admin_email, settings.bootstrap_admin_password)


@pytest.fixture
def stakeholder_token() -> str:
    return _login("stakeholder@example.com", "stakeholder-password")


def _seed_projects() -> tuple[str, str, str, str]:
    """Create two projects with sources; return (pid_a, sid_a, pid_b, sid_b)."""
    pid_a = str(uuid.uuid4())
    pid_b = str(uuid.uuid4())
    did_a = str(uuid.uuid4())
    did_b = str(uuid.uuid4())
    sid_a = str(uuid.uuid4())
    sid_b = str(uuid.uuid4())
    admin = None
    stakeholder = None
    with SessionLocal() as db:
        admin = db.scalar(select(User).where(User.role == CENTRAL_TEAM_ROLE))
        stakeholder = db.scalar(select(User).where(User.email == "stakeholder@example.com"))
        db.add(ProjectDefinition(definition_id=did_a, project_id=pid_a, name="A", status="active"))
        db.add(ProjectRegistry(project_id=pid_a, name="Proj A", definition_id=did_a, status="active"))
        db.add(SourceDefinition(
            source_definition_id=sid_a, project_id=pid_a, source_type="csv",
            source_contract_version="v1", destination_object_references=["T1"],
            source_details={"label": "A", "encoding": "utf-8"}, status="active",
        ))
        db.add(ProjectDefinition(definition_id=did_b, project_id=pid_b, name="B", status="active"))
        db.add(ProjectRegistry(project_id=pid_b, name="Proj B", definition_id=did_b, status="active"))
        db.add(SourceDefinition(
            source_definition_id=sid_b, project_id=pid_b, source_type="csv",
            source_contract_version="v1", destination_object_references=["T2"],
            source_details={"label": "B", "encoding": "utf-8"}, status="active",
        ))
        db.commit()
    return pid_a, sid_a, pid_b, sid_b


def test_version_history_hints_capture(admin_token: str, _seed_projects: tuple) -> None:
    pid, sid, _, _ = _seed_projects
    # Write hints
    resp = client.patch(
        f"/projects/{pid}/sources/{sid}/hints",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"mapping_hints": "test hints v1"},
    )
    assert resp.status_code == 200
    # Check version history
    resp = client.get(
        f"/projects/{pid}/versions/hints/versions",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    versions = resp.json()
    assert len(versions) == 1
    assert versions[0]["field_name"] == "mapping_hints"
    assert versions[0]["new_value"] == "test hints v1"


def test_version_history_hints_empty_old(admin_token: str, _seed_projects: tuple) -> None:
    pid, sid, _, _ = _seed_projects
    # First write (no prior value)
    resp = client.patch(
        f"/projects/{pid}/sources/{sid}/hints",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"mapping_hints": "first value"},
    )
    assert resp.status_code == 200
    resp = client.get(f"/projects/{pid}/versions/hints/versions", headers={"Authorization": f"Bearer {admin_token}"})
    assert resp.json()[0]["old_value"] is None


def test_version_history_transformation_capture(admin_token: str, _seed_projects: tuple) -> None:
    pid, sid, _, _ = _seed_projects
    resp = client.patch(
        f"/projects/{pid}/sources/{sid}/transformation-instructions",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"transformation_instructions": "trans v1"},
    )
    assert resp.status_code == 200
    resp = client.get(f"/projects/{pid}/versions/transformation/versions", headers={"Authorization": f"Bearer {admin_token}"})
    assert resp.status_code == 200
    assert resp.json()[0]["new_value"] == "trans v1"


def test_version_history_codegen_capture(admin_token: str) -> None:
    pid = str(uuid.uuid4())
    did = str(uuid.uuid4())
    with SessionLocal() as db:
        admin = db.scalar(select(User).where(User.role == CENTRAL_TEAM_ROLE))
        db.add(ProjectDefinition(definition_id=did, project_id=pid, name="C", status="active"))
        db.add(ProjectRegistry(project_id=pid, name="Proj C", definition_id=did, status="active"))
        db.commit()
    resp = client.patch(
        f"/projects/{pid}/codegen-instructions",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"codegen_instructions": "# test instructions"},
    )
    assert resp.status_code == 200
    resp = client.get(f"/projects/{pid}/versions/codegen/versions", headers={"Authorization": f"Bearer {admin_token}"})
    assert resp.status_code == 200
    assert resp.json()[0]["new_value"] == "# test instructions"


def test_version_history_project_scoped(stakeholder_token: str, _seed_projects: tuple) -> None:
    pid_a, sid_a, pid_b, sid_b = _seed_projects
    # Stakeholder is a member of A (via project membership), not B
    # Try to access B's version history — should 403 or 404 due to require_project_access
    resp = client.get(f"/projects/{pid_b}/versions/hints/versions", headers={"Authorization": f"Bearer {stakeholder_token}"})
    assert resp.status_code == 403


def test_version_history_entity_types(admin_token: str, _seed_projects: tuple) -> None:
    pid, sid, _, _ = _seed_projects
    # Ensure each entity_type endpoint returns empty list (no writes yet)
    for endpoint in ["hints", "transformation", "codegen", "sql"]:
        resp = client.get(f"/projects/{pid}/versions/{endpoint}/versions", headers={"Authorization": f"Bearer {admin_token}"})
        assert resp.status_code == 200
        assert resp.json() == []
```

## Verification

```bash
cd engine && pytest tests/test_version_history.py -v
```

## Pitfalls

1. **`_dt.timezone.utc` crashes** — `datetime` class has no `.timezone` attribute. Use `from datetime import UTC` (capital, module-level) and `datetime.now(UTC)`. This is the pattern already used in `codegen/service.py:3`.
2. **Project scoping** — Routes must use `/projects/{project_id}/versions/{entity_type}/versions` (project_id in path, entity_type as prefix). Every handler must call `require_project_access(db, user=actor, project_id=project_id)`.
3. **Codegen old value** — The `patch_codegen_instructions` handler must read the old `codegen_instructions` from the current `ProjectDefinition` *before* calling `update_project()`, which creates a new definition.
4. **Test fixture ordering** — The `VersionHistory` table must be created by the existing `_setup_sqlite_db` fixture's `Base.metadata.create_all()`. Ensure `VersionHistory` is imported before the fixture runs.
5. **SQLAlchemy `from_attributes=True`** — The `VersionHistoryResponse` schema needs `model_config = ConfigDict(from_attributes=True)` to map ORM objects to JSON.

## Commit

```
feat(versioning): add version_history table, API, and patch hooks

- Migration 0043: version_history table with indexed (entity_type, entity_id, field_name)
- VersionHistory SQLAlchemy model
- VersionHistoryResponse + VersionHistoryCreateRequest schemas
- GET /projects/{pid}/versions/{entity_type} endpoint with require_project_access
- Patch hooks in feeds.py (hints, transformation), projects.py (codegen), codegen/service.py (sql)
- Test suite: 6 tests covering capture, project scoping, and entity types
```
