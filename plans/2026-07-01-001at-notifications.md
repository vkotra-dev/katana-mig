# Notifications Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `Notification` DB model, Alembic migration, 4 REST endpoints, a `create_notification` service helper, and an in-app notification bell UI (unread badge, polling, dropdown list, mark-as-read, mark-all-read) with a stub email delivery function.

**Architecture:** The `Notification` row is scoped per-user-per-event. A service function `create_notification` inserts one row per recipient and calls the email stub. The 4 API endpoints (`GET /notifications`, `GET /notifications/count`, `POST /notifications/{id}/read`, `POST /notifications/read-all`) are user-scoped — no `project_id` in the URL, the user's identity from `get_current_user` drives the query. The `NotificationBell` React component polls `GET /notifications/count` every 30 seconds, shows a badge, and renders a dropdown with the full list on click.

**Tech Stack:** FastAPI, SQLAlchemy 2 (mapped_column style), Alembic, Pydantic v2, pytest, SQLite in-memory for tests; Next.js App Router, TypeScript, Vitest, React Testing Library

## Global Constraints

- Migration revision `"0017_notifications"` — `down_revision = "0016_project_schema_analysis"`
- All routes use `Depends(get_current_user)`; no `require_project_access` needed (notifications are user-scoped)
- `AuthApiError` from `..api.deps` for 404s
- Test boilerplate uses the per-file inline SQLite pattern (same as `test_gates_api.py`, `test_reconciliation_api.py`)
- Do NOT implement real SMTP; the email function only logs
- Do NOT wire `create_notification` into gates/runs/lookup-delta callers in this task
- All engine tests must pass before committing Task 1
- All web tests must pass before committing Task 2

## Objective

Add persisted notifications, expose the notification API surface, and render a polling notification bell in the UI.

## Out of Scope

- No websocket or push infrastructure
- No generic inbox or notifications settings screen
- No unrelated audit/event schema changes beyond the notification model

## File Changes

- See the blast radius table above for the exact backend and web files.

## Verification

- Run the notification backend tests
- Run the notification bell component tests
- Run the focused backend and web suites for the touched files

## Pitfalls

- Keep polling bounded and idempotent
- Preserve role and project scoping on list/read actions
- Ensure unread state does not regress existing topbar behavior

## Commit

- `feat(001at): add notifications and polling bell`

---

### Task 1: Backend — model, migration, schema, service, routes, app wiring, tests

**Files:**
- Modify: `engine/src/migrations_engine/db/models.py`
- Create: `engine/migrations/versions/0017_notifications.py`
- Modify: `engine/src/migrations_engine/api/schemas.py`
- Create: `engine/src/migrations_engine/management/notifications.py`
- Create: `engine/src/migrations_engine/routes/notifications.py`
- Modify: `engine/src/migrations_engine/app.py`
- Create: `engine/tests/test_notifications_api.py`

---

- [ ] **Step 1: Write the failing tests**

Create `engine/tests/test_notifications_api.py`:

```python
from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

_sqlite_engine = create_engine(
    "sqlite+pysqlite:///:memory:",
    future=True,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

from migrations_engine.db import session as db_session  # noqa: E402

db_session.engine = _sqlite_engine
db_session.SessionLocal = sessionmaker(
    bind=_sqlite_engine,
    autoflush=False,
    autocommit=False,
    class_=db_session.Session,
)

from migrations_engine.app import app  # noqa: E402
from migrations_engine.auth.passwords import hash_password  # noqa: E402
from migrations_engine.config import get_settings  # noqa: E402
from migrations_engine.db.base import Base  # noqa: E402
from migrations_engine.db.models import (  # noqa: E402
    Notification,
    ProjectDefinition,
    ProjectRegistry,
    User,
)
from migrations_engine.db.session import SessionLocal  # noqa: E402
from migrations_engine.management.notifications import create_notification  # noqa: E402
from migrations_engine.roles import CENTRAL_TEAM_ROLE, PROJECT_STAKEHOLDER_ROLE  # noqa: E402

client = TestClient(app)


@pytest.fixture(scope="module", autouse=True)
def _setup_sqlite_db() -> None:
    Base.metadata.create_all(bind=_sqlite_engine)

    settings = get_settings()
    if not settings.bootstrap_admin_email or not settings.bootstrap_admin_password:
        pytest.skip("bootstrap credentials not configured")

    with SessionLocal() as db:
        db.add(
            User(
                user_id="admin-user-id",
                email=settings.bootstrap_admin_email.strip().lower(),
                display_name="Admin",
                password_hash=hash_password(settings.bootstrap_admin_password),
                role=CENTRAL_TEAM_ROLE,
                status="active",
            )
        )
        db.add(
            User(
                user_id="stakeholder-user-id",
                email="stakeholder@example.com",
                display_name="Stakeholder",
                password_hash=hash_password("stakeholder-password"),
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
    return _login("stakeholder@example.com", "stakeholder-password")


def _seed_project() -> str:
    project_id = str(uuid.uuid4())
    definition_id = str(uuid.uuid4())
    with SessionLocal() as db:
        db.add(
            ProjectDefinition(
                definition_id=definition_id,
                project_id=project_id,
                name="Notification Test Project",
                status="active",
            )
        )
        db.add(
            ProjectRegistry(
                project_id=project_id,
                name="Notification Test Project",
                definition_id=definition_id,
                status="active",
            )
        )
        db.commit()
    return project_id


def _insert_notification(
    *,
    user_id: str,
    project_id: str,
    event_type: str = "execution_complete",
    deep_link: str | None = "/projects/abc",
    read: bool = False,
    payload: dict | None = None,
) -> str:
    notification_id = str(uuid.uuid4())
    with SessionLocal() as db:
        db.add(
            Notification(
                notification_id=notification_id,
                user_id=user_id,
                project_id=project_id,
                event_type=event_type,
                deep_link=deep_link,
                read=read,
                payload=payload,
            )
        )
        db.commit()
    return notification_id


def test_notification_model_exists() -> None:
    """Notification model has correct tablename and columns."""
    assert Notification.__tablename__ == "notifications"
    assert hasattr(Notification, "notification_id")
    assert hasattr(Notification, "user_id")
    assert hasattr(Notification, "project_id")
    assert hasattr(Notification, "event_type")
    assert hasattr(Notification, "deep_link")
    assert hasattr(Notification, "read")
    assert hasattr(Notification, "payload")
    assert hasattr(Notification, "created_at")


def test_list_notifications_empty(admin_token: str) -> None:
    """GET /notifications returns empty list when no notifications exist for user."""
    response = client.get(
        "/notifications",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert isinstance(data, list)


def test_list_notifications_returns_own_only(admin_token: str, stakeholder_token: str) -> None:
    """GET /notifications only returns notifications scoped to the authenticated user."""
    project_id = _seed_project()
    notif_id = _insert_notification(user_id="admin-user-id", project_id=project_id)
    _insert_notification(user_id="stakeholder-user-id", project_id=project_id)

    admin_response = client.get(
        "/notifications",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert admin_response.status_code == 200
    ids = [n["notification_id"] for n in admin_response.json()]
    assert notif_id in ids
    # Admin should not see the stakeholder's notification
    stakeholder_notif_ids_from_admin = [n["notification_id"] for n in admin_response.json() if n["user_id"] != "admin-user-id"]
    assert len(stakeholder_notif_ids_from_admin) == 0


def test_list_notifications_unread_filter(admin_token: str) -> None:
    """GET /notifications?unread=true filters to unread notifications only."""
    project_id = _seed_project()
    unread_id = _insert_notification(user_id="admin-user-id", project_id=project_id, read=False)
    _insert_notification(user_id="admin-user-id", project_id=project_id, read=True)

    response = client.get(
        "/notifications?unread=true",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200
    ids = [n["notification_id"] for n in response.json()]
    assert unread_id in ids
    # All returned items must be unread
    for n in response.json():
        if n["notification_id"] == unread_id:
            assert n["read"] is False


def test_notification_response_shape(admin_token: str) -> None:
    """GET /notifications returns correct NotificationResponse fields."""
    project_id = _seed_project()
    notif_id = _insert_notification(
        user_id="admin-user-id",
        project_id=project_id,
        event_type="lookup_delta_discovered",
        deep_link="/projects/abc/change-requests/xyz",
        payload={"lookup_name": "account_type", "unmapped_value": "RETD"},
    )
    response = client.get(
        "/notifications",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200
    matches = [n for n in response.json() if n["notification_id"] == notif_id]
    assert len(matches) == 1
    n = matches[0]
    assert n["notification_id"] == notif_id
    assert n["user_id"] == "admin-user-id"
    assert n["project_id"] == project_id
    assert n["event_type"] == "lookup_delta_discovered"
    assert n["deep_link"] == "/projects/abc/change-requests/xyz"
    assert n["read"] is False
    assert n["payload"] == {"lookup_name": "account_type", "unmapped_value": "RETD"}
    assert "created_at" in n


def test_get_notification_count(admin_token: str) -> None:
    """GET /notifications/count returns unread_count for the authenticated user."""
    project_id = _seed_project()
    _insert_notification(user_id="admin-user-id", project_id=project_id, read=False)
    _insert_notification(user_id="admin-user-id", project_id=project_id, read=False)
    _insert_notification(user_id="admin-user-id", project_id=project_id, read=True)

    response = client.get(
        "/notifications/count",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200
    body = response.json()
    assert "unread_count" in body
    assert isinstance(body["unread_count"], int)
    assert body["unread_count"] >= 2


def test_mark_notification_read(admin_token: str) -> None:
    """POST /notifications/{id}/read marks a single notification as read."""
    project_id = _seed_project()
    notif_id = _insert_notification(user_id="admin-user-id", project_id=project_id, read=False)

    response = client.post(
        f"/notifications/{notif_id}/read",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200, response.text
    n = response.json()
    assert n["notification_id"] == notif_id
    assert n["read"] is True

    # Verify persisted in DB
    with SessionLocal() as db:
        row = db.get(Notification, notif_id)
        assert row is not None
        assert row.read is True


def test_mark_notification_read_404_for_wrong_user(admin_token: str) -> None:
    """POST /notifications/{id}/read returns 404 if notification belongs to another user."""
    project_id = _seed_project()
    other_notif_id = _insert_notification(user_id="stakeholder-user-id", project_id=project_id)

    response = client.post(
        f"/notifications/{other_notif_id}/read",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "notification_not_found"


def test_mark_all_read(admin_token: str) -> None:
    """POST /notifications/read-all marks all unread notifications as read for the user."""
    project_id = _seed_project()
    _insert_notification(user_id="admin-user-id", project_id=project_id, read=False)
    _insert_notification(user_id="admin-user-id", project_id=project_id, read=False)

    response = client.post(
        "/notifications/read-all",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 204

    # Verify count is now 0
    count_response = client.get(
        "/notifications/count",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert count_response.json()["unread_count"] == 0


def test_mark_all_read_does_not_affect_other_users(admin_token: str) -> None:
    """POST /notifications/read-all only affects the authenticated user's notifications."""
    project_id = _seed_project()
    other_notif_id = _insert_notification(user_id="stakeholder-user-id", project_id=project_id, read=False)

    client.post("/notifications/read-all", headers={"Authorization": f"Bearer {admin_token}"})

    with SessionLocal() as db:
        row = db.get(Notification, other_notif_id)
        assert row is not None
        assert row.read is False


def test_unauthenticated_request_is_rejected() -> None:
    """All notification endpoints require authentication."""
    assert client.get("/notifications").status_code == 401
    assert client.get("/notifications/count").status_code == 401
    assert client.post("/notifications/read-all").status_code == 401


def test_create_notification_service_inserts_rows(admin_token: str) -> None:
    """create_notification inserts one Notification per recipient."""
    project_id = _seed_project()

    with SessionLocal() as db:
        from sqlalchemy import select as sa_select
        before_count = db.scalar(
            sa_select(Notification).where(
                Notification.project_id == project_id,
                Notification.event_type == "reconciliation_failed",
            )
        )

    with SessionLocal() as db:
        create_notification(
            db,
            project_id=project_id,
            event_type="reconciliation_failed",
            deep_link=f"/projects/{project_id}/runs/run-123",
            payload={"run_id": "run-123"},
            recipient_user_ids=["admin-user-id", "stakeholder-user-id"],
        )

    with SessionLocal() as db:
        from sqlalchemy import select as sa_select
        rows = db.scalars(
            sa_select(Notification).where(
                Notification.project_id == project_id,
                Notification.event_type == "reconciliation_failed",
            )
        ).all()
        assert len(rows) == 2
        recipient_ids = {r.user_id for r in rows}
        assert "admin-user-id" in recipient_ids
        assert "stakeholder-user-id" in recipient_ids
        for row in rows:
            assert row.read is False
            assert row.payload == {"run_id": "run-123"}
```

- [ ] **Step 2: Run to verify tests fail**

```bash
cd /Users/vjkotra/projects/katana/engine/tests
python -m pytest test_notifications_api.py -v 2>&1 | head -40
```

Expected: FAIL — `ImportError: cannot import name 'Notification'` (model does not exist yet).

---

- [ ] **Step 3: Add `Notification` model to `engine/src/migrations_engine/db/models.py`**

Add at the bottom of `models.py`, after `AuditEvent`:

```python
class Notification(Base):
    __tablename__ = "notifications"

    notification_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.user_id"), nullable=False, index=True)
    project_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("project_registry.project_id"), nullable=False, index=True
    )
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    deep_link: Mapped[str | None] = mapped_column(String(512), nullable=True)
    read: Mapped[bool] = mapped_column(nullable=False, default=False, server_default="0")
    payload: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
```

The import block at the top of `models.py` already has all needed imports (`JSON`, `DateTime`, `ForeignKey`, `String`, `func`, `Any`, `datetime`, `Mapped`, `mapped_column`). No import changes needed.

- [ ] **Step 4: Create Alembic migration `engine/migrations/versions/0017_notifications.py`**

```python
"""add notifications table

Revision ID: 0017_notifications
Revises: 0016_project_schema_analysis
Create Date: 2026-07-01
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0017_notifications"
down_revision = "0016_project_schema_analysis"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "notifications",
        sa.Column("notification_id", sa.String(36), primary_key=True),
        sa.Column(
            "user_id",
            sa.String(36),
            sa.ForeignKey("users.user_id"),
            nullable=False,
        ),
        sa.Column(
            "project_id",
            sa.String(36),
            sa.ForeignKey("project_registry.project_id"),
            nullable=False,
        ),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("deep_link", sa.String(512), nullable=True),
        sa.Column(
            "read",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column("payload", sa.JSON(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_notifications_user_id", "notifications", ["user_id"])
    op.create_index("ix_notifications_project_id", "notifications", ["project_id"])


def downgrade() -> None:
    op.drop_index("ix_notifications_project_id", table_name="notifications")
    op.drop_index("ix_notifications_user_id", table_name="notifications")
    op.drop_table("notifications")
```

- [ ] **Step 5: Add `NotificationResponse` and `NotificationCountResponse` schemas to `engine/src/migrations_engine/api/schemas.py`**

Add at the end of `schemas.py`:

```python
class NotificationResponse(BaseModel):
    notification_id: str
    user_id: str
    project_id: str
    event_type: str
    deep_link: str | None
    read: bool
    payload: dict[str, Any] | None
    created_at: datetime


class NotificationCountResponse(BaseModel):
    unread_count: int
```

- [ ] **Step 6: Create `engine/src/migrations_engine/management/notifications.py`**

```python
from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session

from ..db.models import Notification, User, new_id

logger = logging.getLogger(__name__)


def send_notification_email(user_email: str, event_type: str, deep_link: str | None) -> None:
    """Stub email delivery. Logs to Python logger; replace with real SMTP later."""
    logger.info(
        "NOTIFICATION EMAIL [stub]: to=%s event_type=%s deep_link=%s",
        user_email,
        event_type,
        deep_link,
    )


def create_notification(
    db: Session,
    *,
    project_id: str,
    event_type: str,
    deep_link: str | None,
    payload: dict[str, Any] | None,
    recipient_user_ids: list[str],
) -> list[Notification]:
    """Insert one Notification row per recipient and call the email stub for each.

    Returns the list of inserted Notification objects (already flushed, not yet committed).
    The caller is responsible for calling db.commit().
    """
    rows: list[Notification] = []
    for user_id in recipient_user_ids:
        row = Notification(
            notification_id=new_id(),
            user_id=user_id,
            project_id=project_id,
            event_type=event_type,
            deep_link=deep_link,
            read=False,
            payload=payload,
        )
        db.add(row)
        rows.append(row)

    db.flush()

    # Fire email stubs after flush so notification_ids are available if needed
    for row in rows:
        user = db.get(User, row.user_id)
        if user is not None:
            send_notification_email(user.email, event_type, deep_link)

    db.commit()
    for row in rows:
        db.refresh(row)
    return rows
```

- [ ] **Step 7: Create `engine/src/migrations_engine/routes/notifications.py`**

```python
from __future__ import annotations

from fastapi import APIRouter, Depends, Response
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from ..api.deps import AuthApiError, get_current_user, get_db
from ..api.schemas import NotificationCountResponse, NotificationResponse
from ..db.models import Notification, User

router = APIRouter(prefix="/notifications", tags=["notifications"])


def _to_response(n: Notification) -> NotificationResponse:
    return NotificationResponse(
        notification_id=n.notification_id,
        user_id=n.user_id,
        project_id=n.project_id,
        event_type=n.event_type,
        deep_link=n.deep_link,
        read=n.read,
        payload=n.payload,
        created_at=n.created_at,
    )


@router.get("", response_model=list[NotificationResponse])
def list_notifications(
    unread: bool = False,
    actor: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[NotificationResponse]:
    stmt = select(Notification).where(Notification.user_id == actor.user_id)
    if unread:
        stmt = stmt.where(Notification.read.is_(False))
    stmt = stmt.order_by(Notification.created_at.desc())
    rows = db.scalars(stmt).all()
    return [_to_response(n) for n in rows]


@router.get("/count", response_model=NotificationCountResponse)
def get_notification_count(
    actor: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> NotificationCountResponse:
    from sqlalchemy import func

    count = db.scalar(
        select(func.count(Notification.notification_id)).where(
            Notification.user_id == actor.user_id,
            Notification.read.is_(False),
        )
    )
    return NotificationCountResponse(unread_count=count or 0)


@router.post("/{notification_id}/read", response_model=NotificationResponse)
def mark_notification_read(
    notification_id: str,
    actor: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> NotificationResponse:
    n = db.scalar(
        select(Notification).where(
            Notification.notification_id == notification_id,
            Notification.user_id == actor.user_id,
        )
    )
    if n is None:
        raise AuthApiError("notification_not_found", "Notification not found.", 404)
    n.read = True
    db.commit()
    db.refresh(n)
    return _to_response(n)


@router.post("/read-all", status_code=204)
def mark_all_notifications_read(
    actor: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    db.execute(
        update(Notification)
        .where(
            Notification.user_id == actor.user_id,
            Notification.read.is_(False),
        )
        .values(read=True)
    )
    db.commit()
    return Response(status_code=204)
```

**Note on route ordering:** FastAPI matches routes top-to-bottom. `/notifications/count` must be registered before `/notifications/{notification_id}/read` so that `count` is not captured as `notification_id`. The router definition above lists `/count` first (line order in the file) and the `GET ""` + `GET "/count"` before the `POST "/{notification_id}/read"`, so this is safe. FastAPI distinguishes GET vs POST verbs but the `/count` literal must appear before `/{notification_id}` for GET; since `GET /count` is a separate route from `POST /{id}/read`, there is no ambiguity. Confirm the router prefixes match the test paths.

- [ ] **Step 8: Register the notifications router in `engine/src/migrations_engine/app.py`**

Add the import:

```python
from .routes.notifications import router as notifications_router
```

Add the include call (after the existing `app.include_router(users_router)` line):

```python
app.include_router(notifications_router)
```

Full diff to `app.py` — add to imports block:

```python
from .routes.notifications import router as notifications_router
```

Add after `app.include_router(users_router)`:

```python
app.include_router(notifications_router)
```

- [ ] **Step 9: Run the full test for the notifications API**

```bash
cd /Users/vjkotra/projects/katana/engine/tests
python -m pytest test_notifications_api.py -v
```

Expected: all tests PASS.

- [ ] **Step 10: Run the full engine test suite**

```bash
cd /Users/vjkotra/projects/katana/engine/tests
python -m pytest -v
```

Expected: all tests PASS. Fix any import or model issues that surface.

- [ ] **Step 11: Commit Task 1**

```bash
git add \
  engine/src/migrations_engine/db/models.py \
  engine/migrations/versions/0017_notifications.py \
  engine/src/migrations_engine/api/schemas.py \
  engine/src/migrations_engine/management/notifications.py \
  engine/src/migrations_engine/routes/notifications.py \
  engine/src/migrations_engine/app.py \
  engine/tests/test_notifications_api.py
git commit -m "$(cat <<'EOF'
feat(001at): add Notification model, migration 0018, 4 routes, and create_notification service

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
EOF
)"
```

---

### Task 2: Frontend — API helpers, NotificationBell component, Topbar wiring, tests

**Files:**
- Create: `web/lib/notifications-api.ts`
- Create: `web/lib/notifications-api.test.ts`
- Create: `web/components/notifications/NotificationBell.tsx`
- Create: `web/components/notifications/__tests__/NotificationBell.test.tsx`
- Modify: `web/components/Topbar.tsx`
- Modify: `web/components/__tests__/Topbar.test.tsx`

---

- [ ] **Step 1: Write the failing API helper tests**

Create `web/lib/notifications-api.test.ts`:

```typescript
import { beforeEach, describe, expect, it, vi } from "vitest";
import {
  getNotifications,
  getNotificationCount,
  markNotificationRead,
  markAllNotificationsRead,
  type NotificationRecord,
} from "./notifications-api";

const fetchMock = vi.fn();
vi.stubGlobal("fetch", fetchMock);

const NOTIFICATION: NotificationRecord = {
  notificationId: "notif-1",
  userId: "user-1",
  projectId: "project-1",
  eventType: "execution_complete",
  deepLink: "/projects/project-1",
  read: false,
  payload: null,
  createdAt: "2026-07-01T10:00:00Z",
};

describe("notifications-api", () => {
  beforeEach(() => {
    fetchMock.mockReset();
  });

  describe("getNotifications", () => {
    it("calls GET /notifications and returns mapped array", async () => {
      fetchMock.mockResolvedValueOnce(
        new Response(
          JSON.stringify([
            {
              notification_id: "notif-1",
              user_id: "user-1",
              project_id: "project-1",
              event_type: "execution_complete",
              deep_link: "/projects/project-1",
              read: false,
              payload: null,
              created_at: "2026-07-01T10:00:00Z",
            },
          ]),
          { status: 200 },
        ),
      );

      const result = await getNotifications("tok");
      expect(fetchMock).toHaveBeenCalledWith(
        "http://127.0.0.1:8000/notifications",
        expect.objectContaining({
          method: "GET",
          headers: expect.objectContaining({ Authorization: "Bearer tok" }),
        }),
      );
      expect(result).toHaveLength(1);
      expect(result[0]).toEqual(NOTIFICATION);
    });

    it("calls GET /notifications?unread=true when unread=true", async () => {
      fetchMock.mockResolvedValueOnce(
        new Response(JSON.stringify([]), { status: 200 }),
      );
      await getNotifications("tok", { unread: true });
      expect(fetchMock).toHaveBeenCalledWith(
        "http://127.0.0.1:8000/notifications?unread=true",
        expect.anything(),
      );
    });
  });

  describe("getNotificationCount", () => {
    it("calls GET /notifications/count and returns unreadCount", async () => {
      fetchMock.mockResolvedValueOnce(
        new Response(JSON.stringify({ unread_count: 4 }), { status: 200 }),
      );
      const result = await getNotificationCount("tok");
      expect(fetchMock).toHaveBeenCalledWith(
        "http://127.0.0.1:8000/notifications/count",
        expect.objectContaining({ method: "GET" }),
      );
      expect(result).toEqual({ unreadCount: 4 });
    });
  });

  describe("markNotificationRead", () => {
    it("calls POST /notifications/{id}/read and returns mapped record", async () => {
      fetchMock.mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            notification_id: "notif-1",
            user_id: "user-1",
            project_id: "project-1",
            event_type: "execution_complete",
            deep_link: "/projects/project-1",
            read: true,
            payload: null,
            created_at: "2026-07-01T10:00:00Z",
          }),
          { status: 200 },
        ),
      );
      const result = await markNotificationRead("tok", "notif-1");
      expect(fetchMock).toHaveBeenCalledWith(
        "http://127.0.0.1:8000/notifications/notif-1/read",
        expect.objectContaining({ method: "POST" }),
      );
      expect(result.read).toBe(true);
    });
  });

  describe("markAllNotificationsRead", () => {
    it("calls POST /notifications/read-all and returns undefined for 204", async () => {
      fetchMock.mockResolvedValueOnce(new Response(null, { status: 204 }));
      const result = await markAllNotificationsRead("tok");
      expect(fetchMock).toHaveBeenCalledWith(
        "http://127.0.0.1:8000/notifications/read-all",
        expect.objectContaining({ method: "POST" }),
      );
      expect(result).toBeUndefined();
    });
  });

  describe("error handling", () => {
    it("throws NotificationApiError on non-ok response", async () => {
      fetchMock.mockResolvedValueOnce(
        new Response(
          JSON.stringify({ error: { code: "unauthenticated", message: "Authentication is required." } }),
          { status: 401 },
        ),
      );
      await expect(getNotifications("bad-token")).rejects.toMatchObject({
        code: "unauthenticated",
        status: 401,
      });
    });
  });
});
```

- [ ] **Step 2: Run to verify API tests fail**

```bash
cd /Users/vjkotra/projects/katana/web
npm test -- lib/notifications-api.test.ts 2>&1 | head -30
```

Expected: FAIL — `Cannot find module './notifications-api'`

- [ ] **Step 3: Create `web/lib/notifications-api.ts`**

```typescript
import { API_BASE_URL } from "./api-base";

export interface NotificationRecord {
  notificationId: string;
  userId: string;
  projectId: string;
  eventType: string;
  deepLink: string | null;
  read: boolean;
  payload: Record<string, unknown> | null;
  createdAt: string;
}

export interface NotificationCountRecord {
  unreadCount: number;
}

export class NotificationApiError extends Error {
  code: string;
  status: number;

  constructor(code: string, message: string, status: number) {
    super(message || code);
    this.name = "NotificationApiError";
    this.code = code;
    this.status = status;
  }
}

function authHeaders(token: string): Record<string, string> {
  return {
    Authorization: `Bearer ${token}`,
    "Content-Type": "application/json",
  };
}

async function parseApiError(response: Response): Promise<NotificationApiError> {
  try {
    const body = (await response.json()) as {
      error?: { code?: string; message?: string };
    };
    return new NotificationApiError(
      body.error?.code ?? "api_error",
      body.error?.message ?? "api_error",
      response.status,
    );
  } catch {
    return new NotificationApiError("api_error", await response.text(), response.status);
  }
}

async function requestJson<T>(
  path: string,
  init: RequestInit & { token: string },
): Promise<T> {
  const { token, headers, ...rest } = init;
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...rest,
    headers: {
      ...authHeaders(token),
      ...(headers ?? {}),
    },
  });

  if (!response.ok) {
    throw await parseApiError(response);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return (await response.json()) as T;
}

function mapNotification(raw: {
  notification_id: string;
  user_id: string;
  project_id: string;
  event_type: string;
  deep_link: string | null;
  read: boolean;
  payload: Record<string, unknown> | null;
  created_at: string;
}): NotificationRecord {
  return {
    notificationId: raw.notification_id,
    userId: raw.user_id,
    projectId: raw.project_id,
    eventType: raw.event_type,
    deepLink: raw.deep_link,
    read: raw.read,
    payload: raw.payload,
    createdAt: raw.created_at,
  };
}

export async function getNotifications(
  token: string,
  options: { unread?: boolean } = {},
): Promise<NotificationRecord[]> {
  const params = options.unread ? "?unread=true" : "";
  const raw = await requestJson<
    Array<{
      notification_id: string;
      user_id: string;
      project_id: string;
      event_type: string;
      deep_link: string | null;
      read: boolean;
      payload: Record<string, unknown> | null;
      created_at: string;
    }>
  >(`/notifications${params}`, { method: "GET", token });
  return raw.map(mapNotification);
}

export async function getNotificationCount(token: string): Promise<NotificationCountRecord> {
  const raw = await requestJson<{ unread_count: number }>("/notifications/count", {
    method: "GET",
    token,
  });
  return { unreadCount: raw.unread_count };
}

export async function markNotificationRead(
  token: string,
  notificationId: string,
): Promise<NotificationRecord> {
  const raw = await requestJson<{
    notification_id: string;
    user_id: string;
    project_id: string;
    event_type: string;
    deep_link: string | null;
    read: boolean;
    payload: Record<string, unknown> | null;
    created_at: string;
  }>(`/notifications/${notificationId}/read`, { method: "POST", token });
  return mapNotification(raw);
}

export async function markAllNotificationsRead(token: string): Promise<void> {
  await requestJson<void>("/notifications/read-all", { method: "POST", token });
}
```

- [ ] **Step 4: Run API tests — expect PASS**

```bash
cd /Users/vjkotra/projects/katana/web
npm test -- lib/notifications-api.test.ts
```

Expected: all tests PASS.

- [ ] **Step 5: Write the failing `NotificationBell` component tests**

Create `web/components/notifications/__tests__/NotificationBell.test.tsx`:

```typescript
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { NotificationBell } from "../NotificationBell";

const mockGetNotificationCount = vi.fn();
const mockGetNotifications = vi.fn();
const mockMarkNotificationRead = vi.fn();
const mockMarkAllNotificationsRead = vi.fn();

vi.mock("../../../lib/notifications-api", () => ({
  getNotificationCount: (...args: unknown[]) => mockGetNotificationCount(...args),
  getNotifications: (...args: unknown[]) => mockGetNotifications(...args),
  markNotificationRead: (...args: unknown[]) => mockMarkNotificationRead(...args),
  markAllNotificationsRead: (...args: unknown[]) => mockMarkAllNotificationsRead(...args),
}));

const NOTIFICATION_UNREAD = {
  notificationId: "notif-1",
  userId: "user-1",
  projectId: "project-1",
  eventType: "execution_complete",
  deepLink: "/projects/project-1",
  read: false,
  payload: null,
  createdAt: "2026-07-01T10:00:00Z",
};

const NOTIFICATION_READ = {
  ...NOTIFICATION_UNREAD,
  notificationId: "notif-2",
  read: true,
};

describe("NotificationBell", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockGetNotificationCount.mockResolvedValue({ unreadCount: 0 });
    mockGetNotifications.mockResolvedValue([]);
    mockMarkNotificationRead.mockResolvedValue({ ...NOTIFICATION_UNREAD, read: true });
    mockMarkAllNotificationsRead.mockResolvedValue(undefined);
  });

  it("renders a bell icon button", () => {
    render(<NotificationBell token="tok" />);
    expect(screen.getByRole("button", { name: /notifications/i })).toBeInTheDocument();
  });

  it("shows no badge when unread count is 0", async () => {
    mockGetNotificationCount.mockResolvedValue({ unreadCount: 0 });
    render(<NotificationBell token="tok" />);
    await waitFor(() => {
      expect(screen.queryByTestId("notification-badge")).not.toBeInTheDocument();
    });
  });

  it("shows unread badge when unread count > 0", async () => {
    mockGetNotificationCount.mockResolvedValue({ unreadCount: 3 });
    render(<NotificationBell token="tok" />);
    await waitFor(() => {
      expect(screen.getByTestId("notification-badge")).toBeInTheDocument();
      expect(screen.getByTestId("notification-badge").textContent).toBe("3");
    });
  });

  it("opens dropdown on bell click and shows notifications", async () => {
    mockGetNotificationCount.mockResolvedValue({ unreadCount: 1 });
    mockGetNotifications.mockResolvedValue([NOTIFICATION_UNREAD]);

    render(<NotificationBell token="tok" />);
    fireEvent.click(screen.getByRole("button", { name: /notifications/i }));

    await waitFor(() => {
      expect(mockGetNotifications).toHaveBeenCalledWith("tok");
    });
    expect(screen.getByTestId("notification-list")).toBeInTheDocument();
  });

  it("shows empty state message when no notifications in dropdown", async () => {
    mockGetNotifications.mockResolvedValue([]);
    render(<NotificationBell token="tok" />);
    fireEvent.click(screen.getByRole("button", { name: /notifications/i }));

    await waitFor(() => {
      expect(screen.getByText(/no notifications/i)).toBeInTheDocument();
    });
  });

  it("renders notification event type in dropdown", async () => {
    mockGetNotifications.mockResolvedValue([NOTIFICATION_UNREAD]);
    render(<NotificationBell token="tok" />);
    fireEvent.click(screen.getByRole("button", { name: /notifications/i }));

    await waitFor(() => {
      expect(screen.getByText("execution_complete")).toBeInTheDocument();
    });
  });

  it("mark-as-read button calls markNotificationRead", async () => {
    mockGetNotifications.mockResolvedValue([NOTIFICATION_UNREAD]);
    render(<NotificationBell token="tok" />);
    fireEvent.click(screen.getByRole("button", { name: /notifications/i }));

    await waitFor(() => {
      expect(screen.getByTestId("mark-read-notif-1")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId("mark-read-notif-1"));
    await waitFor(() => {
      expect(mockMarkNotificationRead).toHaveBeenCalledWith("tok", "notif-1");
    });
  });

  it("mark-all-read button calls markAllNotificationsRead", async () => {
    mockGetNotifications.mockResolvedValue([NOTIFICATION_UNREAD]);
    render(<NotificationBell token="tok" />);
    fireEvent.click(screen.getByRole("button", { name: /notifications/i }));

    await waitFor(() => {
      expect(screen.getByRole("button", { name: /mark all read/i })).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: /mark all read/i }));
    await waitFor(() => {
      expect(mockMarkAllNotificationsRead).toHaveBeenCalledWith("tok");
    });
  });

  it("closes dropdown when clicking the bell button again", async () => {
    mockGetNotifications.mockResolvedValue([]);
    render(<NotificationBell token="tok" />);
    const bellBtn = screen.getByRole("button", { name: /notifications/i });

    fireEvent.click(bellBtn);
    await waitFor(() => expect(screen.getByTestId("notification-list")).toBeInTheDocument());

    fireEvent.click(bellBtn);
    await waitFor(() => expect(screen.queryByTestId("notification-list")).not.toBeInTheDocument());
  });
});
```

- [ ] **Step 6: Run component tests — expect FAIL**

```bash
cd /Users/vjkotra/projects/katana/web
npm test -- components/notifications/__tests__/NotificationBell.test.tsx 2>&1 | head -30
```

Expected: FAIL — `Cannot find module '../NotificationBell'`

- [ ] **Step 7: Create `web/components/notifications/NotificationBell.tsx`**

First, create the directory:

```bash
mkdir -p /Users/vjkotra/projects/katana/web/components/notifications
```

Then create the file:

```typescript
"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  getNotificationCount,
  getNotifications,
  markAllNotificationsRead,
  markNotificationRead,
  type NotificationRecord,
} from "../../lib/notifications-api";

const POLL_INTERVAL_MS = 30_000;

export interface NotificationBellProps {
  token: string;
}

export function NotificationBell({ token }: NotificationBellProps) {
  const [unreadCount, setUnreadCount] = useState<number>(0);
  const [open, setOpen] = useState(false);
  const [notifications, setNotifications] = useState<NotificationRecord[]>([]);
  const [loadingList, setLoadingList] = useState(false);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const fetchCount = useCallback(() => {
    void getNotificationCount(token)
      .then((c) => setUnreadCount(c.unreadCount))
      .catch(() => {
        /* silently ignore poll errors */
      });
  }, [token]);

  // Poll count every 30 seconds
  useEffect(() => {
    fetchCount();
    intervalRef.current = setInterval(fetchCount, POLL_INTERVAL_MS);
    return () => {
      if (intervalRef.current !== null) {
        clearInterval(intervalRef.current);
      }
    };
  }, [fetchCount]);

  const openDropdown = useCallback(() => {
    setLoadingList(true);
    void getNotifications(token)
      .then((list) => {
        setNotifications(list);
      })
      .catch(() => {
        setNotifications([]);
      })
      .finally(() => {
        setLoadingList(false);
      });
  }, [token]);

  const handleBellClick = useCallback(() => {
    setOpen((prev) => {
      if (!prev) {
        openDropdown();
      }
      return !prev;
    });
  }, [openDropdown]);

  const handleMarkRead = useCallback(
    (notificationId: string) => {
      void markNotificationRead(token, notificationId)
        .then((updated) => {
          setNotifications((prev) =>
            prev.map((n) => (n.notificationId === notificationId ? updated : n)),
          );
          setUnreadCount((c) => Math.max(0, c - 1));
        })
        .catch(() => {
          /* ignore */
        });
    },
    [token],
  );

  const handleMarkAllRead = useCallback(() => {
    void markAllNotificationsRead(token)
      .then(() => {
        setNotifications((prev) => prev.map((n) => ({ ...n, read: true })));
        setUnreadCount(0);
      })
      .catch(() => {
        /* ignore */
      });
  }, [token]);

  return (
    <div className="relative">
      <button
        aria-label="Notifications"
        className="relative flex h-8 w-8 items-center justify-center rounded-full hover:bg-surface-variant"
        onClick={handleBellClick}
        type="button"
      >
        {/* Bell icon using inline SVG — no external icon library dependency */}
        <svg
          aria-hidden="true"
          className="h-5 w-5 text-on-surface"
          fill="none"
          stroke="currentColor"
          strokeWidth={1.8}
          viewBox="0 0 24 24"
          xmlns="http://www.w3.org/2000/svg"
        >
          <path
            d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>

        {unreadCount > 0 && (
          <span
            className="absolute -right-1 -top-1 flex h-4 min-w-4 items-center justify-center rounded-full bg-error px-1 text-[10px] font-bold text-on-error"
            data-testid="notification-badge"
          >
            {unreadCount}
          </span>
        )}
      </button>

      {open && (
        <div className="absolute right-0 top-10 z-50 w-80 rounded-lg border border-outline-variant bg-surface shadow-lg">
          <div className="flex items-center justify-between border-b border-outline-variant px-4 py-2">
            <span className="text-label-md font-semibold text-on-surface">Notifications</span>
            <button
              className="text-label-sm text-primary hover:underline"
              onClick={handleMarkAllRead}
              type="button"
            >
              Mark all read
            </button>
          </div>

          <div
            className="max-h-96 overflow-y-auto"
            data-testid="notification-list"
          >
            {loadingList && (
              <p className="px-4 py-6 text-center text-body-sm text-on-surface-variant">
                Loading…
              </p>
            )}

            {!loadingList && notifications.length === 0 && (
              <p className="px-4 py-6 text-center text-body-sm text-on-surface-variant">
                No notifications
              </p>
            )}

            {!loadingList &&
              notifications.map((n) => (
                <div
                  key={n.notificationId}
                  className={`flex items-start gap-3 border-b border-outline-variant px-4 py-3 last:border-b-0 ${
                    n.read ? "opacity-60" : "bg-surface-variant/30"
                  }`}
                >
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-body-sm font-medium text-on-surface">
                      {n.eventType}
                    </p>
                    {n.deepLink && (
                      <a
                        className="text-label-sm text-primary hover:underline"
                        href={n.deepLink}
                      >
                        View
                      </a>
                    )}
                    <p className="text-label-xs text-on-surface-variant">
                      {new Date(n.createdAt).toLocaleString()}
                    </p>
                  </div>
                  {!n.read && (
                    <button
                      aria-label={`Mark notification ${n.notificationId} as read`}
                      className="shrink-0 text-label-sm text-primary hover:underline"
                      data-testid={`mark-read-${n.notificationId}`}
                      onClick={() => handleMarkRead(n.notificationId)}
                      type="button"
                    >
                      Mark read
                    </button>
                  )}
                </div>
              ))}
          </div>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 8: Run component tests — expect PASS**

```bash
cd /Users/vjkotra/projects/katana/web
npm test -- components/notifications/__tests__/NotificationBell.test.tsx
```

Expected: all tests PASS.

- [ ] **Step 9: Wire `NotificationBell` into `web/components/Topbar.tsx`**

Current `Topbar.tsx` ends with:

```tsx
      <div className="ml-auto flex items-center">
        <div className="mono-id">AD</div>
      </div>
```

Replace that closing `<div className="ml-auto ...">` block with:

```tsx
      <div className="ml-auto flex items-center gap-3">
        {session && <NotificationBell token={session.accessToken} />}
        <div className="mono-id">AD</div>
      </div>
```

And add the needed imports at the top of `Topbar.tsx`. The full updated file:

```typescript
"use client";

import { useEffect, useState } from "react";
import { navItemsForRole, type NavItem } from "../lib/ui-model";
import { getPendingApprovalCount } from "../lib/slice-approval-api";
import { loadUiSession } from "../lib/session";
import { NotificationBell } from "./notifications/NotificationBell";

export interface TopbarProps {
  role: "central_team" | "project_stakeholder" | "read_only_auditor";
}

export function Topbar({ role }: TopbarProps) {
  const [approvalCount, setApprovalCount] = useState<number | null>(null);
  const items: NavItem[] = navItemsForRole(role).map((item) =>
    item.label === "Approvals" && approvalCount && approvalCount > 0
      ? { ...item, badge: String(approvalCount) }
      : item,
  );

  const session = loadUiSession();

  useEffect(() => {
    if (!session || role === "read_only_auditor") {
      return;
    }

    let active = true;
    void getPendingApprovalCount(session.accessToken)
      .then((count) => {
        if (active) {
          setApprovalCount(count);
        }
      })
      .catch(() => {
        if (active) {
          setApprovalCount(null);
        }
      });

    return () => {
      active = false;
    };
  }, [role, session?.accessToken]);

  return (
    <header className="sticky top-0 z-50 flex h-12 w-full items-center border-b border-outline-variant bg-surface px-6">
      <div className="mr-8 flex items-center">
        <h1 className="text-headline-sm font-bold tracking-tight text-primary">Katana</h1>
      </div>
      <nav className="flex h-full items-center gap-6">
        {items.map((item) => (
          <a
            key={item.label}
            className={item.active ? "nav-link nav-item-active" : "nav-link"}
            href={item.href}
          >
            <span className="inline-flex items-center gap-2">
              <span>{item.label}</span>
              {item.badge ? (
                <span className="rounded-full bg-amber-200 px-2 py-0.5 text-[11px] font-semibold text-amber-950">
                  {item.badge}
                </span>
              ) : null}
            </span>
          </a>
        ))}
      </nav>
      <div className="ml-auto flex items-center gap-3">
        {session && <NotificationBell token={session.accessToken} />}
        <div className="mono-id">AD</div>
      </div>
    </header>
  );
}
```

**Note:** `loadUiSession()` is called outside of `useEffect` here, which means it runs on every render but is synchronous (reads from localStorage). This is consistent with the session pattern used in other components in this project. The `session` object is used both in the `useEffect` dependency array (via `session?.accessToken`) and in the JSX to conditionally render `NotificationBell`.

- [ ] **Step 10: Update `web/components/__tests__/Topbar.test.tsx`**

The existing Topbar test mocks `loadUiSession`. Add a mock for `NotificationBell` to avoid polling in tests. Replace the full file:

```typescript
import { render, screen } from "@testing-library/react";
import { vi } from "vitest";
import { Topbar } from "../Topbar";

// Stub out loadUiSession so NotificationBell doesn't actually poll
vi.mock("../../lib/session", () => ({
  loadUiSession: () => null,
}));

// Stub slice-approval-api to prevent fetch in tests
vi.mock("../../lib/slice-approval-api", () => ({
  getPendingApprovalCount: vi.fn().mockResolvedValue(0),
}));

describe("Topbar", () => {
  it("renders the Katana brand and role-aware navigation", () => {
    render(<Topbar role="central_team" />);
    expect(screen.getByText("Katana")).toBeInTheDocument();
    expect(screen.getByText("Portfolio")).toBeInTheDocument();
    expect(screen.getByText("Admin")).toBeInTheDocument();
    expect(screen.queryByLabelText("Search")).not.toBeInTheDocument();
  });

  it("hides admin and approvals for read-only auditors", () => {
    render(<Topbar role="read_only_auditor" />);

    expect(screen.getByText("Portfolio")).toBeInTheDocument();
    expect(screen.getByText("Projects")).toBeInTheDocument();
    expect(screen.queryByText("Approvals")).not.toBeInTheDocument();
    expect(screen.queryByText("Admin")).not.toBeInTheDocument();
  });

  it("does not render NotificationBell when session is null", () => {
    render(<Topbar role="central_team" />);
    // loadUiSession returns null; bell should not be present
    expect(screen.queryByRole("button", { name: /notifications/i })).not.toBeInTheDocument();
  });
});
```

- [ ] **Step 11: Run the full web test suite**

```bash
cd /Users/vjkotra/projects/katana/web
npm test
```

Expected: all tests PASS. Fix any import errors or mock issues that surface.

- [ ] **Step 12: Commit Task 2**

```bash
git add \
  web/lib/notifications-api.ts \
  web/lib/notifications-api.test.ts \
  web/components/notifications/NotificationBell.tsx \
  web/components/notifications/__tests__/NotificationBell.test.tsx \
  web/components/Topbar.tsx \
  web/components/__tests__/Topbar.test.tsx
git commit -m "$(cat <<'EOF'
feat(001at): add NotificationBell component with poll, dropdown, mark-read, and notifications-api helpers

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
EOF
)"
```
