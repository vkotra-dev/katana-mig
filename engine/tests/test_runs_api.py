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
    LookupSnapshot,
    MappingSnapshot,
    ProjectDefinition,
    ProjectRegistry,
    RunCheckpoint,
    RunRecord,
    SourceDefinition,
    SourceSlice,
    SourceSliceRow,
    User,
)
from migrations_engine.db.session import SessionLocal  # noqa: E402
from migrations_engine.mapping import FieldBinding, create_approved_lookup_snapshot, create_approved_mapping_snapshot  # noqa: E402
from migrations_engine.roles import CENTRAL_TEAM_ROLE  # noqa: E402

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


def _seed_project_state(project_id: str) -> str:
    source_definition_id = str(uuid.uuid4())
    with SessionLocal() as db:
        db.add(
            SourceDefinition(
                source_definition_id=source_definition_id,
                project_id=project_id,
                source_type="csv",
                source_contract_version="v1",
                source_details={"label": "Customers", "encoding": "utf-8"},
                status="active",
            )
        )
        db.flush()

        source_slice = SourceSlice(
            source_slice_id=str(uuid.uuid4()),
            source_definition_id=source_definition_id,
            source_contract_version="v1",
            source_slice_version="v1",
            source_schema_artifact=None,
            masking_policy=None,
            header_csv="STATUS",
            slice_payload=None,
            status="approved",
            parse_warnings=[],
            file_storage_path=None,
        )
        db.add(source_slice)
        db.flush()
        db.add(
            SourceSliceRow(
                source_slice_id=source_slice.source_slice_id,
                row_index=0,
                row_csv="A",
            )
        )
        db.add(
            SourceSliceRow(
                source_slice_id=source_slice.source_slice_id,
                row_index=1,
                row_csv="B",
            )
        )
        create_approved_mapping_snapshot(
            db,
            project_id=project_id,
            destination_object_name="Customer",
            mapping_snapshot_version="v1",
            field_bindings=[
                FieldBinding(source_field="STATUS", destination_field="status", lookup_name="status_map")
            ],
        )
        create_approved_lookup_snapshot(
            db,
            project_id=project_id,
            lookup_name="status_map",
            lookup_snapshot_version="v1",
            value_map={"A": "ACTIVE"},
        )
        db.commit()
    return source_definition_id


def test_run_crud_launch_and_resume_via_api(admin_token: str) -> None:
    with SessionLocal() as db:
        project_id, _ = _create_project(db, f"Runs-{uuid.uuid4().hex[:8]}")
        source_definition_id = _seed_project_state(project_id)

    create = client.post(
        f"/projects/{project_id}/runs",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "destination_object_name": "Customer",
            "source_definition_id": source_definition_id,
            "environment": "dev",
        },
    )
    assert create.status_code == 201, create.text
    run = create.json()
    assert run["status"] == "queued"
    assert run["destination_object_name"] == "Customer"

    list_response = client.get(
        f"/projects/{project_id}/runs",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert list_response.status_code == 200, list_response.text
    assert len(list_response.json()) == 1

    detail_response = client.get(
        f"/projects/{project_id}/runs/{run['run_id']}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert detail_response.status_code == 200, detail_response.text
    assert detail_response.json()["status"] == "queued"

    launch = client.post(
        f"/projects/{project_id}/runs/{run['run_id']}/launch",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert launch.status_code == 200, launch.text
    assert launch.json()["status"] == "awaiting_approval"
    assert launch.json()["pause_metadata"]["pause_reason"] == "lookup_delta"

    checkpoints_response = client.get(
        f"/projects/{project_id}/runs/{run['run_id']}/checkpoints",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert checkpoints_response.status_code == 200, checkpoints_response.text
    checkpoints = checkpoints_response.json()
    assert len(checkpoints) == 1
    assert checkpoints[0]["pause_reason"] == "lookup_delta"

    with SessionLocal() as db:
        create_approved_lookup_snapshot(
            db,
            project_id=project_id,
            lookup_name="status_map",
            lookup_snapshot_version="v2",
            value_map={"A": "ACTIVE", "B": "BLOCKED"},
        )
        db.commit()

    resume = client.post(
        f"/projects/{project_id}/runs/{run['run_id']}/resume",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resume.status_code == 200, resume.text
    assert resume.json()["status"] == "completed"
    assert resume.json()["lookup_snapshot_version"] == "v2"

    with SessionLocal() as db:
        stored_run = db.get(RunRecord, run["run_id"])
        stored_checkpoints = list(db.scalars(select(RunCheckpoint).where(RunCheckpoint.run_id == run["run_id"])))

    assert stored_run is not None
    assert stored_run.status == "completed"
    assert len(stored_checkpoints) >= 1
