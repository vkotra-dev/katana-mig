# Project CRUD — Backend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add fully encapsulated project lifecycle management — create, read/list, update, archive — as a self-contained vertical slice through schemas, access guards, service, and routes.

**Architecture:**
- `ProjectRegistry` is the durable routing entry. `ProjectDefinition` is a frozen snapshot — it is **never mutated after creation**. Update clones the definition into a new row and advances `ProjectRegistry.definition_id`; the old row is preserved for run lineage. Archive sets `archived_at` on the registry. No hard-delete.
- Role and membership enforcement belongs at the API layer (`access.py` + `deps.py`). Service functions contain only business logic.

**Layer responsibilities:**
- `management/access.py` — *who* can perform an action
- `api/deps.py` — FastAPI dependency wiring of access guards
- `management/projects.py` — *what* happens (pure business logic)
- `routes/projects.py` — wires deps to service; calls access guards for project-scoped routes

**Role gating:**
- `POST /projects` — `central_team` or `project_stakeholder`; stakeholder auto-membered in service (business logic)
- `GET /projects`, `GET /projects/{id}` — any authenticated user; `GET /{id}` calls `require_project_access` in route handler
- `PATCH /projects/{id}`, `POST /projects/{id}/archive` — `central_team` only

**Tech Stack:** Python ≥ 3.11, FastAPI, SQLAlchemy 2.x (sync, mapped-column style), Pydantic v2, pytest + FastAPI TestClient, SQLite test DB (no mocking).

## Global Constraints

- `from __future__ import annotations` at top of every file
- All IDs: UUID4 strings via `new_id()` from `db.models`
- `status` field values: `"active"` | `"archived"` (string ≤ 32 chars)
- No hard-delete — archive only; archived rows excluded from list by default
- Every mutation calls `record_management_audit()` from `management.platform`
- PATCH semantics: `None` = leave unchanged; send `[]` to clear a list
- **I17:** `ProjectDefinition` rows are immutable once created — update clones, never patches

---

## Full Field Inventory

### `ProjectDefinition` columns → API fields

| Column | Type | Notes |
|--------|------|-------|
| `name` | `str` | Required on create; mirrored to `ProjectRegistry.name` |
| `goal` | `str \| None` | Free-text migration goal |
| `repos` | `list[dict] \| None` | Git/repo references |
| `workspace` | `dict \| None` | Generic workspace config |
| `environment` | `str \| None` | Primary environment label |
| `execution_environments` | `list[str] \| None` | Ordered env pipeline e.g. `["STG","UAT","PROD"]` |
| `model_policy` | `dict \| None` | AI model governance policy |
| `canonical_terms` | `list[str] \| None` | Domain vocabulary |
| `constraints` | `list[str] \| None` | Compliance constraints |
| `unresolved_questions` | `list[str] \| None` | Open governance questions |
| `assumptions` | `list[str] \| None` | Baseline assumptions |
| `domain_config` | `dict \| None` | `MigrationProjectConfig`: source type, DDL, sample policy, dry-run, source composition |

### `ProjectRegistry` columns → API fields

| Column | Type | Notes |
|--------|------|-------|
| `project_id` | `str` | Read-only; UUID generated on create |
| `name` | `str` | Mirrored from current definition |
| `lexicon_scope` | `dict \| None` | Vocabulary scope; stored on registry |
| `status` | `"active" \| "archived"` | Changed by archive action only |
| `created_at` | `datetime` | Read-only |
| `updated_at` | `datetime` | Read-only |
| `archived_at` | `datetime \| None` | Set by archive action |

---

## Out of Scope

- Initial CR on project creation — separate governance task
- Portfolio operational fields (stage, days in stage, blocked indicator) — require run-state joins

---

## File Structure

| File | Action | Role |
|------|--------|------|
| `engine/src/migrations_engine/api/schemas.py` | Modify | Add `ProjectStatus`, `ProjectResponse`, `ProjectCreateRequest`, `ProjectUpdateRequest` |
| `engine/src/migrations_engine/management/access.py` | Modify | Add `require_non_auditor`, `require_project_access` |
| `engine/src/migrations_engine/api/deps.py` | Modify | Add `get_project_initiation_user` |
| `engine/src/migrations_engine/management/projects.py` | Create | Service — pure business logic |
| `engine/src/migrations_engine/routes/projects.py` | Modify | Wire deps; access guards in route handlers |
| `engine/tests/test_project_crud_api.py` | Create | Integration tests per endpoint group |

---

### Task 1 — Project schemas

**Files:** `engine/src/migrations_engine/api/schemas.py`

**Produces:** `ProjectStatus`, `ProjectResponse`, `ProjectCreateRequest`, `ProjectUpdateRequest`

- [ ] **Step 1: Add `Any` to the typing import**

```python
# before
from typing import Literal
# after
from typing import Any, Literal
```

- [ ] **Step 2: Append after `MembershipResponse`**

```python
TargetDbEngine = Literal["mssql", "oracle", "postgresql", "mysql"]
ProjectStatus = Literal["active", "archived"]


class MigrationProjectConfig(BaseModel):
    target_db_engine: TargetDbEngine
    staging_schema: str | None = None
    dry_run: bool = False
    sample_policy: dict[str, Any] | None = None


class ProjectResponse(BaseModel):
    project_id: str
    name: str
    goal: str | None
    repos: list[dict[str, Any]] | None
    workspace: dict[str, Any] | None
    environment: str | None
    execution_environments: list[str] | None
    model_policy: dict[str, Any] | None
    canonical_terms: list[str] | None
    constraints: list[str] | None
    unresolved_questions: list[str] | None
    assumptions: list[str] | None
    domain_config: MigrationProjectConfig | None
    lexicon_scope: dict[str, Any] | None
    status: ProjectStatus
    created_at: datetime
    updated_at: datetime
    archived_at: datetime | None


class ProjectCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    goal: str | None = None
    repos: list[dict[str, Any]] | None = None
    workspace: dict[str, Any] | None = None
    environment: str | None = None
    execution_environments: list[str] | None = None
    model_policy: dict[str, Any] | None = None
    canonical_terms: list[str] | None = None
    constraints: list[str] | None = None
    unresolved_questions: list[str] | None = None
    assumptions: list[str] | None = None
    domain_config: MigrationProjectConfig | None = None
    lexicon_scope: dict[str, Any] | None = None


class ProjectUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    goal: str | None = None
    repos: list[dict[str, Any]] | None = None
    workspace: dict[str, Any] | None = None
    environment: str | None = None
    execution_environments: list[str] | None = None
    model_policy: dict[str, Any] | None = None
    canonical_terms: list[str] | None = None
    constraints: list[str] | None = None
    unresolved_questions: list[str] | None = None
    assumptions: list[str] | None = None
    domain_config: MigrationProjectConfig | None = None
    lexicon_scope: dict[str, Any] | None = None
```

- [ ] **Step 3: Verify**

```bash
cd engine && python -c "from migrations_engine.api.schemas import ProjectResponse, ProjectCreateRequest, ProjectUpdateRequest, MigrationProjectConfig; print('ok')"
```

Expected: `ok`

- [ ] **Step 4: Commit**

```bash
git add engine/src/migrations_engine/api/schemas.py
git commit -m "feat: add project CRUD schemas"
```

---

### Task 2 — Access guards and dep

**Files:**
- `engine/src/migrations_engine/management/access.py`
- `engine/src/migrations_engine/api/deps.py`

**Why:** Role and membership enforcement belongs at the API layer, following the existing `require_central_team` / `get_central_team_user` pattern.

**Produces:**
- `require_non_auditor(user) -> None` — raises 403 for `read_only_auditor`
- `require_project_access(db, *, user, project_id) -> None` — raises 403 when stakeholder lacks membership; wraps existing `user_has_project_access`
- `get_project_initiation_user` dep — allows `central_team` or `project_stakeholder`

- [ ] **Step 1: Append to `management/access.py`**

```python
def require_non_auditor(user: User) -> None:
    if user.role == READ_ONLY_AUDITOR_ROLE:
        raise AuthApiError("forbidden", "Read-only auditors cannot initiate projects.", 403)


def require_project_access(db: Session, *, user: User, project_id: str) -> None:
    if not user_has_project_access(db, user=user, project_id=project_id):
        raise AuthApiError("forbidden", "Access to this project requires membership.", 403)
```

- [ ] **Step 2: Append to `api/deps.py`**

```python
def get_project_initiation_user(user: User = Depends(get_current_user)) -> User:
    from ..management.access import require_non_auditor

    require_non_auditor(user)
    return user
```

- [ ] **Step 3: Verify**

```bash
cd engine && python -c "
from migrations_engine.management.access import require_non_auditor, require_project_access
from migrations_engine.api.deps import get_project_initiation_user
print('ok')
"
```

Expected: `ok`

- [ ] **Step 4: Commit**

```bash
git add engine/src/migrations_engine/management/access.py \
        engine/src/migrations_engine/api/deps.py
git commit -m "feat: add require_non_auditor, require_project_access, get_project_initiation_user"
```

---

### Task 3 — Project service

**Files:** `engine/src/migrations_engine/management/projects.py` (create)

**Contract:** Zero role checks. Zero membership guards. Auto-membering a stakeholder on create is business logic (a rule about what happens), not access control. Membership JOIN in `list_projects` is query/data scoping.

**Consumes:** Task 1 schemas, `ProjectDefinition`, `ProjectMembership`, `ProjectRegistry`, `User`, `new_id`, `record_management_audit`, `PROJECT_STAKEHOLDER_ROLE`, `AuthApiError`

**Produces:**
- `create_project(db, *, actor, body) -> ProjectResponse`
- `list_projects(db, *, actor, include_archived) -> list[ProjectResponse]`
- `get_project(db, *, project_id) -> ProjectResponse`
- `update_project(db, *, actor, project_id, body) -> ProjectResponse`
- `archive_project(db, *, actor, project_id) -> ProjectResponse`

- [ ] **Step 1: Create `engine/src/migrations_engine/management/projects.py`**

```python
from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..api.deps import AuthApiError
from ..api.schemas import (
    ProjectCreateRequest,
    ProjectResponse,
    ProjectUpdateRequest,
)
from ..db.models import ProjectDefinition, ProjectMembership, ProjectRegistry, User, new_id
from ..roles import PROJECT_STAKEHOLDER_ROLE
from .platform import record_management_audit


def create_project(db: Session, *, actor: User, body: ProjectCreateRequest) -> ProjectResponse:
    project_id = new_id()
    definition_id = new_id()

    definition = ProjectDefinition(
        definition_id=definition_id,
        project_id=project_id,
        name=body.name,
        goal=body.goal,
        repos=body.repos,
        workspace=body.workspace,
        environment=body.environment,
        execution_environments=body.execution_environments,
        model_policy=body.model_policy,
        canonical_terms=body.canonical_terms,
        constraints=body.constraints,
        unresolved_questions=body.unresolved_questions,
        assumptions=body.assumptions,
        domain_config=body.domain_config,
        status="active",
    )
    registry = ProjectRegistry(
        project_id=project_id,
        name=body.name,
        definition_id=definition_id,
        lexicon_scope=body.lexicon_scope,
        status="active",
    )
    db.add(definition)
    db.add(registry)
    db.flush()

    if actor.role == PROJECT_STAKEHOLDER_ROLE:
        db.add(ProjectMembership(project_id=project_id, user_id=actor.user_id))

    record_management_audit(
        db,
        project_id=project_id,
        actor_user_id=actor.user_id,
        event_type="project.created",
        payload={"project_id": project_id, "name": body.name},
    )
    db.commit()
    db.refresh(registry)
    db.refresh(definition)
    return _project_response(registry, definition)


def list_projects(
    db: Session,
    *,
    actor: User,
    include_archived: bool = False,
) -> list[ProjectResponse]:
    stmt = select(ProjectRegistry, ProjectDefinition).join(
        ProjectDefinition,
        ProjectRegistry.definition_id == ProjectDefinition.definition_id,
    )
    if not include_archived:
        stmt = stmt.where(ProjectRegistry.archived_at.is_(None))
    stmt = stmt.where(ProjectRegistry.soft_deleted_at.is_(None))

    if actor.role == PROJECT_STAKEHOLDER_ROLE:
        stmt = stmt.join(
            ProjectMembership,
            (ProjectMembership.project_id == ProjectRegistry.project_id)
            & (ProjectMembership.user_id == actor.user_id),
        )

    stmt = stmt.order_by(ProjectRegistry.name)
    rows = db.execute(stmt).all()
    return [_project_response(reg, defn) for reg, defn in rows]


def get_project(db: Session, *, project_id: str) -> ProjectResponse:
    reg, defn = _get_project_rows(db, project_id)
    return _project_response(reg, defn)


def update_project(
    db: Session,
    *,
    actor: User,
    project_id: str,
    body: ProjectUpdateRequest,
) -> ProjectResponse:
    reg, current_defn = _get_project_rows(db, project_id)
    if reg.archived_at is not None:
        raise AuthApiError("project_archived", "Cannot update an archived project.", 409)

    new_definition_id = new_id()
    new_defn = ProjectDefinition(
        definition_id=new_definition_id,
        project_id=project_id,
        name=body.name if body.name is not None else current_defn.name,
        goal=body.goal if body.goal is not None else current_defn.goal,
        repos=body.repos if body.repos is not None else current_defn.repos,
        workspace=body.workspace if body.workspace is not None else current_defn.workspace,
        environment=body.environment if body.environment is not None else current_defn.environment,
        execution_environments=(
            body.execution_environments
            if body.execution_environments is not None
            else current_defn.execution_environments
        ),
        model_policy=body.model_policy if body.model_policy is not None else current_defn.model_policy,
        canonical_terms=body.canonical_terms if body.canonical_terms is not None else current_defn.canonical_terms,
        constraints=body.constraints if body.constraints is not None else current_defn.constraints,
        unresolved_questions=(
            body.unresolved_questions
            if body.unresolved_questions is not None
            else current_defn.unresolved_questions
        ),
        assumptions=body.assumptions if body.assumptions is not None else current_defn.assumptions,
        domain_config=body.domain_config if body.domain_config is not None else current_defn.domain_config,
        status="active",
    )
    db.add(new_defn)
    db.flush()

    reg.definition_id = new_definition_id
    if body.name is not None:
        reg.name = body.name
    if body.lexicon_scope is not None:
        reg.lexicon_scope = body.lexicon_scope

    changed_keys = [k for k, v in body.model_dump().items() if v is not None]
    if changed_keys:
        record_management_audit(
            db,
            project_id=project_id,
            actor_user_id=actor.user_id,
            event_type="project.updated",
            payload={
                "project_id": project_id,
                "new_definition_id": new_definition_id,
                "changed_fields": changed_keys,
            },
        )
    db.commit()
    db.refresh(reg)
    db.refresh(new_defn)
    return _project_response(reg, new_defn)


def archive_project(db: Session, *, actor: User, project_id: str) -> ProjectResponse:
    reg, defn = _get_project_rows(db, project_id)
    if reg.archived_at is not None:
        raise AuthApiError("project_already_archived", "Project is already archived.", 409)

    now = datetime.now(UTC)
    reg.archived_at = now
    reg.status = "archived"

    record_management_audit(
        db,
        project_id=project_id,
        actor_user_id=actor.user_id,
        event_type="project.archived",
        payload={"project_id": project_id},
    )
    db.commit()
    db.refresh(reg)
    db.refresh(defn)
    return _project_response(reg, defn)


def _get_project_rows(db: Session, project_id: str) -> tuple[ProjectRegistry, ProjectDefinition]:
    reg = db.get(ProjectRegistry, project_id)
    if reg is None or reg.soft_deleted_at is not None:
        raise AuthApiError("project_not_found", "Project not found.", 404)
    defn = db.get(ProjectDefinition, reg.definition_id)
    if defn is None:
        raise AuthApiError("project_not_found", "Project not found.", 404)
    return reg, defn


def _project_response(reg: ProjectRegistry, defn: ProjectDefinition) -> ProjectResponse:
    return ProjectResponse(
        project_id=reg.project_id,
        name=reg.name,
        goal=defn.goal,
        repos=defn.repos,
        workspace=defn.workspace,
        environment=defn.environment,
        execution_environments=defn.execution_environments,
        model_policy=defn.model_policy,
        canonical_terms=defn.canonical_terms,
        constraints=defn.constraints,
        unresolved_questions=defn.unresolved_questions,
        assumptions=defn.assumptions,
        domain_config=defn.domain_config,
        lexicon_scope=reg.lexicon_scope,
        status=reg.status,  # type: ignore[arg-type]
        created_at=reg.created_at,
        updated_at=reg.updated_at,
        archived_at=reg.archived_at,
    )
```

- [ ] **Step 2: Verify import**

```bash
cd engine && python -c "
from migrations_engine.management.projects import (
    create_project, list_projects, get_project, update_project, archive_project
)
print('ok')
"
```

Expected: `ok`

- [ ] **Step 3: Commit**

```bash
git add engine/src/migrations_engine/management/projects.py
git commit -m "feat: add project service (pure business logic)"
```

---

### Task 4a — Create and list routes + tests

Each sub-task is a full red → green → commit cycle for one endpoint group.

**Files:**
- `engine/src/migrations_engine/routes/projects.py` (create skeleton + POST + GET routes)
- `engine/tests/test_project_crud_api.py` (create with create + list tests)

**Consumes:** Tasks 1–3 schemas, service, deps

- [ ] **Step 1: Create test file with create + list tests**

Create `engine/tests/test_project_crud_api.py`:

```python
from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from migrations_engine.app import app
from migrations_engine.auth.passwords import hash_password
from migrations_engine.config import get_settings
from migrations_engine.db.models import AuthSession, ProjectMembership, User
from migrations_engine.db.session import SessionLocal
from migrations_engine.roles import PROJECT_STAKEHOLDER_ROLE, READ_ONLY_AUDITOR_ROLE

client = TestClient(app)


@pytest.fixture(autouse=True)
def _clear_settings_cache() -> None:
    get_settings.cache_clear()


def _login(email: str, password: str) -> str:
    r = client.post("/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


@pytest.fixture
def admin_token() -> str:
    settings = get_settings()
    if not settings.bootstrap_admin_email or not settings.bootstrap_admin_password:
        pytest.skip("bootstrap credentials not configured")
    return _login(settings.bootstrap_admin_email, settings.bootstrap_admin_password)


def _make_user(role: str) -> tuple[str, str, str]:
    user_id = str(uuid.uuid4())
    email = f"{role[:4]}-{user_id[:8]}@example.com"
    password = "test-password"
    with SessionLocal() as db:
        db.add(User(
            user_id=user_id, email=email,
            password_hash=hash_password(password),
            role=role, status="active",
        ))
        db.commit()
    return user_id, email, password


def _cleanup_user(user_id: str) -> None:
    with SessionLocal() as db:
        for row in db.scalars(select(AuthSession).where(AuthSession.user_id == user_id)):
            db.delete(row)
        for row in db.scalars(select(ProjectMembership).where(ProjectMembership.user_id == user_id)):
            db.delete(row)
        user = db.get(User, user_id)
        if user:
            db.delete(user)
        db.commit()


@pytest.fixture
def stakeholder() -> tuple[str, str]:
    user_id, email, password = _make_user(PROJECT_STAKEHOLDER_ROLE)
    token = _login(email, password)
    yield user_id, token
    _cleanup_user(user_id)


@pytest.fixture
def auditor_token() -> str:
    user_id, email, password = _make_user(READ_ONLY_AUDITOR_ROLE)
    token = _login(email, password)
    yield token
    _cleanup_user(user_id)


# ── POST /projects ────────────────────────────────────────────────────────────

def test_admin_can_create_minimal(admin_token: str) -> None:
    r = client.post("/projects", headers={"Authorization": f"Bearer {admin_token}"},
                    json={"name": "Minimal"})
    assert r.status_code == 201, r.text
    b = r.json()
    assert b["name"] == "Minimal"
    assert b["status"] == "active"
    assert b["archived_at"] is None


def test_create_all_fields_roundtrip(admin_token: str) -> None:
    r = client.post("/projects", headers={"Authorization": f"Bearer {admin_token}"},
                    json={
                        "name": "Full",
                        "goal": "Migrate CRM",
                        "execution_environments": ["STG", "UAT", "PROD"],
                        "constraints": ["Art 6(1)(c)"],
                        "assumptions": ["Replica stable"],
                        "unresolved_questions": ["PHI present?"],
                        "canonical_terms": ["customer_id"],
                        "domain_config": {"source_type": "database",
                                          "destination_schema_ddl": "CREATE TABLE t (id INT);"},
                        "lexicon_scope": {"domain": "finance"},
                        "environment": "STG",
                    })
    assert r.status_code == 201, r.text
    b = r.json()
    assert b["execution_environments"] == ["STG", "UAT", "PROD"]
    assert b["domain_config"]["source_type"] == "database"
    assert b["lexicon_scope"]["domain"] == "finance"


def test_stakeholder_can_create_and_is_auto_membered(stakeholder: tuple[str, str]) -> None:
    user_id, token = stakeholder
    r = client.post("/projects", headers={"Authorization": f"Bearer {token}"},
                    json={"name": "SH Project"})
    assert r.status_code == 201, r.text
    project_id = r.json()["project_id"]
    with SessionLocal() as db:
        m = db.scalar(select(ProjectMembership).where(
            ProjectMembership.project_id == project_id,
            ProjectMembership.user_id == user_id,
        ))
    assert m is not None


def test_auditor_cannot_create(auditor_token: str) -> None:
    r = client.post("/projects", headers={"Authorization": f"Bearer {auditor_token}"},
                    json={"name": "Blocked"})
    assert r.status_code == 403


def test_unauthenticated_create_rejected() -> None:
    assert client.post("/projects", json={"name": "X"}).status_code == 401


# ── GET /projects ─────────────────────────────────────────────────────────────

def test_list_excludes_archived_by_default(admin_token: str) -> None:
    suffix = uuid.uuid4().hex[:6]
    active_id = client.post("/projects", headers={"Authorization": f"Bearer {admin_token}"},
                            json={"name": f"Active-{suffix}"}).json()["project_id"]
    arch_id = client.post("/projects", headers={"Authorization": f"Bearer {admin_token}"},
                          json={"name": f"Arch-{suffix}"}).json()["project_id"]
    client.post(f"/projects/{arch_id}/archive", headers={"Authorization": f"Bearer {admin_token}"})

    ids = [p["project_id"] for p in client.get(
        "/projects", headers={"Authorization": f"Bearer {admin_token}"}).json()]
    assert active_id in ids
    assert arch_id not in ids

    ids_all = [p["project_id"] for p in client.get(
        "/projects?include_archived=true", headers={"Authorization": f"Bearer {admin_token}"}).json()]
    assert arch_id in ids_all


def test_stakeholder_sees_only_member_projects(admin_token: str, stakeholder: tuple[str, str]) -> None:
    user_id, sh_token = stakeholder
    member_id = client.post("/projects", headers={"Authorization": f"Bearer {admin_token}"},
                            json={"name": f"Member-{uuid.uuid4().hex[:6]}"}).json()["project_id"]
    other_id = client.post("/projects", headers={"Authorization": f"Bearer {admin_token}"},
                           json={"name": f"Other-{uuid.uuid4().hex[:6]}"}).json()["project_id"]
    client.post(f"/projects/{member_id}/members",
                headers={"Authorization": f"Bearer {admin_token}"},
                json={"user_id": user_id})

    ids = [p["project_id"] for p in client.get(
        "/projects", headers={"Authorization": f"Bearer {sh_token}"}).json()]
    assert member_id in ids
    assert other_id not in ids


def test_auditor_can_list_all_projects(admin_token: str, auditor_token: str) -> None:
    pid = client.post("/projects", headers={"Authorization": f"Bearer {admin_token}"},
                      json={"name": f"AuditVis-{uuid.uuid4().hex[:6]}"}).json()["project_id"]
    ids = [p["project_id"] for p in client.get(
        "/projects", headers={"Authorization": f"Bearer {auditor_token}"}).json()]
    assert pid in ids


def test_unauthenticated_list_rejected() -> None:
    assert client.get("/projects").status_code == 401
```

- [ ] **Step 2: Run tests — confirm all fail (endpoints not yet defined)**

```bash
cd engine && python -m pytest tests/test_project_crud_api.py -v 2>&1 | tail -20
```

Expected: failures with `404` or `AttributeError` — routes do not exist yet.

- [ ] **Step 3: Create `routes/projects.py` with skeleton + POST + GET routes**

```python
from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Response, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..api.deps import (
    get_central_team_user,
    get_current_user,
    get_db,
    get_project_initiation_user,
)
from ..api.schemas import (
    MembershipResponse,
    ProjectCreateRequest,
    ProjectMemberResponse,
    ProjectResponse,
    ProjectUpdateRequest,
)
from ..db.models import User
from ..management.access import require_project_access
from ..management.projects import (
    archive_project,
    create_project,
    get_project,
    list_projects,
    update_project,
)
from ..management.service import (
    add_project_member,
    list_project_members,
    remove_project_member,
)

router = APIRouter(prefix="/projects", tags=["projects"])


class AddMemberRequest(BaseModel):
    user_id: str


@router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
def post_project(
    body: ProjectCreateRequest,
    actor: User = Depends(get_project_initiation_user),
    db: Session = Depends(get_db),
) -> ProjectResponse:
    return create_project(db, actor=actor, body=body)


@router.get("", response_model=list[ProjectResponse])
def get_projects(
    include_archived: bool = Query(default=False),
    actor: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[ProjectResponse]:
    return list_projects(db, actor=actor, include_archived=include_archived)


# ── placeholders — implemented in Task 4b and 4c ─────────────────────────────

@router.get("/{project_id}", response_model=ProjectResponse)
def get_project_by_id(
    project_id: str,
    actor: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ProjectResponse:
    raise NotImplementedError


@router.patch("/{project_id}", response_model=ProjectResponse)
def patch_project(
    project_id: str,
    body: ProjectUpdateRequest,
    actor: User = Depends(get_central_team_user),
    db: Session = Depends(get_db),
) -> ProjectResponse:
    raise NotImplementedError


@router.post("/{project_id}/archive", response_model=ProjectResponse)
def post_project_archive(
    project_id: str,
    actor: User = Depends(get_central_team_user),
    db: Session = Depends(get_db),
) -> ProjectResponse:
    raise NotImplementedError


@router.get("/{project_id}/members", response_model=list[ProjectMemberResponse])
def get_project_members(
    project_id: str,
    _actor: User = Depends(get_central_team_user),
    db: Session = Depends(get_db),
) -> list[ProjectMemberResponse]:
    return list_project_members(db, project_id=project_id)


@router.post("/{project_id}/members", response_model=MembershipResponse)
def post_project_member(
    project_id: str,
    body: AddMemberRequest,
    actor: User = Depends(get_central_team_user),
    db: Session = Depends(get_db),
) -> MembershipResponse:
    return add_project_member(db, actor=actor, project_id=project_id, user_id=body.user_id)


@router.delete("/{project_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project_member(
    project_id: str,
    user_id: str,
    actor: User = Depends(get_central_team_user),
    db: Session = Depends(get_db),
) -> Response:
    remove_project_member(db, actor=actor, project_id=project_id, user_id=user_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
```

- [ ] **Step 4: Run create + list tests — confirm they pass**

```bash
cd engine && python -m pytest tests/test_project_crud_api.py -k "create or list" -v
```

Expected: all selected tests pass.

- [ ] **Step 5: Run full suite — confirm no regressions**

```bash
cd engine && python -m pytest tests/ -v
```

Expected: all pass (placeholder routes not yet tested).

- [ ] **Step 6: Commit**

```bash
git add engine/src/migrations_engine/routes/projects.py \
        engine/tests/test_project_crud_api.py
git commit -m "feat: add project create and list routes with passing tests"
```

---

### Task 4b — Get and update routes + tests

- [ ] **Step 1: Add get + update tests to `test_project_crud_api.py`**

Append to `engine/tests/test_project_crud_api.py`:

```python
# ── GET /projects/{id} ────────────────────────────────────────────────────────

def test_get_project_returns_all_fields(admin_token: str) -> None:
    pid = client.post("/projects", headers={"Authorization": f"Bearer {admin_token}"},
                      json={"name": "GetMe", "constraints": ["GDPR"],
                            "execution_environments": ["PROD"]}).json()["project_id"]
    r = client.get(f"/projects/{pid}", headers={"Authorization": f"Bearer {admin_token}"})
    assert r.status_code == 200
    b = r.json()
    assert b["constraints"] == ["GDPR"]
    assert b["execution_environments"] == ["PROD"]


def test_get_project_not_found(admin_token: str) -> None:
    r = client.get("/projects/00000000-0000-0000-0000-000000000000",
                   headers={"Authorization": f"Bearer {admin_token}"})
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "project_not_found"


def test_stakeholder_blocked_from_non_member_project(
        admin_token: str, stakeholder: tuple[str, str]) -> None:
    _, sh_token = stakeholder
    pid = client.post("/projects", headers={"Authorization": f"Bearer {admin_token}"},
                      json={"name": f"NoAccess-{uuid.uuid4().hex[:6]}"}).json()["project_id"]
    r = client.get(f"/projects/{pid}", headers={"Authorization": f"Bearer {sh_token}"})
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "forbidden"


def test_auditor_can_get_any_project(admin_token: str, auditor_token: str) -> None:
    pid = client.post("/projects", headers={"Authorization": f"Bearer {admin_token}"},
                      json={"name": f"AuditGet-{uuid.uuid4().hex[:6]}"}).json()["project_id"]
    r = client.get(f"/projects/{pid}", headers={"Authorization": f"Bearer {auditor_token}"})
    assert r.status_code == 200


# ── PATCH /projects/{id} ──────────────────────────────────────────────────────

def test_update_partial_leaves_unchanged_fields(admin_token: str) -> None:
    pid = client.post("/projects", headers={"Authorization": f"Bearer {admin_token}"},
                      json={"name": "Before", "goal": "Old", "constraints": ["C1"]}).json()["project_id"]
    r = client.patch(f"/projects/{pid}", headers={"Authorization": f"Bearer {admin_token}"},
                     json={"name": "After"})
    assert r.status_code == 200
    b = r.json()
    assert b["name"] == "After"
    assert b["goal"] == "Old"
    assert b["constraints"] == ["C1"]


def test_update_creates_new_definition_row(admin_token: str) -> None:
    from migrations_engine.db.models import ProjectDefinition as _PD
    pid = client.post("/projects", headers={"Authorization": f"Bearer {admin_token}"},
                      json={"name": "Immutable", "goal": "Original"}).json()["project_id"]
    client.patch(f"/projects/{pid}", headers={"Authorization": f"Bearer {admin_token}"},
                 json={"goal": "Updated"})
    assert client.get(f"/projects/{pid}",
                      headers={"Authorization": f"Bearer {admin_token}"}).json()["goal"] == "Updated"
    with SessionLocal() as db:
        rows = db.scalars(select(_PD).where(_PD.project_id == pid)).all()
    assert len(rows) == 2, "old and new definition must both exist (I17 lineage)"


def test_update_all_fields(admin_token: str) -> None:
    pid = client.post("/projects", headers={"Authorization": f"Bearer {admin_token}"},
                      json={"name": "All"}).json()["project_id"]
    r = client.patch(f"/projects/{pid}", headers={"Authorization": f"Bearer {admin_token}"},
                     json={
                         "goal": "New", "repos": [{"url": "https://github.com/x"}],
                         "workspace": {"editor": "vscode"}, "environment": "UAT",
                         "execution_environments": ["UAT", "PROD"],
                         "model_policy": {"model": "claude-sonnet-4-6"},
                         "canonical_terms": ["invoice_id"], "constraints": ["GDPR"],
                         "unresolved_questions": ["Q?"], "assumptions": ["A."],
                         "domain_config": {"source_type": "csv",
                                           "destination_schema_ddl": "CREATE TABLE t (id INT);"},
                         "lexicon_scope": {"domain": "billing"},
                     })
    assert r.status_code == 200
    b = r.json()
    assert b["goal"] == "New"
    assert b["execution_environments"] == ["UAT", "PROD"]
    assert b["domain_config"]["source_type"] == "csv"
    assert b["lexicon_scope"]["domain"] == "billing"


def test_update_archived_project_returns_409(admin_token: str) -> None:
    pid = client.post("/projects", headers={"Authorization": f"Bearer {admin_token}"},
                      json={"name": "Locked"}).json()["project_id"]
    client.post(f"/projects/{pid}/archive", headers={"Authorization": f"Bearer {admin_token}"})
    r = client.patch(f"/projects/{pid}", headers={"Authorization": f"Bearer {admin_token}"},
                     json={"name": "Fail"})
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "project_archived"


def test_stakeholder_cannot_update_even_own_project(
        admin_token: str, stakeholder: tuple[str, str]) -> None:
    user_id, sh_token = stakeholder
    pid = client.post("/projects", headers={"Authorization": f"Bearer {admin_token}"},
                      json={"name": f"NoEdit-{uuid.uuid4().hex[:6]}"}).json()["project_id"]
    client.post(f"/projects/{pid}/members",
                headers={"Authorization": f"Bearer {admin_token}"},
                json={"user_id": user_id})
    r = client.patch(f"/projects/{pid}", headers={"Authorization": f"Bearer {sh_token}"},
                     json={"name": "Blocked"})
    assert r.status_code == 403
```

- [ ] **Step 2: Run new tests — confirm they fail**

```bash
cd engine && python -m pytest tests/test_project_crud_api.py -k "get_project or update" -v 2>&1 | tail -20
```

Expected: failures — routes raise `NotImplementedError`.

- [ ] **Step 3: Implement `get_project_by_id` and `patch_project` in `routes/projects.py`**

Replace the two placeholder route bodies:

```python
@router.get("/{project_id}", response_model=ProjectResponse)
def get_project_by_id(
    project_id: str,
    actor: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ProjectResponse:
    require_project_access(db, user=actor, project_id=project_id)
    return get_project(db, project_id=project_id)


@router.patch("/{project_id}", response_model=ProjectResponse)
def patch_project(
    project_id: str,
    body: ProjectUpdateRequest,
    actor: User = Depends(get_central_team_user),
    db: Session = Depends(get_db),
) -> ProjectResponse:
    return update_project(db, actor=actor, project_id=project_id, body=body)
```

- [ ] **Step 4: Run get + update tests — confirm they pass**

```bash
cd engine && python -m pytest tests/test_project_crud_api.py -k "get_project or update" -v
```

Expected: all pass.

- [ ] **Step 5: Run full suite — no regressions**

```bash
cd engine && python -m pytest tests/ -v
```

Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add engine/src/migrations_engine/routes/projects.py \
        engine/tests/test_project_crud_api.py
git commit -m "feat: add project get and update routes with passing tests"
```

---

### Task 4c — Archive route + tests + full regression

- [ ] **Step 1: Add archive tests to `test_project_crud_api.py`**

Append to `engine/tests/test_project_crud_api.py`:

```python
# ── POST /projects/{id}/archive ───────────────────────────────────────────────

def test_archive_sets_status_and_archived_at(admin_token: str) -> None:
    pid = client.post("/projects", headers={"Authorization": f"Bearer {admin_token}"},
                      json={"name": "ToArchive"}).json()["project_id"]
    r = client.post(f"/projects/{pid}/archive",
                    headers={"Authorization": f"Bearer {admin_token}"})
    assert r.status_code == 200
    b = r.json()
    assert b["status"] == "archived"
    assert b["archived_at"] is not None


def test_double_archive_returns_409(admin_token: str) -> None:
    pid = client.post("/projects", headers={"Authorization": f"Bearer {admin_token}"},
                      json={"name": "Double"}).json()["project_id"]
    client.post(f"/projects/{pid}/archive", headers={"Authorization": f"Bearer {admin_token}"})
    r = client.post(f"/projects/{pid}/archive", headers={"Authorization": f"Bearer {admin_token}"})
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "project_already_archived"


def test_stakeholder_cannot_archive(admin_token: str, stakeholder: tuple[str, str]) -> None:
    _, sh_token = stakeholder
    pid = client.post("/projects", headers={"Authorization": f"Bearer {admin_token}"},
                      json={"name": f"NoArch-{uuid.uuid4().hex[:6]}"}).json()["project_id"]
    r = client.post(f"/projects/{pid}/archive",
                    headers={"Authorization": f"Bearer {sh_token}"})
    assert r.status_code == 403


def test_auditor_cannot_archive(admin_token: str, auditor_token: str) -> None:
    pid = client.post("/projects", headers={"Authorization": f"Bearer {admin_token}"},
                      json={"name": f"NoAuditArch-{uuid.uuid4().hex[:6]}"}).json()["project_id"]
    r = client.post(f"/projects/{pid}/archive",
                    headers={"Authorization": f"Bearer {auditor_token}"})
    assert r.status_code == 403
```

- [ ] **Step 2: Run archive tests — confirm they fail**

```bash
cd engine && python -m pytest tests/test_project_crud_api.py -k "archive" -v 2>&1 | tail -20
```

Expected: failures — route raises `NotImplementedError`.

- [ ] **Step 3: Implement `post_project_archive` in `routes/projects.py`**

Replace the placeholder:

```python
@router.post("/{project_id}/archive", response_model=ProjectResponse)
def post_project_archive(
    project_id: str,
    actor: User = Depends(get_central_team_user),
    db: Session = Depends(get_db),
) -> ProjectResponse:
    return archive_project(db, actor=actor, project_id=project_id)
```

- [ ] **Step 4: Run archive tests — confirm they pass**

```bash
cd engine && python -m pytest tests/test_project_crud_api.py -k "archive" -v
```

Expected: all pass.

- [ ] **Step 5: Run the complete test suite**

```bash
cd engine && python -m pytest tests/ -v
```

Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add engine/src/migrations_engine/routes/projects.py \
        engine/tests/test_project_crud_api.py
git commit -m "feat: add project archive route with passing tests"
```

---

### Task 5 — Document endpoints

**Files:** `docs/domain/api.md`

Already updated in the previous session. Verify and commit if not already done.

- [ ] **Step 1: Confirm project section exists**

```bash
grep -n "POST /projects" docs/domain/api.md
```

Expected: line found.

- [ ] **Step 2: Commit if unstaged**

```bash
git add docs/domain/api.md
git commit -m "docs: add project CRUD endpoint contract to api.md" 2>/dev/null || echo "already committed"
```

---

## Self-Review

**Task granularity:**
- Tasks 4a / 4b / 4c each have their own red → green → commit cycle ✓
- Each commit leaves the suite fully passing ✓
- No task mixes concerns from two endpoint groups ✓

**Architecture:**
- Access enforcement in `access.py` + `deps.py` only ✓
- Service layer has no role or membership checks ✓
- `require_project_access` called in route body for `GET /{id}` ✓
- Auto-membership (stakeholder business logic) and list scoping remain in service ✓

**Type consistency:**
- `require_project_access(db, user=actor, project_id=...)` — matches Task 2 signature ✓
- `get_project(db, project_id=project_id)` — no `actor` param ✓
- `list_projects(db, actor=actor, include_archived=...)` — actor for query scoping only ✓
