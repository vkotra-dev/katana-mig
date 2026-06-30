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
    LookupValueMap,
    MappingSnapshot,
    ProjectDefinition,
    ProjectRegistry,
    RunRecord,
    SourceDefinition,
    SourceSchemaArtifact,
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


def _seed_gate_run() -> tuple[str, str, str]:
    project_id = str(uuid.uuid4())
    definition_id = str(uuid.uuid4())
    source_definition_id = str(uuid.uuid4())
    run_id = str(uuid.uuid4())

    with SessionLocal() as db:
        db.add(
            ProjectDefinition(
                definition_id=definition_id,
                project_id=project_id,
                name="Gate Review Project",
                status="active",
            )
        )
        db.add(
            ProjectRegistry(
                project_id=project_id,
                name="Gate Review Project",
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
                source_details={"label": "Customer Extract", "encoding": "utf-8"},
                destination_object_references=["Customer"],
                status="active",
            )
        )
        db.add(
            SourceSchemaArtifact(
                schema_artifact_id=str(uuid.uuid4()),
                source_definition_id=source_definition_id,
                source_slice_version="v1",
                columns=[
                    {"name": "customer_id", "inferred_type": "text", "nullable": False, "max_length": None},
                    {"name": "email", "inferred_type": "text", "nullable": True, "max_length": 255},
                    {"name": "notes", "inferred_type": "text", "nullable": True, "max_length": None},
                ],
            )
        )
        db.add(
            MappingSnapshot(
                mapping_snapshot_id=str(uuid.uuid4()),
                project_id=project_id,
                destination_object_name="Customer",
                mapping_snapshot_version="v1",
                field_bindings=[
                    {"source_field": "customer_id", "destination_field": "customer_id", "lookup_name": None},
                    {"source_field": "status_code", "destination_field": "status", "lookup_name": "status_map"},
                ],
                status="approved",
            )
        )
        db.add(
            LookupValueMap(
                lookup_value_map_id=str(uuid.uuid4()),
                source_definition_id=source_definition_id,
                lookup_name="status_map",
                destination_table=[{"id": "ACTIVE", "label": "Active"}],
                source_value_map={"A": "ACTIVE", "B": "MISSING"},
                status="approved",
            )
        )
        db.add(
            RunRecord(
                run_id=run_id,
                project_id=project_id,
                destination_object_name="Customer",
                source_definition_reference=source_definition_id,
                status="queued",
                approvals=[],
            )
        )
        db.commit()

    return project_id, source_definition_id, run_id


def test_gate_status_and_evidence(admin_token: str) -> None:
    project_id, _, run_id = _seed_gate_run()

    status_response = client.get(
        f"/projects/{project_id}/runs/{run_id}/gates",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert status_response.status_code == 200, status_response.text
    assert status_response.json() == {"run_id": run_id, "gate_1": None, "gate_2": None}

    gate1_response = client.get(
        f"/projects/{project_id}/runs/{run_id}/gates/gate-1/evidence",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert gate1_response.status_code == 200, gate1_response.text
    gate1 = gate1_response.json()
    assert gate1["destination_object_name"] == "Customer"
    assert gate1["mapping_snapshot_version"] == "v1"
    assert [binding["source_field"] for binding in gate1["field_bindings"]] == ["customer_id", "status_code"]
    assert "email" in gate1["pii_fields"]
    assert "notes" in gate1["coverage_gaps"]

    gate2_response = client.get(
        f"/projects/{project_id}/runs/{run_id}/gates/gate-2/evidence",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert gate2_response.status_code == 200, gate2_response.text
    gate2 = gate2_response.json()
    assert gate2["lookup_name"] == "status_map"
    assert gate2["confirmed_count"] == 1
    assert gate2["unmapped_count"] == 1


def test_gate_approval_and_rejection_flow(admin_token: str) -> None:
    project_id, _, run_id = _seed_gate_run()

    gate1_approve = client.post(
        f"/projects/{project_id}/runs/{run_id}/gates/gate-1/approve",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"notes": "Looks good."},
    )
    assert gate1_approve.status_code == 200, gate1_approve.text
    gate1 = gate1_approve.json()
    assert gate1["gate_1"]["decision"] == "approved"
    assert gate1["gate_2"] is None

    gate1_duplicate = client.post(
        f"/projects/{project_id}/runs/{run_id}/gates/gate-1/approve",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"notes": "Looks good."},
    )
    assert gate1_duplicate.status_code == 422
    assert gate1_duplicate.json()["error"]["code"] == "gate_already_approved"

    gate2_reject = client.post(
        f"/projects/{project_id}/runs/{run_id}/gates/gate-2/reject",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "affected_objects": ["Customer"],
            "required_changes": "Resolve unmapped lookup values.",
            "notes": "Push back for cleanup.",
        },
    )
    assert gate2_reject.status_code == 200, gate2_reject.text
    gate2 = gate2_reject.json()
    assert gate2["gate_1"]["decision"] == "approved"
    assert gate2["gate_2"]["decision"] == "rejected"

    with SessionLocal() as db:
        run = db.get(RunRecord, run_id)
        assert run is not None
        assert run.status == "paused"
        assert run.pause_metadata is not None
        assert run.pause_metadata["gate"] == "gate_2"
        assert run.pause_metadata["reason"] == "Resolve unmapped lookup values."


def test_gate_2_requires_gate_1_approval(admin_token: str) -> None:
    project_id, _, run_id = _seed_gate_run()

    gate2_approve = client.post(
        f"/projects/{project_id}/runs/{run_id}/gates/gate-2/approve",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"notes": "Ready."},
    )
    assert gate2_approve.status_code == 422
    assert gate2_approve.json()["error"]["code"] == "gate_1_not_approved"


def test_gate_buttons_are_role_scoped(stakeholder_token: str) -> None:
    project_id, _, run_id = _seed_gate_run()

    gate1_approve = client.post(
        f"/projects/{project_id}/runs/{run_id}/gates/gate-1/approve",
        headers={"Authorization": f"Bearer {stakeholder_token}"},
        json={"notes": "Looks good."},
    )
    assert gate1_approve.status_code == 403
