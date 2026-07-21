from __future__ import annotations

import uuid
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from sqlite_test_support import Base, SessionLocal, TEST_ENGINE
from migrations_engine.ai.adapter import AICallResult
from migrations_engine.app import app  # noqa: E402
from migrations_engine.auth.passwords import hash_password  # noqa: E402
from migrations_engine.config import get_settings  # noqa: E402
from migrations_engine.db.models import ProjectDefinition, ProjectMembership, ProjectRegistry, SourceDefinition, SourceSchemaArtifact, User  # noqa: E402
from migrations_engine.mapping import review as mapping_review_module, ai_schemas  # noqa: E402
from migrations_engine.roles import CENTRAL_TEAM_ROLE, PROJECT_STAKEHOLDER_ROLE, PM_ROLE  # noqa: E402

client = TestClient(app)

SAMPLE_DDL = (
    "CREATE TABLE Customer (\n"
    "  customer_id INT NOT NULL,\n"
    "  full_name VARCHAR(200),\n"
    "  email_address VARCHAR(255)\n"
    ");"
)


class FakeAdapter:
    def __init__(self, bindings: list[dict[str, str]], destination_table_name: str = "Customer") -> None:
        self.bindings = bindings
        self.destination_table_name = destination_table_name
        self.model_id = "test-model"
        self.calls: list[SimpleNamespace] = []

    def call(self, system: str, user: str, response_model: type[object]):
        self.calls.append(SimpleNamespace(system=system, user=user, response_model=response_model))
        
        bindings_objs = []
        for binding in self.bindings:
            b_data = {"binding_type": "direct", "reference_table_name": None}
            b_data.update(binding)
            bindings_objs.append(ai_schemas.Binding(**b_data))
            
        table_mapping = ai_schemas.TableProposal(
            destination_table_name=self.destination_table_name,
            bindings=bindings_objs,
        )
        parsed_result = response_model(
            tables=[table_mapping],
            error_code=None,
            error_message=None,
        )
        return AICallResult(parsed=parsed_result, raw_response="raw_response")


@pytest.fixture(scope="module", autouse=True)
def _setup_db() -> None:
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
        if db.scalar(select(User).where(User.email == "stakeholder@example.com")) is None:
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


def _seed_project(*, with_ddl: bool = True) -> tuple[str, str]:
    project_id = str(uuid.uuid4())
    definition_id = str(uuid.uuid4())
    source_id = str(uuid.uuid4())
    with SessionLocal() as db:
        stakeholder_user = db.scalar(select(User).where(User.email == "stakeholder@example.com"))
        assert stakeholder_user is not None
        db.add(
            ProjectDefinition(
                definition_id=definition_id,
                project_id=project_id,
                name="Mapping Test Project",
                status="active",
                domain_config={"destination_schema_ddl": SAMPLE_DDL} if with_ddl else {},
            )
        )
        db.add(
            ProjectRegistry(
                project_id=project_id,
                name="Mapping Test Project",
                definition_id=definition_id,
                status="active",
            )
        )
        db.flush()
        db.add(ProjectMembership(project_id=project_id, user_id=stakeholder_user.user_id))
        db.add(
            SourceDefinition(
                source_definition_id=source_id,
                project_id=project_id,
                source_type="csv",
                source_contract_version="v1",
                source_details={"label": "Customer Extract", "encoding": "utf-8"},
                status="active",
            )
        )
        db.add(
            SourceSchemaArtifact(
                schema_artifact_id=str(uuid.uuid4()),
                source_definition_id=source_id,
                source_slice_version="v1",
                columns=[
                    {"name": "customer_id", "inferred_type": "integer", "nullable": False, "max_length": None},
                    {"name": "full_name", "inferred_type": "text", "nullable": True, "max_length": 200},
                    {"name": "email_address", "inferred_type": "text", "nullable": True, "max_length": 255},
                ],
            )
        )
        db.commit()
    return project_id, source_id


def test_propose_requires_central_team(stakeholder_token: str) -> None:
    project_id, source_id = _seed_project()

    response = client.post(
        f"/projects/{project_id}/sources/{source_id}/mapping/propose",
        headers={"Authorization": f"Bearer {stakeholder_token}"},
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "forbidden"


def test_propose_creates_draft_snapshot(monkeypatch: pytest.MonkeyPatch, admin_token: str) -> None:
    project_id, source_id = _seed_project()
    fake = FakeAdapter(
        [
            {"source_field": "customer_id", "destination_field": "customer_id"},
            {"source_field": "full_name", "destination_field": "full_name"},
            {"source_field": "email_address", "destination_field": "email_address"},
        ]
    )
    monkeypatch.setattr(mapping_review_module, "get_adapter", lambda task: fake)

    response = client.post(
        f"/projects/{project_id}/sources/{source_id}/mapping/propose",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["status"] == "draft"
    assert data["destination_object_name"] == "Customer"
    assert data["destination_fields"] == ["customer_id", "full_name", "email_address"]
    assert len(data["field_bindings"]) == 3
    assert fake.calls[0].user.startswith("Source columns:")


def test_propose_persists_destination_data_type(monkeypatch: pytest.MonkeyPatch, admin_token: str) -> None:
    project_id, source_id = _seed_project()
    fake = FakeAdapter(
        [
            {"source_field": "customer_id", "destination_field": "customer_id", "destination_data_type": "INT"},
            {"source_field": "full_name", "destination_field": "full_name", "destination_data_type": "VARCHAR(200)"},
            {"source_field": "email_address", "destination_field": "email_address", "destination_data_type": None},
        ]
    )
    monkeypatch.setattr(mapping_review_module, "get_adapter", lambda task: fake)

    response = client.post(
        f"/projects/{project_id}/sources/{source_id}/mapping/propose",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200, response.text
    bindings = {b["destination_field"]: b for b in response.json()["field_bindings"]}
    assert bindings["customer_id"]["destination_data_type"] == "INT"
    assert bindings["full_name"]["destination_data_type"] == "VARCHAR(200)"
    assert bindings["email_address"]["destination_data_type"] is None


def test_propose_returns_schema_error_when_missing_ddl(monkeypatch: pytest.MonkeyPatch, admin_token: str) -> None:
    project_id, source_id = _seed_project(with_ddl=False)
    fake = FakeAdapter([])
    monkeypatch.setattr(mapping_review_module, "get_adapter", lambda task: fake)

    response = client.post(
        f"/projects/{project_id}/sources/{source_id}/mapping/propose",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "destination_schema_missing"


def test_get_returns_latest_snapshot(monkeypatch: pytest.MonkeyPatch, admin_token: str) -> None:
    project_id, source_id = _seed_project()
    fake = FakeAdapter([
        {"source_field": "customer_id", "destination_field": "customer_id"},
    ])
    monkeypatch.setattr(mapping_review_module, "get_adapter", lambda task: fake)

    client.post(
        f"/projects/{project_id}/sources/{source_id}/mapping/propose",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    response = client.get(
        f"/projects/{project_id}/sources/{source_id}/mapping",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200, response.text
    assert response.json()["status"] == "draft"


def test_get_returns_404_when_no_snapshot(admin_token: str) -> None:
    project_id, source_id = _seed_project()

    response = client.get(
        f"/projects/{project_id}/sources/{source_id}/mapping",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "mapping_not_found"


def test_patch_updates_field_bindings(monkeypatch: pytest.MonkeyPatch, admin_token: str) -> None:
    project_id, source_id = _seed_project()
    fake = FakeAdapter([
        {"source_field": "customer_id", "destination_field": "customer_id"},
    ])
    monkeypatch.setattr(mapping_review_module, "get_adapter", lambda task: fake)

    client.post(
        f"/projects/{project_id}/sources/{source_id}/mapping/propose",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    response = client.patch(
        f"/projects/{project_id}/sources/{source_id}/mapping",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "field_bindings": [
                {
                    "source_field": "customer_id",
                    "destination_field": "full_name",
                    "lookup_name": None,
                }
            ]
        },
    )

    assert response.status_code == 200, response.text
    assert response.json()["field_bindings"][0]["destination_field"] == "full_name"


def test_patch_rejects_invalid_destination_fields(monkeypatch: pytest.MonkeyPatch, admin_token: str) -> None:
    project_id, source_id = _seed_project()
    fake = FakeAdapter([
        {"source_field": "customer_id", "destination_field": "customer_id"},
    ])
    monkeypatch.setattr(mapping_review_module, "get_adapter", lambda task: fake)

    client.post(
        f"/projects/{project_id}/sources/{source_id}/mapping/propose",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    response = client.patch(
        f"/projects/{project_id}/sources/{source_id}/mapping",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "field_bindings": [
                {
                    "source_field": "customer_id",
                    "destination_field": "unknown_field",
                    "lookup_name": None,
                }
            ]
        },
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "mapping_invalid_destination_field"


def test_approve_writes_destination_object_references(monkeypatch: pytest.MonkeyPatch, admin_token: str, stakeholder_token: str) -> None:
    project_id, source_id = _seed_project()
    fake = FakeAdapter([
        {"source_field": "customer_id", "destination_field": "customer_id"},
    ])
    monkeypatch.setattr(mapping_review_module, "get_adapter", lambda task: fake)

    client.post(
        f"/projects/{project_id}/sources/{source_id}/mapping/propose",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    response = client.post(
        f"/projects/{project_id}/sources/{source_id}/mapping/approve",
        headers={"Authorization": f"Bearer {stakeholder_token}"},
    )

    assert response.status_code == 200, response.text
    assert response.json()["status"] == "approved"

    with SessionLocal() as db:
        source = db.scalar(select(SourceDefinition).where(SourceDefinition.source_definition_id == source_id))
        assert source is not None
        assert source.destination_object_references == ["Customer"]


def test_unapprove_mapping_by_pm(monkeypatch: pytest.MonkeyPatch, admin_token: str, stakeholder_token: str) -> None:
    project_id, source_id = _seed_project()
    fake = FakeAdapter([
        {"source_field": "customer_id", "destination_field": "customer_id"},
    ])
    monkeypatch.setattr(mapping_review_module, "get_adapter", lambda task: fake)

    client.post(
        f"/projects/{project_id}/sources/{source_id}/mapping/propose",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    client.post(
        f"/projects/{project_id}/sources/{source_id}/mapping/approve",
        headers={"Authorization": f"Bearer {stakeholder_token}"},
    )

    # Verify approved state
    with SessionLocal() as db:
        source = db.scalar(select(SourceDefinition).where(SourceDefinition.source_definition_id == source_id))
        assert source is not None
        assert source.destination_object_references == ["Customer"]

    # Seed and log in PM user
    with SessionLocal() as db:
        pm_user = db.scalar(select(User).where(User.email == "pm_test@example.com"))
        if not pm_user:
            db.add(
                User(
                    user_id=str(uuid.uuid4()),
                    email="pm_test@example.com",
                    display_name="PM Test",
                    password_hash=hash_password("pm-password"),
                    role=PM_ROLE,
                    status="active",
                )
            )
            db.commit()

    pm_token = _login("pm_test@example.com", "pm-password")

    # Update pm_user_id on project registry to grant PM access
    with SessionLocal() as db:
        pm_db = db.scalar(select(User).where(User.email == "pm_test@example.com"))
        registry = db.scalar(select(ProjectRegistry).where(ProjectRegistry.project_id == project_id))
        registry.pm_user_id = pm_db.user_id
        db.commit()

    response = client.post(
        f"/projects/{project_id}/sources/{source_id}/mapping/unapprove",
        headers={"Authorization": f"Bearer {pm_token}"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "draft"

    # Verify unapproved state in DB
    with SessionLocal() as db:
        source = db.scalar(select(SourceDefinition).where(SourceDefinition.source_definition_id == source_id))
        assert source is not None
        assert source.destination_object_references == []


def test_reject_marks_snapshot_rejected(monkeypatch: pytest.MonkeyPatch, admin_token: str, stakeholder_token: str) -> None:
    project_id, source_id = _seed_project()
    fake = FakeAdapter([
        {"source_field": "customer_id", "destination_field": "customer_id"},
    ])
    monkeypatch.setattr(mapping_review_module, "get_adapter", lambda task: fake)

    client.post(
        f"/projects/{project_id}/sources/{source_id}/mapping/propose",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    response = client.post(
        f"/projects/{project_id}/sources/{source_id}/mapping/reject",
        headers={"Authorization": f"Bearer {stakeholder_token}"},
        json={"reason": "Needs another source field mapped."},
    )

    assert response.status_code == 200, response.text
    assert response.json()["status"] == "rejected"


def test_patch_422_on_approved_snapshot(monkeypatch: pytest.MonkeyPatch, admin_token: str, stakeholder_token: str) -> None:
    project_id, source_id = _seed_project()
    fake = FakeAdapter([
        {"source_field": "customer_id", "destination_field": "customer_id"},
    ])
    monkeypatch.setattr(mapping_review_module, "get_adapter", lambda task: fake)

    client.post(
        f"/projects/{project_id}/sources/{source_id}/mapping/propose",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    client.post(
        f"/projects/{project_id}/sources/{source_id}/mapping/approve",
        headers={"Authorization": f"Bearer {stakeholder_token}"},
    )

    response = client.patch(
        f"/projects/{project_id}/sources/{source_id}/mapping",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "field_bindings": [
                {
                    "source_field": "customer_id",
                    "destination_field": "full_name",
                    "lookup_name": None,
                }
            ]
        },
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "mapping_not_editable"


def test_propose_creates_multiple_snapshots_and_validates_table_names(monkeypatch: pytest.MonkeyPatch, admin_token: str) -> None:
    project_id, source_id = _seed_project()
    
    class MultiTableFakeAdapter:
        def __init__(self) -> None:
            self.model_id = "test-model"
            
        def call(self, system: str, user: str, response_model: type[object]):
            parsed = response_model(
                tables=[
                    ai_schemas.TableProposal(
                        destination_table_name="Customer",
                        bindings=[
                            ai_schemas.Binding(
                                source_field="customer_id",
                                destination_field="customer_id",
                                binding_type="direct"
                            )
                        ]
                    ),
                    ai_schemas.TableProposal(
                        destination_table_name="UnknownTable",
                        bindings=[
                            ai_schemas.Binding(
                                source_field="email_address",
                                destination_field="email",
                                binding_type="direct"
                            )
                        ]
                    )
                ]
            )
            return AICallResult(parsed=parsed, raw_response="raw")

    monkeypatch.setattr(mapping_review_module, "get_adapter", lambda task: MultiTableFakeAdapter())
    
    response = client.post(
        f"/projects/{project_id}/sources/{source_id}/mapping/propose",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "destination_table_invalid"

    with SessionLocal() as db:
        definition = db.scalar(select(ProjectDefinition).join(ProjectRegistry).where(ProjectRegistry.project_id == project_id))
        assert definition is not None
        definition.domain_config = {
            "destination_schema_ddl": (
                "CREATE TABLE Customer (\n"
                "  customer_id INT NOT NULL,\n"
                "  full_name VARCHAR(200)\n"
                ");\n"
                "CREATE TABLE OrderTable (\n"
                "  order_id INT NOT NULL,\n"
                "  customer_fk INT\n"
                ");"
            )
        }
        db.commit()
        
    class ValidMultiTableFakeAdapter:
        def __init__(self) -> None:
            self.model_id = "test-model"
            
        def call(self, system: str, user: str, response_model: type[object]):
            parsed = response_model(
                tables=[
                    ai_schemas.TableProposal(
                        destination_table_name="Customer",
                        bindings=[
                            ai_schemas.Binding(
                                source_field="customer_id",
                                destination_field="customer_id",
                                binding_type="direct"
                            )
                        ]
                    ),
                    ai_schemas.TableProposal(
                        destination_table_name="OrderTable",
                        bindings=[
                            ai_schemas.Binding(
                                source_field="customer_id",
                                destination_field="order_id",
                                binding_type="direct"
                            ),
                            ai_schemas.Binding(
                                source_field="customer_id",
                                destination_field="customer_fk",
                                binding_type="lookup_fk",
                                reference_table_name="Customer"
                            ),
                            ai_schemas.Binding(
                                source_field="email_address",
                                destination_field="status_fk",
                                binding_type="lookup_fk",
                                reference_table_name="StatusTable"
                            )
                        ]
                    )
                ]
            )
            return AICallResult(parsed=parsed, raw_response="raw")

    monkeypatch.setattr(mapping_review_module, "get_adapter", lambda task: ValidMultiTableFakeAdapter())
    
    response = client.post(
        f"/projects/{project_id}/sources/{source_id}/mapping/propose",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200, response.text
    
    resp_customer = client.get(
        f"/projects/{project_id}/sources/{source_id}/mapping?destination_object_name=Customer",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp_customer.status_code == 200
    data_customer = resp_customer.json()
    assert data_customer["destination_object_name"] == "Customer"
    assert len(data_customer["field_bindings"]) == 1
    
    resp_order = client.get(
        f"/projects/{project_id}/sources/{source_id}/mapping?destination_object_name=OrderTable",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp_order.status_code == 200
    data_order = resp_order.json()
    assert data_order["destination_object_name"] == "OrderTable"
    assert len(data_order["lookup_table_references"]) == 1
    assert data_order["lookup_table_references"][0]["lookup_name"] == "email_address"
    assert data_order["lookup_table_references"][0]["destination_table_name"] == "StatusTable"
    
    with SessionLocal() as db:
        snapshot = db.scalar(
            select(mapping_review_module.MappingSnapshot)
            .where(
                mapping_review_module.MappingSnapshot.project_id == project_id,
                mapping_review_module.MappingSnapshot.destination_object_name == "OrderTable"
            )
        )
        assert snapshot is not None
        bindings = {b["source_field"]: b for b in snapshot.field_bindings}
        assert bindings["customer_id"]["binding_type"] == "detail_fk"
        assert bindings["email_address"]["binding_type"] == "lookup_fk"


def test_bulk_approve_and_reject_multiple_snapshots(monkeypatch: pytest.MonkeyPatch, admin_token: str, stakeholder_token: str) -> None:
    project_id, source_id = _seed_project()
    with SessionLocal() as db:
        definition = db.scalar(select(ProjectDefinition).join(ProjectRegistry).where(ProjectRegistry.project_id == project_id))
        assert definition is not None
        definition.domain_config = {
            "destination_schema_ddl": (
                "CREATE TABLE Customer (\n"
                "  customer_id INT NOT NULL,\n"
                "  full_name VARCHAR(200)\n"
                ");\n"
                "CREATE TABLE OrderTable (\n"
                "  order_id INT NOT NULL,\n"
                "  customer_fk INT\n"
                ");"
            )
        }
        db.commit()

    class ValidMultiTableFakeAdapter:
        def __init__(self) -> None:
            self.model_id = "test-model"
            
        def call(self, system: str, user: str, response_model: type[object]):
            parsed = response_model(
                tables=[
                    ai_schemas.TableProposal(
                        destination_table_name="Customer",
                        bindings=[
                            ai_schemas.Binding(
                                source_field="customer_id",
                                destination_field="customer_id",
                                binding_type="direct"
                            )
                        ]
                    ),
                    ai_schemas.TableProposal(
                        destination_table_name="OrderTable",
                        bindings=[
                            ai_schemas.Binding(
                                source_field="customer_id",
                                destination_field="order_id",
                                binding_type="direct"
                            )
                        ]
                    )
                ]
            )
            return AICallResult(parsed=parsed, raw_response="raw")

    monkeypatch.setattr(mapping_review_module, "get_adapter", lambda task: ValidMultiTableFakeAdapter())
    
    # 1. Propose mapping to create draft snapshots
    response = client.post(
        f"/projects/{project_id}/sources/{source_id}/mapping/propose",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200

    # 2. Approve all (bulk approve)
    resp_approve = client.post(
        f"/projects/{project_id}/sources/{source_id}/mapping/approve",
        headers={"Authorization": f"Bearer {stakeholder_token}"},
    )
    assert resp_approve.status_code == 200

    with SessionLocal() as db:
        snapshots = db.scalars(
            select(mapping_review_module.MappingSnapshot)
            .where(
                mapping_review_module.MappingSnapshot.project_id == project_id,
                mapping_review_module.MappingSnapshot.source_definition_id == source_id,
            )
        ).all()
        assert len(snapshots) == 2
        for s in snapshots:
            assert s.status == "approved"
            # Revert to draft for testing reject
            s.status = "draft"
        db.commit()

    # 3. Reject all (bulk reject)
    resp_reject = client.post(
        f"/projects/{project_id}/sources/{source_id}/mapping/reject",
        headers={"Authorization": f"Bearer {stakeholder_token}"},
        json={"reason": "Bulk rejection test"}
    )
    assert resp_reject.status_code == 200

    with SessionLocal() as db:
        snapshots = db.scalars(
            select(mapping_review_module.MappingSnapshot)
            .where(
                mapping_review_module.MappingSnapshot.project_id == project_id,
                mapping_review_module.MappingSnapshot.source_definition_id == source_id,
            )
        ).all()
        assert len(snapshots) == 2
        for s in snapshots:
            assert s.status == "rejected"


def test_feed_hints_and_ai_tracing(monkeypatch: pytest.MonkeyPatch, admin_token: str) -> None:
    project_id, source_id = _seed_project()
    
    # 1. Update hints
    response = client.patch(
        f"/projects/{project_id}/sources/{source_id}/hints",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"mapping_hints": "Pre-parsed dates: YYYYMMDD"}
    )
    assert response.status_code == 200, response.text
    assert response.json()["mapping_hints"] == "Pre-parsed dates: YYYYMMDD"

    called_user_prompt = None
    
    class TracingFakeAdapter(FakeAdapter):
        def call(self, system_prompt, user_prompt, response_schema):
            nonlocal called_user_prompt
            called_user_prompt = user_prompt
            return super().call(system_prompt, user_prompt, response_schema)
            
    fake = TracingFakeAdapter([
        {"source_field": "customer_id", "destination_field": "customer_id"},
    ])
    monkeypatch.setattr(mapping_review_module, "get_adapter", lambda task, policy=None: fake)

    # Inject project constraint
    from migrations_engine.db.models import ProjectDefinition, ProjectRegistry
    with SessionLocal() as db:
        registry = db.get(ProjectRegistry, project_id)
        project_def = db.get(ProjectDefinition, registry.definition_id)
        project_def.constraints = ["Max value 100"]
        db.commit()

    # 2. Propose mapping
    propose_resp = client.post(
        f"/projects/{project_id}/sources/{source_id}/mapping/propose",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert propose_resp.status_code == 200, propose_resp.text
    
    # Verify trace was stored and prompt contains context
    assert called_user_prompt is not None
    assert "Mapping hints (operator-supplied):" in called_user_prompt
    assert "Pre-parsed dates: YYYYMMDD" in called_user_prompt
    assert "Project constraints:" in called_user_prompt
    assert "Max value 100" in called_user_prompt

    # Fetch latest snapshot using GET
    get_resp = client.get(
        f"/projects/{project_id}/sources/{source_id}/mapping",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert get_resp.status_code == 200


def test_propose_skips_tables_already_approved_project_wide(
    monkeypatch: pytest.MonkeyPatch, admin_token: str
) -> None:
    """Re-uploading a feed must not create a new snapshot for a destination
    table that already has an approved snapshot from a different feed."""
    from migrations_engine.db.models import MappingSnapshot, new_id
    from sqlite_test_support import SessionLocal

    # Seed an approved snapshot for "Customer" under a *different* active feed
    project_id, source_id = _seed_project()

    with SessionLocal() as db:
        from migrations_engine.db.models import Feed as FeedModel
        other_feed = FeedModel(
            source_definition_id=new_id(),
            project_id=project_id,
            source_type="csv",
            source_contract_version="v1",
            status="active",
            source_details={"label": "other"},
        )
        db.add(other_feed)
        db.flush()
        existing = MappingSnapshot(
            mapping_snapshot_id=new_id(),
            project_id=project_id,
            source_definition_id=other_feed.source_definition_id,
            destination_object_name="Customer",
            mapping_snapshot_version="v1",
            field_bindings=[],
            status="approved",
        )
        db.add(existing)
        db.commit()

    fake = FakeAdapter([
        {"source_field": "customer_id", "destination_field": "customer_id"},
    ])
    monkeypatch.setattr(mapping_review_module, "get_adapter", lambda task: fake)

    response = client.post(
        f"/projects/{project_id}/sources/{source_id}/mapping/propose",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "mapping_already_proposed"

