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
    LookupDestEntry,
    LookupDestFeed,
    LookupMapping,
    LookupSourceEntry,
    ProjectDefinition,
    ProjectMembership,
    ProjectFiber,
    ProjectRegistry,
    User,
)
from migrations_engine.db.session import SessionLocal  # noqa: E402
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


def _create_project_and_feed(db) -> tuple[str, str]:
    project_id = str(uuid.uuid4())
    definition_id = str(uuid.uuid4())
    feed_id = str(uuid.uuid4())
    db.add(
        ProjectDefinition(
            definition_id=definition_id,
            project_id=project_id,
            name="Fiber Project",
            status="active",
        )
    )
    db.add(
        ProjectRegistry(
            project_id=project_id,
            name="Fiber Project",
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
            source_details={"label": "Customer Feed", "encoding": "utf-8"},
            status="active",
        )
    )
    db.commit()
    return project_id, feed_id


def test_fiber_models_exist_and_are_linked_to_feeds() -> None:
    assert ProjectFiber.__tablename__ == "project_fibers"
    assert LookupSourceEntry.__tablename__ == "lookup_source_entries"
    assert LookupDestFeed.__tablename__ == "lookup_dest_feeds"
    assert LookupDestEntry.__tablename__ == "lookup_dest_entries"
    assert LookupMapping.__tablename__ == "lookup_mappings"

    fiber_columns = {column.name for column in ProjectFiber.__table__.columns}
    assert {"fiber_id", "feed_id", "project_id", "fiber_type", "fiber_key", "status", "source"}.issubset(
        fiber_columns
    )

    feed_fk = next(iter(ProjectFiber.__table__.c.feed_id.foreign_keys))
    assert feed_fk.column.table.name == "source_definitions"
    assert feed_fk.column.name == "source_definition_id"


def test_fiber_crud_via_api(admin_token: str) -> None:
    with SessionLocal() as db:
        project_id, feed_id = _create_project_and_feed(db)

    create_response = client.post(
        f"/projects/{project_id}/feeds/{feed_id}/fibers",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "fiber_type": "lookup",
            "fiber_key": "status_code",
        },
    )
    assert create_response.status_code == 201, create_response.text
    fiber = create_response.json()
    assert fiber["project_id"] == project_id
    assert fiber["feed_id"] == feed_id
    assert fiber["fiber_type"] == "lookup"
    assert fiber["fiber_key"] == "status_code"
    assert fiber["source"] == "manual"
    fiber_id = fiber["fiber_id"]

    list_response = client.get(
        f"/projects/{project_id}/feeds/{feed_id}/fibers",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert list_response.status_code == 200, list_response.text
    assert len(list_response.json()) == 1
    assert list_response.json()[0]["fiber_id"] == fiber_id

    detail_response = client.get(
        f"/projects/{project_id}/feeds/{feed_id}/fibers/{fiber_id}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert detail_response.status_code == 200, detail_response.text
    assert detail_response.json()["fiber_id"] == fiber_id


def test_fiber_list_and_get_require_project_membership(admin_token: str) -> None:
    with SessionLocal() as db:
        project_id, feed_id = _create_project_and_feed(db)
        user_id = str(uuid.uuid4())
        email = f"fiber-member-{uuid.uuid4().hex[:8]}@example.com"
        db.add(
            User(
                user_id=user_id,
                email=email,
                display_name="Fiber Member",
                password_hash=hash_password("pass12345"),
                role=PROJECT_STAKEHOLDER_ROLE,
                status="active",
            )
        )
        db.add(ProjectMembership(project_id=project_id, user_id=user_id))
        db.commit()
    member_token = _login(email, "pass12345")

    list_response = client.get(
        f"/projects/{project_id}/feeds/{feed_id}/fibers",
        headers={"Authorization": f"Bearer {member_token}"},
    )
    assert list_response.status_code == 200, list_response.text

    detail_response = client.get(
        f"/projects/{project_id}/feeds/{feed_id}/fibers/does-not-exist",
        headers={"Authorization": f"Bearer {member_token}"},
    )
    assert detail_response.status_code == 404, detail_response.text
