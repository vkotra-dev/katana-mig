# 001an: Fiber 3-Step Approval Chain

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add three approval-chain endpoints (`/assign`, `/approve`, `/trigger`) to the existing fibers router and wire them up with a fiber detail page in the frontend. These endpoints advance a `ProjectFiber` through the tail of its lifecycle: `mapped → operator_assigned → business_approved → operator_triggered`, with the trigger step checking whether all fibers for the same domain object are now triggered (and logging a codegen queue notice when they are).

**Architecture:** Adds `FiberActionRequest` to `api/schemas.py`. Adds three service functions to the existing `management/fibers.py`. Adds three routes to the existing `routes/fibers.py` (no new router file, no `app.py` change needed). Frontend: three new API helper functions appended to `web/lib/feeds-api.ts`, plus a new fiber detail page at `web/app/projects/[id]/feeds/[feedId]/fibers/[fiberId]/page.tsx`.

**Tech Stack:** FastAPI, SQLAlchemy 2, Pydantic v2, pytest, SQLite in-memory test DB; Next.js App Router, TypeScript, Vitest, React Testing Library.

**Prerequisites:** 001ak (ProjectFiber model + CRUD routes), 001aj (Feed rename, feeds-api.ts), 001al (lookup-inputs endpoint), 001am (analyze-feed endpoint) — all already implemented.

## Objective

Add the three-step fiber approval chain and the matching fiber detail page that lets operators assign, business users approve, and operators trigger codegen.

## Out of Scope

- No new fiber model definitions beyond the dependency tasks
- No bundle sequencing work
- No unrelated project detail tab changes

## File Changes

- See the blast radius table above for the exact backend and web files.

## Verification

- Run the new fiber approval API tests
- Run the new fiber detail page tests
- Run the touched backend and web suites

## Pitfalls

- Keep the state transitions strictly ordered
- Preserve role-based access at each step of the chain
- Do not collapse the three-step chain into a single approval action

## Commit

- `feat(001an): add fiber approval chain`


---

## Global Constraints

- Never import from `sources_api`; import from `feeds-api.ts` (post-001aj rename).
- `FiberActionRequest.comment` is optional (`str | None = None`); body itself is optional (send `{}`).
- Approval guard pattern: raise `AuthApiError("fiber_not_ready", "Fiber is not in the expected state.", 409)` when status mismatch.
- `trigger_fiber` queues codegen with a log statement only: `logger.info("codegen queued for %s", fiber.fiber_key)` — actual codegen wiring is 001aq.
- The "all fibers triggered" check counts fibers with `project_id == fiber.project_id AND fiber_key == fiber.fiber_key AND status != "operator_triggered"` after flushing the current transition to DB.
- `approve` endpoint uses `get_current_user` (not `get_central_team_user`); service enforces `actor.role == PROJECT_STAKEHOLDER_ROLE` and calls `require_project_access`.
- Route prefix is already `/projects/{project_id}/feeds/{feed_id}/fibers`; new routes append `/{fiber_id}/assign`, `/{fiber_id}/approve`, `/{fiber_id}/trigger`.
- All engine tests must pass before committing each task.
- All web tests must pass before committing Task 2 and Task 3.

---

## Blast Radius

| File | Change |
|---|---|
| `engine/src/migrations_engine/api/schemas.py` | Add `FiberActionRequest` |
| `engine/src/migrations_engine/management/fibers.py` | Add `_require_fiber`, `assign_fiber`, `approve_fiber`, `trigger_fiber` |
| `engine/src/migrations_engine/routes/fibers.py` | Add 3 POST routes: assign, approve, trigger |
| `engine/tests/test_fiber_approval_api.py` | Create — service + route tests |
| `web/lib/feeds-api.ts` | Add `FiberRecord` type + `getFiber` + `assignFiber` + `approveFiber` + `triggerFiber` |
| `web/lib/feeds-api.test.ts` | Add tests for the 4 new fiber helpers |
| `web/app/projects/[id]/feeds/[feedId]/fibers/[fiberId]/page.tsx` | Create — fiber detail + approval action UI |
| `web/app/projects/[id]/feeds/[feedId]/fibers/[fiberId]/page.test.tsx` | Create — component tests |

---

## Task 1: Backend — Schema + Service Functions + Routes + Tests

**Files:**
- Modify: `engine/src/migrations_engine/api/schemas.py`
- Modify: `engine/src/migrations_engine/management/fibers.py`
- Modify: `engine/src/migrations_engine/routes/fibers.py`
- Create: `engine/tests/test_fiber_approval_api.py`

**Interfaces:**
- Consumes: `ProjectFiber` from `db.models`; `FiberResponse` from `api.schemas`; `require_project_access`, `require_central_team` from `management.access`; `AuthApiError` from `api.deps`
- Produces:
  - `FiberActionRequest` — Pydantic body with `comment: str | None = None`
  - `assign_fiber(db, *, actor, project_id, feed_id, fiber_id, body) -> FiberResponse`
  - `approve_fiber(db, *, actor, project_id, feed_id, fiber_id, body) -> FiberResponse`
  - `trigger_fiber(db, *, actor, project_id, feed_id, fiber_id, body) -> FiberResponse`
  - `POST /projects/{project_id}/feeds/{feed_id}/fibers/{fiber_id}/assign` → `FiberResponse` 200
  - `POST /projects/{project_id}/feeds/{feed_id}/fibers/{fiber_id}/approve` → `FiberResponse` 200
  - `POST /projects/{project_id}/feeds/{feed_id}/fibers/{fiber_id}/trigger` → `FiberResponse` 200

---

- [ ] **Step 1: Write the failing test file**

Create `engine/tests/test_fiber_approval_api.py`:

```python
from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

import sqlite_test_support  # noqa: F401 — patches db.session before app import

from migrations_engine.app import app
from migrations_engine.auth.passwords import hash_password
from migrations_engine.config import get_settings
from migrations_engine.db.models import (
    Feed,
    ProjectDefinition,
    ProjectFiber,
    ProjectMembership,
    ProjectRegistry,
    User,
)
from migrations_engine.db.session import SessionLocal
from migrations_engine.roles import CENTRAL_TEAM_ROLE, PROJECT_STAKEHOLDER_ROLE

client = TestClient(app)

_ADMIN_EMAIL = "admin-approval@example.com"
_ADMIN_PASSWORD = "admin-password-123"
_STAKEHOLDER_EMAIL = "stakeholder-approval@example.com"
_STAKEHOLDER_PASSWORD = "stakeholder-password-123"


@pytest.fixture(scope="module", autouse=True)
def _seed_users() -> None:
    from migrations_engine.db.base import Base
    from sqlite_test_support import TEST_ENGINE

    Base.metadata.create_all(bind=TEST_ENGINE)

    with SessionLocal() as db:
        if db.scalar(select(User).where(User.email == _ADMIN_EMAIL)) is None:
            db.add(
                User(
                    user_id=str(uuid.uuid4()),
                    email=_ADMIN_EMAIL,
                    display_name="Admin Approval",
                    password_hash=hash_password(_ADMIN_PASSWORD),
                    role=CENTRAL_TEAM_ROLE,
                    status="active",
                )
            )
        if db.scalar(select(User).where(User.email == _STAKEHOLDER_EMAIL)) is None:
            db.add(
                User(
                    user_id=str(uuid.uuid4()),
                    email=_STAKEHOLDER_EMAIL,
                    display_name="Stakeholder Approval",
                    password_hash=hash_password(_STAKEHOLDER_PASSWORD),
                    role=PROJECT_STAKEHOLDER_ROLE,
                    status="active",
                )
            )
        db.commit()


@pytest.fixture(autouse=True)
def _clear_settings_cache() -> None:
    get_settings.cache_clear()


def _login(email: str, password: str) -> str:
    r = client.post("/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


@pytest.fixture
def admin_token() -> str:
    return _login(_ADMIN_EMAIL, _ADMIN_PASSWORD)


@pytest.fixture
def stakeholder_token() -> str:
    return _login(_STAKEHOLDER_EMAIL, _STAKEHOLDER_PASSWORD)


def _make_project_and_feed() -> tuple[str, str]:
    """Returns (project_id, feed_id)."""
    project_id = str(uuid.uuid4())
    feed_id = str(uuid.uuid4())
    definition_id = str(uuid.uuid4())
    with SessionLocal() as db:
        db.add(
            ProjectDefinition(
                definition_id=definition_id,
                project_id=project_id,
                name=f"Approval Project {project_id[:8]}",
                status="active",
            )
        )
        db.add(
            ProjectRegistry(
                project_id=project_id,
                name=f"Approval Project {project_id[:8]}",
                definition_id=definition_id,
                status="active",
            )
        )
        db.add(
            Feed(
                source_definition_id=feed_id,
                project_id=project_id,
                source_type="csv",
                source_contract_version="v1",
                source_details={"label": "Test Feed", "encoding": "utf-8"},
                status="active",
            )
        )
        db.commit()
    return project_id, feed_id


def _seed_fiber(project_id: str, feed_id: str, status: str, fiber_key: str = "customer") -> str:
    """Seeds a ProjectFiber at the given status. Returns fiber_id."""
    fiber_id = str(uuid.uuid4())
    with SessionLocal() as db:
        db.add(
            ProjectFiber(
                fiber_id=fiber_id,
                feed_id=feed_id,
                project_id=project_id,
                fiber_type="domain_object",
                fiber_key=fiber_key,
                status=status,
                source="auto",
            )
        )
        db.commit()
    return fiber_id


def _add_stakeholder_membership(project_id: str) -> None:
    with SessionLocal() as db:
        stakeholder = db.scalar(select(User).where(User.email == _STAKEHOLDER_EMAIL))
        assert stakeholder is not None
        if db.scalar(
            select(ProjectMembership).where(
                ProjectMembership.project_id == project_id,
                ProjectMembership.user_id == stakeholder.user_id,
            )
        ) is None:
            db.add(ProjectMembership(project_id=project_id, user_id=stakeholder.user_id))
            db.commit()


# ---------------------------------------------------------------------------
# FiberActionRequest schema
# ---------------------------------------------------------------------------


def test_fiber_action_request_schema_has_optional_comment() -> None:
    from migrations_engine.api.schemas import FiberActionRequest

    req = FiberActionRequest()
    assert req.comment is None

    req_with = FiberActionRequest(comment="looks good")
    assert req_with.comment == "looks good"


# ---------------------------------------------------------------------------
# assign
# ---------------------------------------------------------------------------


def test_assign_transitions_mapped_to_operator_assigned(admin_token: str) -> None:
    project_id, feed_id = _make_project_and_feed()
    fiber_id = _seed_fiber(project_id, feed_id, status="mapped")

    r = client.post(
        f"/projects/{project_id}/feeds/{feed_id}/fibers/{fiber_id}/assign",
        json={},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "operator_assigned"
    assert body["fiber_id"] == fiber_id


def test_assign_with_comment(admin_token: str) -> None:
    project_id, feed_id = _make_project_and_feed()
    fiber_id = _seed_fiber(project_id, feed_id, status="mapped")

    r = client.post(
        f"/projects/{project_id}/feeds/{feed_id}/fibers/{fiber_id}/assign",
        json={"comment": "ready for business review"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "operator_assigned"


def test_assign_rejects_wrong_status(admin_token: str) -> None:
    project_id, feed_id = _make_project_and_feed()
    fiber_id = _seed_fiber(project_id, feed_id, status="created")

    r = client.post(
        f"/projects/{project_id}/feeds/{feed_id}/fibers/{fiber_id}/assign",
        json={},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 409, r.text
    assert r.json()["error"]["code"] == "fiber_not_ready"


def test_assign_requires_central_team(stakeholder_token: str) -> None:
    project_id, feed_id = _make_project_and_feed()
    fiber_id = _seed_fiber(project_id, feed_id, status="mapped")

    r = client.post(
        f"/projects/{project_id}/feeds/{feed_id}/fibers/{fiber_id}/assign",
        json={},
        headers={"Authorization": f"Bearer {stakeholder_token}"},
    )
    assert r.status_code == 403, r.text


def test_assign_requires_authentication() -> None:
    r = client.post(
        "/projects/p/feeds/f/fibers/x/assign",
        json={},
    )
    assert r.status_code == 401


def test_assign_returns_404_for_missing_fiber(admin_token: str) -> None:
    project_id, feed_id = _make_project_and_feed()

    r = client.post(
        f"/projects/{project_id}/feeds/{feed_id}/fibers/nonexistent/assign",
        json={},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# approve
# ---------------------------------------------------------------------------


def test_approve_transitions_operator_assigned_to_business_approved(stakeholder_token: str) -> None:
    project_id, feed_id = _make_project_and_feed()
    _add_stakeholder_membership(project_id)
    fiber_id = _seed_fiber(project_id, feed_id, status="operator_assigned")

    r = client.post(
        f"/projects/{project_id}/feeds/{feed_id}/fibers/{fiber_id}/approve",
        json={},
        headers={"Authorization": f"Bearer {stakeholder_token}"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "business_approved"
    assert body["fiber_id"] == fiber_id


def test_approve_with_comment(stakeholder_token: str) -> None:
    project_id, feed_id = _make_project_and_feed()
    _add_stakeholder_membership(project_id)
    fiber_id = _seed_fiber(project_id, feed_id, status="operator_assigned")

    r = client.post(
        f"/projects/{project_id}/feeds/{feed_id}/fibers/{fiber_id}/approve",
        json={"comment": "LGTM"},
        headers={"Authorization": f"Bearer {stakeholder_token}"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "business_approved"


def test_approve_rejects_wrong_status(stakeholder_token: str) -> None:
    project_id, feed_id = _make_project_and_feed()
    _add_stakeholder_membership(project_id)
    fiber_id = _seed_fiber(project_id, feed_id, status="mapped")

    r = client.post(
        f"/projects/{project_id}/feeds/{feed_id}/fibers/{fiber_id}/approve",
        json={},
        headers={"Authorization": f"Bearer {stakeholder_token}"},
    )
    assert r.status_code == 409, r.text
    assert r.json()["error"]["code"] == "fiber_not_ready"


def test_approve_requires_project_stakeholder_role(admin_token: str) -> None:
    project_id, feed_id = _make_project_and_feed()
    fiber_id = _seed_fiber(project_id, feed_id, status="operator_assigned")

    r = client.post(
        f"/projects/{project_id}/feeds/{feed_id}/fibers/{fiber_id}/approve",
        json={},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 403, r.text


def test_approve_requires_project_membership(stakeholder_token: str) -> None:
    """Stakeholder without membership gets 403."""
    project_id, feed_id = _make_project_and_feed()
    # No _add_stakeholder_membership call
    fiber_id = _seed_fiber(project_id, feed_id, status="operator_assigned")

    r = client.post(
        f"/projects/{project_id}/feeds/{feed_id}/fibers/{fiber_id}/approve",
        json={},
        headers={"Authorization": f"Bearer {stakeholder_token}"},
    )
    assert r.status_code == 403, r.text


def test_approve_requires_authentication() -> None:
    r = client.post("/projects/p/feeds/f/fibers/x/approve", json={})
    assert r.status_code == 401


# ---------------------------------------------------------------------------
# trigger
# ---------------------------------------------------------------------------


def test_trigger_transitions_business_approved_to_operator_triggered(admin_token: str) -> None:
    project_id, feed_id = _make_project_and_feed()
    fiber_id = _seed_fiber(project_id, feed_id, status="business_approved")

    r = client.post(
        f"/projects/{project_id}/feeds/{feed_id}/fibers/{fiber_id}/trigger",
        json={},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "operator_triggered"
    assert body["fiber_id"] == fiber_id


def test_trigger_with_comment(admin_token: str) -> None:
    project_id, feed_id = _make_project_and_feed()
    fiber_id = _seed_fiber(project_id, feed_id, status="business_approved")

    r = client.post(
        f"/projects/{project_id}/feeds/{feed_id}/fibers/{fiber_id}/trigger",
        json={"comment": "initiating codegen"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "operator_triggered"


def test_trigger_rejects_wrong_status(admin_token: str) -> None:
    project_id, feed_id = _make_project_and_feed()
    fiber_id = _seed_fiber(project_id, feed_id, status="operator_assigned")

    r = client.post(
        f"/projects/{project_id}/feeds/{feed_id}/fibers/{fiber_id}/trigger",
        json={},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 409, r.text
    assert r.json()["error"]["code"] == "fiber_not_ready"


def test_trigger_requires_central_team(stakeholder_token: str) -> None:
    project_id, feed_id = _make_project_and_feed()
    fiber_id = _seed_fiber(project_id, feed_id, status="business_approved")

    r = client.post(
        f"/projects/{project_id}/feeds/{feed_id}/fibers/{fiber_id}/trigger",
        json={},
        headers={"Authorization": f"Bearer {stakeholder_token}"},
    )
    assert r.status_code == 403, r.text


def test_trigger_requires_authentication() -> None:
    r = client.post("/projects/p/feeds/f/fibers/x/trigger", json={})
    assert r.status_code == 401


def test_trigger_logs_codegen_queued_when_all_fibers_triggered(
    admin_token: str, caplog: pytest.LogCaptureFixture
) -> None:
    """When all fibers for the same project+fiber_key are operator_triggered after this call, a log line appears."""
    import logging

    project_id, feed_id = _make_project_and_feed()
    fiber_a = _seed_fiber(project_id, feed_id, status="business_approved", fiber_key="invoice")
    fiber_b = _seed_fiber(project_id, feed_id, status="operator_triggered", fiber_key="invoice")

    with caplog.at_level(logging.INFO, logger="migrations_engine.management.fibers"):
        r = client.post(
            f"/projects/{project_id}/feeds/{feed_id}/fibers/{fiber_a}/trigger",
            json={},
            headers={"Authorization": f"Bearer {admin_token}"},
        )

    assert r.status_code == 200, r.text
    assert r.json()["status"] == "operator_triggered"
    assert any("codegen queued for invoice" in record.message for record in caplog.records)


def test_trigger_does_not_log_codegen_when_sibling_fiber_not_triggered(
    admin_token: str, caplog: pytest.LogCaptureFixture
) -> None:
    """If a sibling fiber is still in business_approved, codegen is not queued."""
    import logging

    project_id, feed_id = _make_project_and_feed()
    fiber_a = _seed_fiber(project_id, feed_id, status="business_approved", fiber_key="order")
    _fiber_b = _seed_fiber(project_id, feed_id, status="business_approved", fiber_key="order")

    with caplog.at_level(logging.INFO, logger="migrations_engine.management.fibers"):
        r = client.post(
            f"/projects/{project_id}/feeds/{feed_id}/fibers/{fiber_a}/trigger",
            json={},
            headers={"Authorization": f"Bearer {admin_token}"},
        )

    assert r.status_code == 200, r.text
    assert not any("codegen queued" in record.message for record in caplog.records)


# ---------------------------------------------------------------------------
# Full happy-path chain
# ---------------------------------------------------------------------------


def test_full_approval_chain(admin_token: str, stakeholder_token: str) -> None:
    """mapped → operator_assigned → business_approved → operator_triggered."""
    project_id, feed_id = _make_project_and_feed()
    _add_stakeholder_membership(project_id)
    fiber_id = _seed_fiber(project_id, feed_id, status="mapped", fiber_key="payment")

    assign_r = client.post(
        f"/projects/{project_id}/feeds/{feed_id}/fibers/{fiber_id}/assign",
        json={},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert assign_r.status_code == 200
    assert assign_r.json()["status"] == "operator_assigned"

    approve_r = client.post(
        f"/projects/{project_id}/feeds/{feed_id}/fibers/{fiber_id}/approve",
        json={},
        headers={"Authorization": f"Bearer {stakeholder_token}"},
    )
    assert approve_r.status_code == 200
    assert approve_r.json()["status"] == "business_approved"

    trigger_r = client.post(
        f"/projects/{project_id}/feeds/{feed_id}/fibers/{fiber_id}/trigger",
        json={},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert trigger_r.status_code == 200
    assert trigger_r.json()["status"] == "operator_triggered"
```

---

- [ ] **Step 2: Run to verify tests fail**

```bash
cd /Users/vjkotra/projects/katana/engine/tests
python -m pytest test_fiber_approval_api.py -v 2>&1 | head -40
```

Expected: FAIL — `ImportError: cannot import name 'FiberActionRequest'` (schema missing) and routes returning 404.

---

- [ ] **Step 3: Add `FiberActionRequest` to `engine/src/migrations_engine/api/schemas.py`**

Append after the `LookupMappingPatchRequest` class (which was added in 001ak):

```python
class FiberActionRequest(BaseModel):
    comment: str | None = None
```

---

- [ ] **Step 4: Add service functions to `engine/src/migrations_engine/management/fibers.py`**

Add the following to the existing `management/fibers.py` (which already contains `create_fiber`, `list_fibers`, `get_fiber`, `_to_response`, `_require_feed`). Add imports and the four new symbols:

```python
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..api.deps import AuthApiError
from ..api.schemas import FiberActionRequest, FiberCreateRequest, FiberResponse
from ..db.models import Feed, ProjectFiber, User
from ..management.access import require_project_access
from ..roles import PROJECT_STAKEHOLDER_ROLE

logger = logging.getLogger(__name__)


# --- existing helpers (_to_response, _require_feed, create_fiber, list_fibers, get_fiber) ---
# (unchanged — shown here only for context)


def _require_fiber(
    db: Session,
    *,
    feed_id: str,
    fiber_id: str,
    project_id: str,
) -> ProjectFiber:
    """Fetches the ProjectFiber object, validating feed ownership."""
    _require_feed(db, feed_id=feed_id, project_id=project_id)
    fiber = db.scalars(
        select(ProjectFiber).where(
            ProjectFiber.fiber_id == fiber_id,
            ProjectFiber.feed_id == feed_id,
        )
    ).first()
    if fiber is None:
        raise AuthApiError("fiber_not_found", "Fiber not found.", 404)
    return fiber


def assign_fiber(
    db: Session,
    *,
    actor: User,
    project_id: str,
    feed_id: str,
    fiber_id: str,
    body: FiberActionRequest,
) -> FiberResponse:
    fiber = _require_fiber(db, feed_id=feed_id, fiber_id=fiber_id, project_id=project_id)
    if fiber.status != "mapped":
        raise AuthApiError("fiber_not_ready", "Fiber is not in the expected state.", 409)
    fiber.status = "operator_assigned"
    db.commit()
    db.refresh(fiber)
    return _to_response(fiber)


def approve_fiber(
    db: Session,
    *,
    actor: User,
    project_id: str,
    feed_id: str,
    fiber_id: str,
    body: FiberActionRequest,
) -> FiberResponse:
    require_project_access(db, user=actor, project_id=project_id)
    if actor.role != PROJECT_STAKEHOLDER_ROLE:
        raise AuthApiError(
            "forbidden",
            "Business approval requires project_stakeholder role.",
            403,
        )
    fiber = _require_fiber(db, feed_id=feed_id, fiber_id=fiber_id, project_id=project_id)
    if fiber.status != "operator_assigned":
        raise AuthApiError("fiber_not_ready", "Fiber is not in the expected state.", 409)
    fiber.status = "business_approved"
    db.commit()
    db.refresh(fiber)
    return _to_response(fiber)


def trigger_fiber(
    db: Session,
    *,
    actor: User,
    project_id: str,
    feed_id: str,
    fiber_id: str,
    body: FiberActionRequest,
) -> FiberResponse:
    fiber = _require_fiber(db, feed_id=feed_id, fiber_id=fiber_id, project_id=project_id)
    if fiber.status != "business_approved":
        raise AuthApiError("fiber_not_ready", "Fiber is not in the expected state.", 409)

    fiber_key = fiber.fiber_key
    fiber.status = "operator_triggered"
    db.flush()

    remaining = db.scalar(
        select(func.count(ProjectFiber.fiber_id)).where(
            ProjectFiber.project_id == project_id,
            ProjectFiber.fiber_key == fiber_key,
            ProjectFiber.status != "operator_triggered",
        )
    )
    should_queue = (remaining or 0) == 0

    db.commit()
    db.refresh(fiber)

    if should_queue:
        logger.info("codegen queued for %s", fiber_key)

    return _to_response(fiber)
```

Note: the full file after editing will look like the original `management/fibers.py` from 001ak, with these additions. The critical change to the existing top of the file is updating the import block to include `func`, `require_project_access`, and `PROJECT_STAKEHOLDER_ROLE`. The existing `_require_feed`, `_to_response`, `create_fiber`, `list_fibers`, and `get_fiber` functions remain unchanged.

The final import block for `management/fibers.py` must be:

```python
from __future__ import annotations

import logging

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..api.deps import AuthApiError
from ..api.schemas import FiberActionRequest, FiberCreateRequest, FiberResponse
from ..db.models import Feed, ProjectFiber, User
from ..management.access import require_project_access
from ..roles import PROJECT_STAKEHOLDER_ROLE

logger = logging.getLogger(__name__)
```

---

- [ ] **Step 5: Add three routes to `engine/src/migrations_engine/routes/fibers.py`**

The existing `routes/fibers.py` from 001ak has `post_fiber`, `get_fibers`, `get_fiber_by_id`. Append the following routes to the end of that file (update its imports to include `FiberActionRequest`, `assign_fiber`, `approve_fiber`, `trigger_fiber`):

Updated imports at the top of `routes/fibers.py`:

```python
from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from ..api.deps import get_central_team_user, get_current_user, get_db
from ..api.schemas import FiberActionRequest, FiberCreateRequest, FiberResponse
from ..db.models import User
from ..management.access import require_project_access
from ..management.fibers import (
    assign_fiber,
    approve_fiber,
    create_fiber,
    get_fiber,
    list_fibers,
    trigger_fiber,
)

router = APIRouter(
    prefix="/projects/{project_id}/feeds/{feed_id}/fibers",
    tags=["fibers"],
)
```

New routes to append after the existing GET endpoints:

```python
@router.post("/{fiber_id}/assign", response_model=FiberResponse)
def post_fiber_assign(
    project_id: str,
    feed_id: str,
    fiber_id: str,
    body: FiberActionRequest,
    actor: User = Depends(get_central_team_user),
    db: Session = Depends(get_db),
) -> FiberResponse:
    return assign_fiber(
        db,
        actor=actor,
        project_id=project_id,
        feed_id=feed_id,
        fiber_id=fiber_id,
        body=body,
    )


@router.post("/{fiber_id}/approve", response_model=FiberResponse)
def post_fiber_approve(
    project_id: str,
    feed_id: str,
    fiber_id: str,
    body: FiberActionRequest,
    actor: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FiberResponse:
    return approve_fiber(
        db,
        actor=actor,
        project_id=project_id,
        feed_id=feed_id,
        fiber_id=fiber_id,
        body=body,
    )


@router.post("/{fiber_id}/trigger", response_model=FiberResponse)
def post_fiber_trigger(
    project_id: str,
    feed_id: str,
    fiber_id: str,
    body: FiberActionRequest,
    actor: User = Depends(get_central_team_user),
    db: Session = Depends(get_db),
) -> FiberResponse:
    return trigger_fiber(
        db,
        actor=actor,
        project_id=project_id,
        feed_id=feed_id,
        fiber_id=fiber_id,
        body=body,
    )
```

---

- [ ] **Step 6: Run the approval test suite — all tests must pass**

```bash
cd /Users/vjkotra/projects/katana/engine/tests
python -m pytest test_fiber_approval_api.py -v
```

Expected: all tests GREEN. Verify each test name appears with `PASSED`.

---

- [ ] **Step 7: Run the full engine test suite**

```bash
cd /Users/vjkotra/projects/katana/engine/tests
python -m pytest -v
```

Expected: all tests PASS. Zero regressions.

---

- [ ] **Step 8: Commit**

```bash
git add engine/src/migrations_engine/api/schemas.py \
        engine/src/migrations_engine/management/fibers.py \
        engine/src/migrations_engine/routes/fibers.py \
        engine/tests/test_fiber_approval_api.py
git commit -m "feat(001an): add 3-step fiber approval chain (assign/approve/trigger)"
```

---

## Task 2: Frontend API Helpers + Tests

**Files:**
- Modify: `web/lib/feeds-api.ts`
- Modify: `web/lib/feeds-api.test.ts`

**Interfaces:**
- Consumes: existing `requestJson`, `parseApiError`, `API_BASE_URL` patterns in `feeds-api.ts`
- Produces:
  - `FiberRecord` — TypeScript interface for fiber API responses
  - `getFiber(token, projectId, feedId, fiberId) -> Promise<FiberRecord>`
  - `assignFiber(token, projectId, feedId, fiberId) -> Promise<FiberRecord>`
  - `approveFiber(token, projectId, feedId, fiberId) -> Promise<FiberRecord>`
  - `triggerFiber(token, projectId, feedId, fiberId) -> Promise<FiberRecord>`

---

- [ ] **Step 1: Write the failing tests**

Append to `web/lib/feeds-api.test.ts`:

```typescript
// --- Fiber approval chain tests ---

import {
  assignFiber,
  approveFiber,
  getFiber,
  triggerFiber,
  type FiberRecord,
} from "./feeds-api";

const BASE = "http://127.0.0.1:8000";

const fiberResponse = {
  fiber_id: "fiber-1",
  feed_id: "feed-1",
  project_id: "project-1",
  fiber_type: "domain_object",
  fiber_key: "customer",
  status: "mapped",
  source: "auto",
  proposed_mappings: null,
  field_bindings: [{ source_field: "cust_id", destination_field: "customer_id", lookup_name: null }],
  output_sql: null,
  created_at: "2026-07-01T00:00:00Z",
  updated_at: "2026-07-01T00:00:00Z",
};

const fiber: FiberRecord = {
  fiberId: "fiber-1",
  feedId: "feed-1",
  projectId: "project-1",
  fiberType: "domain_object",
  fiberKey: "customer",
  status: "mapped",
  source: "auto",
  proposedMappings: null,
  fieldBindings: [{ sourceField: "cust_id", destinationField: "customer_id", lookupName: null }],
  outputSql: null,
  createdAt: "2026-07-01T00:00:00Z",
  updatedAt: "2026-07-01T00:00:00Z",
};

describe("feeds-api fiber helpers", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("getFiber fetches and maps a fiber", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => fiberResponse,
    });
    vi.stubGlobal("fetch", fetchMock);

    const result = await getFiber("tok", "project-1", "feed-1", "fiber-1");

    expect(fetchMock).toHaveBeenCalledWith(
      `${BASE}/projects/project-1/feeds/feed-1/fibers/fiber-1`,
      expect.objectContaining({ method: "GET" }),
    );
    expect(result).toEqual(fiber);
  });

  it("assignFiber POSTs to /assign and maps response", async () => {
    const assigned = { ...fiberResponse, status: "operator_assigned" };
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => assigned,
    });
    vi.stubGlobal("fetch", fetchMock);

    const result = await assignFiber("tok", "project-1", "feed-1", "fiber-1");

    expect(fetchMock).toHaveBeenCalledWith(
      `${BASE}/projects/project-1/feeds/feed-1/fibers/fiber-1/assign`,
      expect.objectContaining({ method: "POST" }),
    );
    expect(result.status).toBe("operator_assigned");
  });

  it("approveFiber POSTs to /approve and maps response", async () => {
    const approved = { ...fiberResponse, status: "business_approved" };
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => approved,
    });
    vi.stubGlobal("fetch", fetchMock);

    const result = await approveFiber("tok", "project-1", "feed-1", "fiber-1");

    expect(fetchMock).toHaveBeenCalledWith(
      `${BASE}/projects/project-1/feeds/feed-1/fibers/fiber-1/approve`,
      expect.objectContaining({ method: "POST" }),
    );
    expect(result.status).toBe("business_approved");
  });

  it("triggerFiber POSTs to /trigger and maps response", async () => {
    const triggered = { ...fiberResponse, status: "operator_triggered" };
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => triggered,
    });
    vi.stubGlobal("fetch", fetchMock);

    const result = await triggerFiber("tok", "project-1", "feed-1", "fiber-1");

    expect(fetchMock).toHaveBeenCalledWith(
      `${BASE}/projects/project-1/feeds/feed-1/fibers/fiber-1/trigger`,
      expect.objectContaining({ method: "POST" }),
    );
    expect(result.status).toBe("operator_triggered");
  });

  it("getFiber throws a typed error on 404", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: false,
      status: 404,
      json: async () => ({ error: { code: "fiber_not_found", message: "Fiber not found." } }),
    });
    vi.stubGlobal("fetch", fetchMock);

    await expect(getFiber("tok", "p", "f", "missing")).rejects.toThrow();
  });

  it("assignFiber throws a typed error on 409", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: false,
      status: 409,
      json: async () => ({ error: { code: "fiber_not_ready", message: "Fiber is not in the expected state." } }),
    });
    vi.stubGlobal("fetch", fetchMock);

    await expect(assignFiber("tok", "p", "f", "fiber-1")).rejects.toThrow();
  });
});
```

---

- [ ] **Step 2: Run to verify tests fail**

```bash
cd /Users/vjkotra/projects/katana/web
npx vitest run feeds-api.test.ts 2>&1 | tail -20
```

Expected: FAIL — `getFiber`, `assignFiber`, `approveFiber`, `triggerFiber`, `FiberRecord` are not exported from `feeds-api.ts`.

---

- [ ] **Step 3: Add fiber types and helpers to `web/lib/feeds-api.ts`**

Append the following to the end of `web/lib/feeds-api.ts`. The file already contains `FeedRecord`, `FeedSliceRecord`, and related helpers from 001aj:

```typescript
// ---------------------------------------------------------------------------
// Fiber types
// ---------------------------------------------------------------------------

export interface FiberFieldBindingRecord {
  sourceField: string;
  destinationField: string;
  lookupName: string | null;
}

export interface FiberRecord {
  fiberId: string;
  feedId: string;
  projectId: string;
  fiberType: "lookup" | "domain_object";
  fiberKey: string;
  status: string;
  source: "auto" | "manual";
  proposedMappings: Array<Record<string, unknown>> | null;
  fieldBindings: Array<FiberFieldBindingRecord> | null;
  outputSql: string | null;
  createdAt: string;
  updatedAt: string;
}

// ---------------------------------------------------------------------------
// Raw API shape (snake_case from FastAPI)
// ---------------------------------------------------------------------------

type FiberRaw = {
  fiber_id: string;
  feed_id: string;
  project_id: string;
  fiber_type: "lookup" | "domain_object";
  fiber_key: string;
  status: string;
  source: "auto" | "manual";
  proposed_mappings: Array<Record<string, unknown>> | null;
  field_bindings: Array<{
    source_field: string;
    destination_field: string;
    lookup_name: string | null;
  }> | null;
  output_sql: string | null;
  created_at: string;
  updated_at: string;
};

function mapFiberResponse(raw: FiberRaw): FiberRecord {
  return {
    fiberId: raw.fiber_id,
    feedId: raw.feed_id,
    projectId: raw.project_id,
    fiberType: raw.fiber_type,
    fiberKey: raw.fiber_key,
    status: raw.status,
    source: raw.source,
    proposedMappings: raw.proposed_mappings,
    fieldBindings: raw.field_bindings
      ? raw.field_bindings.map((b) => ({
          sourceField: b.source_field,
          destinationField: b.destination_field,
          lookupName: b.lookup_name,
        }))
      : null,
    outputSql: raw.output_sql,
    createdAt: raw.created_at,
    updatedAt: raw.updated_at,
  };
}

// ---------------------------------------------------------------------------
// Fiber API helpers
// ---------------------------------------------------------------------------

export async function getFiber(
  token: string,
  projectId: string,
  feedId: string,
  fiberId: string,
): Promise<FiberRecord> {
  const response = await requestJson<FiberRaw>(
    `/projects/${projectId}/feeds/${feedId}/fibers/${fiberId}`,
    { method: "GET", token },
  );
  return mapFiberResponse(response);
}

export async function assignFiber(
  token: string,
  projectId: string,
  feedId: string,
  fiberId: string,
): Promise<FiberRecord> {
  const response = await requestJson<FiberRaw>(
    `/projects/${projectId}/feeds/${feedId}/fibers/${fiberId}/assign`,
    { method: "POST", token, body: JSON.stringify({}) },
  );
  return mapFiberResponse(response);
}

export async function approveFiber(
  token: string,
  projectId: string,
  feedId: string,
  fiberId: string,
): Promise<FiberRecord> {
  const response = await requestJson<FiberRaw>(
    `/projects/${projectId}/feeds/${feedId}/fibers/${fiberId}/approve`,
    { method: "POST", token, body: JSON.stringify({}) },
  );
  return mapFiberResponse(response);
}

export async function triggerFiber(
  token: string,
  projectId: string,
  feedId: string,
  fiberId: string,
): Promise<FiberRecord> {
  const response = await requestJson<FiberRaw>(
    `/projects/${projectId}/feeds/${feedId}/fibers/${fiberId}/trigger`,
    { method: "POST", token, body: JSON.stringify({}) },
  );
  return mapFiberResponse(response);
}
```

Note: `requestJson` and `parseApiError` are the private helpers that already exist in `feeds-api.ts` (carried over from `sources-api.ts` in 001aj). If `requestJson` is not already defined there (because sources-api.ts used a slightly different name), use whichever internal helper function already handles auth headers and JSON parsing in that file.

---

- [ ] **Step 4: Run the feeds-api tests — all must pass**

```bash
cd /Users/vjkotra/projects/katana/web
npx vitest run feeds-api.test.ts
```

Expected: all tests GREEN.

---

- [ ] **Step 5: Run the full web test suite**

```bash
cd /Users/vjkotra/projects/katana/web
npm test
```

Expected: all tests PASS. Zero regressions.

---

- [ ] **Step 6: Commit**

```bash
git add web/lib/feeds-api.ts \
        web/lib/feeds-api.test.ts
git commit -m "feat(001an): add getFiber + fiber approval API helpers to feeds-api.ts"
```

---

## Task 3: Fiber Detail Page + Tests

**Files:**
- Create: `web/app/projects/[id]/feeds/[feedId]/fibers/[fiberId]/page.tsx`
- Create: `web/app/projects/[id]/feeds/[feedId]/fibers/[fiberId]/page.test.tsx`

**Interfaces:**
- Consumes: `getFiber`, `assignFiber`, `approveFiber`, `triggerFiber`, `FiberRecord` from `feeds-api.ts`; `loadUiSession`, `UiSession`, `SessionRole` from `session.ts`; `Topbar` from `components/Topbar`; `useParams`, `useRouter` from `next/navigation`
- Route params: `{ id: string; feedId: string; fiberId: string }`
- Renders:
  - Fiber status badge
  - `field_bindings` table when `fiber_type === "domain_object"` and data is present
  - `proposed_mappings` JSON preview when `fiber_type === "lookup"` and data is present
  - "Assign for Review" button (central_team + status "mapped")
  - "Approve" button (project_stakeholder + status "operator_assigned")
  - "Trigger" button (central_team + status "business_approved")
  - Loading state while fetching
  - Error banner on failed load or action

---

- [ ] **Step 1: Write the failing test file**

Create `web/app/projects/[id]/feeds/[feedId]/fibers/[fiberId]/page.test.tsx`:

```typescript
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import FiberDetailPage from "./page";

const {
  getFiberMock,
  assignFiberMock,
  approveFiberMock,
  triggerFiberMock,
  loadUiSessionMock,
  topbarMock,
  backMock,
} = vi.hoisted(() => ({
  getFiberMock: vi.fn(),
  assignFiberMock: vi.fn(),
  approveFiberMock: vi.fn(),
  triggerFiberMock: vi.fn(),
  loadUiSessionMock: vi.fn(),
  topbarMock: vi.fn(),
  backMock: vi.fn(),
}));

vi.mock("../../../../../../components/Topbar", () => ({
  Topbar: () => {
    topbarMock();
    return null;
  },
}));

vi.mock("../../../../../../lib/session", () => ({
  loadUiSession: loadUiSessionMock,
}));

vi.mock("../../../../../../lib/feeds-api", () => ({
  getFiber: getFiberMock,
  assignFiber: assignFiberMock,
  approveFiber: approveFiberMock,
  triggerFiber: triggerFiberMock,
}));

vi.mock("next/navigation", () => ({
  useParams: () => ({ id: "project-1", feedId: "feed-1", fiberId: "fiber-1" }),
  useRouter: () => ({ back: backMock }),
}));

const SESSION_CENTRAL = {
  accessToken: "token-central",
  expiresAt: "2026-07-01T12:00:00Z",
  role: "central_team" as const,
  sessionVersion: 1,
  userId: "user-central",
};

const SESSION_STAKEHOLDER = {
  accessToken: "token-stakeholder",
  expiresAt: "2026-07-01T12:00:00Z",
  role: "project_stakeholder" as const,
  sessionVersion: 1,
  userId: "user-stakeholder",
};

const FIBER_MAPPED = {
  fiberId: "fiber-1",
  feedId: "feed-1",
  projectId: "project-1",
  fiberType: "domain_object" as const,
  fiberKey: "customer",
  status: "mapped",
  source: "auto" as const,
  proposedMappings: null,
  fieldBindings: [
    { sourceField: "cust_id", destinationField: "customer_id", lookupName: null },
    { sourceField: "cust_name", destinationField: "full_name", lookupName: null },
  ],
  outputSql: null,
  createdAt: "2026-07-01T00:00:00Z",
  updatedAt: "2026-07-01T00:00:00Z",
};

const FIBER_OPERATOR_ASSIGNED = { ...FIBER_MAPPED, status: "operator_assigned" };
const FIBER_BUSINESS_APPROVED = { ...FIBER_MAPPED, status: "business_approved" };
const FIBER_OPERATOR_TRIGGERED = { ...FIBER_MAPPED, status: "operator_triggered" };

const FIBER_LOOKUP_ASSIGNED = {
  ...FIBER_MAPPED,
  fiberType: "lookup" as const,
  fiberKey: "account_type",
  status: "operator_assigned",
  fieldBindings: null,
  proposedMappings: [{ sourceValue: "A", destValue: "Active" }],
};

beforeEach(() => {
  vi.resetAllMocks();
});

describe("FiberDetailPage", () => {
  it("shows loading state while fetching fiber", () => {
    loadUiSessionMock.mockReturnValue(SESSION_CENTRAL);
    getFiberMock.mockReturnValue(new Promise(() => {})); // never resolves

    render(<FiberDetailPage />);

    expect(screen.getByText(/loading/i)).toBeInTheDocument();
  });

  it("shows the fiber status badge after loading", async () => {
    loadUiSessionMock.mockReturnValue(SESSION_CENTRAL);
    getFiberMock.mockResolvedValue(FIBER_MAPPED);

    render(<FiberDetailPage />);

    expect(await screen.findByText("mapped")).toBeInTheDocument();
  });

  it("shows field_bindings table for domain_object fiber", async () => {
    loadUiSessionMock.mockReturnValue(SESSION_CENTRAL);
    getFiberMock.mockResolvedValue(FIBER_MAPPED);

    render(<FiberDetailPage />);

    expect(await screen.findByText("cust_id")).toBeInTheDocument();
    expect(screen.getByText("customer_id")).toBeInTheDocument();
    expect(screen.getByText("cust_name")).toBeInTheDocument();
    expect(screen.getByText("full_name")).toBeInTheDocument();
  });

  it("shows proposed_mappings for lookup fiber", async () => {
    loadUiSessionMock.mockReturnValue(SESSION_STAKEHOLDER);
    getFiberMock.mockResolvedValue(FIBER_LOOKUP_ASSIGNED);

    render(<FiberDetailPage />);

    expect(await screen.findByText(/proposed mappings/i)).toBeInTheDocument();
    expect(screen.getByText(/account_type/i)).toBeInTheDocument();
  });

  // ---------------------------------------------------------------------------
  // Assign (central_team + status=mapped)
  // ---------------------------------------------------------------------------

  it("shows Assign for Review button for central_team when status=mapped", async () => {
    loadUiSessionMock.mockReturnValue(SESSION_CENTRAL);
    getFiberMock.mockResolvedValue(FIBER_MAPPED);

    render(<FiberDetailPage />);

    expect(await screen.findByRole("button", { name: /assign for review/i })).toBeInTheDocument();
  });

  it("calls assignFiber on Assign click and updates status", async () => {
    loadUiSessionMock.mockReturnValue(SESSION_CENTRAL);
    getFiberMock.mockResolvedValue(FIBER_MAPPED);
    assignFiberMock.mockResolvedValue(FIBER_OPERATOR_ASSIGNED);

    render(<FiberDetailPage />);

    const btn = await screen.findByRole("button", { name: /assign for review/i });
    fireEvent.click(btn);

    await waitFor(() => {
      expect(assignFiberMock).toHaveBeenCalledWith("token-central", "project-1", "feed-1", "fiber-1");
    });
    expect(await screen.findByText("operator_assigned")).toBeInTheDocument();
  });

  it("does NOT show Assign button for project_stakeholder", async () => {
    loadUiSessionMock.mockReturnValue(SESSION_STAKEHOLDER);
    getFiberMock.mockResolvedValue(FIBER_MAPPED);

    render(<FiberDetailPage />);

    await screen.findByText("mapped"); // wait for load
    expect(screen.queryByRole("button", { name: /assign for review/i })).not.toBeInTheDocument();
  });

  it("does NOT show Assign button when status is not mapped", async () => {
    loadUiSessionMock.mockReturnValue(SESSION_CENTRAL);
    getFiberMock.mockResolvedValue(FIBER_OPERATOR_ASSIGNED);

    render(<FiberDetailPage />);

    await screen.findByText("operator_assigned");
    expect(screen.queryByRole("button", { name: /assign for review/i })).not.toBeInTheDocument();
  });

  // ---------------------------------------------------------------------------
  // Approve (project_stakeholder + status=operator_assigned)
  // ---------------------------------------------------------------------------

  it("shows Approve button for project_stakeholder when status=operator_assigned", async () => {
    loadUiSessionMock.mockReturnValue(SESSION_STAKEHOLDER);
    getFiberMock.mockResolvedValue(FIBER_OPERATOR_ASSIGNED);

    render(<FiberDetailPage />);

    expect(await screen.findByRole("button", { name: /^approve$/i })).toBeInTheDocument();
  });

  it("calls approveFiber on Approve click and updates status", async () => {
    loadUiSessionMock.mockReturnValue(SESSION_STAKEHOLDER);
    getFiberMock.mockResolvedValue(FIBER_OPERATOR_ASSIGNED);
    approveFiberMock.mockResolvedValue(FIBER_BUSINESS_APPROVED);

    render(<FiberDetailPage />);

    const btn = await screen.findByRole("button", { name: /^approve$/i });
    fireEvent.click(btn);

    await waitFor(() => {
      expect(approveFiberMock).toHaveBeenCalledWith(
        "token-stakeholder",
        "project-1",
        "feed-1",
        "fiber-1",
      );
    });
    expect(await screen.findByText("business_approved")).toBeInTheDocument();
  });

  it("does NOT show Approve button for central_team", async () => {
    loadUiSessionMock.mockReturnValue(SESSION_CENTRAL);
    getFiberMock.mockResolvedValue(FIBER_OPERATOR_ASSIGNED);

    render(<FiberDetailPage />);

    await screen.findByText("operator_assigned");
    expect(screen.queryByRole("button", { name: /^approve$/i })).not.toBeInTheDocument();
  });

  it("does NOT show Approve button when status is not operator_assigned", async () => {
    loadUiSessionMock.mockReturnValue(SESSION_STAKEHOLDER);
    getFiberMock.mockResolvedValue(FIBER_MAPPED);

    render(<FiberDetailPage />);

    await screen.findByText("mapped");
    expect(screen.queryByRole("button", { name: /^approve$/i })).not.toBeInTheDocument();
  });

  // ---------------------------------------------------------------------------
  // Trigger (central_team + status=business_approved)
  // ---------------------------------------------------------------------------

  it("shows Trigger button for central_team when status=business_approved", async () => {
    loadUiSessionMock.mockReturnValue(SESSION_CENTRAL);
    getFiberMock.mockResolvedValue(FIBER_BUSINESS_APPROVED);

    render(<FiberDetailPage />);

    expect(await screen.findByRole("button", { name: /^trigger$/i })).toBeInTheDocument();
  });

  it("calls triggerFiber on Trigger click and updates status", async () => {
    loadUiSessionMock.mockReturnValue(SESSION_CENTRAL);
    getFiberMock.mockResolvedValue(FIBER_BUSINESS_APPROVED);
    triggerFiberMock.mockResolvedValue(FIBER_OPERATOR_TRIGGERED);

    render(<FiberDetailPage />);

    const btn = await screen.findByRole("button", { name: /^trigger$/i });
    fireEvent.click(btn);

    await waitFor(() => {
      expect(triggerFiberMock).toHaveBeenCalledWith(
        "token-central",
        "project-1",
        "feed-1",
        "fiber-1",
      );
    });
    expect(await screen.findByText("operator_triggered")).toBeInTheDocument();
  });

  it("does NOT show Trigger button for project_stakeholder", async () => {
    loadUiSessionMock.mockReturnValue(SESSION_STAKEHOLDER);
    getFiberMock.mockResolvedValue(FIBER_BUSINESS_APPROVED);

    render(<FiberDetailPage />);

    await screen.findByText("business_approved");
    expect(screen.queryByRole("button", { name: /^trigger$/i })).not.toBeInTheDocument();
  });

  it("does NOT show Trigger button when status is not business_approved", async () => {
    loadUiSessionMock.mockReturnValue(SESSION_CENTRAL);
    getFiberMock.mockResolvedValue(FIBER_MAPPED);

    render(<FiberDetailPage />);

    await screen.findByText("mapped");
    expect(screen.queryByRole("button", { name: /^trigger$/i })).not.toBeInTheDocument();
  });

  // ---------------------------------------------------------------------------
  // Terminal state (operator_triggered — no action button)
  // ---------------------------------------------------------------------------

  it("shows no action button when status=operator_triggered", async () => {
    loadUiSessionMock.mockReturnValue(SESSION_CENTRAL);
    getFiberMock.mockResolvedValue(FIBER_OPERATOR_TRIGGERED);

    render(<FiberDetailPage />);

    await screen.findByText("operator_triggered");
    expect(screen.queryByRole("button", { name: /assign for review/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /^approve$/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /^trigger$/i })).not.toBeInTheDocument();
  });

  // ---------------------------------------------------------------------------
  // Error handling
  // ---------------------------------------------------------------------------

  it("shows error banner when fiber fetch fails", async () => {
    loadUiSessionMock.mockReturnValue(SESSION_CENTRAL);
    getFiberMock.mockRejectedValue(new Error("network error"));

    render(<FiberDetailPage />);

    expect(await screen.findByRole("alert")).toBeInTheDocument();
  });

  it("shows error banner when assign action fails", async () => {
    loadUiSessionMock.mockReturnValue(SESSION_CENTRAL);
    getFiberMock.mockResolvedValue(FIBER_MAPPED);
    assignFiberMock.mockRejectedValue(new Error("409: fiber_not_ready"));

    render(<FiberDetailPage />);

    const btn = await screen.findByRole("button", { name: /assign for review/i });
    fireEvent.click(btn);

    expect(await screen.findByRole("alert")).toBeInTheDocument();
  });

  it("disables action button while request is in-flight", async () => {
    loadUiSessionMock.mockReturnValue(SESSION_CENTRAL);
    getFiberMock.mockResolvedValue(FIBER_MAPPED);
    assignFiberMock.mockReturnValue(new Promise(() => {})); // never resolves

    render(<FiberDetailPage />);

    const btn = await screen.findByRole("button", { name: /assign for review/i });
    fireEvent.click(btn);

    await waitFor(() => {
      expect(screen.getByRole("button", { name: /assigning/i })).toBeDisabled();
    });
  });
});
```

---

- [ ] **Step 2: Run to verify tests fail**

```bash
cd /Users/vjkotra/projects/katana/web
npx vitest run "app/projects/\[id\]/feeds/\[feedId\]/fibers/\[fiberId\]/page.test.tsx" 2>&1 | tail -20
```

Expected: FAIL — module not found for `./page`.

---

- [ ] **Step 3: Create `web/app/projects/[id]/feeds/[feedId]/fibers/[fiberId]/page.tsx`**

First, ensure the directory exists:

```bash
mkdir -p "/Users/vjkotra/projects/katana/web/app/projects/[id]/feeds/[feedId]/fibers/[fiberId]"
```

Then create the file:

```typescript
"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { Topbar } from "../../../../../../components/Topbar";
import {
  assignFiber,
  approveFiber,
  getFiber,
  triggerFiber,
  type FiberRecord,
} from "../../../../../../lib/feeds-api";
import { loadUiSession, type SessionRole, type UiSession } from "../../../../../../lib/session";

function statusBadgeClass(status: string): string {
  if (status === "operator_triggered" || status === "codegen_complete") {
    return "border-emerald-500/20 bg-emerald-500/10 text-emerald-700";
  }
  if (status === "business_approved") {
    return "border-blue-500/20 bg-blue-500/10 text-blue-700";
  }
  if (status === "operator_assigned") {
    return "border-amber-500/20 bg-amber-500/10 text-amber-700";
  }
  return "border-slate-200 bg-slate-50 text-slate-600";
}

type ActionState = "idle" | "assigning" | "approving" | "triggering";

export default function FiberDetailPage() {
  const router = useRouter();
  const params = useParams<{ id: string; feedId: string; fiberId: string }>();
  const projectId = params.id;
  const feedId = params.feedId;
  const fiberId = params.fiberId;

  const [session, setSession] = useState<UiSession | null>(null);
  const [fiber, setFiber] = useState<FiberRecord | null>(null);
  const [loading, setLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [actionState, setActionState] = useState<ActionState>("idle");

  useEffect(() => {
    setSession(loadUiSession());
  }, []);

  useEffect(() => {
    if (!session) {
      return;
    }

    let active = true;
    setLoading(true);
    setErrorMessage(null);

    void getFiber(session.accessToken, projectId, feedId, fiberId)
      .then((result) => {
        if (active) {
          setFiber(result);
        }
      })
      .catch((err: unknown) => {
        if (active) {
          setErrorMessage(err instanceof Error ? err.message : "Unable to load fiber.");
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
  }, [session, projectId, feedId, fiberId]);

  const role: SessionRole = session?.role ?? "read_only_auditor";

  async function handleAssign(): Promise<void> {
    if (!session) return;
    setActionState("assigning");
    setErrorMessage(null);
    try {
      const updated = await assignFiber(session.accessToken, projectId, feedId, fiberId);
      setFiber(updated);
    } catch (err: unknown) {
      setErrorMessage(err instanceof Error ? err.message : "Assign failed.");
    } finally {
      setActionState("idle");
    }
  }

  async function handleApprove(): Promise<void> {
    if (!session) return;
    setActionState("approving");
    setErrorMessage(null);
    try {
      const updated = await approveFiber(session.accessToken, projectId, feedId, fiberId);
      setFiber(updated);
    } catch (err: unknown) {
      setErrorMessage(err instanceof Error ? err.message : "Approve failed.");
    } finally {
      setActionState("idle");
    }
  }

  async function handleTrigger(): Promise<void> {
    if (!session) return;
    setActionState("triggering");
    setErrorMessage(null);
    try {
      const updated = await triggerFiber(session.accessToken, projectId, feedId, fiberId);
      setFiber(updated);
    } catch (err: unknown) {
      setErrorMessage(err instanceof Error ? err.message : "Trigger failed.");
    } finally {
      setActionState("idle");
    }
  }

  const canAssign = role === "central_team" && fiber?.status === "mapped";
  const canApprove = role === "project_stakeholder" && fiber?.status === "operator_assigned";
  const canTrigger = role === "central_team" && fiber?.status === "business_approved";
  const busy = actionState !== "idle";

  return (
    <main className="flex min-h-screen flex-col bg-slate-50 text-slate-900">
      <Topbar role={role} />
      <section className="mx-auto flex w-full max-w-[1200px] flex-1 flex-col gap-6 px-6 py-6">
        <div className="flex items-center gap-2 text-xs text-slate-500">
          <button
            className="hover:text-slate-900 hover:underline"
            onClick={() => router.back()}
            type="button"
          >
            ← Back
          </button>
          <span className="text-slate-300">|</span>
          <span className="font-mono uppercase tracking-[0.2em]">Fiber Detail</span>
          {fiber && (
            <>
              <span className="text-slate-300">•</span>
              <span
                className={`inline-flex rounded-full border px-2 py-0.5 font-mono text-[10px] uppercase ${statusBadgeClass(fiber.status)}`}
              >
                {fiber.status}
              </span>
            </>
          )}
        </div>

        {errorMessage && (
          <div
            role="alert"
            className="rounded-2xl border border-red-500/20 bg-red-500/10 px-4 py-3 text-sm text-red-700"
          >
            {errorMessage}
          </div>
        )}

        {loading && (
          <div className="rounded-2xl border border-slate-200 bg-white p-8 text-sm text-slate-600">
            Loading fiber…
          </div>
        )}

        {!loading && fiber && (
          <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
            {/* Main panel */}
            <div className="space-y-4 rounded-3xl border border-slate-200 bg-white p-6 shadow-sm lg:col-span-2">
              <div className="border-b border-slate-200 pb-4">
                <p className="text-[10px] font-semibold uppercase tracking-[0.25em] text-slate-500">
                  {fiber.fiberType === "lookup" ? "Lookup Fiber" : "Domain Object Fiber"}
                </p>
                <h1 className="mt-1 text-xl font-semibold text-slate-900">{fiber.fiberKey}</h1>
              </div>

              {/* domain_object: field bindings table */}
              {fiber.fiberType === "domain_object" && fiber.fieldBindings && fiber.fieldBindings.length > 0 && (
                <div className="overflow-hidden rounded-2xl border border-slate-200">
                  <table className="w-full border-collapse text-sm">
                    <thead className="bg-slate-50">
                      <tr className="text-left text-[10px] font-semibold uppercase tracking-[0.2em] text-slate-500">
                        <th className="px-4 py-3">Source field</th>
                        <th className="px-4 py-3">Destination field</th>
                        <th className="px-4 py-3">Lookup</th>
                      </tr>
                    </thead>
                    <tbody>
                      {fiber.fieldBindings.map((binding, idx) => (
                        <tr key={`${binding.sourceField}-${idx}`} className="border-t border-slate-200">
                          <td className="px-4 py-3 font-mono text-xs font-semibold text-slate-700">
                            {binding.sourceField}
                          </td>
                          <td className="px-4 py-3 font-mono text-xs text-slate-700">
                            {binding.destinationField}
                          </td>
                          <td className="px-4 py-3">
                            {binding.lookupName ? (
                              <span className="inline-flex rounded-full border border-amber-500/20 bg-amber-500/10 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-[0.2em] text-amber-700">
                                {binding.lookupName}
                              </span>
                            ) : (
                              <span className="text-slate-400">—</span>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}

              {/* lookup: proposed mappings preview */}
              {fiber.fiberType === "lookup" && (
                <div className="space-y-2 rounded-2xl border border-slate-200 p-4">
                  <p className="text-[10px] font-semibold uppercase tracking-[0.2em] text-slate-500">
                    Proposed Mappings
                  </p>
                  {fiber.proposedMappings && fiber.proposedMappings.length > 0 ? (
                    <pre className="overflow-x-auto rounded-xl bg-slate-50 px-4 py-3 text-xs text-slate-700">
                      {JSON.stringify(fiber.proposedMappings, null, 2)}
                    </pre>
                  ) : (
                    <p className="text-sm text-slate-500">No proposed mappings yet.</p>
                  )}
                </div>
              )}

              <div className="grid gap-4 rounded-2xl border border-slate-200 bg-slate-50 p-4 md:grid-cols-2">
                <div>
                  <p className="text-[10px] font-semibold uppercase tracking-[0.2em] text-slate-500">
                    Fiber ID
                  </p>
                  <p className="mt-1 font-mono text-xs text-slate-700">{fiber.fiberId}</p>
                </div>
                <div>
                  <p className="text-[10px] font-semibold uppercase tracking-[0.2em] text-slate-500">
                    Type / Source
                  </p>
                  <p className="mt-1 text-sm text-slate-700">
                    {fiber.fiberType} · {fiber.source}
                  </p>
                </div>
              </div>
            </div>

            {/* Action sidebar */}
            <aside className="space-y-4 rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
              <div className="border-b border-slate-200 pb-4">
                <p className="text-[10px] font-semibold uppercase tracking-[0.25em] text-slate-500">
                  Approval Chain
                </p>
                <h2 className="mt-1 text-lg font-semibold text-slate-900">Actions</h2>
              </div>

              {canAssign && (
                <button
                  className="w-full rounded-xl bg-slate-900 px-4 py-2.5 text-sm font-semibold text-white hover:bg-slate-800 disabled:opacity-60"
                  disabled={busy}
                  onClick={() => void handleAssign()}
                  type="button"
                >
                  {actionState === "assigning" ? "Assigning…" : "Assign for Review"}
                </button>
              )}

              {canApprove && (
                <button
                  className="w-full rounded-xl bg-slate-900 px-4 py-2.5 text-sm font-semibold text-white hover:bg-slate-800 disabled:opacity-60"
                  disabled={busy}
                  onClick={() => void handleApprove()}
                  type="button"
                >
                  {actionState === "approving" ? "Approving…" : "Approve"}
                </button>
              )}

              {canTrigger && (
                <button
                  className="w-full rounded-xl bg-slate-900 px-4 py-2.5 text-sm font-semibold text-white hover:bg-slate-800 disabled:opacity-60"
                  disabled={busy}
                  onClick={() => void handleTrigger()}
                  type="button"
                >
                  {actionState === "triggering" ? "Triggering…" : "Trigger"}
                </button>
              )}

              {!canAssign && !canApprove && !canTrigger && (
                <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4 text-sm text-slate-600">
                  {fiber.status === "operator_triggered" || fiber.status === "codegen_complete"
                    ? "Codegen has been queued. No further action required."
                    : "No action available for your role and fiber status."}
                </div>
              )}
            </aside>
          </div>
        )}
      </section>
    </main>
  );
}
```

---

- [ ] **Step 4: Run the page tests — all must pass**

```bash
cd /Users/vjkotra/projects/katana/web
npx vitest run "app/projects/\[id\]/feeds/\[feedId\]/fibers/\[fiberId\]/page.test.tsx"
```

Expected: all tests GREEN.

---

- [ ] **Step 5: Run the full web test suite**

```bash
cd /Users/vjkotra/projects/katana/web
npm test
```

Expected: all tests PASS. Zero regressions.

---

- [ ] **Step 6: Commit**

```bash
git add "web/app/projects/[id]/feeds/[feedId]/fibers/[fiberId]/page.tsx" \
        "web/app/projects/[id]/feeds/[feedId]/fibers/[fiberId]/page.test.tsx"
git commit -m "feat(001an): add fiber detail page with 3-step approval action buttons"
```

---

## Verification Checklist

After all three tasks are complete, run the following to confirm nothing is broken end-to-end:

```bash
# Backend
cd /Users/vjkotra/projects/katana/engine/tests
python -m pytest -v

# Frontend
cd /Users/vjkotra/projects/katana/web
npm test
```

All tests must pass with zero failures before this task is considered done.
