# Lookup Delta CR Review — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build three backend endpoints (list, get, resolve) for lookup delta change requests and a frontend review screen where a project stakeholder can map an unmapped lookup value and resume the paused run.

**Architecture:** A new `management/change_requests.py` service handles all domain logic — finding the CR, patching the LookupValueMap, minting a new approved LookupSnapshot, queuing the paused run, and closing the CR in a single transaction. A thin `routes/change_requests.py` router delegates to it. The frontend adds `lib/change-requests-api.ts` (three typed fetch helpers) and a single `"use client"` page at `/projects/[id]/change-requests/[crId]` that loads the CR detail, presents the mapping form, calls resolve, and redirects on success.

**Tech Stack:** FastAPI + SQLAlchemy (SQLite in tests), Pydantic v2, Next.js 15, React 19, Vitest 3 + Testing Library, Tailwind CSS 4.

## Global Constraints

- No new DB model or migration — all models (`ChangeRequest`, `LookupValueMap`, `LookupSnapshot`, `RunRecord`) already exist in `engine/src/migrations_engine/db/models.py`.
- Test imports: `from sqlite_test_support import Base, SessionLocal, TEST_ENGINE` — do not create a new in-memory engine.
- Auth pattern: `Depends(get_current_user)` — **never** `Depends(get_central_team_user)` for the resolve endpoint (must allow `project_stakeholder`).
- Pydantic response schemas go in `engine/src/migrations_engine/api/schemas.py`.
- TypeScript API helpers use `jsonRequest` from `web/lib/api-base.ts` with snake_case → camelCase mapping in a local helper function.
- Frontend tests use `vi.hoisted` + `vi.mock` for all module-level mocks; no real fetch calls.
- Error shape from backend: `{"error": {"code": "...", "message": "..."}}`.
- Backend resolve errors: `409 cr_not_open` (status != "open"), `409 cr_wrong_type` (type != "lookup_delta").
- `LookupValueMap.source_value_map` is a JSON column — always reassign the entire dict to trigger SQLAlchemy change tracking.

## Objective

Add lookup-delta change-request review endpoints and a project-scoped review page for listing, opening, and resolving lookup delta CRs.

## Out of Scope

- No new persistence model
- No changes to lookup value mapping approval flows
- No unrelated CR categories

## File Changes

- See the file map above for the exact backend and web files.

## Verification

- Run the new backend change-request review tests
- Run the new lookup-delta review page tests
- Run the relevant backend and web suites for CR review

## Pitfalls

- Keep review actions scoped to the current project
- Preserve read-only behavior on list/get routes
- Make sure resolved items disappear or update consistently in the UI

## Commit

- `feat(001ap): add lookup delta review flow`


---

## File Map

| File | Action | Purpose |
|---|---|---|
| `engine/src/migrations_engine/api/schemas.py` | Modify | Add `ChangeRequestSummary`, `ChangeRequestDetail`, `ChangeRequestResolveRequest`, `ChangeRequestResolveResponse` |
| `engine/src/migrations_engine/management/change_requests.py` | Create | Service: `list_change_requests`, `get_change_request`, `resolve_change_request` |
| `engine/src/migrations_engine/routes/change_requests.py` | Create | Router: GET list, GET detail, POST resolve |
| `engine/src/migrations_engine/app.py` | Modify | Register `change_requests_router` |
| `engine/tests/test_change_requests_api.py` | Create | Backend API tests |
| `web/lib/change-requests-api.ts` | Create | TS types + three fetch helpers |
| `web/lib/change-requests-api.test.ts` | Create | Unit tests for the three helpers |
| `web/app/projects/[id]/change-requests/[crId]/page.tsx` | Create | Review screen |
| `web/app/projects/[id]/change-requests/[crId]/page.test.tsx` | Create | Component test |

---

## Task 1: Backend — Schemas, Service, Routes, Tests

**Files:**
- Modify: `engine/src/migrations_engine/api/schemas.py`
- Create: `engine/src/migrations_engine/management/change_requests.py`
- Create: `engine/src/migrations_engine/routes/change_requests.py`
- Modify: `engine/src/migrations_engine/app.py`
- Create: `engine/tests/test_change_requests_api.py`

**Interfaces:**
- Produces:
  - `list_change_requests(db, *, project_id: str) -> list[ChangeRequestSummary]`
  - `get_change_request(db, *, project_id: str, change_request_id: str) -> ChangeRequestDetail`
  - `resolve_change_request(db, *, actor: User, project_id: str, change_request_id: str, accepted_value: str) -> ChangeRequestResolveResponse`
  - Routes: `GET /projects/{project_id}/change-requests`, `GET /projects/{project_id}/change-requests/{cr_id}`, `POST /projects/{project_id}/change-requests/{cr_id}/resolve`

---

- [ ] **Step 1: Write the failing tests**

Create `engine/tests/test_change_requests_api.py`:

```python
from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from sqlite_test_support import Base, SessionLocal, TEST_ENGINE
from migrations_engine.app import app
from migrations_engine.auth.passwords import hash_password
from migrations_engine.config import get_settings
from migrations_engine.db.models import (
    ChangeRequest,
    LookupSnapshot,
    LookupValueMap,
    ProjectDefinition,
    ProjectMembership,
    ProjectRegistry,
    RunRecord,
    SourceDefinition,
    User,
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
            db.add(
                User(
                    user_id=str(uuid.uuid4()),
                    email=settings.bootstrap_admin_email.strip().lower(),
                    display_name=settings.bootstrap_admin_display_name,
                    password_hash=hash_password(settings.bootstrap_admin_password),
                    role=CENTRAL_TEAM_ROLE,
                    status="active",
                )
            )
        if db.scalar(select(User).where(User.email == "cr-stakeholder@example.com")) is None:
            db.add(
                User(
                    user_id=str(uuid.uuid4()),
                    email="cr-stakeholder@example.com",
                    display_name="CR Stakeholder",
                    password_hash=hash_password("stakeholder-pass"),
                    role=PROJECT_STAKEHOLDER_ROLE,
                    status="active",
                )
            )
        db.commit()


@pytest.fixture(autouse=True)
def _clear_settings_cache() -> None:
    get_settings.cache_clear()


def _login(email: str, password: str) -> str:
    response = client.post("/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


@pytest.fixture
def admin_token() -> str:
    settings = get_settings()
    if not settings.bootstrap_admin_email or not settings.bootstrap_admin_password:
        pytest.skip("bootstrap credentials not configured")
    return _login(settings.bootstrap_admin_email, settings.bootstrap_admin_password)


@pytest.fixture
def stakeholder_token() -> str:
    return _login("cr-stakeholder@example.com", "stakeholder-pass")


def _seed_cr_scenario() -> dict[str, str]:
    """Returns ids for project, source_definition, run, lookup_value_map, open_cr."""
    project_id = str(uuid.uuid4())
    definition_id = str(uuid.uuid4())
    source_definition_id = str(uuid.uuid4())
    run_id = str(uuid.uuid4())
    lookup_value_map_id = str(uuid.uuid4())
    cr_id = str(uuid.uuid4())

    with SessionLocal() as db:
        stakeholder = db.scalar(select(User).where(User.email == "cr-stakeholder@example.com"))
        assert stakeholder is not None

        db.add(ProjectDefinition(definition_id=definition_id, project_id=project_id, name="CR Test", status="active"))
        db.add(ProjectRegistry(project_id=project_id, name="CR Test", definition_id=definition_id, status="active"))
        db.add(ProjectMembership(project_id=project_id, user_id=stakeholder.user_id))
        db.add(
            SourceDefinition(
                source_definition_id=source_definition_id,
                project_id=project_id,
                source_type="csv",
                source_contract_version="v1",
                destination_object_references=["customers"],
                status="active",
            )
        )
        db.add(
            RunRecord(
                run_id=run_id,
                project_id=project_id,
                destination_object_name="customers",
                source_definition_reference=source_definition_id,
                status="awaiting_approval",
                pause_metadata={
                    "pause_reason": "lookup_delta",
                    "change_request_id": cr_id,
                    "last_completed_row": 5,
                    "paused_at": datetime.now(UTC).isoformat(),
                },
            )
        )
        db.add(
            LookupValueMap(
                lookup_value_map_id=lookup_value_map_id,
                source_definition_id=source_definition_id,
                lookup_name="account_type",
                destination_table=[{"id": "ACTIVE"}, {"id": "CLOSED"}],
                source_value_map={"ACT": "ACTIVE", "CLS": "CLOSED"},
                status="draft",
            )
        )
        db.add(
            ChangeRequest(
                change_request_id=cr_id,
                project_id=project_id,
                change_request_type="lookup_delta",
                status="open",
                title="Lookup delta for account_type",
                payload={
                    "run_id": run_id,
                    "lookup_name": "account_type",
                    "unmapped_value": "RETD",
                    "destination_object_name": "customers",
                },
            )
        )
        db.commit()

    return {
        "project_id": project_id,
        "source_definition_id": source_definition_id,
        "run_id": run_id,
        "lookup_value_map_id": lookup_value_map_id,
        "cr_id": cr_id,
    }


def test_list_change_requests_requires_auth() -> None:
    ids = _seed_cr_scenario()
    response = client.get(f"/projects/{ids['project_id']}/change-requests")
    assert response.status_code == 401


def test_list_change_requests_returns_open_cr(admin_token: str) -> None:
    ids = _seed_cr_scenario()
    response = client.get(
        f"/projects/{ids['project_id']}/change-requests",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 1
    cr = next(item for item in data if item["change_request_id"] == ids["cr_id"])
    assert cr["change_request_type"] == "lookup_delta"
    assert cr["status"] == "open"
    assert cr["title"] == "Lookup delta for account_type"
    assert "payload" not in cr  # summary only


def test_get_change_request_returns_detail(admin_token: str) -> None:
    ids = _seed_cr_scenario()
    response = client.get(
        f"/projects/{ids['project_id']}/change-requests/{ids['cr_id']}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["change_request_id"] == ids["cr_id"]
    assert data["payload"]["run_id"] == ids["run_id"]
    assert data["payload"]["lookup_name"] == "account_type"
    assert data["payload"]["unmapped_value"] == "RETD"
    assert data["payload"]["destination_object_name"] == "customers"
    assert "updated_at" in data


def test_get_change_request_404_wrong_project(admin_token: str) -> None:
    ids = _seed_cr_scenario()
    wrong_project = str(uuid.uuid4())
    response = client.get(
        f"/projects/{wrong_project}/change-requests/{ids['cr_id']}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "change_request_not_found"


def test_resolve_requires_auth() -> None:
    ids = _seed_cr_scenario()
    response = client.post(
        f"/projects/{ids['project_id']}/change-requests/{ids['cr_id']}/resolve",
        json={"accepted_value": "RETIRED"},
    )
    assert response.status_code == 401


def test_resolve_forbidden_for_non_stakeholder(admin_token: str) -> None:
    ids = _seed_cr_scenario()
    # admin (central_team, not project_stakeholder) must be forbidden
    response = client.post(
        f"/projects/{ids['project_id']}/change-requests/{ids['cr_id']}/resolve",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"accepted_value": "RETIRED"},
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "forbidden"


def test_resolve_change_request_success(stakeholder_token: str) -> None:
    ids = _seed_cr_scenario()

    response = client.post(
        f"/projects/{ids['project_id']}/change-requests/{ids['cr_id']}/resolve",
        headers={"Authorization": f"Bearer {stakeholder_token}"},
        json={"accepted_value": "RETIRED"},
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["change_request_id"] == ids["cr_id"]
    assert data["status"] == "resolved"

    # Verify side-effects
    with SessionLocal() as db:
        cr = db.get(ChangeRequest, ids["cr_id"])
        assert cr is not None
        assert cr.status == "resolved"
        assert cr.closed_at is not None

        run = db.get(RunRecord, ids["run_id"])
        assert run is not None
        assert run.status == "queued"
        assert run.pause_metadata is None

        lvm = db.get(LookupValueMap, ids["lookup_value_map_id"])
        assert lvm is not None
        assert lvm.source_value_map.get("RETD") == "RETIRED"

        snapshot = db.scalar(
            select(LookupSnapshot)
            .where(
                LookupSnapshot.project_id == ids["project_id"],
                LookupSnapshot.lookup_name == "account_type",
            )
            .order_by(LookupSnapshot.created_at.desc())
        )
        assert snapshot is not None
        assert snapshot.status == "approved"
        assert snapshot.value_map.get("RETD") == "RETIRED"
        assert snapshot.approved_at is not None


def test_resolve_409_cr_not_open(stakeholder_token: str) -> None:
    ids = _seed_cr_scenario()
    # Resolve once (success)
    first = client.post(
        f"/projects/{ids['project_id']}/change-requests/{ids['cr_id']}/resolve",
        headers={"Authorization": f"Bearer {stakeholder_token}"},
        json={"accepted_value": "RETIRED"},
    )
    assert first.status_code == 200

    # Resolve again — should 409
    second = client.post(
        f"/projects/{ids['project_id']}/change-requests/{ids['cr_id']}/resolve",
        headers={"Authorization": f"Bearer {stakeholder_token}"},
        json={"accepted_value": "RETIRED"},
    )
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "cr_not_open"


def test_resolve_409_cr_wrong_type(stakeholder_token: str) -> None:
    project_id = str(uuid.uuid4())
    definition_id = str(uuid.uuid4())
    cr_id = str(uuid.uuid4())

    with SessionLocal() as db:
        stakeholder = db.scalar(select(User).where(User.email == "cr-stakeholder@example.com"))
        assert stakeholder is not None
        db.add(ProjectDefinition(definition_id=definition_id, project_id=project_id, name="Type Test", status="active"))
        db.add(ProjectRegistry(project_id=project_id, name="Type Test", definition_id=definition_id, status="active"))
        db.add(ProjectMembership(project_id=project_id, user_id=stakeholder.user_id))
        db.add(
            ChangeRequest(
                change_request_id=cr_id,
                project_id=project_id,
                change_request_type="other_type",
                status="open",
                title="Other CR",
                payload={},
            )
        )
        db.commit()

    response = client.post(
        f"/projects/{project_id}/change-requests/{cr_id}/resolve",
        headers={"Authorization": f"Bearer {stakeholder_token}"},
        json={"accepted_value": "RETIRED"},
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "cr_wrong_type"
```

- [ ] **Step 2: Run tests to confirm they fail (routes don't exist yet)**

```bash
cd /Users/vjkotra/projects/katana/engine && python -m pytest tests/test_change_requests_api.py -v 2>&1 | head -30
```

Expected: `ImportError` or `404` — routes not registered yet.

- [ ] **Step 3: Add Pydantic schemas to `api/schemas.py`**

Open `engine/src/migrations_engine/api/schemas.py` and add these four classes at the end of the file (before the final line):

```python
class ChangeRequestPayload(BaseModel):
    run_id: str
    lookup_name: str
    unmapped_value: str
    destination_object_name: str


class ChangeRequestSummary(BaseModel):
    change_request_id: str
    project_id: str
    change_request_type: str
    status: str
    title: str
    created_at: datetime


class ChangeRequestDetail(BaseModel):
    change_request_id: str
    project_id: str
    change_request_type: str
    status: str
    title: str
    payload: ChangeRequestPayload | None
    created_at: datetime
    updated_at: datetime


class ChangeRequestResolveRequest(BaseModel):
    accepted_value: str = Field(min_length=1, max_length=128)


class ChangeRequestResolveResponse(BaseModel):
    change_request_id: str
    status: Literal["resolved"]
```

- [ ] **Step 4: Run tests — still expect failure (service not created)**

```bash
cd /Users/vjkotra/projects/katana/engine && python -m pytest tests/test_change_requests_api.py::test_list_change_requests_requires_auth -v 2>&1 | head -20
```

Expected: `404` on the route (not 401) — the router is not registered yet.

- [ ] **Step 5: Create the service `management/change_requests.py`**

Create `engine/src/migrations_engine/management/change_requests.py`:

```python
from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..api.deps import AuthApiError
from ..api.schemas import (
    ChangeRequestDetail,
    ChangeRequestPayload,
    ChangeRequestResolveResponse,
    ChangeRequestSummary,
)
from ..db.models import ChangeRequest, LookupSnapshot, LookupValueMap, RunRecord, User, new_id
from ..mapping.constants import LOOKUP_DELTA_CHANGE_REQUEST_TYPE
from ..management.access import require_project_access
from ..management.platform import record_management_audit
from ..roles import PROJECT_STAKEHOLDER_ROLE

_SNAPSHOT_VERSION_RE = re.compile(r"^v(?P<number>\d+)$")


def list_change_requests(
    db: Session,
    *,
    project_id: str,
) -> list[ChangeRequestSummary]:
    rows = db.scalars(
        select(ChangeRequest)
        .where(ChangeRequest.project_id == project_id)
        .order_by(ChangeRequest.created_at.desc(), ChangeRequest.change_request_id.desc())
    ).all()
    return [_summary(cr) for cr in rows]


def get_change_request(
    db: Session,
    *,
    project_id: str,
    change_request_id: str,
) -> ChangeRequestDetail:
    cr = _get_cr(db, project_id=project_id, change_request_id=change_request_id)
    return _detail(cr)


def resolve_change_request(
    db: Session,
    *,
    actor: User,
    project_id: str,
    change_request_id: str,
    accepted_value: str,
) -> ChangeRequestResolveResponse:
    # Auth: only project_stakeholder role may resolve
    if actor.role != PROJECT_STAKEHOLDER_ROLE:
        raise AuthApiError("forbidden", "Only project stakeholders can resolve change requests.", 403)
    require_project_access(db, user=actor, project_id=project_id)

    cr = _get_cr(db, project_id=project_id, change_request_id=change_request_id)

    if cr.status != "open":
        raise AuthApiError("cr_not_open", "This change request is already closed.", 409)
    if cr.change_request_type != LOOKUP_DELTA_CHANGE_REQUEST_TYPE:
        raise AuthApiError("cr_wrong_type", "This change request is not a lookup delta CR.", 409)

    payload: dict[str, Any] = cr.payload or {}
    run_id: str = payload["run_id"]
    lookup_name: str = payload["lookup_name"]
    unmapped_value: str = payload["unmapped_value"]

    # 1. Update the LookupValueMap — add unmapped_value → accepted_value
    run = db.get(RunRecord, run_id)
    if run is None or run.project_id != project_id:
        raise AuthApiError("run_not_found", "Run record not found.", 404)

    source_definition_id: str | None = run.source_definition_reference
    if not source_definition_id:
        raise AuthApiError("source_not_found", "Run has no source definition reference.", 404)

    lookup_value_map = db.scalar(
        select(LookupValueMap)
        .where(
            LookupValueMap.source_definition_id == source_definition_id,
            LookupValueMap.lookup_name == lookup_name,
        )
        .order_by(LookupValueMap.created_at.desc(), LookupValueMap.lookup_value_map_id.desc())
    )
    if lookup_value_map is None:
        raise AuthApiError("lookup_map_not_found", "Lookup value map not found for this lookup.", 404)

    new_source_value_map = dict(lookup_value_map.source_value_map)
    new_source_value_map[unmapped_value] = accepted_value
    lookup_value_map.source_value_map = new_source_value_map

    # 2. Generate a new approved LookupSnapshot from the updated map
    new_version = _next_snapshot_version(db, project_id=project_id, lookup_name=lookup_name)
    snapshot = LookupSnapshot(
        lookup_snapshot_id=new_id(),
        project_id=project_id,
        lookup_name=lookup_name,
        lookup_snapshot_version=new_version,
        value_map=dict(new_source_value_map),
        status="approved",
        approved_at=datetime.now(UTC),
        approved_by_user_id=actor.user_id,
    )
    db.add(snapshot)

    # 3. Resume the paused RunRecord
    run.status = "queued"
    run.pause_metadata = None

    # 4. Close the ChangeRequest
    now = datetime.now(UTC)
    cr.status = "resolved"
    cr.closed_at = now

    record_management_audit(
        db,
        project_id=project_id,
        actor_user_id=actor.user_id,
        event_type="change_request.resolved",
        payload={
            "change_request_id": change_request_id,
            "lookup_name": lookup_name,
            "unmapped_value": unmapped_value,
            "accepted_value": accepted_value,
            "run_id": run_id,
            "lookup_snapshot_version": new_version,
        },
    )
    db.commit()

    return ChangeRequestResolveResponse(
        change_request_id=cr.change_request_id,
        status="resolved",
    )


# ── private helpers ──────────────────────────────────────────────────────────

def _get_cr(db: Session, *, project_id: str, change_request_id: str) -> ChangeRequest:
    cr = db.get(ChangeRequest, change_request_id)
    if cr is None or cr.project_id != project_id:
        raise AuthApiError("change_request_not_found", "Change request not found.", 404)
    return cr


def _next_snapshot_version(db: Session, *, project_id: str, lookup_name: str) -> str:
    versions = db.scalars(
        select(LookupSnapshot.lookup_snapshot_version).where(
            LookupSnapshot.project_id == project_id,
            LookupSnapshot.lookup_name == lookup_name,
        )
    ).all()
    highest = 0
    for version in versions:
        match = _SNAPSHOT_VERSION_RE.match(version)
        if match:
            highest = max(highest, int(match.group("number")))
    return f"v{highest + 1}"


def _summary(cr: ChangeRequest) -> ChangeRequestSummary:
    return ChangeRequestSummary(
        change_request_id=cr.change_request_id,
        project_id=cr.project_id,
        change_request_type=cr.change_request_type,
        status=cr.status,
        title=cr.title,
        created_at=cr.created_at,
    )


def _detail(cr: ChangeRequest) -> ChangeRequestDetail:
    raw_payload: dict[str, Any] | None = cr.payload
    parsed_payload: ChangeRequestPayload | None = None
    if raw_payload and cr.change_request_type == LOOKUP_DELTA_CHANGE_REQUEST_TYPE:
        parsed_payload = ChangeRequestPayload(
            run_id=str(raw_payload.get("run_id", "")),
            lookup_name=str(raw_payload.get("lookup_name", "")),
            unmapped_value=str(raw_payload.get("unmapped_value", "")),
            destination_object_name=str(raw_payload.get("destination_object_name", "")),
        )
    return ChangeRequestDetail(
        change_request_id=cr.change_request_id,
        project_id=cr.project_id,
        change_request_type=cr.change_request_type,
        status=cr.status,
        title=cr.title,
        payload=parsed_payload,
        created_at=cr.created_at,
        updated_at=cr.updated_at,
    )
```

- [ ] **Step 6: Create the router `routes/change_requests.py`**

Create `engine/src/migrations_engine/routes/change_requests.py`:

```python
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..api.deps import get_current_user, get_db
from ..api.schemas import (
    ChangeRequestDetail,
    ChangeRequestResolveRequest,
    ChangeRequestResolveResponse,
    ChangeRequestSummary,
)
from ..db.models import User
from ..management.access import require_project_access
from ..management.change_requests import (
    get_change_request,
    list_change_requests,
    resolve_change_request,
)

router = APIRouter(prefix="/projects", tags=["change-requests"])


@router.get("/{project_id}/change-requests", response_model=list[ChangeRequestSummary])
def get_change_requests(
    project_id: str,
    actor: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[ChangeRequestSummary]:
    require_project_access(db, user=actor, project_id=project_id)
    return list_change_requests(db, project_id=project_id)


@router.get("/{project_id}/change-requests/{cr_id}", response_model=ChangeRequestDetail)
def get_change_request_by_id(
    project_id: str,
    cr_id: str,
    actor: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ChangeRequestDetail:
    require_project_access(db, user=actor, project_id=project_id)
    return get_change_request(db, project_id=project_id, change_request_id=cr_id)


@router.post("/{project_id}/change-requests/{cr_id}/resolve", response_model=ChangeRequestResolveResponse)
def post_resolve_change_request(
    project_id: str,
    cr_id: str,
    body: ChangeRequestResolveRequest,
    actor: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ChangeRequestResolveResponse:
    return resolve_change_request(
        db,
        actor=actor,
        project_id=project_id,
        change_request_id=cr_id,
        accepted_value=body.accepted_value,
    )
```

- [ ] **Step 7: Register the router in `app.py`**

In `engine/src/migrations_engine/app.py`, add the import and `app.include_router` call:

```python
# Add to imports section (after existing route imports):
from .routes.change_requests import router as change_requests_router

# Add to include_router calls (after existing ones, before exception handlers):
app.include_router(change_requests_router)
```

The import block should look like:
```python
from .routes.change_requests import router as change_requests_router
```

And in the router registrations:
```python
app.include_router(users_router)
app.include_router(change_requests_router)
```

- [ ] **Step 8: Run the tests**

```bash
cd /Users/vjkotra/projects/katana/engine && python -m pytest tests/test_change_requests_api.py -v 2>&1
```

Expected: All 9 tests PASS.

- [ ] **Step 9: Commit**

```bash
git add \
  engine/src/migrations_engine/api/schemas.py \
  engine/src/migrations_engine/management/change_requests.py \
  engine/src/migrations_engine/routes/change_requests.py \
  engine/src/migrations_engine/app.py \
  engine/tests/test_change_requests_api.py
git commit -m "$(cat <<'EOF'
feat(001ap): add change request list/get/resolve endpoints

Three FastAPI endpoints under /projects/{id}/change-requests:
GET list, GET detail, POST resolve. Resolve patches the
LookupValueMap, mints an auto-approved LookupSnapshot, queues
the paused RunRecord, and closes the CR in one transaction.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: Frontend API Helpers

**Files:**
- Create: `web/lib/change-requests-api.ts`
- Create: `web/lib/change-requests-api.test.ts`

**Interfaces:**
- Consumes: `jsonRequest` from `web/lib/api-base.ts`
- Produces:
  - `interface ChangeRequestRecord` (camelCase shape used for detail view)
  - `interface ChangeRequestSummaryRecord` (camelCase shape for list view)
  - `listChangeRequests(token, projectId) -> Promise<ChangeRequestSummaryRecord[]>`
  - `getChangeRequest(token, projectId, crId) -> Promise<ChangeRequestRecord>`
  - `resolveChangeRequest(token, projectId, crId, { acceptedValue }) -> Promise<{ changeRequestId: string; status: "resolved" }>`

---

- [ ] **Step 1: Write the failing tests**

Create `web/lib/change-requests-api.test.ts`:

```typescript
import { afterEach, describe, expect, it, vi } from "vitest";
import {
  getChangeRequest,
  listChangeRequests,
  resolveChangeRequest,
  type ChangeRequestRecord,
  type ChangeRequestSummaryRecord,
} from "./change-requests-api";

const BASE = "http://127.0.0.1:8000";

const summaryResponse = {
  change_request_id: "cr-1",
  project_id: "project-1",
  change_request_type: "lookup_delta",
  status: "open",
  title: "Lookup delta for account_type",
  created_at: "2026-07-01T10:00:00Z",
};

const detailResponse = {
  change_request_id: "cr-1",
  project_id: "project-1",
  change_request_type: "lookup_delta",
  status: "open",
  title: "Lookup delta for account_type",
  payload: {
    run_id: "run-1",
    lookup_name: "account_type",
    unmapped_value: "RETD",
    destination_object_name: "customers",
  },
  created_at: "2026-07-01T10:00:00Z",
  updated_at: "2026-07-01T10:00:00Z",
};

afterEach(() => {
  vi.restoreAllMocks();
});

describe("listChangeRequests", () => {
  it("calls GET /projects/{id}/change-requests with auth headers and maps to camelCase", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => [summaryResponse],
    });
    vi.stubGlobal("fetch", fetchMock);

    const result = await listChangeRequests("token-1", "project-1");

    expect(fetchMock).toHaveBeenCalledWith(
      `${BASE}/projects/project-1/change-requests`,
      expect.objectContaining({
        method: "GET",
        headers: expect.objectContaining({ Authorization: "Bearer token-1" }),
      }),
    );

    const expected: ChangeRequestSummaryRecord = {
      changeRequestId: "cr-1",
      projectId: "project-1",
      changeRequestType: "lookup_delta",
      status: "open",
      title: "Lookup delta for account_type",
      createdAt: "2026-07-01T10:00:00Z",
    };
    expect(result).toEqual([expected]);
  });
});

describe("getChangeRequest", () => {
  it("calls GET /projects/{id}/change-requests/{crId} and maps payload to camelCase", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => detailResponse,
    });
    vi.stubGlobal("fetch", fetchMock);

    const result = await getChangeRequest("token-1", "project-1", "cr-1");

    expect(fetchMock).toHaveBeenCalledWith(
      `${BASE}/projects/project-1/change-requests/cr-1`,
      expect.objectContaining({ method: "GET" }),
    );

    const expected: ChangeRequestRecord = {
      changeRequestId: "cr-1",
      projectId: "project-1",
      changeRequestType: "lookup_delta",
      status: "open",
      title: "Lookup delta for account_type",
      payload: {
        runId: "run-1",
        lookupName: "account_type",
        unmappedValue: "RETD",
        destinationObjectName: "customers",
      },
      createdAt: "2026-07-01T10:00:00Z",
      updatedAt: "2026-07-01T10:00:00Z",
    };
    expect(result).toEqual(expected);
  });

  it("handles null payload gracefully", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ ...detailResponse, payload: null }),
    }));

    const result = await getChangeRequest("token-1", "project-1", "cr-1");
    expect(result.payload).toBeNull();
  });

  it("throws on 404 with error code", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      ok: false,
      status: 404,
      text: async () => JSON.stringify({ error: { code: "change_request_not_found", message: "Not found." } }),
    }));

    await expect(getChangeRequest("token-1", "project-1", "missing")).rejects.toThrow();
  });
});

describe("resolveChangeRequest", () => {
  it("posts accepted_value to /resolve and returns resolved status", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ change_request_id: "cr-1", status: "resolved" }),
    });
    vi.stubGlobal("fetch", fetchMock);

    const result = await resolveChangeRequest("token-1", "project-1", "cr-1", {
      acceptedValue: "RETIRED",
    });

    expect(fetchMock).toHaveBeenCalledWith(
      `${BASE}/projects/project-1/change-requests/cr-1/resolve`,
      expect.objectContaining({
        method: "POST",
        headers: expect.objectContaining({ Authorization: "Bearer token-1" }),
        body: JSON.stringify({ accepted_value: "RETIRED" }),
      }),
    );
    expect(result.changeRequestId).toBe("cr-1");
    expect(result.status).toBe("resolved");
  });

  it("throws on 409 cr_not_open", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      ok: false,
      status: 409,
      text: async () => JSON.stringify({ error: { code: "cr_not_open", message: "Already closed." } }),
    }));

    await expect(
      resolveChangeRequest("token-1", "project-1", "cr-1", { acceptedValue: "X" }),
    ).rejects.toThrow();
  });
});
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
cd /Users/vjkotra/projects/katana/web && npm test -- change-requests-api.test 2>&1 | head -20
```

Expected: `Cannot find module './change-requests-api'`.

- [ ] **Step 3: Create `web/lib/change-requests-api.ts`**

```typescript
import { API_BASE_URL } from "./api-base";

export type ChangeRequestStatus = "open" | "resolved" | "closed";
export type ChangeRequestType = "lookup_delta";

export interface ChangeRequestPayloadRecord {
  runId: string;
  lookupName: string;
  unmappedValue: string;
  destinationObjectName: string;
}

export interface ChangeRequestSummaryRecord {
  changeRequestId: string;
  projectId: string;
  changeRequestType: ChangeRequestType | string;
  status: ChangeRequestStatus | string;
  title: string;
  createdAt: string;
}

export interface ChangeRequestRecord extends ChangeRequestSummaryRecord {
  payload: ChangeRequestPayloadRecord | null;
  updatedAt: string;
}

export interface ChangeRequestResolveInput {
  acceptedValue: string;
}

export interface ChangeRequestResolveResult {
  changeRequestId: string;
  status: "resolved";
}

// ── raw API shapes ───────────────────────────────────────────────────────────

interface RawPayload {
  run_id: string;
  lookup_name: string;
  unmapped_value: string;
  destination_object_name: string;
}

interface RawSummary {
  change_request_id: string;
  project_id: string;
  change_request_type: string;
  status: string;
  title: string;
  created_at: string;
}

interface RawDetail extends RawSummary {
  payload: RawPayload | null;
  updated_at: string;
}

interface RawResolveResponse {
  change_request_id: string;
  status: "resolved";
}

// ── mappers ──────────────────────────────────────────────────────────────────

function mapSummary(raw: RawSummary): ChangeRequestSummaryRecord {
  return {
    changeRequestId: raw.change_request_id,
    projectId: raw.project_id,
    changeRequestType: raw.change_request_type,
    status: raw.status,
    title: raw.title,
    createdAt: raw.created_at,
  };
}

function mapPayload(raw: RawPayload | null): ChangeRequestPayloadRecord | null {
  if (!raw) return null;
  return {
    runId: raw.run_id,
    lookupName: raw.lookup_name,
    unmappedValue: raw.unmapped_value,
    destinationObjectName: raw.destination_object_name,
  };
}

function mapDetail(raw: RawDetail): ChangeRequestRecord {
  return {
    ...mapSummary(raw),
    payload: mapPayload(raw.payload),
    updatedAt: raw.updated_at,
  };
}

// ── request helper ───────────────────────────────────────────────────────────

async function apiRequest<T>(
  path: string,
  init: RequestInit & { token: string },
): Promise<T> {
  const { token, headers, ...rest } = init;
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...rest,
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
      ...(headers ?? {}),
    },
  });

  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `HTTP ${response.status}`);
  }

  return (await response.json()) as T;
}

// ── public API ───────────────────────────────────────────────────────────────

export async function listChangeRequests(
  token: string,
  projectId: string,
): Promise<ChangeRequestSummaryRecord[]> {
  const response = await apiRequest<RawSummary[]>(
    `/projects/${projectId}/change-requests`,
    { method: "GET", token },
  );
  return response.map(mapSummary);
}

export async function getChangeRequest(
  token: string,
  projectId: string,
  crId: string,
): Promise<ChangeRequestRecord> {
  const response = await apiRequest<RawDetail>(
    `/projects/${projectId}/change-requests/${crId}`,
    { method: "GET", token },
  );
  return mapDetail(response);
}

export async function resolveChangeRequest(
  token: string,
  projectId: string,
  crId: string,
  input: ChangeRequestResolveInput,
): Promise<ChangeRequestResolveResult> {
  const response = await apiRequest<RawResolveResponse>(
    `/projects/${projectId}/change-requests/${crId}/resolve`,
    {
      method: "POST",
      token,
      body: JSON.stringify({ accepted_value: input.acceptedValue }),
    },
  );
  return {
    changeRequestId: response.change_request_id,
    status: response.status,
  };
}
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
cd /Users/vjkotra/projects/katana/web && npm test -- change-requests-api.test 2>&1
```

Expected: All 6 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add web/lib/change-requests-api.ts web/lib/change-requests-api.test.ts
git commit -m "$(cat <<'EOF'
feat(001ap): add change-requests-api TypeScript helpers

Three typed fetch helpers (list, get, resolve) with snake_case
to camelCase mapping for the change request API endpoints.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: Review Page Component

**Files:**
- Create: `web/app/projects/[id]/change-requests/[crId]/page.tsx`
- Create: `web/app/projects/[id]/change-requests/[crId]/page.test.tsx`

**Interfaces:**
- Consumes:
  - `getChangeRequest(token, projectId, crId) -> Promise<ChangeRequestRecord>` from `web/lib/change-requests-api.ts`
  - `resolveChangeRequest(token, projectId, crId, { acceptedValue }) -> Promise<{ changeRequestId, status }>` from `web/lib/change-requests-api.ts`
  - `loadUiSession()` from `web/lib/session.ts`
  - `Topbar` from `web/components/Topbar.tsx`
  - `useRouter` from `next/navigation`

---

- [ ] **Step 1: Write the failing test**

Create `web/app/projects/[id]/change-requests/[crId]/page.test.tsx`:

```tsx
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import CrReviewPage from "./page";

const {
  getChangeRequestMock,
  resolveChangeRequestMock,
  loadUiSessionMock,
  pushMock,
  topbarMock,
} = vi.hoisted(() => ({
  getChangeRequestMock: vi.fn(),
  resolveChangeRequestMock: vi.fn(),
  loadUiSessionMock: vi.fn(),
  pushMock: vi.fn(),
  topbarMock: vi.fn(),
}));

vi.mock("../../../../../components/Topbar", () => ({
  Topbar: () => {
    topbarMock();
    return null;
  },
}));

vi.mock("../../../../../lib/session", () => ({
  loadUiSession: loadUiSessionMock,
}));

vi.mock("../../../../../lib/change-requests-api", () => ({
  getChangeRequest: getChangeRequestMock,
  resolveChangeRequest: resolveChangeRequestMock,
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: pushMock }),
}));

const session = {
  accessToken: "token-1",
  expiresAt: "2026-07-02T00:00:00Z",
  role: "project_stakeholder",
  sessionVersion: 1,
  userId: "user-1",
};

const crDetail = {
  changeRequestId: "cr-1",
  projectId: "project-1",
  changeRequestType: "lookup_delta",
  status: "open",
  title: "Lookup delta for account_type",
  payload: {
    runId: "run-1",
    lookupName: "account_type",
    unmappedValue: "RETD",
    destinationObjectName: "customers",
  },
  createdAt: "2026-07-01T10:00:00Z",
  updatedAt: "2026-07-01T10:00:00Z",
};

describe("CrReviewPage", () => {
  it("renders CR detail fields after load", async () => {
    loadUiSessionMock.mockReturnValue(session);
    getChangeRequestMock.mockResolvedValue(crDetail);

    render(
      <CrReviewPage
        params={Promise.resolve({ id: "project-1", crId: "cr-1" })}
      />,
    );

    expect(await screen.findByText("account_type")).toBeInTheDocument();
    expect(screen.getByText("RETD")).toBeInTheDocument();
    expect(screen.getByText("customers")).toBeInTheDocument();
    expect(screen.getByText("run-1")).toBeInTheDocument();

    expect(getChangeRequestMock).toHaveBeenCalledWith("token-1", "project-1", "cr-1");
  });

  it("submits the accepted value and redirects to project overview on success", async () => {
    loadUiSessionMock.mockReturnValue(session);
    getChangeRequestMock.mockResolvedValue(crDetail);
    resolveChangeRequestMock.mockResolvedValue({
      changeRequestId: "cr-1",
      status: "resolved",
    });

    render(
      <CrReviewPage
        params={Promise.resolve({ id: "project-1", crId: "cr-1" })}
      />,
    );

    const input = await screen.findByLabelText("Map this to:");
    fireEvent.change(input, { target: { value: "RETIRED" } });

    fireEvent.click(screen.getByRole("button", { name: "Submit" }));

    await waitFor(() =>
      expect(resolveChangeRequestMock).toHaveBeenCalledWith(
        "token-1",
        "project-1",
        "cr-1",
        { acceptedValue: "RETIRED" },
      ),
    );

    expect(pushMock).toHaveBeenCalledWith("/projects/project-1");
  });

  it("shows an error alert when resolve fails", async () => {
    loadUiSessionMock.mockReturnValue(session);
    getChangeRequestMock.mockResolvedValue(crDetail);
    resolveChangeRequestMock.mockRejectedValue(new Error("Already closed."));

    render(
      <CrReviewPage
        params={Promise.resolve({ id: "project-1", crId: "cr-1" })}
      />,
    );

    const input = await screen.findByLabelText("Map this to:");
    fireEvent.change(input, { target: { value: "RETIRED" } });
    fireEvent.click(screen.getByRole("button", { name: "Submit" }));

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("Already closed.");
    expect(pushMock).not.toHaveBeenCalled();
  });

  it("shows a load error when getChangeRequest fails", async () => {
    loadUiSessionMock.mockReturnValue(session);
    getChangeRequestMock.mockRejectedValue(new Error("Not found."));

    render(
      <CrReviewPage
        params={Promise.resolve({ id: "project-1", crId: "cr-1" })}
      />,
    );

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("Not found.");
  });

  it("disables submit while submitting", async () => {
    loadUiSessionMock.mockReturnValue(session);
    getChangeRequestMock.mockResolvedValue(crDetail);
    let resolvePromise!: (v: unknown) => void;
    resolveChangeRequestMock.mockReturnValue(
      new Promise((res) => {
        resolvePromise = res;
      }),
    );

    render(
      <CrReviewPage
        params={Promise.resolve({ id: "project-1", crId: "cr-1" })}
      />,
    );

    const input = await screen.findByLabelText("Map this to:");
    fireEvent.change(input, { target: { value: "RETIRED" } });
    fireEvent.click(screen.getByRole("button", { name: "Submit" }));

    expect(screen.getByRole("button", { name: "Submit" })).toBeDisabled();

    resolvePromise({ changeRequestId: "cr-1", status: "resolved" });
    await waitFor(() => expect(pushMock).toHaveBeenCalled());
  });
});
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
cd /Users/vjkotra/projects/katana/web && npm test -- "change-requests/\[crId\]/page.test" 2>&1 | head -20
```

Expected: `Cannot find module './page'`.

- [ ] **Step 3: Create the page component**

Create `web/app/projects/[id]/change-requests/[crId]/page.tsx`:

```tsx
"use client";

import { use, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Topbar } from "../../../../../components/Topbar";
import {
  getChangeRequest,
  resolveChangeRequest,
  type ChangeRequestRecord,
} from "../../../../../lib/change-requests-api";
import { loadUiSession, type SessionRole, type UiSession } from "../../../../../lib/session";

export default function CrReviewPage({
  params,
}: {
  params: Promise<{ id: string; crId: string }>;
}) {
  const router = useRouter();
  const { id: projectId, crId } = use(params);

  const [session, setSession] = useState<UiSession | null>(null);
  const [cr, setCr] = useState<ChangeRequestRecord | null>(null);
  const [acceptedValue, setAcceptedValue] = useState("");
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

  useEffect(() => {
    setSession(loadUiSession());
  }, []);

  useEffect(() => {
    if (!session) {
      setLoading(false);
      return;
    }

    let active = true;
    setLoading(true);
    setLoadError(null);

    void getChangeRequest(session.accessToken, projectId, crId)
      .then((response) => {
        if (active) {
          setCr(response);
        }
      })
      .catch((error: unknown) => {
        if (active) {
          setLoadError(error instanceof Error ? error.message : "Unable to load change request.");
        }
      })
      .finally(() => {
        if (active) {
          setLoading(false);
        }
      });

    return () => {
      active = false;
    };
  }, [projectId, crId, session]);

  const handleSubmit = async () => {
    if (!session || !acceptedValue.trim()) return;

    setSubmitting(true);
    setSubmitError(null);

    try {
      await resolveChangeRequest(session.accessToken, projectId, crId, {
        acceptedValue: acceptedValue.trim(),
      });
      router.push(`/projects/${projectId}`);
    } catch (error: unknown) {
      setSubmitError(error instanceof Error ? error.message : "Unable to resolve change request.");
    } finally {
      setSubmitting(false);
    }
  };

  const role: SessionRole = session?.role ?? "read_only_auditor";
  const payload = cr?.payload ?? null;

  return (
    <main className="flex min-h-screen flex-col bg-surface text-slate-800">
      <Topbar role={role} />
      <section className="mx-auto flex w-full max-w-[900px] flex-1 flex-col gap-4 px-6 py-6">
        <div className="flex items-center justify-between">
          <button
            className="rounded-md border border-outline-variant bg-surface-container px-3 py-2 text-sm font-medium text-slate-700 hover:bg-outline-variant"
            onClick={() => router.push(`/projects/${projectId}`)}
            type="button"
          >
            Back to project
          </button>
        </div>

        {loading ? (
          <div className="rounded-2xl border border-outline-variant bg-surface-container p-8 text-sm text-slate-600">
            Loading change request...
          </div>
        ) : loadError ? (
          <div
            role="alert"
            className="rounded-2xl border border-error/30 bg-error/10 px-4 py-3 text-sm text-error"
          >
            {loadError}
          </div>
        ) : cr ? (
          <div className="space-y-6 rounded-2xl border border-outline-variant bg-surface-container p-6 shadow-sm">
            <div className="space-y-1">
              <h1 className="text-2xl font-semibold text-slate-900">{cr.title}</h1>
              <p className="text-sm text-slate-500">Change request ID: {cr.changeRequestId}</p>
            </div>

            <div className="grid gap-3 sm:grid-cols-2">
              <div className="rounded-xl border border-outline-variant bg-surface px-4 py-3">
                <div className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">
                  Destination object
                </div>
                <div className="mt-1 text-sm text-slate-900">{payload?.destinationObjectName ?? "—"}</div>
              </div>
              <div className="rounded-xl border border-outline-variant bg-surface px-4 py-3">
                <div className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">
                  Run ID
                </div>
                <div className="mt-1 font-mono text-sm text-slate-900">{payload?.runId ?? "—"}</div>
              </div>
              <div className="rounded-xl border border-outline-variant bg-surface px-4 py-3">
                <div className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">
                  Lookup name (source column)
                </div>
                <div className="mt-1 text-sm text-slate-900">{payload?.lookupName ?? "—"}</div>
              </div>
              <div className="rounded-xl border border-outline-variant bg-surface px-4 py-3">
                <div className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">
                  Unmapped value found
                </div>
                <div className="mt-1 font-mono text-sm font-semibold text-rose-700">
                  {payload?.unmappedValue ?? "—"}
                </div>
              </div>
            </div>

            <div className="space-y-2">
              <label
                className="block text-sm font-semibold text-slate-900"
                htmlFor="accepted-value"
              >
                Map this to:
              </label>
              <input
                className="w-full rounded-md border border-outline-variant bg-white px-3 py-2 text-sm text-slate-900 focus:outline-none focus:ring-2 focus:ring-primary/40"
                id="accepted-value"
                onChange={(e) => setAcceptedValue(e.currentTarget.value)}
                placeholder="e.g. RETIRED"
                type="text"
                value={acceptedValue}
              />
            </div>

            {submitError ? (
              <div
                role="alert"
                className="rounded-xl border border-error/30 bg-error/10 px-4 py-3 text-sm text-error"
              >
                {submitError}
              </div>
            ) : null}

            <div className="flex gap-3">
              <button
                className="rounded-md bg-primary px-4 py-2 text-sm font-semibold text-white disabled:opacity-60"
                disabled={submitting || !acceptedValue.trim()}
                onClick={() => void handleSubmit()}
                type="button"
              >
                Submit
              </button>
            </div>
          </div>
        ) : null}
      </section>
    </main>
  );
}
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
cd /Users/vjkotra/projects/katana/web && npm test -- "change-requests/\[crId\]/page.test" 2>&1
```

Expected: All 5 tests PASS.

- [ ] **Step 5: Run the full frontend test suite to ensure no regressions**

```bash
cd /Users/vjkotra/projects/katana/web && npm test 2>&1 | tail -20
```

Expected: All tests PASS (no new failures).

- [ ] **Step 6: Commit**

```bash
git add \
  "web/app/projects/[id]/change-requests/[crId]/page.tsx" \
  "web/app/projects/[id]/change-requests/[crId]/page.test.tsx"
git commit -m "$(cat <<'EOF'
feat(001ap): add lookup delta CR review screen

Client page at /projects/[id]/change-requests/[crId] loads the
change request detail, shows the unmapped value and run context,
accepts the resolved mapping value, calls POST /resolve, and
redirects to the project overview on success.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
EOF
)"
```

---

## Self-Review

**Spec coverage check:**

| Requirement | Covered by |
|---|---|
| `GET /projects/{id}/change-requests` → list | Task 1 route + service + test |
| `GET /projects/{id}/change-requests/{cr_id}` → detail, 404 on wrong project | Task 1 route + service + test |
| `POST .../resolve` → stakeholder + project member | Task 1 service `require_project_access` + role check + test |
| 409 `cr_not_open` | Task 1 service + test |
| 409 `cr_wrong_type` | Task 1 service + test |
| Add unmapped_value → accepted_value to LookupValueMap | Task 1 service step 1 + test side-effect verify |
| Generate new LookupSnapshot from updated map | Task 1 service step 2 + test side-effect verify |
| Auto-approve the new LookupSnapshot | Task 1 service — snapshot created with `status="approved"` + test |
| Resume RunRecord: status="queued", clear pause_metadata | Task 1 service step 3 + test side-effect verify |
| Close ChangeRequest: status="resolved", closed_at=now | Task 1 service step 4 + test side-effect verify |
| ChangeRequestSummary shape (no payload) | Task 1 schema + test asserts `"payload" not in cr` |
| ChangeRequestDetail shape (with payload) | Task 1 schema + test |
| Resolve response shape `{change_request_id, status}` | Task 1 schema |
| `web/lib/change-requests-api.ts` — 3 helpers + type | Task 2 |
| UI route `/projects/[id]/change-requests/[crId]` | Task 3 |
| Shows destination_object_name, run_id, lookup_name, unmapped_value | Task 3 page + test |
| Single input "Map this to:" | Task 3 page + test asserts `getByLabelText("Map this to:")` |
| Submit → resolve → redirect to project overview | Task 3 page + test |
| Error display on resolve failure | Task 3 page + test |
| Submit button disabled while submitting | Task 3 page + test |

**Placeholder scan:** No TBD, TODO, or "similar to" references found. All code blocks are complete.

**Type consistency check:**
- `ChangeRequestRecord` (camelCase) used consistently across Task 2 and Task 3.
- `ChangeRequestResolveInput.acceptedValue` → serialized to `accepted_value` in Task 2 → `body.accepted_value` in Task 1 route → `accepted_value: str` in `ChangeRequestResolveRequest` schema. Consistent.
- `ChangeRequestResolveResponse.status: Literal["resolved"]` in Task 1 schema → `result.status === "resolved"` in Task 2 test. Consistent.
- Backend: `list_change_requests` → `list[ChangeRequestSummary]`. Router response_model `list[ChangeRequestSummary]`. Consistent.
- Task 3 mock path `../../../../../lib/change-requests-api` — page is at `web/app/projects/[id]/change-requests/[crId]/page.tsx`, lib is at `web/lib/`. Five `../` levels: `[crId]` → `change-requests` → `[id]` → `projects` → `app` → `web`, then `lib/`. Correct.
- Task 3 mock path `../../../../../components/Topbar` — same depth, correct.
