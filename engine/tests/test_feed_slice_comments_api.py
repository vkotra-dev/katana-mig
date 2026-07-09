from datetime import datetime, UTC
import uuid
from typing import Any
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
from migrations_engine.db.models import Feed, FeedSlice, ProjectMembership, User  # noqa: E402
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
        if db.scalar(select(User).where(User.email == "pm@example.com")) is None:
            db.add(
                User(
                    user_id=str(uuid.uuid4()),
                    email="pm@example.com",
                    display_name="Project Manager",
                    password_hash=hash_password("pm-password"),
                    role="pm",
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


def _seed_project_with_feed_and_slice(admin_token: str) -> tuple[str, str, str]:
    pm_token = _login("pm@example.com", "pm-password")
    project_resp = client.post(
        "/projects",
        headers={"Authorization": f"Bearer {pm_token}"},
        json={"name": f"Comment-Test-{uuid.uuid4().hex[:8]}"},
    )
    assert project_resp.status_code == 201, project_resp.text
    project_id = project_resp.json()["project_id"]

    feed_id = str(uuid.uuid4())
    slice_id = str(uuid.uuid4())
    with SessionLocal() as db:
        db.add(
            Feed(
                source_definition_id=feed_id,
                project_id=project_id,
                source_type="csv",
                source_contract_version="v1",
                source_details={"label": "Comments Feed", "encoding": "utf-8"},
                status="active",
            )
        )
        db.add(
            FeedSlice(
                source_slice_id=slice_id,
                source_definition_id=feed_id,
                source_contract_version="v1",
                source_slice_version="v1.1",
                status="pending_approval",
                created_at=datetime.now(UTC) if hasattr(datetime, "now") else None,
            )
        )
        db.commit()

    return project_id, feed_id, slice_id


def test_list_slice_comments_empty_for_new_slice(admin_token: str) -> None:
    project_id, feed_id, slice_id = _seed_project_with_feed_and_slice(admin_token)

    response = client.get(
        f"/projects/{project_id}/sources/{feed_id}/slices/{slice_id}/comments",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200, response.text
    assert response.json() == []


def test_list_slice_comments_returns_created_comments(admin_token: str) -> None:
    project_id, feed_id, slice_id = _seed_project_with_feed_and_slice(admin_token)

    post_response = client.post(
        f"/projects/{project_id}/sources/{feed_id}/slices/{slice_id}/comments",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"body": "Slice looks good but needs date formatting corrections."},
    )
    assert post_response.status_code == 201, post_response.text

    list_response = client.get(
        f"/projects/{project_id}/sources/{feed_id}/slices/{slice_id}/comments",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert list_response.status_code == 200, list_response.text
    items = list_response.json()
    assert len(items) == 1
    assert items[0]["body"] == "Slice looks good but needs date formatting corrections."
    assert items[0]["source_slice_id"] == slice_id
    assert items[0]["role"] == CENTRAL_TEAM_ROLE
    assert "comment_id" in items[0]
    assert "user_id" in items[0]
    assert "created_at" in items[0]


def test_list_slice_comments_requires_auth(admin_token: str) -> None:
    project_id, feed_id, slice_id = _seed_project_with_feed_and_slice(admin_token)

    response = client.get(f"/projects/{project_id}/sources/{feed_id}/slices/{slice_id}/comments")
    assert response.status_code == 401


def test_post_slice_comment_rejects_empty_body(admin_token: str) -> None:
    project_id, feed_id, slice_id = _seed_project_with_feed_and_slice(admin_token)

    response = client.post(
        f"/projects/{project_id}/sources/{feed_id}/slices/{slice_id}/comments",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"body": "   "},
    )
    assert response.status_code == 422
