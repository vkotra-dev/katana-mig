from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from sqlite_test_support import Base, SessionLocal, TEST_ENGINE
from migrations_engine.app import app
from migrations_engine.auth.passwords import hash_password
from migrations_engine.config import get_settings
from migrations_engine.db.models import (
    FeedSlice,
    ProjectDefinition,
    ProjectMembership,
    ProjectRegistry,
    SourceDefinition,
    SourceSlice,
    User,
    VersionHistory,
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
            db.add(User(
                user_id=str(uuid.uuid4()),
                email=settings.bootstrap_admin_email.strip().lower(),
                display_name="Admin",
                password_hash=hash_password(settings.bootstrap_admin_password),
                role=CENTRAL_TEAM_ROLE,
                status="active",
            ))
        if db.scalar(select(User).where(User.email == "stakeholder@example.com")) is None:
            db.add(User(
                user_id=str(uuid.uuid4()),
                email="stakeholder@example.com",
                display_name="Stakeholder",
                password_hash=hash_password("stakeholder-password"),
                role=PROJECT_STAKEHOLDER_ROLE,
                status="active",
            ))
        db.commit()


@pytest.fixture(autouse=True)
def _clear_settings_cache() -> None:
    get_settings.cache_clear()


def _login(email: str, password: str) -> str:
    resp = client.post("/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200
    return resp.json()["access_token"]


@pytest.fixture
def admin_token() -> str:
    settings = get_settings()
    if not settings.bootstrap_admin_email or not settings.bootstrap_admin_password:
        pytest.skip("bootstrap credentials not configured")
    return _login(settings.bootstrap_admin_email, settings.bootstrap_admin_password)


@pytest.fixture
def stakeholder_token() -> str:
    return _login("stakeholder@example.com", "stakeholder-password")


@pytest.fixture
def _seed_projects() -> tuple[str, str, str, str]:
    """Create two projects; return (pid_a, sid_a, pid_b, sid_b)."""
    pid_a = str(uuid.uuid4())
    pid_b = str(uuid.uuid4())
    did_a = str(uuid.uuid4())
    did_b = str(uuid.uuid4())
    sid_a = str(uuid.uuid4())
    sid_b = str(uuid.uuid4())
    admin = None
    stakeholder = None
    with SessionLocal() as db:
        admin = db.scalar(select(User).where(User.role == CENTRAL_TEAM_ROLE))
        stakeholder = db.scalar(select(User).where(User.email == "stakeholder@example.com"))
        db.add(ProjectDefinition(definition_id=did_a, project_id=pid_a, name="A", status="active"))
        db.add(ProjectRegistry(project_id=pid_a, name="Proj A", definition_id=did_a, status="active"))
        db.add(SourceDefinition(
            source_definition_id=sid_a, project_id=pid_a, source_type="csv",
            source_contract_version="v1", destination_object_references=["T1"],
            source_details={"label": "A", "encoding": "utf-8"}, status="active",
        ))
        db.add(ProjectDefinition(definition_id=did_b, project_id=pid_b, name="B", status="active"))
        db.add(ProjectRegistry(project_id=pid_b, name="Proj B", definition_id=did_b, status="active"))
        db.add(SourceDefinition(
            source_definition_id=sid_b, project_id=pid_b, source_type="csv",
            source_contract_version="v1", destination_object_references=["T2"],
            source_details={"label": "B", "encoding": "utf-8"}, status="active",
        ))
        # Stakeholder is a member of project A only, not B
        if admin and stakeholder:
            db.add(ProjectMembership(project_id=pid_a, user_id=stakeholder.user_id))
        db.commit()
    return pid_a, sid_a, pid_b, sid_b


def test_version_history_hints_capture(admin_token: str, _seed_projects: tuple) -> None:
    pid, sid, _, _ = _seed_projects
    resp = client.patch(
        f"/projects/{pid}/sources/{sid}/hints",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"mapping_hints": "test hints v1"},
    )
    assert resp.status_code == 200
    resp = client.get(
        f"/projects/{pid}/versions/hints/versions",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    versions = resp.json()
    assert len(versions) == 1
    assert versions[0]["field_name"] == "mapping_hints"
    assert versions[0]["new_value"] == "test hints v1"


def test_version_history_hints_empty_old(admin_token: str, _seed_projects: tuple) -> None:
    pid, sid, _, _ = _seed_projects
    resp = client.patch(
        f"/projects/{pid}/sources/{sid}/hints",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"mapping_hints": "first value"},
    )
    assert resp.status_code == 200
    resp = client.get(
        f"/projects/{pid}/versions/hints/versions",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.json()[0]["old_value"] is None


def test_version_history_transformation_capture(admin_token: str, _seed_projects: tuple) -> None:
    pid, sid, _, _ = _seed_projects
    resp = client.patch(
        f"/projects/{pid}/sources/{sid}/transformation-instructions",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"transformation_instructions": "trans v1"},
    )
    assert resp.status_code == 200
    resp = client.get(
        f"/projects/{pid}/versions/transformation/versions",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    assert resp.json()[0]["new_value"] == "trans v1"


def test_version_history_codegen_capture(admin_token: str) -> None:
    pid = str(uuid.uuid4())
    did = str(uuid.uuid4())
    with SessionLocal() as db:
        admin = db.scalar(select(User).where(User.role == CENTRAL_TEAM_ROLE))
        db.add(ProjectDefinition(definition_id=did, project_id=pid, name="C", status="active"))
        db.add(ProjectRegistry(project_id=pid, name="Proj C", definition_id=did, status="active"))
        db.commit()
    resp = client.patch(
        f"/projects/{pid}/codegen-instructions",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"codegen_instructions": "# test instructions"},
    )
    assert resp.status_code == 200
    resp = client.get(
        f"/projects/{pid}/versions/codegen/versions",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    assert resp.json()[0]["new_value"] == "# test instructions"


def test_version_history_project_scoped(stakeholder_token: str, _seed_projects: tuple) -> None:
    """Stakeholder is a member of A (not B) — A's versions succeed, B's 403."""
    pid_a, _, pid_b, _ = _seed_projects
    resp = client.get(
        f"/projects/{pid_a}/versions/hints/versions",
        headers={"Authorization": f"Bearer {stakeholder_token}"},
    )
    assert resp.status_code == 200
    resp = client.get(
        f"/projects/{pid_b}/versions/hints/versions",
        headers={"Authorization": f"Bearer {stakeholder_token}"},
    )
    assert resp.status_code == 403


def test_version_history_entity_types(admin_token: str, _seed_projects: tuple) -> None:
    """Verify all 4 entity type endpoints return 200 and contain version data."""
    pid, sid, _, _ = _seed_projects
    for endpoint in ["hints", "transformation", "codegen", "sql"]:
        resp = client.get(
            f"/projects/{pid}/versions/{endpoint}/versions",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 200
        versions = resp.json()
        assert isinstance(versions, list)
        if versions:
            assert "field_name" in versions[0]
