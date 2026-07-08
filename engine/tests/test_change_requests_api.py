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


def _create_project(db, name: str) -> tuple[str, str]:
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
    return project_id, definition_id


@pytest.fixture
def seed_change_request() -> dict[str, str]:
    project_id = str(uuid.uuid4())
    source_definition_id = str(uuid.uuid4())
    run_id = str(uuid.uuid4())
    lookup_value_map_id = str(uuid.uuid4())
    open_cr_id = str(uuid.uuid4())
    closed_cr_id = str(uuid.uuid4())

    with SessionLocal() as db:
        stakeholder = db.scalar(select(User).where(User.email == "cr-stakeholder@example.com"))
        assert stakeholder is not None

        project_id, definition_id = _create_project(db, f"CR-{uuid.uuid4().hex[:8]}")
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
                    "change_request_id": open_cr_id,
                    "last_completed_row": 5,
                    "paused_at": datetime.now(UTC).isoformat(),
                },
                updated_at=datetime(2026, 7, 1, 10, 0, tzinfo=UTC),
            )
        )
        db.add(
            LookupValueMap(
                lookup_value_map_id=lookup_value_map_id,
                project_id=project_id,
                lookup_name="account_type",
                destination_table=[
                    {"id": "ACTIVE", "label": "Active"},
                    {"id": "CLOSED", "label": "Closed"},
                ],
                source_value_map={"ACT": "ACTIVE", "CLS": "CLOSED"},
                status="draft",
            )
        )
        db.add(
            ChangeRequest(
                change_request_id=open_cr_id,
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
        db.add(
            ChangeRequest(
                change_request_id=closed_cr_id,
                project_id=project_id,
                change_request_type="lookup_delta",
                status="resolved",
                title="Already closed",
                payload={
                    "run_id": run_id,
                    "lookup_name": "account_type",
                    "unmapped_value": "X",
                    "destination_object_name": "customers",
                },
                closed_at=datetime(2026, 7, 1, 11, 0, tzinfo=UTC),
            )
        )
        db.commit()

    return {
        "project_id": project_id,
        "source_definition_id": source_definition_id,
        "run_id": run_id,
        "lookup_value_map_id": lookup_value_map_id,
        "open_cr_id": open_cr_id,
        "closed_cr_id": closed_cr_id,
    }


def test_list_change_requests_requires_auth(seed_change_request: dict[str, str]) -> None:
    response = client.get(f"/projects/{seed_change_request['project_id']}/change-requests")
    assert response.status_code == 401


def test_list_change_requests_returns_open_cr(admin_token: str, seed_change_request: dict[str, str]) -> None:
    response = client.get(
        f"/projects/{seed_change_request['project_id']}/change-requests",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert isinstance(data, list)
    cr = next(item for item in data if item["change_request_id"] == seed_change_request["open_cr_id"])
    assert cr["change_request_type"] == "lookup_delta"
    assert cr["status"] == "open"
    assert cr["title"] == "Lookup delta for account_type"
    assert "payload" not in cr
    assert all(item["status"] == "open" for item in data)


def test_get_change_request_returns_detail(admin_token: str, seed_change_request: dict[str, str]) -> None:
    response = client.get(
        f"/projects/{seed_change_request['project_id']}/change-requests/{seed_change_request['open_cr_id']}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["change_request_id"] == seed_change_request["open_cr_id"]
    assert data["payload"]["run_id"] == seed_change_request["run_id"]
    assert data["payload"]["lookup_name"] == "account_type"
    assert data["payload"]["unmapped_value"] == "RETD"
    assert data["payload"]["destination_object_name"] == "customers"
    assert "updated_at" in data


def test_get_change_request_404_wrong_project(admin_token: str, seed_change_request: dict[str, str]) -> None:
    wrong_project = str(uuid.uuid4())
    definition_id = str(uuid.uuid4())
    with SessionLocal() as db:
        db.add(ProjectDefinition(definition_id=definition_id, project_id=wrong_project, name="Wrong Project", status="active"))
        db.add(ProjectRegistry(project_id=wrong_project, name="Wrong Project", definition_id=definition_id, status="active"))
        db.commit()

    response = client.get(
        f"/projects/{wrong_project}/change-requests/{seed_change_request['open_cr_id']}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "change_request_not_found"


def test_resolve_requires_auth(seed_change_request: dict[str, str]) -> None:
    response = client.post(
        f"/projects/{seed_change_request['project_id']}/change-requests/{seed_change_request['open_cr_id']}/resolve",
        json={"accepted_value": "RETIRED"},
    )
    assert response.status_code == 401


def test_resolve_forbidden_for_non_stakeholder(admin_token: str, seed_change_request: dict[str, str]) -> None:
    response = client.post(
        f"/projects/{seed_change_request['project_id']}/change-requests/{seed_change_request['open_cr_id']}/resolve",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"accepted_value": "RETIRED"},
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "forbidden"


def test_resolve_change_request_success(stakeholder_token: str, seed_change_request: dict[str, str]) -> None:
    response = client.post(
        f"/projects/{seed_change_request['project_id']}/change-requests/{seed_change_request['open_cr_id']}/resolve",
        headers={"Authorization": f"Bearer {stakeholder_token}"},
        json={"accepted_value": "RETIRED"},
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["change_request_id"] == seed_change_request["open_cr_id"]
    assert data["status"] == "resolved"

    with SessionLocal() as db:
        cr = db.get(ChangeRequest, seed_change_request["open_cr_id"])
        assert cr is not None
        assert cr.status == "resolved"
        assert cr.closed_at is not None

        run = db.get(RunRecord, seed_change_request["run_id"])
        assert run is not None
        assert run.status == "queued"
        assert run.pause_metadata is None

        lvm = db.get(LookupValueMap, seed_change_request["lookup_value_map_id"])
        assert lvm is not None
        assert lvm.source_value_map.get("RETD") == "RETIRED"

        snapshot = db.scalar(
            select(LookupSnapshot)
            .where(
                LookupSnapshot.project_id == seed_change_request["project_id"],
                LookupSnapshot.lookup_name == "account_type",
            )
            .order_by(LookupSnapshot.created_at.desc(), LookupSnapshot.lookup_snapshot_id.desc())
        )
        assert snapshot is not None
        assert snapshot.status == "approved"
        assert snapshot.value_map.get("RETD") == "RETIRED"
        assert snapshot.approved_at is not None


def test_resolve_409_cr_not_open(stakeholder_token: str, seed_change_request: dict[str, str]) -> None:
    first = client.post(
        f"/projects/{seed_change_request['project_id']}/change-requests/{seed_change_request['open_cr_id']}/resolve",
        headers={"Authorization": f"Bearer {stakeholder_token}"},
        json={"accepted_value": "RETIRED"},
    )
    assert first.status_code == 200

    second = client.post(
        f"/projects/{seed_change_request['project_id']}/change-requests/{seed_change_request['open_cr_id']}/resolve",
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
