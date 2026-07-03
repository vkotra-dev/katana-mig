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
from migrations_engine.db.models import ProjectDefinition, ProjectRegistry, RunRecord, User
from migrations_engine.execution.engine import list_knowledge_freezes
from migrations_engine.roles import CENTRAL_TEAM_ROLE

client = TestClient(app)


@pytest.fixture(scope="module", autouse=True)
def _setup_db() -> None:
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
                    display_name="Admin",
                    password_hash=hash_password(settings.bootstrap_admin_password),
                    role=CENTRAL_TEAM_ROLE,
                    status="active",
                )
            )
        db.commit()


@pytest.fixture(autouse=True)
def _clear_settings_cache() -> None:
    get_settings.cache_clear()


def _login() -> str:
    settings = get_settings()
    response = client.post(
        "/auth/login",
        json={
            "email": settings.bootstrap_admin_email,
            "password": settings.bootstrap_admin_password,
        },
    )
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def _create_project(db, name: str) -> str:
    project_id = str(uuid.uuid4())
    definition_id = str(uuid.uuid4())
    db.add(
        ProjectDefinition(
            definition_id=definition_id,
            project_id=project_id,
            name=name,
            status="active",
        )
    )
    db.add(
        ProjectRegistry(
            project_id=project_id,
            name=name,
            definition_id=definition_id,
            status="active",
        )
    )
    db.flush()
    return project_id


@pytest.fixture
def seeded_project_id() -> str:
    with SessionLocal() as db:
        project_id = _create_project(db, f"Freeze-{uuid.uuid4().hex[:8]}")
        db.add(
            RunRecord(
                run_id=str(uuid.uuid4()),
                project_id=project_id,
                destination_object_name="Customer",
                source_definition_reference="source-1",
                environment="UAT",
                status="completed",
                knowledge_freeze_version="cga-older",
                start_metadata={"started_at": "2026-07-01T09:00:00+00:00"},
                created_at=datetime(2026, 7, 1, 9, 5, tzinfo=UTC),
                updated_at=datetime(2026, 7, 1, 9, 5, tzinfo=UTC),
            )
        )
        db.add(
            RunRecord(
                run_id=str(uuid.uuid4()),
                project_id=project_id,
                destination_object_name="Order",
                source_definition_reference="source-2",
                environment="PROD",
                status="running",
                knowledge_freeze_version=None,
                created_at=datetime(2026, 7, 1, 9, 10, tzinfo=UTC),
                updated_at=datetime(2026, 7, 1, 9, 10, tzinfo=UTC),
            )
        )
        db.add(
            RunRecord(
                run_id=str(uuid.uuid4()),
                project_id=project_id,
                destination_object_name="Invoice",
                source_definition_reference="source-3",
                environment="PROD",
                status="completed",
                knowledge_freeze_version="cga-newer",
                start_metadata={"started_at": "2026-07-01T10:00:00+00:00"},
                created_at=datetime(2026, 7, 1, 10, 5, tzinfo=UTC),
                updated_at=datetime(2026, 7, 1, 10, 5, tzinfo=UTC),
            )
        )
        db.commit()
    return project_id


@pytest.fixture
def empty_project_id() -> str:
    with SessionLocal() as db:
        project_id = _create_project(db, f"FreezeEmpty-{uuid.uuid4().hex[:8]}")
        db.commit()
    return project_id


def test_list_knowledge_freezes_service_filters_and_sorts(seeded_project_id: str) -> None:
    with SessionLocal() as db:
        freezes = list_knowledge_freezes(db, project_id=seeded_project_id)

    assert [freeze["destination_object_name"] for freeze in freezes] == ["Invoice", "Customer"]
    assert [freeze["knowledge_freeze_version"] for freeze in freezes] == ["cga-newer", "cga-older"]
    assert freezes[0]["started_at"] == datetime(2026, 7, 1, 10, 0, tzinfo=UTC)
    assert freezes[1]["started_at"] == datetime(2026, 7, 1, 9, 0, tzinfo=UTC)


def test_get_knowledge_freezes_route_returns_only_frozen_runs(seeded_project_id: str) -> None:
    token = _login()
    response = client.get(
        f"/projects/{seeded_project_id}/knowledge-freezes",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert len(body) == 2
    assert [item["destination_object_name"] for item in body] == ["Invoice", "Customer"]
    assert body[0]["created_at"].startswith("2026-07-01T10:05:00")
    assert body[0]["knowledge_freeze_version"] == "cga-newer"


def test_get_knowledge_freezes_route_returns_empty_list_when_no_freezes(empty_project_id: str) -> None:
    token = _login()
    response = client.get(
        f"/projects/{empty_project_id}/knowledge-freezes",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200, response.text
    assert response.json() == []


def test_get_knowledge_freezes_requires_auth(seeded_project_id: str) -> None:
    response = client.get(f"/projects/{seeded_project_id}/knowledge-freezes")

    assert response.status_code == 401
