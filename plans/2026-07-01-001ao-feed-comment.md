# FeedComment Model + Thread Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver the `FeedComment` DB model, Alembic migration `0020_feed_comments`, Pydantic schemas, two FastAPI endpoints (`GET`/`POST` feed comments), a best-effort notification side-effect, TypeScript API helpers in `feeds-api.ts`, and the `FeedCommentThread` React component — all with full TDD coverage.

**Architecture:**
- New router `routes/feed_comments.py` (`/projects/{project_id}/feeds/{feed_id}/comments`) registered in `app.py`.
- New service file `management/feed_comments.py` with `list_feed_comments` and `create_feed_comment`.
- Both endpoints require any project member (central_team has implicit access; project_stakeholder requires membership).
- After inserting a comment, `create_feed_comment` fires a best-effort notification by calling the `create_notification` stub from `management/notifications.py` inside a bare `try/except Exception: pass` so the endpoint never fails if the stub is missing or throws.
- `FeedCommentResponse` includes `display_name` and `role` resolved by joining the `users` table.
- Frontend: two new exports (`listFeedComments`, `createFeedComment`) added to the existing `web/lib/feeds-api.ts` (created by 001aj from the rename of `sources-api.ts`). New component `web/components/feeds/FeedCommentThread.tsx` fetches on mount, shows comments in a thread, and submits new ones.

**Tech Stack:** FastAPI, SQLAlchemy 2 (declarative mapped columns), Alembic, Pydantic v2, pytest, `TestClient`; Next.js App Router, TypeScript, React 19, Vitest, `@testing-library/react`

## Global Constraints

- Migration revision `"0020_feed_comments"` — `down_revision = "0019_fiber_models"` (001ak)
- `FeedComment.feed_id` is a FK to `feeds.source_definition_id` (the column stays `source_definition_id` after the 001aj table rename; the Python attribute is named `feed_id` and stored in a column called `feed_id`)
- `Feed` model class (post-001aj rename of `SourceDefinition`) must exist before this task is implemented
- Both endpoints return 403 if the actor has no project access; GET requires any project member; POST requires any project member
- Notification call is fire-and-forget: any exception (including `ImportError` when the stub doesn't exist yet) is silently swallowed
- Notification routing: commenter role `central_team` → notify active `project_stakeholder` members of the project; commenter role `project_stakeholder` → notify all active `central_team` users platform-wide
- All engine tests must pass: `cd engine && python -m pytest tests/ -x -q`
- All web tests must pass: `cd web && npm test -- --run`

## Objective

Add feed comments with a persistent thread endpoint and notification fan-out so operators and business users can collaborate on a feed.

## Out of Scope

- No general-purpose chat or markdown editor overhaul
- No unrelated notification settings UI
- No changes to feed analysis or codegen behavior

## File Changes

- See the blast radius table above for the exact backend and web files.

## Verification

- Run the new comment API tests
- Run the new thread component tests
- Run the touched backend and web suites for notifications and feed detail

## Pitfalls

- Keep comment creation idempotent enough for retries
- Preserve feed/project authorization
- Make sure notifications are emitted only for the intended audience

## Commit

- `feat(001ao): add feed comment thread`


---

## Blast radius

| File | Change |
|---|---|
| `engine/src/migrations_engine/db/models.py` | Add `FeedComment` model class |
| `engine/migrations/versions/0020_feed_comments.py` | Create — one new table |
| `engine/src/migrations_engine/api/schemas.py` | Add `FeedCommentCreateRequest`, `FeedCommentResponse` |
| `engine/src/migrations_engine/management/feed_comments.py` | Create — `list_feed_comments`, `create_feed_comment`, `_get_notification_recipients` |
| `engine/src/migrations_engine/routes/feed_comments.py` | Create — GET + POST handlers |
| `engine/src/migrations_engine/app.py` | Add `feed_comments_router` import + `include_router` |
| `engine/tests/test_feed_comments_api.py` | Create — full API test coverage |
| `web/lib/feeds-api.ts` | Add `FeedCommentRecord`, `listFeedComments`, `createFeedComment` |
| `web/lib/feeds-api.test.ts` | Add tests for the two new functions |
| `web/components/feeds/FeedCommentThread.tsx` | Create — comment thread UI |
| `web/components/feeds/__tests__/FeedCommentThread.test.tsx` | Create — component tests |

---

## Task 1: Backend — FeedComment model + migration + schema + endpoints + tests

**Files:**
- Modify: `engine/src/migrations_engine/db/models.py`
- Create: `engine/migrations/versions/0020_feed_comments.py`
- Modify: `engine/src/migrations_engine/api/schemas.py`
- Create: `engine/src/migrations_engine/management/feed_comments.py`
- Create: `engine/src/migrations_engine/routes/feed_comments.py`
- Modify: `engine/src/migrations_engine/app.py`
- Create: `engine/tests/test_feed_comments_api.py`

**Interfaces produced:**
- `FeedComment` SQLAlchemy model in `db/models.py`
- `FeedCommentCreateRequest` and `FeedCommentResponse` in `api/schemas.py`
- `list_feed_comments(db, *, project_id, feed_id) -> list[FeedCommentResponse]`
- `create_feed_comment(db, *, actor, project_id, feed_id, body) -> FeedCommentResponse`
- `GET /projects/{project_id}/feeds/{feed_id}/comments`
- `POST /projects/{project_id}/feeds/{feed_id}/comments` → 201

---

- [ ] **Step 1.1: Write the failing tests**

Create `engine/tests/test_feed_comments_api.py`:

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
    Feed,
    ProjectDefinition,
    ProjectMembership,
    ProjectRegistry,
    User,
)
from migrations_engine.db.session import SessionLocal  # noqa: E402
from migrations_engine.roles import CENTRAL_TEAM_ROLE, PROJECT_STAKEHOLDER_ROLE  # noqa: E402

client = TestClient(app)

_ADMIN_EMAIL = "admin@katana.io"
_ADMIN_PASSWORD = "admin-password"
_STAKEHOLDER_EMAIL = "stakeholder@example.com"
_STAKEHOLDER_PASSWORD = "stakeholder-password"


@pytest.fixture(scope="module", autouse=True)
def _setup_sqlite_db() -> None:
    Base.metadata.create_all(bind=_sqlite_engine)

    settings = get_settings()
    if not settings.bootstrap_admin_email or not settings.bootstrap_admin_password:
        pytest.skip("bootstrap credentials not configured")

    with SessionLocal() as db:
        db.add(
            User(
                user_id=str(uuid.uuid4()),
                email=settings.bootstrap_admin_email.strip().lower(),
                display_name=settings.bootstrap_admin_display_name or "Admin User",
                password_hash=hash_password(settings.bootstrap_admin_password),
                role=CENTRAL_TEAM_ROLE,
                status="active",
            )
        )
        db.add(
            User(
                user_id=str(uuid.uuid4()),
                email=_STAKEHOLDER_EMAIL,
                display_name="Janet Smith",
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
    return _login(_STAKEHOLDER_EMAIL, _STAKEHOLDER_PASSWORD)


def _seed_project_with_feed(admin_token: str, add_stakeholder: bool = False) -> tuple[str, str]:
    """Returns (project_id, feed_id)."""
    project_resp = client.post(
        "/projects",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"name": f"Comment-Test-{uuid.uuid4().hex[:8]}"},
    )
    assert project_resp.status_code == 201, project_resp.text
    project_id = project_resp.json()["project_id"]

    if add_stakeholder:
        with SessionLocal() as db:
            stakeholder = db.scalar(
                __import__("sqlalchemy", fromlist=["select"]).select(User).where(User.email == _STAKEHOLDER_EMAIL)
            )
            assert stakeholder is not None
            db.add(ProjectMembership(project_id=project_id, user_id=stakeholder.user_id))
            db.commit()

    # Create a feed directly in the DB (post-001aj: table is `feeds`, class is `Feed`)
    feed_id = str(uuid.uuid4())
    with SessionLocal() as db:
        db.add(
            Feed(
                source_definition_id=feed_id,
                project_id=project_id,
                source_type="csv",
                source_contract_version="v1",
                source_details={"label": "Customer Extract", "encoding": "utf-8"},
                status="active",
            )
        )
        db.commit()

    return project_id, feed_id


# ── GET /projects/{project_id}/feeds/{feed_id}/comments ─────────────────────


def test_list_comments_empty_for_new_feed(admin_token: str) -> None:
    project_id, feed_id = _seed_project_with_feed(admin_token)

    resp = client.get(
        f"/projects/{project_id}/feeds/{feed_id}/comments",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert resp.status_code == 200, resp.text
    assert resp.json() == []


def test_list_comments_returns_created_comments(admin_token: str) -> None:
    project_id, feed_id = _seed_project_with_feed(admin_token)

    # Post a comment first
    post_resp = client.post(
        f"/projects/{project_id}/feeds/{feed_id}/comments",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"body": "ACCT_TYPE value RETD should map to Retired."},
    )
    assert post_resp.status_code == 201, post_resp.text

    # List should return it
    list_resp = client.get(
        f"/projects/{project_id}/feeds/{feed_id}/comments",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert list_resp.status_code == 200, list_resp.text
    items = list_resp.json()
    assert len(items) == 1
    assert items[0]["body"] == "ACCT_TYPE value RETD should map to Retired."
    assert items[0]["feed_id"] == feed_id
    assert items[0]["role"] == CENTRAL_TEAM_ROLE
    assert "comment_id" in items[0]
    assert "user_id" in items[0]
    assert "created_at" in items[0]


def test_list_comments_requires_auth(admin_token: str) -> None:
    project_id, feed_id = _seed_project_with_feed(admin_token)

    resp = client.get(f"/projects/{project_id}/feeds/{feed_id}/comments")
    assert resp.status_code == 401


def test_list_comments_forbidden_for_non_member_stakeholder(
    admin_token: str, stakeholder_token: str
) -> None:
    project_id, feed_id = _seed_project_with_feed(admin_token, add_stakeholder=False)

    resp = client.get(
        f"/projects/{project_id}/feeds/{feed_id}/comments",
        headers={"Authorization": f"Bearer {stakeholder_token}"},
    )
    assert resp.status_code == 403


def test_list_comments_allowed_for_member_stakeholder(
    admin_token: str, stakeholder_token: str
) -> None:
    project_id, feed_id = _seed_project_with_feed(admin_token, add_stakeholder=True)

    resp = client.get(
        f"/projects/{project_id}/feeds/{feed_id}/comments",
        headers={"Authorization": f"Bearer {stakeholder_token}"},
    )
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_list_comments_ordered_oldest_first(admin_token: str) -> None:
    project_id, feed_id = _seed_project_with_feed(admin_token)

    client.post(
        f"/projects/{project_id}/feeds/{feed_id}/comments",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"body": "First comment"},
    )
    client.post(
        f"/projects/{project_id}/feeds/{feed_id}/comments",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"body": "Second comment"},
    )

    list_resp = client.get(
        f"/projects/{project_id}/feeds/{feed_id}/comments",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    bodies = [item["body"] for item in list_resp.json()]
    assert bodies == ["First comment", "Second comment"]


# ── POST /projects/{project_id}/feeds/{feed_id}/comments ─────────────────────


def test_post_comment_returns_201_with_full_shape(admin_token: str) -> None:
    project_id, feed_id = _seed_project_with_feed(admin_token)

    resp = client.post(
        f"/projects/{project_id}/feeds/{feed_id}/comments",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"body": "ACCT_TYPE value RETD should map to Retired."},
    )

    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["body"] == "ACCT_TYPE value RETD should map to Retired."
    assert body["feed_id"] == feed_id
    assert body["role"] == CENTRAL_TEAM_ROLE
    assert body["display_name"] is not None
    assert uuid.UUID(body["comment_id"])  # valid uuid
    assert "created_at" in body


def test_post_comment_persists_to_db(admin_token: str) -> None:
    project_id, feed_id = _seed_project_with_feed(admin_token)

    resp = client.post(
        f"/projects/{project_id}/feeds/{feed_id}/comments",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"body": "Persisted comment check"},
    )
    assert resp.status_code == 201, resp.text
    comment_id = resp.json()["comment_id"]

    from migrations_engine.db.models import FeedComment

    with SessionLocal() as db:
        row = db.get(FeedComment, comment_id)
    assert row is not None
    assert row.body == "Persisted comment check"
    assert row.feed_id == feed_id


def test_post_comment_requires_auth(admin_token: str) -> None:
    project_id, feed_id = _seed_project_with_feed(admin_token)

    resp = client.post(
        f"/projects/{project_id}/feeds/{feed_id}/comments",
        json={"body": "No auth"},
    )
    assert resp.status_code == 401


def test_post_comment_forbidden_for_non_member_stakeholder(
    admin_token: str, stakeholder_token: str
) -> None:
    project_id, feed_id = _seed_project_with_feed(admin_token, add_stakeholder=False)

    resp = client.post(
        f"/projects/{project_id}/feeds/{feed_id}/comments",
        headers={"Authorization": f"Bearer {stakeholder_token}"},
        json={"body": "Should be forbidden"},
    )
    assert resp.status_code == 403


def test_post_comment_allowed_for_member_stakeholder(
    admin_token: str, stakeholder_token: str
) -> None:
    project_id, feed_id = _seed_project_with_feed(admin_token, add_stakeholder=True)

    resp = client.post(
        f"/projects/{project_id}/feeds/{feed_id}/comments",
        headers={"Authorization": f"Bearer {stakeholder_token}"},
        json={"body": "Stakeholder comment"},
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["role"] == PROJECT_STAKEHOLDER_ROLE
    assert resp.json()["display_name"] == "Janet Smith"


def test_post_comment_rejects_empty_body(admin_token: str) -> None:
    project_id, feed_id = _seed_project_with_feed(admin_token)

    resp = client.post(
        f"/projects/{project_id}/feeds/{feed_id}/comments",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"body": ""},
    )
    assert resp.status_code == 422


def test_post_comment_notification_does_not_fail_if_stub_missing(
    admin_token: str,
) -> None:
    """Verify the endpoint succeeds even if notifications module raises."""
    project_id, feed_id = _seed_project_with_feed(admin_token)

    import unittest.mock as mock

    with mock.patch(
        "migrations_engine.management.feed_comments.create_notification",
        side_effect=RuntimeError("notification service down"),
        create=True,
    ):
        resp = client.post(
            f"/projects/{project_id}/feeds/{feed_id}/comments",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"body": "Notification should not block this"},
        )

    assert resp.status_code == 201, resp.text
```

Verify tests fail (no implementation yet):

```bash
cd /Users/vjkotra/projects/katana/engine && python -m pytest tests/test_feed_comments_api.py -x -q 2>&1 | head -30
```

Expected: `ImportError` or `ModuleNotFoundError` on `Feed`, `FeedComment`.

---

- [ ] **Step 1.2: Add `FeedComment` model to `db/models.py`**

Open `engine/src/migrations_engine/db/models.py`. After the last existing model class (before EOF), add:

```python
class FeedComment(Base):
    __tablename__ = "feed_comments"

    comment_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    feed_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("feeds.source_definition_id"), nullable=False, index=True
    )
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.user_id"), nullable=False
    )
    body: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
```

Note: `feed_id` references `feeds.source_definition_id` because the 001aj migration renames the `source_definitions` table to `feeds` while keeping the column name `source_definition_id`. The Python attribute `feed_id` maps to a DB column also named `feed_id`; the FK constraint points to `feeds.source_definition_id`.

---

- [ ] **Step 1.3: Create Alembic migration `0020_feed_comments`**

Create `engine/migrations/versions/0020_feed_comments.py`:

```python
"""add feed_comments table

Revision ID: 0020_feed_comments
Revises: 0019_fiber_models
Create Date: 2026-07-01
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0020_feed_comments"
down_revision = "0019_fiber_models"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "feed_comments",
        sa.Column("comment_id", sa.String(36), primary_key=True),
        sa.Column(
            "feed_id",
            sa.String(36),
            sa.ForeignKey("feeds.source_definition_id"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.String(36),
            sa.ForeignKey("users.user_id"),
            nullable=False,
        ),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_feed_comments_feed_id", "feed_comments", ["feed_id"])


def downgrade() -> None:
    op.drop_index("ix_feed_comments_feed_id", table_name="feed_comments")
    op.drop_table("feed_comments")
```

---

- [ ] **Step 1.4: Add Pydantic schemas to `api/schemas.py`**

Open `engine/src/migrations_engine/api/schemas.py`. Append at the end of the file:

```python
class FeedCommentCreateRequest(BaseModel):
    body: str = Field(min_length=1)


class FeedCommentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    comment_id: str
    feed_id: str
    user_id: str
    display_name: str | None
    role: str
    body: str
    created_at: datetime
```

---

- [ ] **Step 1.5: Create service `management/feed_comments.py`**

Create `engine/src/migrations_engine/management/feed_comments.py`:

```python
from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..api.deps import AuthApiError
from ..api.schemas import FeedCommentCreateRequest, FeedCommentResponse
from ..db.models import Feed, FeedComment, ProjectMembership, User, new_id
from ..management.access import require_project_access
from ..roles import CENTRAL_TEAM_ROLE, PROJECT_STAKEHOLDER_ROLE


def list_feed_comments(
    db: Session,
    *,
    project_id: str,
    feed_id: str,
) -> list[FeedCommentResponse]:
    _require_feed_in_project(db, project_id=project_id, feed_id=feed_id)

    rows = db.execute(
        select(FeedComment, User)
        .join(User, FeedComment.user_id == User.user_id)
        .where(FeedComment.feed_id == feed_id)
        .order_by(FeedComment.created_at.asc())
    ).all()

    return [
        FeedCommentResponse(
            comment_id=comment.comment_id,
            feed_id=comment.feed_id,
            user_id=comment.user_id,
            display_name=user.display_name,
            role=user.role,
            body=comment.body,
            created_at=comment.created_at,
        )
        for comment, user in rows
    ]


def create_feed_comment(
    db: Session,
    *,
    actor: User,
    project_id: str,
    feed_id: str,
    body: FeedCommentCreateRequest,
) -> FeedCommentResponse:
    _require_feed_in_project(db, project_id=project_id, feed_id=feed_id)

    comment = FeedComment(
        comment_id=new_id(),
        feed_id=feed_id,
        user_id=actor.user_id,
        body=body.body.strip(),
        created_at=datetime.now(UTC),
    )
    db.add(comment)
    db.commit()
    db.refresh(comment)

    response = FeedCommentResponse(
        comment_id=comment.comment_id,
        feed_id=comment.feed_id,
        user_id=comment.user_id,
        display_name=actor.display_name,
        role=actor.role,
        body=comment.body,
        created_at=comment.created_at,
    )

    _fire_notification(
        db,
        project_id=project_id,
        feed_id=feed_id,
        commenter_role=actor.role,
    )

    return response


# ── Private helpers ─────────────────────────────────────────────────────────


def _require_feed_in_project(db: Session, *, project_id: str, feed_id: str) -> None:
    feed = db.scalar(
        select(Feed).where(
            Feed.source_definition_id == feed_id,
            Feed.project_id == project_id,
        )
    )
    if feed is None:
        raise AuthApiError("not_found", "Feed not found in this project.", 404)


def _get_notification_recipients(
    db: Session, *, project_id: str, commenter_role: str
) -> list[str]:
    if commenter_role == CENTRAL_TEAM_ROLE:
        # Notify project_stakeholder members of this project
        rows = db.scalars(
            select(User.user_id)
            .join(ProjectMembership, User.user_id == ProjectMembership.user_id)
            .where(
                ProjectMembership.project_id == project_id,
                User.role == PROJECT_STAKEHOLDER_ROLE,
                User.status == "active",
            )
        ).all()
    else:
        # Notify all active central_team users platform-wide
        rows = db.scalars(
            select(User.user_id).where(
                User.role == CENTRAL_TEAM_ROLE,
                User.status == "active",
            )
        ).all()
    return list(rows)


def _fire_notification(
    db: Session,
    *,
    project_id: str,
    feed_id: str,
    commenter_role: str,
) -> None:
    try:
        from ..management.notifications import create_notification  # type: ignore[import]

        recipient_ids = _get_notification_recipients(
            db, project_id=project_id, commenter_role=commenter_role
        )
        create_notification(
            db,
            project_id=project_id,
            event_type="feed_comment_added",
            deep_link=f"/projects/{project_id}/feeds/{feed_id}",
            payload={"feed_id": feed_id},
            recipient_user_ids=recipient_ids,
        )
    except Exception:  # noqa: BLE001
        pass  # notifications are best-effort
```

---

- [ ] **Step 1.6: Create route file `routes/feed_comments.py`**

Create `engine/src/migrations_engine/routes/feed_comments.py`:

```python
from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from ..api.deps import get_current_user, get_db
from ..api.schemas import FeedCommentCreateRequest, FeedCommentResponse
from ..db.models import User
from ..management.access import require_project_access
from ..management.feed_comments import create_feed_comment, list_feed_comments

router = APIRouter(
    prefix="/projects/{project_id}/feeds/{feed_id}/comments",
    tags=["feed-comments"],
)


@router.get("", response_model=list[FeedCommentResponse])
def get_feed_comments(
    project_id: str,
    feed_id: str,
    actor: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[FeedCommentResponse]:
    require_project_access(db, user=actor, project_id=project_id)
    return list_feed_comments(db, project_id=project_id, feed_id=feed_id)


@router.post(
    "",
    response_model=FeedCommentResponse,
    status_code=status.HTTP_201_CREATED,
)
def post_feed_comment(
    project_id: str,
    feed_id: str,
    body: FeedCommentCreateRequest,
    actor: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FeedCommentResponse:
    require_project_access(db, user=actor, project_id=project_id)
    return create_feed_comment(
        db,
        actor=actor,
        project_id=project_id,
        feed_id=feed_id,
        body=body,
    )
```

---

- [ ] **Step 1.7: Register the router in `app.py`**

Open `engine/src/migrations_engine/app.py`. Add the import and `include_router` call.

In the imports block, after the existing router imports, add:

```python
from .routes.feed_comments import router as feed_comments_router
```

After `app.include_router(slice_approval_router)`, add:

```python
app.include_router(feed_comments_router)
```

---

- [ ] **Step 1.8: Run the tests and confirm green**

```bash
cd /Users/vjkotra/projects/katana/engine && python -m pytest tests/test_feed_comments_api.py -x -q
```

Expected: all tests pass.

Then verify no regressions in the full suite:

```bash
cd /Users/vjkotra/projects/katana/engine && python -m pytest tests/ -x -q
```

Expected: all tests pass.

---

## Task 2: Frontend API helpers in `feeds-api.ts` + tests

**Prerequisite:** 001aj must be complete so that `web/lib/feeds-api.ts` (renamed from `sources-api.ts`) and `web/lib/feeds-api.test.ts` (renamed from `sources-api.test.ts`) already exist.

**Files:**
- Modify: `web/lib/feeds-api.ts`
- Modify: `web/lib/feeds-api.test.ts`

**Interfaces produced:**
- `FeedCommentRecord` TypeScript interface
- `listFeedComments(token, projectId, feedId): Promise<FeedCommentRecord[]>`
- `createFeedComment(token, projectId, feedId, body): Promise<FeedCommentRecord>`

---

- [ ] **Step 2.1: Write the failing tests**

Open `web/lib/feeds-api.test.ts`. Add the following new `describe` block at the end of the file (after the existing `describe("feeds-api", ...)` block):

```typescript
// ── FeedComment helpers ──────────────────────────────────────────────────────

import {
  listFeedComments,
  createFeedComment,
  type FeedCommentRecord,
} from "./feeds-api";

const commentResponse = {
  comment_id: "comment-1",
  feed_id: "feed-1",
  user_id: "user-1",
  display_name: "Janet Smith",
  role: "project_stakeholder",
  body: "ACCT_TYPE value RETD should map to Retired.",
  created_at: "2026-07-01T10:00:00Z",
};

const comment: FeedCommentRecord = {
  commentId: "comment-1",
  feedId: "feed-1",
  userId: "user-1",
  displayName: "Janet Smith",
  role: "project_stakeholder",
  body: "ACCT_TYPE value RETD should map to Retired.",
  createdAt: "2026-07-01T10:00:00Z",
};

describe("feeds-api comment helpers", () => {
  it("listFeedComments fetches and maps comments", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => [commentResponse],
    });
    vi.stubGlobal("fetch", fetchMock);

    const result = await listFeedComments("token-1", "project-1", "feed-1");

    expect(fetchMock).toHaveBeenCalledWith(
      `${BASE}/projects/project-1/feeds/feed-1/comments`,
      expect.objectContaining({
        method: "GET",
        headers: expect.objectContaining({
          Authorization: "Bearer token-1",
        }),
      }),
    );
    expect(result).toHaveLength(1);
    expect(result[0]).toMatchObject(comment);
  });

  it("createFeedComment posts body and returns mapped comment", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => commentResponse,
    });
    vi.stubGlobal("fetch", fetchMock);

    const result = await createFeedComment(
      "token-1",
      "project-1",
      "feed-1",
      "ACCT_TYPE value RETD should map to Retired.",
    );

    expect(fetchMock).toHaveBeenCalledWith(
      `${BASE}/projects/project-1/feeds/feed-1/comments`,
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({
          body: "ACCT_TYPE value RETD should map to Retired.",
        }),
        headers: expect.objectContaining({
          Authorization: "Bearer token-1",
        }),
      }),
    );
    expect(result).toMatchObject(comment);
  });

  it("listFeedComments throws FeedApiError on non-ok response", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: false,
      status: 403,
      json: async () => ({ error: { code: "forbidden", message: "No access" } }),
    });
    vi.stubGlobal("fetch", fetchMock);

    await expect(
      listFeedComments("bad-token", "project-1", "feed-1"),
    ).rejects.toThrow("No access");
  });
});
```

Verify tests fail:

```bash
cd /Users/vjkotra/projects/katana/web && npm test -- --run feeds-api 2>&1 | tail -20
```

Expected: failures for `listFeedComments` and `createFeedComment` not found.

---

- [ ] **Step 2.2: Add types and functions to `feeds-api.ts`**

Open `web/lib/feeds-api.ts`. At the end of the file (after all existing exports), add:

```typescript
// ── FeedComment ──────────────────────────────────────────────────────────────

export interface FeedCommentRecord {
  commentId: string;
  feedId: string;
  userId: string;
  displayName: string | null;
  role: string;
  body: string;
  createdAt: string;
}

function mapFeedCommentResponse(response: {
  comment_id: string;
  feed_id: string;
  user_id: string;
  display_name: string | null;
  role: string;
  body: string;
  created_at: string;
}): FeedCommentRecord {
  return {
    commentId: response.comment_id,
    feedId: response.feed_id,
    userId: response.user_id,
    displayName: response.display_name,
    role: response.role,
    body: response.body,
    createdAt: response.created_at,
  };
}

export async function listFeedComments(
  token: string,
  projectId: string,
  feedId: string,
): Promise<FeedCommentRecord[]> {
  const response = await requestJson<
    Array<Parameters<typeof mapFeedCommentResponse>[0]>
  >(`/projects/${projectId}/feeds/${feedId}/comments`, {
    method: "GET",
    token,
  });
  return response.map(mapFeedCommentResponse);
}

export async function createFeedComment(
  token: string,
  projectId: string,
  feedId: string,
  body: string,
): Promise<FeedCommentRecord> {
  const response = await requestJson<
    Parameters<typeof mapFeedCommentResponse>[0]
  >(`/projects/${projectId}/feeds/${feedId}/comments`, {
    method: "POST",
    token,
    body: JSON.stringify({ body }),
  });
  return mapFeedCommentResponse(response);
}
```

Note: `requestJson` is the existing private helper already defined in `feeds-api.ts` (inherited from `sources-api.ts`). These additions use it directly.

---

- [ ] **Step 2.3: Run the tests and confirm green**

```bash
cd /Users/vjkotra/projects/katana/web && npm test -- --run feeds-api
```

Expected: all tests in `feeds-api.test.ts` pass (both pre-existing and newly added).

Then verify no regressions:

```bash
cd /Users/vjkotra/projects/katana/web && npm test -- --run
```

Expected: all web tests pass.

---

## Task 3: `FeedCommentThread` component + test

**Files:**
- Create: `web/components/feeds/FeedCommentThread.tsx`
- Create: `web/components/feeds/__tests__/FeedCommentThread.test.tsx`

**Interfaces consumed:**
- `listFeedComments` and `createFeedComment` from `../../lib/feeds-api`
- Props: `{ feedId: string; projectId: string; token: string }`

---

- [ ] **Step 3.1: Write the failing component test**

Create `web/components/feeds/__tests__/FeedCommentThread.test.tsx`:

```typescript
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { FeedCommentThread } from "../FeedCommentThread";

const { listFeedCommentsMock, createFeedCommentMock } = vi.hoisted(() => ({
  listFeedCommentsMock: vi.fn(),
  createFeedCommentMock: vi.fn(),
}));

vi.mock("../../../lib/feeds-api", () => ({
  listFeedComments: listFeedCommentsMock,
  createFeedComment: createFeedCommentMock,
}));

const mockComment = {
  commentId: "comment-1",
  feedId: "feed-abc",
  userId: "user-1",
  displayName: "Janet Smith",
  role: "project_stakeholder",
  body: "ACCT_TYPE value RETD should map to Retired.",
  createdAt: "2026-07-01T10:00:00Z",
};

describe("FeedCommentThread", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    listFeedCommentsMock.mockResolvedValue([mockComment]);
    createFeedCommentMock.mockResolvedValue({
      ...mockComment,
      commentId: "comment-2",
      body: "New comment from test",
    });
  });

  it("renders the section heading", async () => {
    render(
      <FeedCommentThread feedId="feed-abc" projectId="project-1" token="tok" />,
    );

    expect(await screen.findByRole("heading", { name: /comments/i })).toBeInTheDocument();
  });

  it("loads and displays comments on mount", async () => {
    render(
      <FeedCommentThread feedId="feed-abc" projectId="project-1" token="tok" />,
    );

    expect(
      await screen.findByText("ACCT_TYPE value RETD should map to Retired."),
    ).toBeInTheDocument();
    expect(screen.getByText("Janet Smith")).toBeInTheDocument();
    expect(screen.getByText("project_stakeholder")).toBeInTheDocument();

    expect(listFeedCommentsMock).toHaveBeenCalledWith("tok", "project-1", "feed-abc");
  });

  it("shows empty-state message when no comments exist", async () => {
    listFeedCommentsMock.mockResolvedValue([]);

    render(
      <FeedCommentThread feedId="feed-abc" projectId="project-1" token="tok" />,
    );

    expect(await screen.findByText(/no comments yet/i)).toBeInTheDocument();
  });

  it("renders the text area and submit button", async () => {
    render(
      <FeedCommentThread feedId="feed-abc" projectId="project-1" token="tok" />,
    );

    await screen.findByText("ACCT_TYPE value RETD should map to Retired.");

    expect(screen.getByPlaceholderText(/add a comment/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /add comment/i })).toBeInTheDocument();
  });

  it("submits a new comment and refreshes the list", async () => {
    listFeedCommentsMock
      .mockResolvedValueOnce([mockComment])
      .mockResolvedValueOnce([
        mockComment,
        { ...mockComment, commentId: "comment-2", body: "New comment from test" },
      ]);

    render(
      <FeedCommentThread feedId="feed-abc" projectId="project-1" token="tok" />,
    );

    await screen.findByText("ACCT_TYPE value RETD should map to Retired.");

    fireEvent.change(screen.getByPlaceholderText(/add a comment/i), {
      target: { value: "New comment from test" },
    });
    fireEvent.click(screen.getByRole("button", { name: /add comment/i }));

    await waitFor(() => {
      expect(createFeedCommentMock).toHaveBeenCalledWith(
        "tok",
        "project-1",
        "feed-abc",
        "New comment from test",
      );
    });

    expect(await screen.findByText("New comment from test")).toBeInTheDocument();
    // list should have been refetched after submit
    expect(listFeedCommentsMock).toHaveBeenCalledTimes(2);
  });

  it("clears the textarea after a successful submit", async () => {
    render(
      <FeedCommentThread feedId="feed-abc" projectId="project-1" token="tok" />,
    );

    await screen.findByText("ACCT_TYPE value RETD should map to Retired.");

    const textarea = screen.getByPlaceholderText(/add a comment/i);
    fireEvent.change(textarea, { target: { value: "Will be cleared" } });
    fireEvent.click(screen.getByRole("button", { name: /add comment/i }));

    await waitFor(() => expect(createFeedCommentMock).toHaveBeenCalled());

    expect(textarea).toHaveValue("");
  });

  it("disables submit button when textarea is empty", async () => {
    render(
      <FeedCommentThread feedId="feed-abc" projectId="project-1" token="tok" />,
    );

    await screen.findByText("ACCT_TYPE value RETD should map to Retired.");

    expect(screen.getByRole("button", { name: /add comment/i })).toBeDisabled();
  });

  it("shows an error message if listFeedComments fails", async () => {
    listFeedCommentsMock.mockRejectedValue(new Error("Network error"));

    render(
      <FeedCommentThread feedId="feed-abc" projectId="project-1" token="tok" />,
    );

    expect(await screen.findByRole("alert")).toBeInTheDocument();
    expect(screen.getByRole("alert")).toHaveTextContent(/unable to load comments/i);
  });
});
```

Verify the test fails because the component file doesn't exist:

```bash
cd /Users/vjkotra/projects/katana/web && npm test -- --run FeedCommentThread 2>&1 | tail -20
```

Expected: error on missing module.

---

- [ ] **Step 3.2: Create `web/components/feeds/FeedCommentThread.tsx`**

First create the `web/components/feeds/` directory by placing the file there directly.

Create `web/components/feeds/FeedCommentThread.tsx`:

```typescript
"use client";

import { useEffect, useState } from "react";
import {
  createFeedComment,
  listFeedComments,
  type FeedCommentRecord,
} from "../../lib/feeds-api";

export interface FeedCommentThreadProps {
  feedId: string;
  projectId: string;
  token: string;
}

function formatTimestamp(value: string): string {
  return value.replace("T", " ").slice(0, 16) + " UTC";
}

function RoleBadge({ role }: { role: string }) {
  const label =
    role === "central_team"
      ? "central_team"
      : role === "project_stakeholder"
        ? "project_stakeholder"
        : role;

  return (
    <span className="inline-flex items-center rounded px-1.5 py-0.5 text-xs font-medium ring-1 ring-inset ring-outline-variant bg-surface text-slate-600">
      {label}
    </span>
  );
}

export function FeedCommentThread({
  feedId,
  projectId,
  token,
}: FeedCommentThreadProps) {
  const [comments, setComments] = useState<FeedCommentRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [draft, setDraft] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const fetchComments = () => {
    setLoading(true);
    setErrorMessage(null);
    void listFeedComments(token, projectId, feedId)
      .then(setComments)
      .catch(() => setErrorMessage("Unable to load comments."))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    fetchComments();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectId, feedId, token]);

  const handleSubmit = () => {
    if (!draft.trim()) return;
    setSubmitting(true);
    void createFeedComment(token, projectId, feedId, draft.trim())
      .then(() => {
        setDraft("");
        fetchComments();
      })
      .finally(() => setSubmitting(false));
  };

  return (
    <section className="space-y-4 rounded-2xl border border-outline-variant bg-surface-container p-6 shadow-sm">
      <h2 className="text-xl font-semibold text-slate-900">Comments</h2>

      {loading ? (
        <div className="rounded-xl border border-outline-variant bg-surface px-4 py-3 text-sm text-slate-600">
          Loading comments...
        </div>
      ) : errorMessage ? (
        <div
          role="alert"
          className="rounded-xl border border-error/30 bg-error/10 px-4 py-3 text-sm text-error"
        >
          {errorMessage}
        </div>
      ) : comments.length === 0 ? (
        <div className="rounded-xl border border-dashed border-outline-variant bg-surface px-4 py-8 text-center text-sm text-slate-500">
          No comments yet.
        </div>
      ) : (
        <ul className="space-y-3">
          {comments.map((c) => (
            <li
              key={c.commentId}
              className="rounded-xl border border-outline-variant bg-surface px-4 py-3"
            >
              <div className="mb-1 flex flex-wrap items-center gap-2">
                <span className="text-sm font-semibold text-slate-900">
                  {c.displayName ?? c.userId}
                </span>
                <RoleBadge role={c.role} />
                <span className="ml-auto text-xs text-slate-500">
                  {formatTimestamp(c.createdAt)}
                </span>
              </div>
              <p className="text-sm text-slate-700">{c.body}</p>
            </li>
          ))}
        </ul>
      )}

      <div className="space-y-2 pt-2">
        <textarea
          className="w-full rounded-xl border border-outline-variant bg-surface px-3 py-2 text-sm text-slate-900 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-primary/40"
          placeholder="Add a comment…"
          rows={3}
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
        />
        <button
          className="rounded-md bg-primary px-4 py-2 text-sm font-semibold text-white disabled:opacity-40"
          disabled={!draft.trim() || submitting}
          onClick={handleSubmit}
          type="button"
        >
          Add comment
        </button>
      </div>
    </section>
  );
}
```

---

- [ ] **Step 3.3: Run the component tests and confirm green**

```bash
cd /Users/vjkotra/projects/katana/web && npm test -- --run FeedCommentThread
```

Expected: all 8 tests pass.

Then verify no regressions:

```bash
cd /Users/vjkotra/projects/katana/web && npm test -- --run
```

Expected: all web tests pass.

---

## Final verification

After all three tasks are complete, run the full test suites end-to-end to confirm no regressions.

```bash
cd /Users/vjkotra/projects/katana/engine && python -m pytest tests/ -x -q
```

```bash
cd /Users/vjkotra/projects/katana/web && npm test -- --run
```

Both must be green before marking this task complete.
