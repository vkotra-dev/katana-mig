from __future__ import annotations

import uuid

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

from migrations_engine.api import deps as deps_module  # noqa: E402
from migrations_engine.auth.passwords import hash_password  # noqa: E402
from migrations_engine.config import get_settings  # noqa: E402
from migrations_engine.db import session as db_session  # noqa: E402

_original_engine = db_session.engine
_original_session_local = db_session.SessionLocal
_original_deps_session_local = deps_module.SessionLocal

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
from migrations_engine.db.models import DryRunArtifact, ProjectDefinition, ProjectRegistry, RunRecord, User  # noqa: E402
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

    yield
    db_session.engine = _original_engine
    db_session.SessionLocal = _original_session_local
    deps_module.SessionLocal = _original_deps_session_local


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


def _seed_dry_run_state() -> tuple[str, str]:
    project_id = str(uuid.uuid4())
    definition_id = str(uuid.uuid4())
    run_id = str(uuid.uuid4())
    artifact_id = str(uuid.uuid4())

    with SessionLocal() as db:
        db.add(
            ProjectDefinition(
                definition_id=definition_id,
                project_id=project_id,
                name="DryRun Project",
                status="active",
            )
        )
        db.add(
            ProjectRegistry(
                project_id=project_id,
                name="DryRun Project",
                definition_id=definition_id,
                status="active",
            )
        )
        db.add(
            RunRecord(
                run_id=run_id,
                project_id=project_id,
                destination_object_name="customers",
                status="dry_run_review",
                approvals=[],
            )
        )
        db.add(
            DryRunArtifact(
                dry_run_artifact_id=artifact_id,
                run_id=run_id,
                project_id=project_id,
                destination_object_name="customers",
                success_count=1840,
                failure_count=2,
                field_coverage_pct=94.3,
                pii_fields=[{"field": "SURNAME", "token": "EMAIL_XXXX"}],
                sample_rows=[{"source": {"CUST_ID": "100042"}, "mapped": {"customer_id": "100042"}}],
                failures=[{"row_index": 141, "reason": "unmapped_lookup", "field": "ACCT_TYPE", "value": "RETD"}],
                push_back_comment=None,
                status="pending",
            )
        )
        db.commit()

    return project_id, run_id


def test_get_dry_run_artifact(admin_token: str) -> None:
    project_id, run_id = _seed_dry_run_state()

    response = client.get(
        f"/projects/{project_id}/runs/{run_id}/dry-run",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["destination_object_name"] == "customers"
    assert body["success_count"] == 1840
    assert body["failure_count"] == 2
    assert abs(body["field_coverage_pct"] - 94.3) < 0.01
    assert body["pii_fields"] == [{"field": "SURNAME", "token": "EMAIL_XXXX"}]
    assert len(body["sample_rows"]) == 1
    assert body["failures"][0]["row_index"] == 141
    assert body["status"] == "pending"
    assert body["push_back_comment"] is None


def test_get_dry_run_artifact_404_when_none(admin_token: str) -> None:
    project_id = str(uuid.uuid4())
    definition_id = str(uuid.uuid4())
    run_id = str(uuid.uuid4())
    with SessionLocal() as db:
        db.add(ProjectDefinition(definition_id=definition_id, project_id=project_id, name="NoDR", status="active"))
        db.add(ProjectRegistry(project_id=project_id, name="NoDR", definition_id=definition_id, status="active"))
        db.add(RunRecord(run_id=run_id, project_id=project_id, destination_object_name="x", status="queued", approvals=[]))
        db.commit()

    response = client.get(
        f"/projects/{project_id}/runs/{run_id}/dry-run",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "dry_run_artifact_not_found"


def test_approve_dry_run(admin_token: str) -> None:
    project_id, run_id = _seed_dry_run_state()

    response = client.post(
        f"/projects/{project_id}/runs/{run_id}/dry-run/approve",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["run_id"] == run_id
    assert body["status"] == "queued"

    with SessionLocal() as db:
        artifact = db.scalar(select(DryRunArtifact).where(DryRunArtifact.run_id == run_id))
        assert artifact is not None
        assert artifact.status == "approved"


def test_push_back_dry_run(admin_token: str) -> None:
    project_id, run_id = _seed_dry_run_state()

    response = client.post(
        f"/projects/{project_id}/runs/{run_id}/dry-run/push-back",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"comment": "Row 142 maps RETD to wrong destination."},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["run_id"] == run_id
    assert body["status"] == "dry_run_review"

    with SessionLocal() as db:
        artifact = db.scalar(select(DryRunArtifact).where(DryRunArtifact.run_id == run_id))
        assert artifact is not None
        assert artifact.status == "pushed_back"
        assert artifact.push_back_comment == "Row 142 maps RETD to wrong destination."


def test_approve_requires_central_team(stakeholder_token: str) -> None:
    project_id, run_id = _seed_dry_run_state()

    response = client.post(
        f"/projects/{project_id}/runs/{run_id}/dry-run/approve",
        headers={"Authorization": f"Bearer {stakeholder_token}"},
    )
    assert response.status_code == 403


def test_push_back_requires_central_team(stakeholder_token: str) -> None:
    project_id, run_id = _seed_dry_run_state()

    response = client.post(
        f"/projects/{project_id}/runs/{run_id}/dry-run/push-back",
        headers={"Authorization": f"Bearer {stakeholder_token}"},
        json={"comment": "Fix this."},
    )
    assert response.status_code == 403


def test_get_requires_project_access() -> None:
    project_id = str(uuid.uuid4())
    definition_id = str(uuid.uuid4())
    run_id = str(uuid.uuid4())
    with SessionLocal() as db:
        db.add(ProjectDefinition(definition_id=definition_id, project_id=project_id, name="Private", status="active"))
        db.add(ProjectRegistry(project_id=project_id, name="Private", definition_id=definition_id, status="active"))
        db.add(RunRecord(run_id=run_id, project_id=project_id, destination_object_name="x", status="dry_run_review", approvals=[]))
        db.commit()

    stakeholder_tok = _login("stakeholder@example.com", "stakeholder-password")
    response = client.get(
        f"/projects/{project_id}/runs/{run_id}/dry-run",
        headers={"Authorization": f"Bearer {stakeholder_tok}"},
    )
    assert response.status_code == 403
