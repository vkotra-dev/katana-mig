from __future__ import annotations

import uuid
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from sqlite_test_support import Base, SessionLocal, TEST_ENGINE
from migrations_engine.app import app  # noqa: E402
from migrations_engine.auth.passwords import hash_password  # noqa: E402
from migrations_engine.config import get_settings  # noqa: E402
from migrations_engine.db.models import ProjectDefinition, ProjectRegistry, SourceDefinition, SourceSchemaArtifact, User  # noqa: E402
from migrations_engine.mapping import review as mapping_review_module  # noqa: E402
from migrations_engine.roles import CENTRAL_TEAM_ROLE, PROJECT_STAKEHOLDER_ROLE  # noqa: E402

client = TestClient(app)

SAMPLE_DDL = (
    "CREATE TABLE Customer (\n"
    "  customer_id INT NOT NULL,\n"
    "  full_name VARCHAR(200),\n"
    "  email_address VARCHAR(255)\n"
    ");"
)


class FakeAdapter:
    def __init__(self, bindings: list[dict[str, str]]) -> None:
        self.bindings = bindings
        self.model_id = "claude-sonnet-4-6"
        self.calls: list[SimpleNamespace] = []

    def call(self, system: str, user: str, response_model: type[object]):
        self.calls.append(SimpleNamespace(system=system, user=user, response_model=response_model))
        return response_model(
            bindings=[mapping_review_module._ProposedBinding(**binding) for binding in self.bindings]
        )


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
        admin_user = db.scalar(select(User).where(User.role == CENTRAL_TEAM_ROLE))
        assert admin_user is not None
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


def test_approve_writes_destination_object_references(monkeypatch: pytest.MonkeyPatch, admin_token: str) -> None:
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
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200, response.text
    assert response.json()["status"] == "approved"

    with SessionLocal() as db:
        source = db.scalar(select(SourceDefinition).where(SourceDefinition.source_definition_id == source_id))
        assert source is not None
        assert source.destination_object_references == ["Customer"]


def test_reject_marks_snapshot_rejected(monkeypatch: pytest.MonkeyPatch, admin_token: str) -> None:
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
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"reason": "Needs another source field mapped."},
    )

    assert response.status_code == 200, response.text
    assert response.json()["status"] == "rejected"


def test_patch_422_on_approved_snapshot(monkeypatch: pytest.MonkeyPatch, admin_token: str) -> None:
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

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "mapping_not_editable"
