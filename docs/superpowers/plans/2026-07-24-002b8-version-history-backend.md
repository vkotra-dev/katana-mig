# Version History Backend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the `version_history` table, scoped REST API, version-capture hooks in PATCH handlers, and tests — enabling per-field version history for mapping hints, codegen instructions, transformation instructions, and SQL scripts.

**Architecture:** A single `version_history` table records every change to four writable text fields. A new `GET /projects/{pid}/versions/{entity}/versions` endpoint returns the version list scoped by project_id and guarded by `require_project_access`. Existing PATCH handlers are augmented with 8-line version-capture blocks that read the old value, write it, and insert a VersionHistory record.

**Tech Stack:** FastAPI, SQLAlchemy ORM, Alembic migrations, Pydantic schemas, SQLite for tests.

## Global Constraints

- **Migration chain:** Must read the last migration revision from disk before writing. Current last migration is `0042_add_source_ddl_to_source_schema_artifact.py` (revision "0042").
- **Route prefix:** All new routes are under `/projects/{project_id}/` and call `require_project_access(db, user=actor, project_id=project_id)` before returning data.
- **Timezone:** Use `from datetime import UTC, datetime` and `datetime.now(UTC)`. Never use `_dt.timezone.utc` (AttributeError).
- **Entity type values:** `"hints"`, `"transformation"`, `"codegen"`, `"sql"` (all lowercase, no spaces, no underscores beyond the name).
- **Test database:** `engine/tests/sqlite_test_support.py` provides `Base`, `SessionLocal`, `TEST_ENGINE`. All models must be imported before `_setup_sqlite_db` calls `Base.metadata.create_all()`.
- **Python path safety:** Always use `.venv/bin/python` (not bare `python`) in the `engine/` directory — bare `python` resolves to a stale global editable install from an unrelated sibling repo. Every `python -c` command in this plan uses `.venv/bin/python`.

---

### Task 1: Migration

**Files:**
- Create: `engine/migrations/versions/0043_add_version_history.py`

**Interfaces:**
- Consumes: Revision chain from `0042_add_source_ddl_to_source_schema_artifact.py`
- Produces: `version_history` table in the database

- [ ] **Step 1: Read the latest migration to confirm revision chain**

Read `engine/migrations/versions/0042_add_source_ddl_to_source_schema_artifact.py` and confirm `down_revision = "0042"`. Verify no newer migration exists in the directory.

- [ ] **Step 2: Create migration file**

Create `engine/migrations/versions/0043_add_version_history.py`:

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

- [ ] **Step 3: Run migration and verify**

```bash
cd engine && .venv/bin/python -m alembic upgrade head
```

Verify the `version_history` table is created:

```bash
cd engine && .venv/bin/python -c "from migrations_engine.db.models import VersionHistory; print(VersionHistory.__tablename__)"
```

Expected: `version_history`

- [ ] **Step 4: Commit**

```bash
git add engine/migrations/versions/0043_add_version_history.py
git commit -m "chore(migration): add version_history table"
```

---

### Task 2: SQLAlchemy Model

**Files:**
- Modify: `engine/src/migrations_engine/db/models.py` (append at end)

**Interfaces:**
- Consumes: None (new model)
- Produces: `VersionHistory` ORM class mapped to `version_history` table

- [ ] **Step 1: Append VersionHistory model**

Read the end of `engine/src/migrations_engine/db/models.py` to find the last class (`AICallLog`). Append after it:

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

- [ ] **Step 2: Verify model compiles**

```bash
cd engine && .venv/bin/python -c "from migrations_engine.db.models import VersionHistory; print(VersionHistory.__tablename__)"
```

Expected: `version_history`

- [ ] **Step 3: Commit**

```bash
git add engine/src/migrations_engine/db/models.py
git commit -m "feat(model): add VersionHistory ORM model"
```

---

### Task 3: Pydantic Schemas

**Files:**
- Modify: `engine/src/migrations_engine/api/schemas.py` (append at end)

**Interfaces:**
- Consumes: None
- Produces: `VersionHistoryResponse` (read-only, for API responses)

- [ ] **Step 1: Append schema model**

Read the end of `engine/src/migrations_engine/api/schemas.py` to find the last class (`AICallLogResponse`). Append after it:

```python
class VersionHistoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    version_id: str
    field_name: str
    old_value: str | None
    new_value: str | None
    changed_by: str | None
    changed_at: datetime
```

- [ ] **Step 2: Verify schemas compile**

```bash
cd engine && .venv/bin/python -c "from migrations_engine.api.schemas import VersionHistoryResponse; print('OK')"
```

- [ ] **Step 3: Commit**

```bash
git add engine/src/migrations_engine/api/schemas.py
git commit -m "feat(schema): add VersionHistoryResponse"
```

---

### Task 4: API Routes

**Files:**
- Create: `engine/src/migrations_engine/routes/versions.py`
- Modify: `engine/src/migrations_engine/app.py`

**Interfaces:**
- Consumes: `VersionHistoryResponse` from schemas, `VersionHistory` from models, `require_project_access` from `management/access.py`, `get_current_user` + `get_db` from `api/deps.py`
- Produces: `GET /projects/{project_id}/versions/{entity_type}/versions` endpoint for entity types: hints, codegen, transformation, sql

- [ ] **Step 1: Create versions.py**

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

- [ ] **Step 2: Register router in app.py**

Read `engine/src/migrations_engine/app.py` to find the import section and the `app.include_router()` calls. Add:

```python
from .routes.versions import router as versions_router
```

And after the last `app.include_router(ai_calls_router)`:
```python
app.include_router(versions_router)
```

- [ ] **Step 3: Verify the route loads**

```bash
cd engine && .venv/bin/python -c "from migrations_engine.app import app; print([r.path for r in app.routes if 'versions' in r.path])"
```

Expected: list of `/projects/{project_id}/versions/hints/versions` etc.

- [ ] **Step 4: Commit**

```bash
git add engine/src/migrations_engine/routes/versions.py engine/src/migrations_engine/app.py
git commit -m "feat(api): add version history GET endpoint with project scoping"
```

---

### Task 5: Patch Hooks — feeds.py (hints + transformation)

**Files:**
- Modify: `engine/src/migrations_engine/routes/feeds.py`

**Interfaces:**
- Consumes: `VersionHistory` model, `UTC` from datetime, `AuthApiError` from deps, `Feed` from models
- Produces: Version snapshot insertion on PATCH hints and PATCH transformation-instructions

- [ ] **Step 1: Update imports at the top of feeds.py**

Current imports (lines 1-9):
```python
from __future__ import annotations

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..api.deps import AuthApiError, get_central_team_user, get_current_user, get_db
from ..api.schemas import FeedCreateRequest, FeedResponse, FeedSliceResponse, FeedMappingHintsRequest, TransformationInstructionsRequest
from ..db.models import User, Feed
from ..management.access import require_project_access
```

Change to:
```python
from __future__ import annotations

from datetime import UTC, datetime as _dt

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..api.deps import AuthApiError, get_central_team_user, get_current_user, get_db
from ..api.schemas import FeedCreateRequest, FeedResponse, FeedSliceResponse, FeedMappingHintsRequest, TransformationInstructionsRequest
from ..db.models import User, Feed, VersionHistory
from ..management.access import require_project_access
```

- [ ] **Step 2: Update `patch_source_hints` (line ~151)**

Replace the body:
```python
    require_project_access(db, user=actor, project_id=project_id)
    feed = db.get(Feed, source_definition_id)
    if feed is None or feed.project_id != project_id:
        raise AuthApiError("feed_not_found", "Feed not found.", 404)
    feed.mapping_hints = body.mapping_hints
    db.commit()
```

With:
```python
    require_project_access(db, user=actor, project_id=project_id)
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

- [ ] **Step 3: Update `patch_source_transformation_instructions` (line ~169)**

Replace the body:
```python
    require_project_access(db, user=actor, project_id=project_id)
    feed = db.get(Feed, source_definition_id)
    if feed is None or feed.project_id != project_id:
        raise AuthApiError("feed_not_found", "Feed not found.", 404)
    feed.transformation_instructions = body.transformation_instructions
    db.commit()
```

With:
```python
    require_project_access(db, user=actor, project_id=project_id)
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

- [ ] **Step 4: Verify syntax**

```bash
cd engine && .venv/bin/python -c "from migrations_engine.routes.feeds import router; print('OK')"
```

- [ ] **Step 5: Commit**

```bash
git add engine/src/migrations_engine/routes/feeds.py
git commit -m "feat(versioning): add version capture in feeds.py patch handlers"
```

---

### Task 6: Patch Hook — projects.py (codegen-instructions)

**Files:**
- Modify: `engine/src/migrations_engine/routes/projects.py`

**Interfaces:**
- Consumes: `ProjectDefinition`, `ProjectRegistry` from models, `update_project` from management/projects
- Produces: Version snapshot insertion on PATCH codegen-instructions

- [ ] **Step 1: Add imports at the top of projects.py**

After `from __future__ import annotations`, add:
```python
from datetime import UTC, datetime
```

The file currently has no datetime imports.

- [ ] **Step 2: Update model import line**

Current (line ~26):
```python
from ..db.models import User
```

Replace with:
```python
from ..db.models import User, VersionHistory, ProjectDefinition, ProjectRegistry
```

- [ ] **Step 3: Update `patch_codegen_instructions` handler**

Current handler (line ~136):
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

Replace with:
```python
@router.patch("/{project_id}/codegen-instructions", response_model=ProjectResponse)
def patch_codegen_instructions(
    project_id: str,
    body: CodegenInstructionsRequest,
    actor: User = Depends(get_central_team_user),
    db: Session = Depends(get_db),
) -> ProjectResponse:
    require_project_access(db, user=actor, project_id=project_id)
    # Capture version snapshot before update_project() overwrites the definition
    current_registry = db.get(ProjectRegistry, project_id)
    _old_val = None
    if current_registry:
        current_def = db.get(ProjectDefinition, current_registry.definition_id)
        if current_def:
            _old_val = current_def.codegen_instructions
    if body.codegen_instructions is not None:
        db.add(VersionHistory(
            entity_type="codegen",
            entity_id=project_id,
            field_name="codegen_instructions",
            old_value=_old_val,
            new_value=body.codegen_instructions,
            changed_by=actor.user_id,
            changed_at=datetime.now(UTC),
        ))
        db.commit()
    return update_project(
        db,
        actor=actor,
        project_id=project_id,
        body=ProjectUpdateRequest(codegen_instructions=body.codegen_instructions),
    )
```

- [ ] **Step 4: Verify syntax**

```bash
cd engine && .venv/bin/python -c "from migrations_engine.routes.projects import router; print('OK')"
```

- [ ] **Step 5: Commit**

```bash
git add engine/src/migrations_engine/routes/projects.py
git commit -m "feat(versioning): add version capture in projects.py codegen-instructions handler"
```

---

### Task 7: Patch Hook — codegen/service.py (SQL scripts)

**Files:**
- Modify: `engine/src/migrations_engine/codegen/service.py`

**Interfaces:**
- Consumes: `VersionHistory` from models, `datetime` and `UTC` from datetime
- Produces: Version snapshot insertion when a new codegen artifact is created

- [ ] **Step 1: Add VersionHistory to the model import block**

Current import block (lines 19-30):
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
)
```

Replace with:
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

- [ ] **Step 2: Add version capture after artifact creation**

After `db.add(artifact)` (around line 199 in `generate_codegen_artifact`), before `record_management_audit`, add:

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

- [ ] **Step 3: Verify syntax**

```bash
cd engine && .venv/bin/python -c "from migrations_engine.codegen.service import generate_codegen_artifact; print('OK')"
```

- [ ] **Step 4: Commit**

```bash
git add engine/src/migrations_engine/codegen/service.py
git commit -m "feat(versioning): add version capture in codegen/service.py artifact creation"
```

---

### Task 8: Tests

**Files:**
- Create: `engine/tests/test_version_history.py`

**Interfaces:**
- Consumes: `VersionHistory` model, `Base` from sqlite_test_support, admin/stakeholder tokens from auth/login
- Produces: 6 test functions verifying version capture, project scoping, and entity types

- [ ] **Step 1: Create test file**

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
    """Create two projects; return (pid_a, sid_a, pid_b, sid_b)."""
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
        # Stakeholder is a member of project A only, not B
        if admin and stakeholder:
            db.add(ProjectMembership(project_id=pid_a, user_id=stakeholder.user_id))
        db.commit()
    return pid_a, sid_a, pid_b, sid_b


def test_version_history_hints_capture(admin_token: str, _seed_projects: tuple) -> None:
    pid, sid, _, _ = _seed_projects
    resp = client.patch(
        f"/projects/{pid}/sources/{sid}/hints",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"mapping_hints": "test hints v1"},
    )
    assert resp.status_code == 200
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
    resp = client.patch(
        f"/projects/{pid}/sources/{sid}/hints",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"mapping_hints": "first value"},
    )
    assert resp.status_code == 200
    resp = client.get(
        f"/projects/{pid}/versions/hints/versions",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.json()[0]["old_value"] is None


def test_version_history_transformation_capture(admin_token: str, _seed_projects: tuple) -> None:
    pid, sid, _, _ = _seed_projects
    resp = client.patch(
        f"/projects/{pid}/sources/{sid}/transformation-instructions",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"transformation_instructions": "trans v1"},
    )
    assert resp.status_code == 200
    resp = client.get(
        f"/projects/{pid}/versions/transformation/versions",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
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
    resp = client.get(
        f"/projects/{pid}/versions/codegen/versions",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    assert resp.json()[0]["new_value"] == "# test instructions"


def test_version_history_project_scoped(stakeholder_token: str, _seed_projects: tuple) -> None:
    """Stakeholder is a member of A (not B) — A's versions succeed, B's 403."""
    pid_a, _, pid_b, _ = _seed_projects
    resp = client.get(
        f"/projects/{pid_a}/versions/hints/versions",
        headers={"Authorization": f"Bearer {stakeholder_token}"},
    )
    assert resp.status_code == 200
    resp = client.get(
        f"/projects/{pid_b}/versions/hints/versions",
        headers={"Authorization": f"Bearer {stakeholder_token}"},
    )
    assert resp.status_code == 403


def test_version_history_entity_types(admin_token: str, _seed_projects: tuple) -> None:
    pid, sid, _, _ = _seed_projects
    for endpoint in ["hints", "transformation", "codegen", "sql"]:
        resp = client.get(
            f"/projects/{pid}/versions/{endpoint}/versions",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 200
        assert resp.json() == []
```

- [ ] **Step 2: Run the full test suite**

```bash
cd engine && pytest tests/test_version_history.py -v
```

Expected: 6 tests, all pass.

- [ ] **Step 3: Commit**

```bash
git add engine/tests/test_version_history.py
git commit -m "test(versioning): add 6 tests for version capture, scoping, and entity types"
```

---

## Verification

After all 8 tasks are complete:

```bash
cd engine && pytest tests/test_version_history.py -v
```

All 6 tests should pass.

## Pitfalls

1. **`_dt.timezone.utc` crashes** — `datetime` class has no `.timezone` attribute. Use `from datetime import UTC, datetime` and `datetime.now(UTC)`.
2. **Project scoping** — Routes use `/projects/{project_id}/versions/{entity_type}/versions`. Every handler calls `require_project_access(db, user=actor, project_id=project_id)`.
3. **Codegen old value** — Must read from `ProjectDefinition` *before* `update_project()` overwrites it.
4. **Test fixture ordering** — `VersionHistory` must be imported before `_setup_sqlite_db`'s `Base.metadata.create_all()`.
5. **SQLAlchemy `from_attributes=True`** — `VersionHistoryResponse` needs `model_config = ConfigDict(from_attributes=True)` to map ORM objects to JSON.

## Commit

After completing all tasks:

```
feat(versioning): add version_history table, API, and patch hooks

- Migration 0043: version_history table with indexed (entity_type, entity_id, field_name)
- VersionHistory SQLAlchemy model
- VersionHistoryResponse schema
- GET /projects/{pid}/versions/{entity_type} endpoint with require_project_access
- Patch hooks in feeds.py (hints, transformation), projects.py (codegen), codegen/service.py (sql)
- Test suite: 6 tests covering capture, project scoping, and entity types
```
