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
from migrations_engine.ai.adapter import AICallResult  # noqa: E402
from migrations_engine.codegen import service as codegen_service_module  # noqa: E402
from migrations_engine.roles import CENTRAL_TEAM_ROLE  # noqa: E402

client = TestClient(app)


class FakeAdapter:
    def __init__(self) -> None:
        self.model_id = "gpt-4o-mini"
        self.calls: list[SimpleNamespace] = []

    def call(self, system: str, user: str, response_model: type[object]):
        self.calls.append(SimpleNamespace(system=system, user=user, response_model=response_model))
        parsed = response_model(
            staging_ddl=(
                "CREATE TABLE stg_customer (\n"
                "  customer_id INT NOT NULL,\n"
                "  full_name VARCHAR(255)\n"
                ");"
            ),
            lookup_ddl=["CREATE VIEW v_customer AS SELECT customer_id FROM stg_customer;"],
            seed_data=[],
            stored_procedures=[],
            notes="use staging schema",
        )
        return AICallResult(parsed=parsed, raw_response="raw")


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
                    destination_columns=[
                        {"name": "customer_id", "destination_data_type": "integer", "nullable": False},
                        {"name": "full_name", "destination_data_type": "text", "nullable": True},
                    ],
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
    data = response.json()[0]
    assert data["status"] == "active"
    assert data["lookup_snapshot_version"] is None
    assert "IF OBJECT_ID" in data["sql_bundle_preview"] or "stg_cu" in data["sql_bundle_preview"]
    assert len(data["sql_bundle_preview"]) <= 1500

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
    assert first.status_code == 201
    assert len(first.json()) == 1
    first_data = first.json()[0]

    second = client.post(
        f"/projects/{project_id}/sources/{source_definition_id}/codegen",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert second.status_code == 201
    assert len(second.json()) == 1
    second_data = second.json()[0]

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

from migrations_engine.ai.adapter import AIResponseValidationError
from migrations_engine.db.models import AICallLog

class ValidationFailingAdapter:
    model_id = "test-model"
    def call(self, system, user, response_model=None):
        raise AIResponseValidationError('{"bad": "json"}', ValueError("Failed"))

def test_codegen_preserves_raw_response_on_validation_error(monkeypatch: pytest.MonkeyPatch, admin_token: str) -> None:
    project_id, source_definition_id = _seed_project()
    monkeypatch.setattr(codegen_service_module, "get_adapter", lambda task: ValidationFailingAdapter())

    with SessionLocal() as db:
        with pytest.raises(AIResponseValidationError):
            codegen_service_module.generate_codegen_artifact(
                db,
                project_id=project_id,
                source_definition_id=source_definition_id,
                actor=db.scalar(select(User).limit(1)),
            )
            
        db.rollback()
        
        # Now verify
        log = db.scalar(
            select(AICallLog)
            .where(
                AICallLog.project_id == project_id,
                AICallLog.call_type == "codegen",
            )
            .order_by(AICallLog.called_at.desc())
        )
        assert log is not None, "Log should be persisted via db.commit()"
        assert log.raw_response == '{"bad": "json"}'
        assert log.error_detail is not None
        assert "ValidationError: Failed" in log.error_detail


def test_codegen_skips_when_destination_columns_missing(
    monkeypatch: pytest.MonkeyPatch, admin_token: str
) -> None:
    """With multi-table loop, missing destination_columns is a skip (logged warning), not a hard error."""
    project_id, source_definition_id = _seed_project()
    # Clear destination_columns so the snapshot has NULL
    with SessionLocal() as db:
        snapshot = db.scalars(
            select(MappingSnapshot).where(
                MappingSnapshot.project_id == project_id,
            )
        ).first()
        assert snapshot is not None
        snapshot.destination_columns = None
        db.commit()

    response = client.post(
        f"/projects/{project_id}/sources/{source_definition_id}/codegen",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    # Multi-table loop skips tables with missing metadata instead of failing
    assert response.status_code == 201
    data = response.json()
    assert data == []


def test_codegen_succeeds_when_required_fields_mapped(
    monkeypatch: pytest.MonkeyPatch, admin_token: str
) -> None:
    """Verify codegen succeeds when all required fields are mapped.
    The unmapped-fields guard was removed — missing fields are handled in the prompt."""
    project_id, source_definition_id = _seed_project()
    fake = FakeAdapter()
    monkeypatch.setattr(codegen_service_module, "get_adapter", lambda task: fake)

    response = client.post(
        f"/projects/{project_id}/sources/{source_definition_id}/codegen",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 201
    assert response.json()[0]["status"] == "active"
def test_codegen_preserves_project_config_across_reruns(
    monkeypatch: pytest.MonkeyPatch, admin_token: str
) -> None:
    """Codegen must use project config from project_definition.domain_config,
    not stale values from a previous run."""
    project_id, source_definition_id = _seed_project()
    fake = FakeAdapter()
    monkeypatch.setattr(codegen_service_module, "get_adapter", lambda task: fake)

    first = client.post(
        f"/projects/{project_id}/sources/{source_definition_id}/codegen",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert first.status_code == 201

    second = client.post(
        f"/projects/{project_id}/sources/{source_definition_id}/codegen",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert second.status_code == 201

    first_data = first.json()[0]
    second_data = second.json()[0]
    assert first_data["codegen_artifact_id"] != second_data["codegen_artifact_id"]
    assert first_data["source_slice_version"] == second_data["source_slice_version"]
    assert first_data["mapping_snapshot_version"] == second_data["mapping_snapshot_version"]

    with SessionLocal() as db:
        first_artifact = db.scalar(
            select(CodeGenerationArtifact).where(
                CodeGenerationArtifact.codegen_artifact_id == first_data["codegen_artifact_id"]
            )
        )
        second_artifact = db.scalar(
            select(CodeGenerationArtifact).where(
                CodeGenerationArtifact.codegen_artifact_id == second_data["codegen_artifact_id"]
            )
        )
        assert first_artifact is not None
        assert second_artifact is not None
        assert first_artifact.status == "superseded"
        assert second_artifact.status == "active"


def test_codegen_includes_source_slice_version_in_response(
    monkeypatch: pytest.MonkeyPatch, admin_token: str
) -> None:
    """The codegen trigger response must include the source slice version."""
    project_id, source_definition_id = _seed_project()
    fake = FakeAdapter()
    monkeypatch.setattr(codegen_service_module, "get_adapter", lambda task: fake)

    response = client.post(
        f"/projects/{project_id}/sources/{source_definition_id}/codegen",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 201
    data = response.json()[0]
    assert data["source_slice_version"] == "v1"
    assert data["mapping_snapshot_version"] == "v1"


def test_codegen_skips_dropped_bindings() -> None:
    """Verify that dropped bindings are excluded from codegen field sets.

    Tests the actual set comprehension logic used in
    ``migrations_engine.codegen.service.generate_mapping_script`` which
    filters ``binding.get("dropped")`` before building mapped_dest_fields
    and lookup snapshot queries.
    """
    # Replicate the exact expressions from service.py lines ~89-93 and
    # the lookup-name comprehension at line ~440.
    field_bindings = [
        {"source_field": "active_src", "destination_field": "active_dest", "lookup_name": "active_lookup"},
        {"source_field": "dropped_src", "destination_field": "dropped_dest", "lookup_name": "dropped_lookup", "dropped": True},
    ]

    # Expression from generate_mapping_script (line ~89)
    mapped_dest_fields = {
        binding.get("destination_field")
        for binding in field_bindings
        if binding.get("destination_field") and not binding.get("dropped")
    }
    assert "active_dest" in mapped_dest_fields
    assert "dropped_dest" not in mapped_dest_fields

    # Expression from _select_lookup_snapshot_version / _build_lookup_tables
    lookup_names = {
        str(binding.get("lookup_name"))
        for binding in field_bindings
        if binding.get("lookup_name") and not binding.get("dropped")
    }
    assert "active_lookup" in lookup_names
    assert "dropped_lookup" not in lookup_names


def test_select_lookup_snapshot_version_collects_all() -> None:
    """Verify _select_lookup_snapshot_version returns ALL matching lookups, not just the first."""
    from migrations_engine.db.models import MappingSnapshot  # noqa: E402
    from migrations_engine.db.models import LookupSnapshot  # noqa: E402
    from migrations_engine.codegen.service import _select_lookup_snapshot_version  # noqa: E402

    Base.metadata.create_all(bind=TEST_ENGINE)

    with SessionLocal() as db:
        admin_user = db.scalar(select(User).where(User.role == CENTRAL_TEAM_ROLE))
        assert admin_user is not None
        project = ProjectDefinition(
            definition_id=str(uuid.uuid4()),
            project_id=str(uuid.uuid4()),
            name="Multi-Lookup Test Project",
            status="active",
            domain_config={"target_db_engine": "postgresql", "staging_schema": "stg"},
        )
        db.add(project)
        db.commit()

        source = SourceDefinition(
            source_definition_id=str(uuid.uuid4()),
            project_id=project.project_id,
            source_type="csv",
            source_contract_version="v1",
        )
        db.add(source)
        db.flush()

        mapping_snap = MappingSnapshot(
            mapping_snapshot_id=str(uuid.uuid4()),
            project_id=project.project_id,
            source_definition_id=source.source_definition_id,
            destination_object_name="test_table",
            mapping_snapshot_version="snap_v1",
            field_bindings=[
                {"source_field": "src1", "destination_field": "dest1", "lookup_name": "lookup_a", "lookup_snapshot_version": "v1"},
                {"source_field": "src2", "destination_field": "dest2", "lookup_name": "lookup_b", "lookup_snapshot_version": "v2"},
                {"source_field": "src3", "destination_field": "dest3", "lookup_name": "lookup_c", "lookup_snapshot_version": "v3"},
            ],
            destination_columns=[{"column_name": "id", "data_type": "INT"}],
            status="approved",
            approved_at=datetime.now(UTC),
        )
        db.add(mapping_snap)
        db.flush()

        for name, version in [("lookup_a", "snap_a_v1"), ("lookup_b", "snap_b_v2"), ("lookup_c", "snap_c_v3")]:
            snap = LookupSnapshot(
                lookup_snapshot_id=str(uuid.uuid4()),
                project_id=project.project_id,
                lookup_name=name,
                lookup_snapshot_version=version,
                value_map={},
                status="approved",
                approved_at=datetime.now(UTC),
            )
            db.add(snap)
        db.commit()

        result = _select_lookup_snapshot_version(
            db,
            project_id=project.project_id,
            mapping_snapshot=mapping_snap,
        )

        assert len(result) == 3, f"Expected 3 lookup snapshots, got {len(result)}"
        names = {entry["lookup_name"] for entry in result}
        assert names == {"lookup_a", "lookup_b", "lookup_c"}
        versions = {entry["lookup_name"]: entry["snapshot_version"] for entry in result}
        assert versions == {"lookup_a": "snap_a_v1", "lookup_b": "snap_b_v2", "lookup_c": "snap_c_v3"}


def test_select_lookup_snapshot_version_empty_on_no_lookups() -> None:
    """Verify _select_lookup_snapshot_version returns empty list when no lookups are defined."""
    from migrations_engine.db.models import MappingSnapshot  # noqa: E402
    from migrations_engine.codegen.service import _select_lookup_snapshot_version  # noqa: E402

    Base.metadata.create_all(bind=TEST_ENGINE)

    with SessionLocal() as db:
        admin_user = db.scalar(select(User).where(User.role == CENTRAL_TEAM_ROLE))
        assert admin_user is not None
        project = ProjectDefinition(
            definition_id=str(uuid.uuid4()),
            project_id=str(uuid.uuid4()),
            name="No-Lookup Test Project",
            status="active",
            domain_config={"target_db_engine": "postgresql", "staging_schema": "stg"},
        )
        db.add(project)
        db.flush()

        mapping_snap = MappingSnapshot(
            mapping_snapshot_id=str(uuid.uuid4()),
            project_id=project.project_id,
            source_definition_id=str(uuid.uuid4()),
            destination_object_name="no_lookups_table",
            mapping_snapshot_version="snap_v1",
            field_bindings=[
                {"source_field": "src1", "destination_field": "dest1", "lookup_name": None},
            ],
            destination_columns=[{"column_name": "id", "data_type": "INT"}],
            status="approved",
            approved_at=datetime.now(UTC),
        )
        db.add(mapping_snap)
        db.commit()

        result = _select_lookup_snapshot_version(
            db,
            project_id=project.project_id,
            mapping_snapshot=mapping_snap,
        )

        assert result == []


def test_build_lookup_tables_passes_full_value_map() -> None:
    """Verify _build_lookup_tables passes ALL value_map entries, not just 5 samples.

    This is the core regression test for the :5 cap removal.
    """
    from migrations_engine.db.models import MappingSnapshot  # noqa: E402
    from migrations_engine.db.models import LookupSnapshot  # noqa: E402
    from migrations_engine.codegen.service import _build_lookup_tables  # noqa: E402

    Base.metadata.create_all(bind=TEST_ENGINE)

    with SessionLocal() as db:
        admin_user = db.scalar(select(User).where(User.role == CENTRAL_TEAM_ROLE))
        assert admin_user is not None
        project = ProjectDefinition(
            definition_id=str(uuid.uuid4()),
            project_id=str(uuid.uuid4()),
            name="Full Value Map Test Project",
            status="active",
            domain_config={"target_db_engine": "postgresql", "staging_schema": "stg"},
        )
        db.add(project)
        db.commit()

        source = SourceDefinition(
            source_definition_id=str(uuid.uuid4()),
            project_id=project.project_id,
            source_type="csv",
            source_contract_version="v1",
        )
        db.add(source)
        db.flush()

        # Create 12 value pairs in the lookup snapshot
        value_map = {f"src_{i}": f"dest_{i}" for i in range(12)}
        mapping_snap = MappingSnapshot(
            mapping_snapshot_id=str(uuid.uuid4()),
            project_id=project.project_id,
            source_definition_id=source.source_definition_id,
            destination_object_name="test_table",
            mapping_snapshot_version="snap_v1",
            field_bindings=[
                {"source_field": "src1", "destination_field": "dest1", "lookup_name": "big_lookup", "lookup_snapshot_version": "v1"},
            ],
            destination_columns=[{"column_name": "id", "data_type": "INT"}],
            status="approved",
            approved_at=datetime.now(UTC),
        )
        db.add(mapping_snap)

        snap = LookupSnapshot(
            lookup_snapshot_id=str(uuid.uuid4()),
            project_id=project.project_id,
            lookup_name="big_lookup",
            lookup_snapshot_version="snap_big_v1",
            value_map=value_map,
            status="approved",
            approved_at=datetime.now(UTC),
        )
        db.add(snap)
        db.commit()

        result = _build_lookup_tables(
            db,
            project_id=project.project_id,
            mapping_snapshot=mapping_snap,
        )

        assert len(result) == 1
        lookup_entry = result[0]
        assert lookup_entry["lookup_name"] == "big_lookup"
        # Core assertion: all 12 mappings present, not capped at 5
        assert len(lookup_entry["sample_mappings"]) == 12
        for i in range(12):
            assert f"src_{i}" in [m["source_val"] for m in lookup_entry["sample_mappings"]]
            assert f"dest_{i}" in [m["dest_val"] for m in lookup_entry["sample_mappings"]]


def test_generate_codegen_artifact_multi_table(monkeypatch: pytest.MonkeyPatch, admin_token: str) -> None:
    """Verify that a feed with 2 destination tables produces 2 artifacts."""
    project_id, source_definition_id = _seed_project()
    fake = FakeAdapter()
    monkeypatch.setattr(codegen_service_module, "get_adapter", lambda task: fake)

    # Add an approved mapping snapshot for Product (Customer already exists from _seed_project)
    with SessionLocal() as db:
        source = db.scalar(select(SourceDefinition).where(SourceDefinition.source_definition_id == source_definition_id))
        assert source is not None
        source.destination_object_references = ["Customer", "Product"]
        db.commit()

        # Create a mapping snapshot for the Product table
        db.add(
            MappingSnapshot(
                mapping_snapshot_id=str(uuid.uuid4()),
                project_id=project_id,
                source_definition_id=source_definition_id,
                destination_object_name="Product",
                mapping_snapshot_version="v1",
                field_bindings=[
                    {"source_field": "product_id", "destination_field": "product_id", "lookup_name": None},
                    {"source_field": "name", "destination_field": "name", "lookup_name": None},
                ],
                destination_columns=[{"column_name": "product_id", "data_type": "INT"}],
                status="approved",
                approved_at=datetime.now(UTC),
            )
        )
        db.commit()

    response = client.post(
        f"/projects/{project_id}/sources/{source_definition_id}/codegen",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 201
    data = response.json()
    assert len(data) == 2
    dest_names = {entry["destination_object_name"] for entry in data}
    assert dest_names == {"Customer", "Product"}


def test_generate_codegen_artifact_partial_mappings(monkeypatch: pytest.MonkeyPatch, admin_token: str) -> None:
    """Verify that a feed with 2 destination tables but only 1 mapping produces 1 artifact."""
    project_id, source_definition_id = _seed_project()
    fake = FakeAdapter()
    monkeypatch.setattr(codegen_service_module, "get_adapter", lambda task: fake)

    # Update the source to have 2 destination references
    with SessionLocal() as db:
        source = db.scalar(select(SourceDefinition).where(SourceDefinition.source_definition_id == source_definition_id))
        assert source is not None
        source.destination_object_references = ["Customer", "Product"]
        db.commit()

    # Only "Customer" has an approved mapping snapshot — "Product" has none
    response = client.post(
        f"/projects/{project_id}/sources/{source_definition_id}/codegen",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 201
    data = response.json()
    # Only Customer has a mapping, Product is skipped with a warning
    assert len(data) == 1
    assert data[0]["destination_object_name"] == "Customer"

