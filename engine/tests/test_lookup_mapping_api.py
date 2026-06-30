from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from migrations_engine.app import app
from migrations_engine.auth.passwords import hash_password
from migrations_engine.db.base import Base
from migrations_engine.config import get_settings
from migrations_engine.db.models import ProjectDefinition, ProjectRegistry, SourceDefinition, User
from migrations_engine.db.session import SessionLocal, engine
from migrations_engine.mapping import FieldBinding, create_approved_mapping_snapshot

client = TestClient(app)


@pytest.fixture(autouse=True)
def _clear_settings_cache() -> None:
    get_settings.cache_clear()


def _login(email: str, password: str) -> str:
    response = client.post("/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def _seed_lookup_context() -> tuple[str, str]:
    Base.metadata.create_all(bind=engine)
    project_id = str(uuid.uuid4())
    definition_id = str(uuid.uuid4())
    source_definition_id = str(uuid.uuid4())
    with SessionLocal() as db:
        db.add(
            ProjectDefinition(
                definition_id=definition_id,
                project_id=project_id,
                name="Lookup Project",
                status="active",
            )
        )
        db.add(
            ProjectRegistry(
                project_id=project_id,
                name="Lookup Project",
                definition_id=definition_id,
                status="active",
            )
        )
        db.add(
            SourceDefinition(
                source_definition_id=source_definition_id,
                project_id=project_id,
                source_type="csv",
                source_contract_version="v1",
                status="active",
            )
        )
        create_approved_mapping_snapshot(
            db,
            project_id=project_id,
            destination_object_name="Account",
            mapping_snapshot_version="v1",
            field_bindings=[
                FieldBinding(
                    source_field="status_code",
                    destination_field="status_id",
                    lookup_name="status_map",
                )
            ],
        )
        db.commit()
    return project_id, source_definition_id


@pytest.fixture
def admin_token() -> str:
    settings = get_settings()
    if not settings.bootstrap_admin_email or not settings.bootstrap_admin_password:
        pytest.skip("bootstrap credentials not configured")
    return _login(settings.bootstrap_admin_email, settings.bootstrap_admin_password)


@pytest.fixture
def stakeholder_token() -> str:
    user_id = str(uuid.uuid4())
    email = f"stakeholder-{user_id[:8]}@example.com"
    password = "stakeholder-password"
    with SessionLocal() as db:
        db.add(
            User(
                user_id=user_id,
                email=email,
                display_name="Stakeholder",
                password_hash=hash_password(password),
                role="project_stakeholder",
                status="active",
            )
        )
        db.commit()
    return _login(email, password)


def test_lookup_api_happy_path(admin_token: str) -> None:
    project_id, source_definition_id = _seed_lookup_context()

    created = client.post(
        f"/projects/{project_id}/sources/{source_definition_id}/lookup-maps",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "lookup_name": "status_map",
            "destination_table": [
                {"id": "ACTIVE", "label": "Active"},
                {"id": "BLOCKED", "label": "Blocked"},
            ],
        },
    )
    assert created.status_code == 201, created.text
    assert created.json()["status"] == "draft"

    with SessionLocal() as db:
        from migrations_engine.db.models import SourceValueSummary

        db.add(
            SourceValueSummary(
                source_definition_id=source_definition_id,
                source_slice_version="v1",
                field_name="status_code",
                value_counts={"ACTIVE": 1, "BLOCKED": 1},
            )
        )
        db.commit()

    listed = client.get(
        f"/projects/{project_id}/sources/{source_definition_id}/lookup-maps",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert listed.status_code == 200, listed.text
    assert len(listed.json()) == 1

    snapshot = client.post(
        f"/projects/{project_id}/sources/{source_definition_id}/lookup-snapshots",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"lookup_name": "status_map"},
    )
    assert snapshot.status_code == 201, snapshot.text
    assert snapshot.json()["status"] == "draft"

    approve = client.post(
        f"/projects/{project_id}/sources/{source_definition_id}/lookup-snapshots/{snapshot.json()['lookup_snapshot_id']}/approve",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert approve.status_code == 200, approve.text
    assert approve.json()["status"] == "approved"


def test_lookup_api_requires_central_team(stakeholder_token: str) -> None:
    project_id, source_definition_id = _seed_lookup_context()

    response = client.post(
        f"/projects/{project_id}/sources/{source_definition_id}/lookup-maps",
        headers={"Authorization": f"Bearer {stakeholder_token}"},
        json={
            "lookup_name": "status_map",
            "destination_table": [{"id": "ACTIVE", "label": "Active"}],
        },
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "forbidden"
