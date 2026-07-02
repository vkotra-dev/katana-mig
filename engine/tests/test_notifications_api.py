from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, delete, select
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
from migrations_engine.db.models import Notification, ProjectDefinition, ProjectRegistry, User  # noqa: E402
from migrations_engine.db.session import SessionLocal  # noqa: E402
from migrations_engine.management.notifications import create_notification  # noqa: E402
from migrations_engine.roles import CENTRAL_TEAM_ROLE  # noqa: E402

client = TestClient(app)


@pytest.fixture(scope="module", autouse=True)
def _setup_sqlite_db() -> None:
    Base.metadata.create_all(bind=_sqlite_engine)
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
            db.commit()


@pytest.fixture(autouse=True)
def _clear_settings_cache() -> None:
    get_settings.cache_clear()


@pytest.fixture(autouse=True)
def _clear_notifications() -> None:
    with SessionLocal() as db:
        db.execute(delete(Notification))
        db.commit()


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


def _create_project(db) -> tuple[str, str]:
    project_id = str(uuid.uuid4())
    definition_id = str(uuid.uuid4())
    db.add(
        ProjectDefinition(
            definition_id=definition_id,
            project_id=project_id,
            name="Notifications Project",
            status="active",
        )
    )
    db.add(
        ProjectRegistry(
            project_id=project_id,
            name="Notifications Project",
            definition_id=definition_id,
            status="active",
        )
    )
    db.flush()
    return project_id, definition_id


def _create_user(db, *, email: str, role: str = CENTRAL_TEAM_ROLE) -> str:
    user_id = str(uuid.uuid4())
    db.add(
        User(
            user_id=user_id,
            email=email,
            display_name=email.split("@", 1)[0].title(),
            password_hash=hash_password("password123"),
            role=role,
            status="active",
        )
    )
    db.flush()
    return user_id


def test_notification_model_is_registered() -> None:
    assert Notification.__tablename__ == "notifications"
    with SessionLocal() as db:
        assert db.scalar(select(Notification)) is None


def test_notifications_routes_require_authentication() -> None:
    assert client.get("/notifications").status_code == 401
    assert client.get("/notifications/count").status_code == 401
    assert client.post("/notifications/read-all").status_code == 401


def test_create_notification_inserts_row(admin_token: str) -> None:
    with SessionLocal() as db:
        project_id, _ = _create_project(db)
        user_id = _create_user(db, email="notified@example.com")

        notification_id = create_notification(
            db,
            user_id=user_id,
            project_id=project_id,
            event_type="gate_1_waiting",
            deep_link=f"/projects/{project_id}/runs/example",
            payload={"run_id": "example"},
        )
        db.commit()

        record = db.scalar(select(Notification).where(Notification.notification_id == notification_id))

    assert record is not None
    assert record.event_type == "gate_1_waiting"
    assert record.read is False


def test_list_notifications_returns_own_items_unread_first(admin_token: str) -> None:
    with SessionLocal() as db:
        project_id, _ = _create_project(db)
        user_id = db.scalar(
            select(User.user_id).where(User.email == get_settings().bootstrap_admin_email.strip().lower())
        )
        assert user_id is not None
        other_user_id = _create_user(db, email="other@example.com")
        create_notification(
            db,
            user_id=user_id,
            project_id=project_id,
            event_type="execution_complete",
            deep_link="/runs/one",
            payload=None,
        )
        create_notification(
            db,
            user_id=user_id,
            project_id=project_id,
            event_type="gate_2_waiting",
            deep_link="/runs/two",
            payload=None,
        )
        create_notification(
            db,
            user_id=other_user_id,
            project_id=project_id,
            event_type="feed_comment_added",
            deep_link="/feeds/one",
            payload=None,
        )
        db.commit()

    response = client.get("/notifications", headers={"Authorization": f"Bearer {admin_token}"})
    assert response.status_code == 200, response.text
    body = response.json()
    assert len(body) == 2
    assert [item["event_type"] for item in body] == ["execution_complete", "gate_2_waiting"]
    assert {item["user_id"] for item in body} == {user_id}


def test_get_notification_count_returns_unread_total(admin_token: str) -> None:
    with SessionLocal() as db:
        project_id, _ = _create_project(db)
        user_id = db.scalar(
            select(User.user_id).where(User.email == get_settings().bootstrap_admin_email.strip().lower())
        )
        assert user_id is not None
        create_notification(
            db,
            user_id=user_id,
            project_id=project_id,
            event_type="dry_run_waiting",
            deep_link="/runs/one",
            payload=None,
        )
        create_notification(
            db,
            user_id=user_id,
            project_id=project_id,
            event_type="lookup_delta_discovered",
            deep_link="/runs/two",
            payload=None,
        )
        db.commit()

    response = client.get("/notifications/count", headers={"Authorization": f"Bearer {admin_token}"})
    assert response.status_code == 200, response.text
    assert response.json() == {"unread_count": 2}


def test_mark_notification_read_and_read_all(admin_token: str) -> None:
    with SessionLocal() as db:
        project_id, _ = _create_project(db)
        user_id = db.scalar(
            select(User.user_id).where(User.email == get_settings().bootstrap_admin_email.strip().lower())
        )
        assert user_id is not None
        first_id = create_notification(
            db,
            user_id=user_id,
            project_id=project_id,
            event_type="reconciliation_failed",
            deep_link="/runs/one",
            payload=None,
        )
        second_id = create_notification(
            db,
            user_id=user_id,
            project_id=project_id,
            event_type="knowledge_freeze_published",
            deep_link="/runs/two",
            payload=None,
        )
        db.commit()

    mark_one_response = client.post(
        f"/notifications/{first_id}/read",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert mark_one_response.status_code == 200, mark_one_response.text
    assert mark_one_response.json()["notification_id"] == first_id
    assert mark_one_response.json()["read"] is True

    mark_all_response = client.post(
        "/notifications/read-all",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert mark_all_response.status_code == 200, mark_all_response.text
    assert mark_all_response.json()["marked_count"] == 1

    with SessionLocal() as db:
        first = db.scalar(select(Notification).where(Notification.notification_id == first_id))
        second = db.scalar(select(Notification).where(Notification.notification_id == second_id))

    assert first is not None and first.read is True
    assert second is not None and second.read is True
