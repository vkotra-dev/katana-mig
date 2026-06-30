from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# Force the engine package onto an isolated SQLite database before app import.
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
from migrations_engine.db.models import ProjectDefinition, ProjectRegistry, SourceDefinition, SourceSlice, User  # noqa: E402
from migrations_engine.db.session import SessionLocal  # noqa: E402
from migrations_engine.roles import CENTRAL_TEAM_ROLE  # noqa: E402

client = TestClient(app)


@pytest.fixture(scope="module", autouse=True)
def _setup_sqlite_db() -> None:
    from migrations_engine.db.base import Base

    Base.metadata.create_all(bind=_sqlite_engine)

    settings = get_settings()
    if not settings.bootstrap_admin_email or not settings.bootstrap_admin_password:
        pytest.skip("bootstrap credentials not configured")

    with SessionLocal() as db:
        admin = User(
            user_id=str(uuid.uuid4()),
            email=settings.bootstrap_admin_email.strip().lower(),
            display_name=settings.bootstrap_admin_display_name,
            password_hash=hash_password(settings.bootstrap_admin_password),
            role=CENTRAL_TEAM_ROLE,
            status="active",
        )
        db.add(admin)
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


def _create_project(token: str, name: str) -> dict[str, object]:
    response = client.post("/projects", headers={"Authorization": f"Bearer {token}"}, json={"name": name})
    assert response.status_code == 201, response.text
    return response.json()


def test_csv_source_intake_masks_and_persists_rows(admin_token: str) -> None:
    project = _create_project(admin_token, f"Source-{uuid.uuid4().hex[:8]}")
    create = client.post(
        f"/projects/{project['project_id']}/sources",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"source_type": "csv", "label": "Customer Extract", "encoding": "utf-8"},
    )
    assert create.status_code == 201, create.text
    source = create.json()
    assert source["label"] == "Customer Extract"
    assert source["status"] == "declared"

    upload = client.post(
        f"/projects/{project['project_id']}/sources/{source['source_definition_id']}/slices",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "content": "CUST_ID,SURNAME,DOB,ACCOUNT_TYPE\n100042,Smith,19800101,DATABASE\n",
        },
    )
    assert upload.status_code == 200, upload.text
    slice_body = upload.json()
    assert slice_body["status"] == "pending_approval"
    assert slice_body["row_count"] == 1
    assert slice_body["preview_rows"][0] == "100042,***,***,DATABASE"

    with SessionLocal() as db:
        stored_definition = db.scalar(
            select(ProjectDefinition).where(ProjectDefinition.project_id == project["project_id"])
        )
        assert stored_definition is not None
        stored_source = db.scalar(select(ProjectRegistry).where(ProjectRegistry.project_id == project["project_id"]))
        assert stored_source is not None
        stored_slice = db.scalar(select(SourceSlice).where(SourceSlice.source_slice_id == slice_body["source_slice_id"]))
    assert stored_slice is not None
    assert stored_slice.file_storage_path is not None


def test_fixed_length_requires_copybook_before_upload(admin_token: str) -> None:
    project = _create_project(admin_token, f"Source-{uuid.uuid4().hex[:8]}")
    create = client.post(
        f"/projects/{project['project_id']}/sources",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"source_type": "fixed_length_file", "label": "Claims Feed", "encoding": "utf-8"},
    )
    assert create.status_code == 201, create.text
    source = create.json()

    upload = client.post(
        f"/projects/{project['project_id']}/sources/{source['source_definition_id']}/slices",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"content": "00000001Smith     19800101"},
    )
    assert upload.status_code == 409
    assert upload.json()["error"]["code"] == "layout_not_ready"

    copybook = client.post(
        f"/projects/{project['project_id']}/sources/{source['source_definition_id']}/copybook",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "content": """
       01  CUSTOMER-RECORD.
           05  CUST-ID         PIC 9(8).
           05  SURNAME         PIC X(10).
           05  DOB             PIC 9(8).
            """.strip(),
        },
    )
    assert copybook.status_code == 200, copybook.text
    assert copybook.json()["status"] == "layout_ready"
    assert copybook.json()["layout_information"][0]["name"] == "CUST_ID"

    fixed_upload = client.post(
        f"/projects/{project['project_id']}/sources/{source['source_definition_id']}/slices",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"content": "00000001Smith     19800101"},
    )
    assert fixed_upload.status_code == 200, fixed_upload.text
    assert fixed_upload.json()["status"] == "pending_approval"
    assert fixed_upload.json()["row_count"] == 1
