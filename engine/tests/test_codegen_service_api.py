from __future__ import annotations

from datetime import UTC, datetime
import uuid
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from sqlite_test_support import Base, SessionLocal, TEST_ENGINE
from migrations_engine.app import app  # noqa: E402
from migrations_engine.auth.passwords import hash_password  # noqa: E402
from migrations_engine.config import get_settings  # noqa: E402
from migrations_engine.db.models import (  # noqa: E402
    CodeGenerationArtifact,
    MappingSnapshot,
    ProjectDefinition,
    ProjectRegistry,
    SourceDefinition,
    SourceSchemaArtifact,
    SourceSlice,
    User,
)
from migrations_engine.codegen import service as codegen_service_module  # noqa: E402
from migrations_engine.roles import CENTRAL_TEAM_ROLE  # noqa: E402

client = TestClient(app)


class FakeAdapter:
    def __init__(self) -> None:
        self.model_id = "gpt-4o-mini"
        self.calls: list[SimpleNamespace] = []

    def call(self, system: str, user: str, response_model: type[object]):
        self.calls.append(SimpleNamespace(system=system, user=user, response_model=response_model))
        return response_model(
            staging_table_ddl=(
                "CREATE TABLE stg_customer (\n"
                "  customer_id INT NOT NULL,\n"
                "  full_name VARCHAR(255)\n"
                ");"
            ),
            views=["CREATE VIEW v_customer AS SELECT customer_id FROM stg_customer;"],
            notes="use staging schema",
        )


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
                    display_name="Admin",
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
                name="Codegen Test Project",
                status="active",
                domain_config={"target_db_engine": "postgresql", "staging_schema": "stg"},
            )
        )
        db.add(
            ProjectRegistry(
                project_id=project_id,
                name="Codegen Test Project",
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
                header_csv="customer_id,full_name",
                slice_payload=None,
                status="approved",
                parse_warnings=[],
                file_storage_path="/tmp/customer.csv",
                approved_at=datetime.now(UTC),
                approved_by_user_id=admin_user.user_id,
            )
        )
        db.add(
            SourceSchemaArtifact(
                schema_artifact_id=str(uuid.uuid4()),
                source_definition_id=source_definition_id,
                source_slice_version="v1",
                columns=[
                    {"name": "customer_id", "inferred_type": "integer", "nullable": False, "max_length": None},
                    {"name": "full_name", "inferred_type": "text", "nullable": True, "max_length": 255},
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
                        {
                            "source_field": "customer_id",
                            "destination_field": "customer_id",
                            "lookup_name": None,
                        },
                        {
                            "source_field": "full_name",
                            "destination_field": "full_name",
                            "lookup_name": None,
                        },
                    ],
                    status="approved",
                    approved_at=datetime.now(UTC),
                    approved_by_user_id=admin_user.user_id,
                )
        )
        db.commit()
    return project_id, source_definition_id


def test_post_codegen_creates_active_artifact_and_preview(monkeypatch: pytest.MonkeyPatch, admin_token: str) -> None:
    project_id, source_definition_id = _seed_project()
    fake = FakeAdapter()
    monkeypatch.setattr(codegen_service_module, "get_adapter", lambda task: fake)

    response = client.post(
        f"/projects/{project_id}/sources/{source_definition_id}/codegen",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 201, response.text
    data = response.json()
    assert data["status"] == "active"
    assert data["lookup_snapshot_version"] is None
    assert data["sql_bundle_preview"].startswith("CREATE TABLE stg_customer")
    assert len(data["sql_bundle_preview"]) <= 500

    with SessionLocal() as db:
        artifact = db.scalar(select(CodeGenerationArtifact).where(CodeGenerationArtifact.codegen_artifact_id == data["codegen_artifact_id"]))
        assert artifact is not None
        assert artifact.status == "active"
        assert "CREATE VIEW v_customer" in (artifact.sql_bundle or "")


def test_delivery_bundle_returns_active_artifacts(monkeypatch: pytest.MonkeyPatch, admin_token: str) -> None:
    project_id, source_definition_id = _seed_project()
    fake = FakeAdapter()
    monkeypatch.setattr(codegen_service_module, "get_adapter", lambda task: fake)

    first = client.post(
        f"/projects/{project_id}/sources/{source_definition_id}/codegen",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert first.status_code == 201, first.text

    second = client.post(
        f"/projects/{project_id}/sources/{source_definition_id}/codegen",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert second.status_code == 201, second.text

    with SessionLocal() as db:
        active = db.scalars(
            select(CodeGenerationArtifact).where(
                CodeGenerationArtifact.project_id == project_id,
                CodeGenerationArtifact.status == "active",
            )
        ).all()
        superseded = db.scalars(
            select(CodeGenerationArtifact).where(
                CodeGenerationArtifact.project_id == project_id,
                CodeGenerationArtifact.status == "superseded",
            )
        ).all()
        assert len(active) == 1
        assert len(superseded) == 1

    response = client.get(
        f"/projects/{project_id}/delivery-bundle",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200, response.text
    assert response.headers["content-disposition"] == 'attachment; filename="delivery-bundle.sql"'
    assert response.text.startswith("-- Customer")
    assert "CREATE TABLE stg_customer" in response.text
