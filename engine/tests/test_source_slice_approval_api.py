from __future__ import annotations

import tempfile
import uuid
from pathlib import Path

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
from migrations_engine.db.models import ProjectDefinition, ProjectMembership, ProjectRegistry, SourceDefinition, SourceSlice, SourceSliceRow, User  # noqa: E402
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
        stakeholder = User(
            user_id=str(uuid.uuid4()),
            email="stakeholder@example.com",
            display_name="Stakeholder",
            password_hash=hash_password("stakeholder-password"),
            role=PROJECT_STAKEHOLDER_ROLE,
            status="active",
        )
        db.add(stakeholder)
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


def _create_project(name: str) -> tuple[str, str]:
    project_id = str(uuid.uuid4())
    definition_id = str(uuid.uuid4())
    with SessionLocal() as db:
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
        db.commit()
    return project_id, definition_id


def _seed_pending_slice(
    db,
    *,
    project_id: str,
    source_definition_id: str,
    source_slice_version: str,
    status: str = "pending_approval",
    reason: str | None = None,
    file_storage_path: str | None = None,
) -> SourceSlice:
    slice_id = str(uuid.uuid4())
    slice_row = SourceSlice(
        source_slice_id=slice_id,
        source_definition_id=source_definition_id,
        source_contract_version="v1",
        source_slice_version=source_slice_version,
        source_schema_artifact=None,
        masking_policy=None,
        header_csv="CUST_ID,SURNAME",
        slice_payload=None,
        status=status,
        approval_rejection_reason=reason,
        parse_warnings=["warn"] if status == "pending_approval" else [],
        file_storage_path=file_storage_path,
    )
    db.add(slice_row)
    db.flush()
    db.add(
        SourceSliceRow(
            source_slice_id=slice_id,
            row_index=0,
            row_csv="100042,***",
        )
    )
    db.commit()
    return slice_row


def test_pending_approvals_respect_membership_and_count(admin_token: str, stakeholder_token: str) -> None:
    project_id, _ = _create_project("Approval Project")
    source_definition_id = str(uuid.uuid4())
    with tempfile.NamedTemporaryFile(delete=False, suffix=".csv", mode="wb") as handle:
        handle.write(b"CUST_ID,SURNAME\n100042,Smith\n")
        retained_path = handle.name

    with SessionLocal() as db:
        source_definition = SourceDefinition(
            source_definition_id=source_definition_id,
            project_id=project_id,
            source_type="csv",
            source_contract_version="v1",
            source_details={"label": "Customer Extract", "encoding": "utf-8"},
            status="active",
        )
        db.add(source_definition)
        db.flush()
        _seed_pending_slice(
            db,
            project_id=project_id,
            source_definition_id=source_definition_id,
            source_slice_version="v1",
            file_storage_path=retained_path,
        )
        stakeholder_user = db.scalar(select(User).where(User.email == "stakeholder@example.com"))
        assert stakeholder_user is not None
        db.add(
            ProjectMembership(
                project_id=project_id,
                user_id=stakeholder_user.user_id,
            )
        )
        db.commit()

    central_count = client.get("/approvals/count", headers={"Authorization": f"Bearer {admin_token}"})
    assert central_count.status_code == 200
    assert central_count.json()["pending_count"] == 1

    stakeholder_list = client.get("/approvals", headers={"Authorization": f"Bearer {stakeholder_token}"})
    assert stakeholder_list.status_code == 200
    assert len(stakeholder_list.json()) == 1
    assert stakeholder_list.json()[0]["project_id"] == project_id


def test_approve_reject_and_resubmit(admin_token: str) -> None:
    project_id, _ = _create_project("Decision Project")
    source_definition_id = str(uuid.uuid4())
    with tempfile.NamedTemporaryFile(delete=False, suffix=".csv", mode="wb") as handle:
        handle.write(b"CUST_ID,SURNAME\n100042,Smith\n")
        retained_path = handle.name

    with SessionLocal() as db:
        db.add(
            SourceDefinition(
                source_definition_id=source_definition_id,
                project_id=project_id,
                source_type="csv",
                source_contract_version="v1",
                source_details={"label": "Customer Extract", "encoding": "utf-8"},
                status="active",
            )
        )
        db.flush()
        pending = _seed_pending_slice(
            db,
            project_id=project_id,
            source_definition_id=source_definition_id,
            source_slice_version="v1",
            file_storage_path=retained_path,
        )
        rejected = _seed_pending_slice(
            db,
            project_id=project_id,
            source_definition_id=source_definition_id,
            source_slice_version="v0",
            status="rejected",
            reason="bad data",
            file_storage_path=retained_path,
        )
        pending_slice_id = pending.source_slice_id
        rejected_slice_id = rejected.source_slice_id
        db.commit()

    approve = client.post(
        f"/projects/{project_id}/sources/{source_definition_id}/slices/{pending_slice_id}/approve",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert approve.status_code == 200, approve.text
    assert approve.json()["status"] == "approved"

    reject = client.post(
        f"/projects/{project_id}/sources/{source_definition_id}/slices/{pending_slice_id}/reject",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"reason": "needs review"},
    )
    assert reject.status_code == 409
    assert reject.json()["error"]["code"] == "slice_not_pending"

    with SessionLocal() as db:
        pending_row = db.get(SourceSlice, pending_slice_id)
        assert pending_row is not None
        pending_row.status = "pending_approval"
        db.commit()

    reject = client.post(
        f"/projects/{project_id}/sources/{source_definition_id}/slices/{pending_slice_id}/reject",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"reason": "needs review"},
    )
    assert reject.status_code == 200, reject.text
    assert reject.json()["status"] == "rejected"
    assert reject.json()["approval_rejection_reason"] == "needs review"

    with SessionLocal() as db:
        superseded = _seed_pending_slice(
            db,
            project_id=project_id,
            source_definition_id=source_definition_id,
            source_slice_version="v2",
            file_storage_path=retained_path,
        )
        superseded_slice_id = superseded.source_slice_id

    resubmit = client.post(
        f"/projects/{project_id}/sources/{source_definition_id}/slices/{rejected_slice_id}/resubmit",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"encoding": "utf-8", "parse_settings": {"delimiter": ","}},
    )
    assert resubmit.status_code == 200, resubmit.text
    assert resubmit.json()["status"] == "pending_approval"
    assert resubmit.json()["source_slice_version"] == "v3"

    with SessionLocal() as db:
        updated_pending = db.get(SourceSlice, superseded_slice_id)
        assert updated_pending is not None
        assert updated_pending.status == "rejected"
        assert updated_pending.approval_rejection_reason == "superseded_by_resubmit"
