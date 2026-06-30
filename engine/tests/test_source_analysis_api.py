from __future__ import annotations

import uuid
from datetime import UTC, datetime
from types import SimpleNamespace

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
    SourceSliceRow,
    User,
)
from migrations_engine.management.source_analysis import AnalysisResult, ColumnSchema  # noqa: E402
from migrations_engine.roles import CENTRAL_TEAM_ROLE, PROJECT_STAKEHOLDER_ROLE  # noqa: E402

client = TestClient(app)


class FakeAdapter:
    def __init__(self, *, analysis_result: AnalysisResult) -> None:
        self.analysis_result = analysis_result
        self.calls: list[SimpleNamespace] = []
        self.model_id = "claude-haiku-4-5-20251001"

    def call(self, system: str, user: str, response_model: type[AnalysisResult]) -> AnalysisResult:
        self.calls.append(SimpleNamespace(system=system, user=user, response_model=response_model))
        return self.analysis_result


@pytest.fixture(scope="module", autouse=True)
def _setup_sqlite_db() -> None:
    Base.metadata.create_all(bind=TEST_ENGINE)

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


def _seed_project_with_slice() -> tuple[str, str]:
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
                name="Source Analysis Project",
                status="active",
            )
        )
        db.add(
            ProjectRegistry(
                project_id=project_id,
                name="Source Analysis Project",
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
                status="active",
            )
        )
        db.flush()
        slice_id = str(uuid.uuid4())
        db.add(
            SourceSlice(
                source_slice_id=slice_id,
                source_definition_id=source_definition_id,
                source_contract_version="v1",
                source_slice_version="v1",
                source_schema_artifact=None,
                masking_policy={"masked_fields": ["SURNAME"]},
                header_csv="CUST_ID,SURNAME",
                slice_payload=None,
                status="approved",
                parse_warnings=[],
                file_storage_path="/tmp/source.csv",
                approved_at=datetime.now(UTC),
                approved_by_user_id=admin_user.user_id,
            )
        )
        db.flush()
        db.add(
            SourceSliceRow(
                source_slice_id=slice_id,
                row_index=0,
                row_csv="100001,***",
            )
        )
        db.add(
            SourceSliceRow(
                source_slice_id=slice_id,
                row_index=1,
                row_csv="100002,***",
            )
        )
        db.commit()
    return project_id, source_definition_id


def test_source_analysis_requires_central_team(admin_token: str, stakeholder_token: str) -> None:
    project_id, source_definition_id = _seed_project_with_slice()

    response = client.post(
        f"/projects/{project_id}/sources/{source_definition_id}/analyze",
        headers={"Authorization": f"Bearer {stakeholder_token}"},
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "forbidden"


def test_source_analysis_returns_schema_and_value_summary(monkeypatch: pytest.MonkeyPatch, admin_token: str) -> None:
    project_id, source_definition_id = _seed_project_with_slice()
    fake_adapter = FakeAdapter(
        analysis_result=AnalysisResult(
            columns=[
                ColumnSchema(name="CUST_ID", inferred_type="integer", nullable=False, max_length=8),
                ColumnSchema(name="SURNAME", inferred_type="text", nullable=True, max_length=40),
            ]
        )
    )
    monkeypatch.setattr("migrations_engine.management.source_analysis.get_adapter", lambda task: fake_adapter)

    analyze = client.post(
        f"/projects/{project_id}/sources/{source_definition_id}/analyze",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert analyze.status_code == 202, analyze.text
    assert analyze.json()["status"] == "queued"
    assert analyze.json()["schema_artifact_id"]

    schema = client.get(
        f"/projects/{project_id}/sources/{source_definition_id}/schema",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert schema.status_code == 200, schema.text
    assert schema.json()[0]["name"] == "CUST_ID"

    value_summary = client.get(
        f"/projects/{project_id}/sources/{source_definition_id}/value-summary?field=SURNAME",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert value_summary.status_code == 200, value_summary.text
    assert value_summary.json()[0]["field_name"] == "SURNAME"
    assert value_summary.json()[0]["value_counts"]["***"] == 2
