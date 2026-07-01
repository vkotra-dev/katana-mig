from __future__ import annotations

import uuid
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

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

from migrations_engine.api import deps as deps_module  # noqa: E402
from migrations_engine.api.deps import get_central_team_user, get_current_user  # noqa: E402
from migrations_engine.db import session as db_session  # noqa: E402

_original_engine = db_session.engine
_original_session_local = db_session.SessionLocal

db_session.engine = _sqlite_engine
db_session.SessionLocal = sessionmaker(
    bind=_sqlite_engine,
    autoflush=False,
    autocommit=False,
    class_=db_session.Session,
)
deps_module.SessionLocal = db_session.SessionLocal

from migrations_engine.app import app  # noqa: E402
from migrations_engine.db.base import Base  # noqa: E402
from migrations_engine.db.models import MappingSnapshot, ProjectDefinition, ProjectRegistry, RunRecord, User  # noqa: E402
from migrations_engine.db.session import SessionLocal  # noqa: E402
from migrations_engine.roles import CENTRAL_TEAM_ROLE, PROJECT_STAKEHOLDER_ROLE  # noqa: E402

client = TestClient(app)

_ADMIN_USER = SimpleNamespace(
    user_id=str(uuid.uuid4()),
    email="admin@example.com",
    display_name="Admin",
    role=CENTRAL_TEAM_ROLE,
    status="active",
)

_STAKEHOLDER_USER = SimpleNamespace(
    user_id=str(uuid.uuid4()),
    email="stakeholder@example.com",
    display_name="Stakeholder",
    role=PROJECT_STAKEHOLDER_ROLE,
    status="active",
)


@pytest.fixture(scope="module", autouse=True)
def _setup_sqlite_db() -> None:
    Base.metadata.create_all(bind=_sqlite_engine)

    with SessionLocal() as db:
        db.add(
            User(
                user_id=_ADMIN_USER.user_id,
                email=_ADMIN_USER.email,
                display_name=_ADMIN_USER.display_name,
                password_hash="hash",
                role=CENTRAL_TEAM_ROLE,
                status="active",
            )
        )
        db.add(
            User(
                user_id=_STAKEHOLDER_USER.user_id,
                email=_STAKEHOLDER_USER.email,
                display_name=_STAKEHOLDER_USER.display_name,
                password_hash="hash",
                role=PROJECT_STAKEHOLDER_ROLE,
                status="active",
            )
        )
        db.commit()

    app.dependency_overrides[get_current_user] = lambda: _ADMIN_USER
    app.dependency_overrides[get_central_team_user] = lambda: _ADMIN_USER
    yield
    app.dependency_overrides.clear()
    db_session.engine = _original_engine
    db_session.SessionLocal = _original_session_local


def _seed_rejected_run(*, with_mapping_snapshot: bool = True, with_sibling_run: bool = True) -> tuple[str, str]:
    project_id = str(uuid.uuid4())
    definition_id = str(uuid.uuid4())
    run_id = str(uuid.uuid4())

    with SessionLocal() as db:
        db.add(
            ProjectDefinition(
                definition_id=definition_id,
                project_id=project_id,
                name="Impact Review Project",
                status="active",
            )
        )
        db.add(
            ProjectRegistry(
                project_id=project_id,
                name="Impact Review Project",
                definition_id=definition_id,
                status="active",
            )
        )

        if with_mapping_snapshot:
            db.add(
                MappingSnapshot(
                    mapping_snapshot_id=str(uuid.uuid4()),
                    project_id=project_id,
                    destination_object_name="customers",
                    mapping_snapshot_version="v1",
                    field_bindings=[
                        {
                            "source_field": "legacy_code",
                            "destination_field": "account_type",
                            "lookup_name": "account_type",
                        }
                    ],
                    status="approved",
                    approved_at=datetime.now(UTC),
                    approved_by_user_id=None,
                )
            )

        db.add(
            RunRecord(
                run_id=run_id,
                project_id=project_id,
                destination_object_name="customers",
                mapping_snapshot_version="v1" if with_mapping_snapshot else None,
                status="paused",
                approvals=[
                    {
                        "gate": "gate_1",
                        "decision": "rejected",
                        "approver_user_id": "user-99",
                        "decided_at": "2026-07-01T10:00:00+00:00",
                        "affected_objects": ["customers", "orders"],
                        "required_changes": "ACCT_TYPE lookup missing RETD. Remove LEGACY_CODE binding.",
                        "notes": None,
                    }
                ],
            )
        )

        if with_sibling_run:
            db.add(
                RunRecord(
                    run_id=str(uuid.uuid4()),
                    project_id=project_id,
                    destination_object_name="orders",
                    status="running",
                )
            )

        db.commit()

    return project_id, run_id


def test_get_impact_returns_report() -> None:
    project_id, run_id = _seed_rejected_run()
    mock_ai_model = MagicMock()

    class _FakeAIResponse:
        recommendation = "Add RETD to account_type lookup and remove LEGACY_CODE from field bindings."
        suggested_fix = "1. Open account_type lookup fiber and add RETD. 2. Remove LEGACY_CODE binding."
        minimal_replay_scope = ["customers"]

    mock_ai_model.call.return_value = _FakeAIResponse()

    with patch("migrations_engine.management.impact.get_adapter", return_value=mock_ai_model):
        response = client.get(f"/projects/{project_id}/runs/{run_id}/impact")

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["run_id"] == run_id
    assert body["gate_rejection"]["affected_objects"] == ["customers", "orders"]
    assert len(body["replay_scope"]) == 1
    assert body["ai_recommendation"]["recommendation"].startswith("Add RETD")


def test_get_impact_can_work_without_mapping_snapshot() -> None:
    project_id, run_id = _seed_rejected_run(with_mapping_snapshot=False, with_sibling_run=False)
    mock_ai_model = MagicMock()

    class _FakeAIResponse:
        recommendation = "Check field mappings."
        suggested_fix = "Re-run mapping."
        minimal_replay_scope: list[str] = []

    mock_ai_model.call.return_value = _FakeAIResponse()

    with patch("migrations_engine.management.impact.get_adapter", return_value=mock_ai_model):
        response = client.get(f"/projects/{project_id}/runs/{run_id}/impact")

    assert response.status_code == 200, response.text
    assert response.json()["ai_recommendation"]["recommendation"] == "Check field mappings."


def test_get_impact_requires_project_access() -> None:
    project_id, run_id = _seed_rejected_run()
    mock_ai_model = MagicMock()

    class _FakeAIResponse:
        recommendation = "x"
        suggested_fix = "x"
        minimal_replay_scope: list[str] = []

    mock_ai_model.call.return_value = _FakeAIResponse()

    app.dependency_overrides[get_current_user] = lambda: _STAKEHOLDER_USER
    try:
        with patch("migrations_engine.management.impact.get_adapter", return_value=mock_ai_model):
            response = client.get(f"/projects/{project_id}/runs/{run_id}/impact")
    finally:
        app.dependency_overrides[get_current_user] = lambda: _ADMIN_USER

    assert response.status_code == 403


def test_acknowledge_returns_updated_run() -> None:
    project_id, run_id = _seed_rejected_run()

    response = client.post(f"/projects/{project_id}/runs/{run_id}/impact/acknowledge")

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["run_id"] == run_id
    assert body["status"] == "pending_gate_1"

    with SessionLocal() as db:
        run = db.get(RunRecord, run_id)
        assert run is not None
        assert run.status == "pending_gate_1"


def test_acknowledge_404_when_run_not_found() -> None:
    project_id = str(uuid.uuid4())
    definition_id = str(uuid.uuid4())

    with SessionLocal() as db:
        db.add(ProjectDefinition(definition_id=definition_id, project_id=project_id, name="P3", status="active"))
        db.add(ProjectRegistry(project_id=project_id, name="P3", definition_id=definition_id, status="active"))
        db.commit()

    response = client.post(f"/projects/{project_id}/runs/{str(uuid.uuid4())}/impact/acknowledge")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "run_not_found"


def test_acknowledge_404_when_no_gate1_rejection() -> None:
    project_id = str(uuid.uuid4())
    definition_id = str(uuid.uuid4())
    run_id = str(uuid.uuid4())

    with SessionLocal() as db:
        db.add(ProjectDefinition(definition_id=definition_id, project_id=project_id, name="P4", status="active"))
        db.add(ProjectRegistry(project_id=project_id, name="P4", definition_id=definition_id, status="active"))
        db.add(
            RunRecord(
                run_id=run_id,
                project_id=project_id,
                destination_object_name="orders",
                status="queued",
                approvals=[],
            )
        )
        db.commit()

    response = client.post(f"/projects/{project_id}/runs/{run_id}/impact/acknowledge")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "gate_1_not_rejected"


def test_acknowledge_requires_central_team() -> None:
    project_id, run_id = _seed_rejected_run()

    app.dependency_overrides[get_current_user] = lambda: _STAKEHOLDER_USER
    app.dependency_overrides[get_central_team_user] = lambda: _STAKEHOLDER_USER
    try:
        response = client.post(f"/projects/{project_id}/runs/{run_id}/impact/acknowledge")
    finally:
        app.dependency_overrides[get_current_user] = lambda: _ADMIN_USER
        app.dependency_overrides[get_central_team_user] = lambda: _ADMIN_USER

    assert response.status_code == 403
