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
    MappingArtifact,
    MappingSnapshot,
    ProjectMembership,
    ProjectDefinition,
    ProjectRegistry,
    RunRecord,
    SourceDefinition,
    SourceSlice,
    SourceSliceRow,
    User,
)
from migrations_engine.db.session import SessionLocal  # noqa: E402
from migrations_engine.roles import CENTRAL_TEAM_ROLE, PROJECT_STAKEHOLDER_ROLE, READ_ONLY_AUDITOR_ROLE  # noqa: E402

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


def _seed_reconciliation_run(
    *,
    source_rows: list[str] | None = None,
    mapped_rows: list[dict[str, object]] | None = None,
    approvals: list[dict[str, str]] | None = None,
) -> tuple[str, str, str]:
    source_rows = source_rows or ["C001,ACTIVE", "C002,ACTIVE"]
    mapped_rows = mapped_rows or [
        {"customer_id": "C001", "status": "ACTIVE", "destination_row_id": "D001"},
        {"customer_id": "C002", "status": "ACTIVE", "destination_row_id": "D002"},
    ]
    approvals = approvals or [
        {"gate": "gate_1", "decision": "approved"},
        {"gate": "gate_2", "decision": "approved"},
    ]

    with SessionLocal() as db:
        project_id, _ = _create_project(db, "Reconciliation Project")
        source_definition_id = str(uuid.uuid4())
        source_slice_id = str(uuid.uuid4())
        run_id = str(uuid.uuid4())

        db.add(
            SourceDefinition(
                source_definition_id=source_definition_id,
                project_id=project_id,
                source_type="csv",
                source_contract_version="v1",
                source_details={"label": "Customers", "encoding": "utf-8"},
                destination_object_references=["Customer"],
                status="active",
            )
        )
        db.add(
            SourceSlice(
                source_slice_id=source_slice_id,
                source_definition_id=source_definition_id,
                source_contract_version="v1",
                source_slice_version="v1",
                header_csv="customer_id,status",
                status="approved",
            )
        )
        for index, row_csv in enumerate(source_rows):
            db.add(
                SourceSliceRow(
                    id=str(uuid.uuid4()),
                    source_slice_id=source_slice_id,
                    row_index=index,
                    row_csv=row_csv,
                )
            )
        db.add(
            MappingSnapshot(
                mapping_snapshot_id=str(uuid.uuid4()),
                project_id=project_id,
                destination_object_name="Customer",
                mapping_snapshot_version="mapping@v1",
                field_bindings=[
                    {"source_field": "customer_id", "destination_field": "customer_id", "lookup_name": None},
                    {"source_field": "status", "destination_field": "status", "lookup_name": "status_map"},
                ],
                status="approved",
            )
        )
        db.add(
            MappingArtifact(
                mapping_artifact_id=str(uuid.uuid4()),
                run_id=run_id,
                project_id=project_id,
                destination_object_name="Customer",
                mapping_snapshot_version="mapping@v1",
                lookup_snapshot_version="lookup@v1",
                mapped_rows=mapped_rows,
            )
        )
        db.add(
            RunRecord(
                run_id=run_id,
                project_id=project_id,
                destination_object_name="Customer",
                source_definition_reference=source_definition_id,
                source_slice_version="v1",
                mapping_snapshot_version="mapping@v1",
                lookup_snapshot_version="lookup@v1",
                lookup_snapshot_versions={"status_map": "lookup@v1"},
                status="completed",
                current_stage="delivery",
                approvals=approvals,
            )
        )
        db.commit()

    return project_id, source_definition_id, run_id


def _seed_outsider_token() -> str:
    with SessionLocal() as db:
        project_id, _ = _create_project(db, "Outsider Project")
        user_id = str(uuid.uuid4())
        db.add(
            User(
                user_id=user_id,
                email=f"stakeholder-{uuid.uuid4().hex[:8]}@example.com",
                display_name="Stakeholder",
                password_hash=hash_password("stakeholder-password"),
                role=PROJECT_STAKEHOLDER_ROLE,
                status="active",
            )
        )
        db.add(ProjectMembership(project_id=project_id, user_id=user_id))
        db.commit()
        user_email = db.get(User, user_id).email  # type: ignore[union-attr]
    return _login(user_email, "stakeholder-password")


def _seed_auditor_token() -> str:
    with SessionLocal() as db:
        user_id = str(uuid.uuid4())
        db.add(
            User(
                user_id=user_id,
                email=f"auditor-{uuid.uuid4().hex[:8]}@example.com",
                display_name="Auditor",
                password_hash=hash_password("auditor-password"),
                role=READ_ONLY_AUDITOR_ROLE,
                status="active",
            )
        )
        db.commit()
        user_email = db.get(User, user_id).email  # type: ignore[union-attr]
    return _login(user_email, "auditor-password")


def test_trigger_creates_report(admin_token: str) -> None:
    project_id, _, run_id = _seed_reconciliation_run()

    response = client.post(
        f"/projects/{project_id}/runs/{run_id}/reconciliation",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 201, response.text
    payload = response.json()
    assert payload["run_id"] == run_id
    assert len(payload["checks"]) == 4


def test_cross_project_access_denied_for_stakeholder(admin_token: str) -> None:
    project_id, _, run_id = _seed_reconciliation_run()
    outsider_token = _seed_outsider_token()

    report = client.post(
        f"/projects/{project_id}/runs/{run_id}/reconciliation",
        headers={"Authorization": f"Bearer {admin_token}"},
    ).json()
    report_id = report["report_id"]

    for path in [
        f"/projects/{project_id}/runs/{run_id}/reconciliation",
        f"/projects/{project_id}/runs/{run_id}/reconciliation/history",
        f"/projects/{project_id}/runs/{run_id}/reconciliation/{report_id}/lineage",
        f"/projects/{project_id}/runs/{run_id}/reconciliation/{report_id}/export",
    ]:
        response = client.get(path, headers={"Authorization": f"Bearer {outsider_token}"})
        assert response.status_code == 403, response.text


def test_lineage_both_filters_returns_400(admin_token: str) -> None:
    project_id, _, run_id = _seed_reconciliation_run()
    report = client.post(
        f"/projects/{project_id}/runs/{run_id}/reconciliation",
        headers={"Authorization": f"Bearer {admin_token}"},
    ).json()
    response = client.get(
        f"/projects/{project_id}/runs/{run_id}/reconciliation/{report['report_id']}/lineage?source_row_index=0&destination_row_id=D001",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 400, response.text
    assert response.json()["error"]["code"] == "invalid_filter"


def test_surplus_mapped_rows_recorded_as_orphaned_and_report_fails(admin_token: str) -> None:
    project_id, _, run_id = _seed_reconciliation_run(
        source_rows=["C001,ACTIVE", "C002,ACTIVE"],
        mapped_rows=[
            {"customer_id": "C001", "status": "ACTIVE", "destination_row_id": "D001"},
            {"customer_id": "C002", "status": "ACTIVE", "destination_row_id": "D002"},
            {"customer_id": "C003", "status": "ACTIVE", "destination_row_id": "D003"},
        ],
    )
    response = client.post(
        f"/projects/{project_id}/runs/{run_id}/reconciliation",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 201, response.text
    payload = response.json()
    assert payload["overall_status"] == "fail"
    assert any(check["check_name"] == "orphaned_mapped_rows" for check in payload["checks"])
    report_id = payload["report_id"]
    lineage_response = client.get(
        f"/projects/{project_id}/runs/{run_id}/reconciliation/{report_id}/lineage",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert lineage_response.status_code == 200, lineage_response.text
    lineage_payload = lineage_response.json()
    assert lineage_payload["total"] == 3
    orphan_rows = [row for row in lineage_payload["rows"] if row["source_row_index"] is None]
    assert len(orphan_rows) == 1
    assert orphan_rows[0]["outcome"] == "rejected"
    assert "orphaned" in orphan_rows[0]["outcome_detail"]


def test_source_row_gap_marks_report_fail(admin_token: str) -> None:
    project_id, _, run_id = _seed_reconciliation_run(
        source_rows=["C001,ACTIVE", "C002,ACTIVE", "C003,ACTIVE"],
        mapped_rows=[
            {"customer_id": "C001", "status": "ACTIVE", "destination_row_id": "D001"},
            {"customer_id": "C002", "status": "ACTIVE", "destination_row_id": "D002"},
        ],
    )
    response = client.post(
        f"/projects/{project_id}/runs/{run_id}/reconciliation",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 201, response.text
    payload = response.json()
    assert payload["overall_status"] == "fail"
    assert any(check["check_name"] == "row_count" and check["status"] == "fail" for check in payload["checks"])


def test_read_only_auditor_can_read_and_export(admin_token: str) -> None:
    project_id, _, run_id = _seed_reconciliation_run()
    report = client.post(
        f"/projects/{project_id}/runs/{run_id}/reconciliation",
        headers={"Authorization": f"Bearer {admin_token}"},
    ).json()
    auditor_token = _seed_auditor_token()

    read_response = client.get(
        f"/projects/{project_id}/runs/{run_id}/reconciliation",
        headers={"Authorization": f"Bearer {auditor_token}"},
    )
    assert read_response.status_code == 200, read_response.text

    export_response = client.get(
        f"/projects/{project_id}/runs/{run_id}/reconciliation/{report['report_id']}/export",
        headers={"Authorization": f"Bearer {auditor_token}"},
    )
    assert export_response.status_code == 200, export_response.text
