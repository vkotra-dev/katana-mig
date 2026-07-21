from __future__ import annotations

from datetime import UTC, datetime
import uuid
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from sqlite_test_support import Base, SessionLocal, TEST_ENGINE
from migrations_engine.ai.adapter import AICallResult
from migrations_engine.app import app  # noqa: E402
from migrations_engine.api.deps import AuthApiError  # noqa: E402
from migrations_engine.auth.passwords import hash_password  # noqa: E402
from migrations_engine.config import get_settings  # noqa: E402
from migrations_engine.codegen import schema_analysis as schema_analysis_module  # noqa: E402
from migrations_engine.codegen import service as codegen_service_module  # noqa: E402
from migrations_engine.db.models import (  # noqa: E402
    CodeGenerationArtifact,
    ProjectDefinition,
    ProjectRegistry,
    ProjectSchemaAnalysis,
    User,
)
from migrations_engine.roles import CENTRAL_TEAM_ROLE  # noqa: E402

client = TestClient(app)


class FakeAdapter:
    def __init__(self, objects: list[dict[str, object]]) -> None:
        self.objects = objects
        self.calls: list[SimpleNamespace] = []
        self.model_id = "test-model"

    def call(self, system: str, user: str, response_model: type[object]):
        self.calls.append(SimpleNamespace(system=system, user=user, response_model=response_model))
        parsed_result = response_model(objects=self.objects)
        return AICallResult(parsed=parsed_result, raw_response="raw_response")


@pytest.fixture(scope="module", autouse=True)
def _setup_sqlite_db() -> None:
    Base.metadata.create_all(bind=TEST_ENGINE)
    settings = get_settings()
    if settings.bootstrap_admin_email and settings.bootstrap_admin_password:
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


def _seed_project(*, destination_schema_ddl: str | None = None) -> str:
    project_id = str(uuid.uuid4())
    definition_id = str(uuid.uuid4())
    with SessionLocal() as db:
        db.add(
            ProjectDefinition(
                definition_id=definition_id,
                project_id=project_id,
                name="Schema Analysis Project",
                status="active",
                domain_config={"destination_schema_ddl": destination_schema_ddl} if destination_schema_ddl else {},
            )
        )
        db.add(
            ProjectRegistry(
                project_id=project_id,
                name="Schema Analysis Project",
                definition_id=definition_id,
                status="active",
            )
        )
        db.commit()
    return project_id


def test_run_schema_analysis_orders_dependencies_and_counts(monkeypatch: pytest.MonkeyPatch) -> None:
    project_id = _seed_project(
        destination_schema_ddl=(
            "CREATE TABLE customers (id INT PRIMARY KEY);\n"
            "CREATE TABLE orders (id INT PRIMARY KEY, customer_id INT, CONSTRAINT fk_orders_customer "
            "FOREIGN KEY (customer_id) REFERENCES customers(id));\n"
            "CREATE TABLE audit_log (id INT PRIMARY KEY);"
        )
    )
    fake = FakeAdapter(
        [
            {"name": "orders", "depends_on": ["customers"]},
            {"name": "customers", "depends_on": []},
            {"name": "audit_log", "depends_on": []},
        ]
    )
    monkeypatch.setattr(schema_analysis_module, "get_adapter", lambda task: fake)

    with SessionLocal() as db:
        db.add(
            CodeGenerationArtifact(
                project_id=project_id,
                destination_object_name="customers",
                source_slice_version="v1",
                mapping_snapshot_version="v1",
                lookup_snapshot_version=None,
                sql_bundle="-- customers",
                status="active",
            )
        )
        db.commit()
        response = schema_analysis_module.run_schema_analysis(db, project_id=project_id)

    assert response.destination_object_sequence == ["audit_log", "customers", "orders"]
    assert response.identified_count == 3
    assert response.processed_count == 1
    assert len(fake.calls) == 1

    with SessionLocal() as db:
        record = db.scalar(select(ProjectSchemaAnalysis).where(ProjectSchemaAnalysis.project_id == project_id))
    assert record is not None
    assert record.destination_object_sequence == ["audit_log", "customers", "orders"]


def test_run_schema_analysis_overwrites_existing_record(monkeypatch: pytest.MonkeyPatch) -> None:
    project_id = _seed_project(destination_schema_ddl="CREATE TABLE customers (id INT);")
    first = FakeAdapter([{ "name": "customers", "depends_on": [] }])
    second = FakeAdapter([{ "name": "customers", "depends_on": [] }, { "name": "orders", "depends_on": ["customers"] }])

    monkeypatch.setattr(schema_analysis_module, "get_adapter", lambda task: first)
    with SessionLocal() as db:
        schema_analysis_module.run_schema_analysis(db, project_id=project_id)

    monkeypatch.setattr(schema_analysis_module, "get_adapter", lambda task: second)
    with SessionLocal() as db:
        schema_analysis_module.run_schema_analysis(db, project_id=project_id)
        records = list(db.scalars(select(ProjectSchemaAnalysis).where(ProjectSchemaAnalysis.project_id == project_id)))

    assert len(records) == 1
    assert records[0].destination_object_sequence == ["customers", "orders"]
    assert second.calls


def test_run_schema_analysis_requires_destination_ddl() -> None:
    project_id = _seed_project()

    with SessionLocal() as db, pytest.raises(AuthApiError) as exc_info:
        schema_analysis_module.run_schema_analysis(db, project_id=project_id)

    assert exc_info.value.code == "missing_ddl"


def test_get_schema_analysis_returns_none_when_absent() -> None:
    project_id = _seed_project(destination_schema_ddl="CREATE TABLE customers (id INT);")

    with SessionLocal() as db:
        response = schema_analysis_module.get_schema_analysis(db, project_id=project_id)

    assert response is None


def test_build_delivery_bundle_text_uses_schema_sequence(monkeypatch: pytest.MonkeyPatch) -> None:
    project_id = _seed_project(destination_schema_ddl="CREATE TABLE customers (id INT);")
    analysis = ProjectSchemaAnalysis(
        analysis_id=str(uuid.uuid4()),
        project_id=project_id,
        destination_object_sequence=["customers", "orders"],
        identified_count=2,
        analyzed_at=datetime.now(UTC),
    )

    with SessionLocal() as db:
        db.add(analysis)
        db.add_all(
            [
                CodeGenerationArtifact(
                    project_id=project_id,
                    destination_object_name="orders",
                    source_slice_version="v2",
                    mapping_snapshot_version="v2",
                    lookup_snapshot_version=None,
                    sql_bundle="CREATE TABLE orders ();",
                    status="active",
                ),
                CodeGenerationArtifact(
                    project_id=project_id,
                    destination_object_name="customers",
                    source_slice_version="v1",
                    mapping_snapshot_version="v1",
                    lookup_snapshot_version=None,
                    sql_bundle="CREATE TABLE customers ();",
                    status="active",
                ),
                CodeGenerationArtifact(
                    project_id=project_id,
                    destination_object_name="audit_log",
                    source_slice_version="v1",
                    mapping_snapshot_version="v1",
                    lookup_snapshot_version=None,
                    sql_bundle="CREATE TABLE audit_log ();",
                    status="active",
                ),
            ]
        )
        db.commit()
        bundle = codegen_service_module.build_delivery_bundle_text(db, project_id=project_id)

    assert bundle.artifact_count == 3
    assert bundle.sql_bundle.startswith("-- [01] customers")
    assert "-- [02] orders" in bundle.sql_bundle
    assert bundle.sql_bundle.rstrip().endswith("-- [03] audit_log\n\nCREATE TABLE audit_log ();")


def test_delivery_bundle_without_schema_analysis_keeps_plain_headings(monkeypatch: pytest.MonkeyPatch) -> None:
    project_id = _seed_project(destination_schema_ddl="CREATE TABLE customers (id INT);")

    with SessionLocal() as db:
        db.add(
            CodeGenerationArtifact(
                project_id=project_id,
                destination_object_name="customers",
                source_slice_version="v1",
                mapping_snapshot_version="v1",
                lookup_snapshot_version=None,
                sql_bundle="CREATE TABLE customers ();",
                status="active",
            )
        )
        db.commit()
        bundle = codegen_service_module.build_delivery_bundle_text(db, project_id=project_id)

    assert bundle.sql_bundle.startswith("-- customers")
    assert "[01]" not in bundle.sql_bundle


def test_schema_analysis_routes(monkeypatch: pytest.MonkeyPatch, admin_token: str) -> None:
    project_id = _seed_project(destination_schema_ddl="CREATE TABLE customers (id INT);")
    fake = FakeAdapter([{ "name": "customers", "depends_on": [] }])
    monkeypatch.setattr(schema_analysis_module, "get_adapter", lambda task: fake)

    response = client.get(
        f"/projects/{project_id}/schema-analysis",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200, response.text
    assert response.json() is None

    post_response = client.post(
        f"/projects/{project_id}/schema-analysis",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert post_response.status_code == 200, post_response.text
    data = post_response.json()
    assert data["identified_count"] == 1
    assert data["processed_count"] == 0

    get_response = client.get(
        f"/projects/{project_id}/schema-analysis",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert get_response.status_code == 200, get_response.text
    assert get_response.json()["destination_object_sequence"] == ["customers"]


def test_schema_analysis_route_requires_access() -> None:
    project_id = _seed_project(destination_schema_ddl="CREATE TABLE customers (id INT);")
    response = client.post(f"/projects/{project_id}/schema-analysis")
    assert response.status_code == 401


from migrations_engine.ai.adapter import AIResponseValidationError
from migrations_engine.db.models import AICallLog
from migrations_engine.codegen import schema_analysis as schema_analysis_module

class ValidationFailingAdapter:
    model_id = "test-model"
    def call(self, system, user, response_model=None):
        raise AIResponseValidationError('{"bad": "json"}', ValueError("Failed"))

def test_schema_analysis_preserves_raw_response_on_validation_error(monkeypatch: pytest.MonkeyPatch) -> None:
    project_id = _seed_project(destination_schema_ddl="CREATE TABLE dummy(id int);")
    monkeypatch.setattr(schema_analysis_module, "get_adapter", lambda task, policy=None: ValidationFailingAdapter())

    with SessionLocal() as db:
        with pytest.raises(AIResponseValidationError):
            schema_analysis_module.run_schema_analysis(db, project_id=project_id)
            
        db.rollback()
        
        log = db.scalar(
            select(AICallLog)
            .where(
                AICallLog.project_id == project_id,
                AICallLog.call_type == "schema_analysis",
            )
            .order_by(AICallLog.called_at.desc())
        )
        assert log is not None, "Log should be persisted via db.commit()"
        assert log.raw_response == '{"bad": "json"}'
        assert log.error_detail is not None
        assert "ValidationError: Failed" in log.error_detail
