from __future__ import annotations

import uuid
from unittest import mock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
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
from migrations_engine.db.models import Feed, ProjectMembership, User  # noqa: E402
from migrations_engine.db.session import SessionLocal  # noqa: E402
from migrations_engine.roles import CENTRAL_TEAM_ROLE, PROJECT_STAKEHOLDER_ROLE  # noqa: E402

client = TestClient(app)

_STAKEHOLDER_EMAIL = "stakeholder@example.com"
_STAKEHOLDER_PASSWORD = "stakeholder-password"


@pytest.fixture(scope="module", autouse=True)
def _setup_sqlite_db() -> None:
    Base.metadata.create_all(bind=_sqlite_engine)

    settings = get_settings()
    if not settings.bootstrap_admin_email or not settings.bootstrap_admin_password:
        pytest.skip("bootstrap credentials not configured")

    with SessionLocal() as db:
        admin_email = settings.bootstrap_admin_email.strip().lower()
        if db.scalar(select(User).where(User.email == admin_email)) is None:
            db.add(
                User(
                    user_id=str(uuid.uuid4()),
                    email=admin_email,
                    display_name=settings.bootstrap_admin_display_name or "Admin User",
                    password_hash=hash_password(settings.bootstrap_admin_password),
                    role=CENTRAL_TEAM_ROLE,
                    status="active",
                )
            )
        if db.scalar(select(User).where(User.email == _STAKEHOLDER_EMAIL)) is None:
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
    project_resp = client.post(
        "/projects",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"name": f"Comment-Test-{uuid.uuid4().hex[:8]}"},
    )
    assert project_resp.status_code == 201, project_resp.text
    project_id = project_resp.json()["project_id"]

    if add_stakeholder:
        with SessionLocal() as db:
            stakeholder = db.scalar(select(User).where(User.email == _STAKEHOLDER_EMAIL))
            assert stakeholder is not None
            membership = db.scalar(
                select(ProjectMembership).where(
                    ProjectMembership.project_id == project_id,
                    ProjectMembership.user_id == stakeholder.user_id,
                )
            )
            if membership is None:
                db.add(ProjectMembership(project_id=project_id, user_id=stakeholder.user_id))
                db.commit()

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


def test_list_comments_empty_for_new_feed(admin_token: str) -> None:
    project_id, feed_id = _seed_project_with_feed(admin_token)

    response = client.get(
        f"/projects/{project_id}/feeds/{feed_id}/comments",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200, response.text
    assert response.json() == []


def test_list_comments_returns_created_comments(admin_token: str) -> None:
    project_id, feed_id = _seed_project_with_feed(admin_token)

    post_response = client.post(
        f"/projects/{project_id}/feeds/{feed_id}/comments",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"body": "ACCT_TYPE value RETD should map to Retired."},
    )
    assert post_response.status_code == 201, post_response.text

    list_response = client.get(
        f"/projects/{project_id}/feeds/{feed_id}/comments",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert list_response.status_code == 200, list_response.text
    items = list_response.json()
    assert len(items) == 1
    assert items[0]["body"] == "ACCT_TYPE value RETD should map to Retired."
    assert items[0]["feed_id"] == feed_id
    assert items[0]["role"] == CENTRAL_TEAM_ROLE
    assert "comment_id" in items[0]
    assert "user_id" in items[0]
    assert "created_at" in items[0]


def test_list_comments_requires_auth(admin_token: str) -> None:
    project_id, feed_id = _seed_project_with_feed(admin_token)

    response = client.get(f"/projects/{project_id}/feeds/{feed_id}/comments")
    assert response.status_code == 401


def test_list_comments_forbidden_for_non_member_stakeholder(
    admin_token: str, stakeholder_token: str
) -> None:
    project_id, feed_id = _seed_project_with_feed(admin_token, add_stakeholder=False)

    response = client.get(
        f"/projects/{project_id}/feeds/{feed_id}/comments",
        headers={"Authorization": f"Bearer {stakeholder_token}"},
    )
    assert response.status_code == 403


def test_list_comments_allowed_for_member_stakeholder(
    admin_token: str, stakeholder_token: str
) -> None:
    project_id, feed_id = _seed_project_with_feed(admin_token, add_stakeholder=True)

    response = client.get(
        f"/projects/{project_id}/feeds/{feed_id}/comments",
        headers={"Authorization": f"Bearer {stakeholder_token}"},
    )
    assert response.status_code == 200
    assert isinstance(response.json(), list)


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

    list_response = client.get(
        f"/projects/{project_id}/feeds/{feed_id}/comments",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    bodies = [item["body"] for item in list_response.json()]
    assert bodies == ["First comment", "Second comment"]


def test_post_comment_returns_201_with_full_shape(admin_token: str) -> None:
    project_id, feed_id = _seed_project_with_feed(admin_token)

    response = client.post(
        f"/projects/{project_id}/feeds/{feed_id}/comments",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"body": "ACCT_TYPE value RETD should map to Retired."},
    )

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["body"] == "ACCT_TYPE value RETD should map to Retired."
    assert body["feed_id"] == feed_id
    assert body["role"] == CENTRAL_TEAM_ROLE
    assert body["display_name"] is not None
    assert uuid.UUID(body["comment_id"])
    assert "created_at" in body


def test_post_comment_persists_to_db(admin_token: str) -> None:
    project_id, feed_id = _seed_project_with_feed(admin_token)

    response = client.post(
        f"/projects/{project_id}/feeds/{feed_id}/comments",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"body": "Persisted comment check"},
    )
    assert response.status_code == 201, response.text
    comment_id = response.json()["comment_id"]

    from migrations_engine.db.models import FeedComment

    with SessionLocal() as db:
        row = db.get(FeedComment, comment_id)
    assert row is not None
    assert row.body == "Persisted comment check"
    assert row.feed_id == feed_id


def test_post_comment_requires_auth(admin_token: str) -> None:
    project_id, feed_id = _seed_project_with_feed(admin_token)

    response = client.post(
        f"/projects/{project_id}/feeds/{feed_id}/comments",
        json={"body": "No auth"},
    )
    assert response.status_code == 401


def test_post_comment_forbidden_for_non_member_stakeholder(
    admin_token: str, stakeholder_token: str
) -> None:
    project_id, feed_id = _seed_project_with_feed(admin_token, add_stakeholder=False)

    response = client.post(
        f"/projects/{project_id}/feeds/{feed_id}/comments",
        headers={"Authorization": f"Bearer {stakeholder_token}"},
        json={"body": "Should be forbidden"},
    )
    assert response.status_code == 403


def test_post_comment_allowed_for_member_stakeholder(
    admin_token: str, stakeholder_token: str
) -> None:
    project_id, feed_id = _seed_project_with_feed(admin_token, add_stakeholder=True)

    response = client.post(
        f"/projects/{project_id}/feeds/{feed_id}/comments",
        headers={"Authorization": f"Bearer {stakeholder_token}"},
        json={"body": "Stakeholder comment"},
    )
    assert response.status_code == 201, response.text
    assert response.json()["role"] == PROJECT_STAKEHOLDER_ROLE
    assert response.json()["display_name"] == "Janet Smith"


def test_post_comment_rejects_empty_body(admin_token: str) -> None:
    project_id, feed_id = _seed_project_with_feed(admin_token)

    response = client.post(
        f"/projects/{project_id}/feeds/{feed_id}/comments",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"body": ""},
    )
    assert response.status_code == 422


def test_post_comment_notification_does_not_fail_if_stub_missing(admin_token: str) -> None:
    project_id, feed_id = _seed_project_with_feed(admin_token)

    with mock.patch(
        "migrations_engine.management.feed_comments.create_notification",
        side_effect=RuntimeError("notification service down"),
        create=True,
    ):
        response = client.post(
            f"/projects/{project_id}/feeds/{feed_id}/comments",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"body": "Notification should not block this"},
        )

    assert response.status_code == 201, response.text


def test_post_comment_notifies_stakeholders_for_central_team_comment(admin_token: str) -> None:
    project_id, feed_id = _seed_project_with_feed(admin_token, add_stakeholder=True)

    recipient_ids: list[str] = []

    def _record_notification(db, *, user_id: str, **kwargs):
        recipient_ids.append(user_id)
        return None

    with mock.patch("migrations_engine.management.feed_comments.create_notification", side_effect=_record_notification):
        response = client.post(
            f"/projects/{project_id}/feeds/{feed_id}/comments",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"body": "Operator comment"},
        )

    assert response.status_code == 201, response.text
    with SessionLocal() as db:
        stakeholder = db.scalar(select(User).where(User.email == _STAKEHOLDER_EMAIL))
        assert stakeholder is not None
    assert recipient_ids == [stakeholder.user_id]


def test_post_comment_notifies_central_team_for_stakeholder_comment(
    admin_token: str, stakeholder_token: str
) -> None:
    project_id, feed_id = _seed_project_with_feed(admin_token, add_stakeholder=True)

    recipient_ids: list[str] = []

    def _record_notification(db, *, user_id: str, **kwargs):
        recipient_ids.append(user_id)
        return None

    with mock.patch("migrations_engine.management.feed_comments.create_notification", side_effect=_record_notification):
        response = client.post(
            f"/projects/{project_id}/feeds/{feed_id}/comments",
            headers={"Authorization": f"Bearer {stakeholder_token}"},
            json={"body": "Stakeholder comment"},
        )

    assert response.status_code == 201, response.text
    with SessionLocal() as db:
        admin = db.scalar(select(User).where(User.email == get_settings().bootstrap_admin_email.strip().lower()))
        assert admin is not None
    assert recipient_ids == [admin.user_id]
