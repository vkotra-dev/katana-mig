from __future__ import annotations

from datetime import UTC, datetime
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from sqlite_test_support import Base, SessionLocal, TEST_ENGINE
from migrations_engine.app import app  # noqa: E402
from migrations_engine.auth.passwords import hash_password  # noqa: E402
from migrations_engine.config import get_settings  # noqa: E402
from migrations_engine.db.models import (  # noqa: E402
    ProjectDefinition,
    ProjectRegistry,
    SourceDefinition,
    SourceSlice,
    SourceValueSummary,
    User,
)
from migrations_engine.mapping.snapshots import FieldBinding, create_approved_mapping_snapshot  # noqa: E402
from migrations_engine.roles import CENTRAL_TEAM_ROLE, PROJECT_STAKEHOLDER_ROLE  # noqa: E402

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
        if db.scalar(select(User).where(User.email == "stakeholder@example.com")) is None:
            db.add(
                User(
                    user_id=str(uuid.uuid4()),
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


def _seed_project() -> tuple[str, str]:
    project_id = str(uuid.uuid4())
    definition_id = str(uuid.uuid4())
    source_definition_id = str(uuid.uuid4())
    with SessionLocal() as db:
        admin_user = db.scalar(select(User).where(User.role == CENTRAL_TEAM_ROLE))
        assert admin_user is not None
        db.add(
            ProjectDefinition(
                definition_id=definition_id,
                project_id=project_id,
                name="Lookup API Project",
                status="active",
            )
        )
        db.add(
            ProjectRegistry(
                project_id=project_id,
                name="Lookup API Project",
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
                destination_object_references=["Customer"],
                source_details={"label": "Customer Extract", "encoding": "utf-8"},
                status="active",
            )
        )
        db.add(
            SourceSlice(
                source_slice_id=str(uuid.uuid4()),
                source_definition_id=source_definition_id,
                source_contract_version="v1",
                source_slice_version="v1",
                source_schema_artifact=None,
                masking_policy={},
                header_csv="STATUS_CODE",
                slice_payload=None,
                status="approved",
                parse_warnings=[],
                file_storage_path="/tmp/source.csv",
                approved_at=datetime.now(UTC),
                approved_by_user_id=admin_user.user_id,
            )
        )
        db.add(
            SourceValueSummary(
                source_definition_id=source_definition_id,
                source_slice_version="v1",
                field_name="STATUS_CODE",
                value_counts={"A": 4, "B": 1},
            )
        )
        create_approved_mapping_snapshot(
            db,
            project_id=project_id,
            destination_object_name="Customer",
            mapping_snapshot_version="v1",
            field_bindings=[
                FieldBinding(
                    source_field="STATUS_CODE",
                    destination_field="status_id",
                    lookup_name="status_code",
                ),
            ],
            approved_by_user_id=admin_user.user_id,
        )
        db.commit()
    return project_id, source_definition_id


def test_lookup_routes_enforce_auth_and_contract(admin_token: str, stakeholder_token: str) -> None:
    project_id, source_definition_id = _seed_project()

    forbidden = client.post(
        f"/projects/{project_id}/sources/{source_definition_id}/lookup-maps",
        headers={"Authorization": f"Bearer {stakeholder_token}"},
        json={
            "lookup_name": "STATUS_CODE",
            "destination_table": [{"id": "ACTIVE", "label": "Active"}],
        },
    )
    assert forbidden.status_code == 403
    assert forbidden.json()["error"]["code"] == "forbidden"

    create = client.post(
        f"/projects/{project_id}/sources/{source_definition_id}/lookup-maps",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "lookup_name": "status_code",
            "destination_table": [{"id": "ACTIVE", "label": "Active"}],
            "source_value_map": {"A": "ACTIVE", "B": "ACTIVE"},
        },
    )
    assert create.status_code == 201, create.text
    assert create.json()["lookup_name"] == "status_code"

    mapping_snapshot = client.get(
        f"/projects/{project_id}/sources/{source_definition_id}/mapping-snapshot",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert mapping_snapshot.status_code == 200, mapping_snapshot.text
    assert mapping_snapshot.json()["mapping_snapshot_version"] == "v1"

    generate = client.post(
        f"/projects/{project_id}/sources/{source_definition_id}/lookup-snapshots",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "lookup_name": "status_code",
        },
    )
    assert generate.status_code == 201, generate.text
    assert generate.json()["lookup_snapshot_version"] == "v1"

    approve = client.post(
        f"/projects/{project_id}/lookup-snapshots/{generate.json()['lookup_snapshot_id']}/approve",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert approve.status_code == 200, approve.text
    assert approve.json()["status"] == "approved"
