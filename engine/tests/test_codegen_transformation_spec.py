"""Tests for the POST /projects/{project_id}/sources/{source_definition_id}/transformation-spec endpoint."""
from __future__ import annotations

import uuid
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from sqlite_test_support import Base, SessionLocal, TEST_ENGINE
from migrations_engine.app import app  # noqa: E402
from migrations_engine.auth.passwords import hash_password  # noqa: E402
from migrations_engine.config import get_settings  # noqa: E402
from migrations_engine.db.models import (  # noqa: E402
    Feed,
    MappingSnapshot,
    ProjectDefinition,
    ProjectFiber,
    ProjectRegistry,
    SourceDefinition,
    SourceSchemaArtifact,
    SourceSlice,
    User,
)
from migrations_engine.roles import CENTRAL_TEAM_ROLE  # noqa: E402

client = TestClient(app)


class FakeAdapter:
    def __init__(self) -> None:
        self.model_id = "gpt-4o-mini"
        self.calls: list = []

    def call(self, system: str, user: str, response_model: type[object]):
        from migrations_engine.ai.adapter import AICallResult
        self.calls.append(SimpleNamespace(system=system, user=user, response_model=response_model))
        parsed = response_model(
            staging_ddl=(
                "CREATE TABLE stg_customer (\n"
                "  customer_id INT NOT NULL,\n"
                "  full_name VARCHAR(255)\n"
                ");"
            ),
            lookup_ddl=[],
            seed_data=[],
            stored_procedures=[],
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


def _seed_project_for_spec(db: Session) -> tuple[str, str]:
    """Create a project with a source, fibers, mapping snapshots, and source schema artifact."""
    project_id = f"proj_{uuid.uuid4().hex}"
    definition_id = f"def_{uuid.uuid4().hex}"
    source_id = f"src_{uuid.uuid4().hex}"

    with db.begin():
        db.add(
            ProjectDefinition(
                definition_id=definition_id,
                project_id=project_id,
                name="Spec Test Project",
                status="active",
                domain_config={"target_db_engine": "postgresql", "staging_schema": "stg"},
            )
        )
        db.add(
            ProjectRegistry(
                project_id=project_id,
                name="Spec Test Project",
                definition_id=definition_id,
                status="active",
            )
        )
        db.add(
            Feed(
                source_definition_id=source_id,
                project_id=project_id,
                source_type="csv",
                source_contract_version="v1",
                source_details={"label": "Customer Extract", "encoding": "utf-8"},
                status="active",
            )
        )
        db.commit()

    return project_id, source_id


def _add_fibers_and_snapshots(db: Session, project_id: str, source_id: str) -> None:
    """Add lookup and domain fibers plus mapping snapshots and source schema artifact."""
    with db.begin():
        # Lookup fiber
        db.add(ProjectFiber(
            fiber_id=f"fiber_lookup_{uuid.uuid4().hex}",
            feed_id=source_id,
            project_id=project_id,
            fiber_type="lookup",
            fiber_key="country_lookup",
            status="business_approved",
            source="auto",
            proposed_mappings=[
                {"sourceValue": "US", "destEntryId": "entry-1", "destRow": None},
                {"sourceValue": "CA", "destEntryId": "entry-2", "destRow": None},
            ],
            field_bindings=[],
        ))
        # Domain fiber
        db.add(ProjectFiber(
            fiber_id=f"fiber_domain_{uuid.uuid4().hex}",
            feed_id=source_id,
            project_id=project_id,
            fiber_type="domain_object",
            fiber_key="Customer",
            status="business_approved",
            source="auto",
            proposed_mappings=[],
            field_bindings=[
                {"source_field": "cust_id", "destination_field": "customer_id", "lookup_name": None},
                {"source_field": "full_name", "destination_field": "full_name", "lookup_name": None},
            ],
        ))
        # Approved mapping snapshot for the domain fiber
        db.add(
            MappingSnapshot(
                mapping_snapshot_id=f"snap_{uuid.uuid4().hex}",
                project_id=project_id,
                source_definition_id=source_id,
                destination_object_name="Customer",
                mapping_snapshot_version="v1",
                field_bindings=[
                    {"source_field": "cust_id", "destination_field": "customer_id", "lookup_name": None},
                    {"source_field": "full_name", "destination_field": "full_name", "lookup_name": None},
                ],
                status="approved",
                approved_at=None,
                approved_by_user_id=None,
                destination_columns=[
                    {"name": "customer_id", "destination_data_type": "integer", "nullable": False},
                    {"name": "full_name", "destination_data_type": "text", "nullable": True},
                ],
            )
        )
        # Approved mapping snapshot for the lookup fiber
        db.add(
            MappingSnapshot(
                mapping_snapshot_id=f"snap_lookup_{uuid.uuid4().hex}",
                project_id=project_id,
                source_definition_id=source_id,
                destination_object_name="country_lookup",
                mapping_snapshot_version="v1",
                field_bindings=[],
                status="approved",
                approved_at=None,
                approved_by_user_id=None,
            )
        )
        # Source schema artifact with type info
        db.add(
            SourceSchemaArtifact(
                schema_artifact_id=f"ssa_{uuid.uuid4().hex}",
                source_definition_id=source_id,
                source_slice_version="v1",
                columns=[
                    {"name": "cust_id", "inferred_type": "integer", "nullable": False, "max_length": None},
                    {"name": "full_name", "inferred_type": "text", "nullable": True, "max_length": 255},
                ],
            )
        )
        db.commit()


def test_transformation_spec_returns_spec_with_type_hints(admin_token: str) -> None:
    """Verify the endpoint returns a spec string with inline [integer] type hints."""
    project_id, source_id = _seed_project_for_spec(SessionLocal())
    with SessionLocal() as db:
        _add_fibers_and_snapshots(db, project_id, source_id)

    response = client.post(
        f"/projects/{project_id}/sources/{source_id}/transformation-spec",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200, response.text
    data = response.json()
    spec = data["spec"]

    assert "### Transformation Specification for Feed: Customer Extract" in spec
    assert "### 1. Approved Lookup Data" in spec
    assert 'Approved lookup: "country_lookup"' in spec
    assert "### 2. Approved Destination Mappings" in spec
    assert "Source table:" in spec
    assert "### 3. Unmapped Required Destination Fields" in spec
    # Type hint assertion — [integer] from SourceSchemaArtifact
    assert "[integer]" in spec
    assert "[text]" in spec


def test_transformation_spec_404_unknown_project(admin_token: str) -> None:
    response = client.post(
        f"/projects/unknown-proj/sources/{uuid.uuid4()}/transformation-spec",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 404


def test_transformation_spec_404_unknown_source(admin_token: str) -> None:
    response = client.post(
        f"/projects/unknown-proj/sources/unknown-src/transformation-spec",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 404


def test_transformation_spec_no_fibers(admin_token: str) -> None:
    """When feed has no approved fibers, spec contains 'no approved mappings'."""
    from sqlalchemy import delete

    project_id, source_id = _seed_project_for_spec(SessionLocal())
    with SessionLocal() as db:
        _add_fibers_and_snapshots(db, project_id, source_id)

    # Override: clear fibers from DB
    with SessionLocal() as db:
        db.execute(delete(ProjectFiber).where(ProjectFiber.feed_id == source_id))
        db.commit()

    response = client.post(
        f"/projects/{project_id}/sources/{source_id}/transformation-spec",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200
    spec = response.json()["spec"]
    assert "No approved destination mappings were identified" in spec
    assert "No approved lookup data was identified" in spec


def test_transformation_spec_includes_unmapped_section(admin_token: str) -> None:
    """When a domain fiber has unmapped required fields, they appear in the spec."""
    project_id = f"proj_unmapped_{uuid.uuid4().hex}"
    definition_id = f"def_unmapped_{uuid.uuid4().hex}"
    source_id = f"src_unmapped_{uuid.uuid4().hex}"
    snap_id = f"snap_unmapped_{uuid.uuid4().hex}"

    with SessionLocal() as db:
        db.add(ProjectDefinition(
            definition_id=definition_id, project_id=project_id,
            name="Unmapped Test", status="active",
            domain_config={"target_db_engine": "postgresql", "staging_schema": "stg"},
        ))
        db.add(ProjectRegistry(
            project_id=project_id, name="Unmapped Test",
            definition_id=definition_id, status="active",
        ))
        db.add(Feed(
            source_definition_id=source_id, project_id=project_id,
            source_type="csv", source_contract_version="v1",
            source_details={"label": "Unmapped Feed", "encoding": "utf-8"},
            status="active",
        ))
        db.add(ProjectFiber(
            fiber_id=f"fiber_unmapped_{uuid.uuid4().hex}",
            feed_id=source_id, project_id=project_id,
            fiber_type="domain_object", fiber_key="Customer",
            status="business_approved", source="auto",
            proposed_mappings=[], field_bindings=[],
        ))
        db.add(MappingSnapshot(
            mapping_snapshot_id=snap_id, project_id=project_id,
            source_definition_id=source_id,
            destination_object_name="Customer",
            mapping_snapshot_version="v1",
            field_bindings=[],
            status="approved", approved_at=None, approved_by_user_id=None,
            destination_columns=[
                {"name": "customer_id", "destination_data_type": "integer", "nullable": False},
                {"name": "email", "destination_data_type": "text", "nullable": False},
            ],
        ))
        db.commit()

    response = client.post(
        f"/projects/{project_id}/sources/{source_id}/transformation-spec",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200
    spec = response.json()["spec"]
    assert "**Customer**" in spec
    assert "**Customer**: 2 required field(s) not yet mapped" in spec


def test_generate_transformation_spec_directly_with_fiber_fallback(admin_token: str) -> None:
    """When no approved MappingSnapshot exists for a domain fiber, use fiber.field_bindings."""
    from migrations_engine.codegen.service import generate_transformation_spec

    project_id = f"proj_fallback_{uuid.uuid4().hex}"
    definition_id = f"def_fallback_{uuid.uuid4().hex}"
    source_id = f"src_fallback_{uuid.uuid4().hex}"

    with SessionLocal() as db:
        db.add(ProjectDefinition(
            definition_id=definition_id, project_id=project_id,
            name="Fallback Test", status="active",
            domain_config={"target_db_engine": "postgresql", "staging_schema": "stg"},
        ))
        db.add(ProjectRegistry(
            project_id=project_id, name="Fallback Test",
            definition_id=definition_id, status="active",
        ))
        db.add(Feed(
            source_definition_id=source_id, project_id=project_id,
            source_type="csv", source_contract_version="v1",
            source_details={"label": "Fallback Feed", "encoding": "utf-8"},
            status="active",
        ))
        db.add(ProjectFiber(
            fiber_id=f"fiber_fb_{uuid.uuid4().hex}",
            feed_id=source_id, project_id=project_id,
            fiber_type="domain_object", fiber_key="PendingTable",
            status="business_approved", source="auto",
            proposed_mappings=[],
            field_bindings=[
                {"source_field": "cust_id", "destination_field": "customer_id", "lookup_name": None},
            ],
        ))
        # Source schema artifact with type info for type hint verification
        db.add(SourceSchemaArtifact(
            schema_artifact_id=f"ssa_fb_{uuid.uuid4().hex}",
            source_definition_id=source_id, source_slice_version="v1",
            columns=[
                {"name": "cust_id", "inferred_type": "integer", "nullable": False, "max_length": None},
            ],
        ))
        db.commit()

    with SessionLocal() as db:
        spec = generate_transformation_spec(db, project_id=project_id, source_definition_id=source_id)

    assert "PendingTable" in spec
    assert "cust_id" in spec
    assert "customer_id" in spec
    assert "[integer]" in spec
