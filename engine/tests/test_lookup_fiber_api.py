from __future__ import annotations

import importlib
import json
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from sqlite_test_support import Base, SessionLocal, TEST_ENGINE

from migrations_engine.auth.passwords import hash_password  # noqa: E402
from migrations_engine.config import get_settings  # noqa: E402
from migrations_engine.db.models import (  # noqa: E402
    Feed,
    LookupDestEntry,
    LookupDestFeed,
    LookupMapping,
    LookupSourceEntry,
    ProjectDefinition,
    ProjectFiber,
    ProjectMembership,
    ProjectRegistry,
    User,
)
from migrations_engine.management import access as access_module  # noqa: E402
from migrations_engine.management import fibers as fibers_module  # noqa: E402
from migrations_engine.roles import CENTRAL_TEAM_ROLE, PROJECT_STAKEHOLDER_ROLE, READ_ONLY_AUDITOR_ROLE  # noqa: E402
import migrations_engine.api.deps as deps_module  # noqa: E402
import migrations_engine.app as app_module  # noqa: E402
import migrations_engine.routes.analysis as analysis_routes_module  # noqa: E402
import migrations_engine.routes.auth as auth_routes_module  # noqa: E402
import migrations_engine.routes.codegen as codegen_routes_module  # noqa: E402
import migrations_engine.routes.feed_slice_approval as feed_slice_approval_routes_module  # noqa: E402
import migrations_engine.routes.feeds as feeds_routes_module  # noqa: E402
import migrations_engine.routes.fibers as fibers_routes_module  # noqa: E402
import migrations_engine.routes.gates as gates_routes_module  # noqa: E402
import migrations_engine.routes.lookup as lookup_routes_module  # noqa: E402
import migrations_engine.routes.mapping as mapping_routes_module  # noqa: E402
import migrations_engine.routes.mapping_snapshots as mapping_snapshots_routes_module  # noqa: E402
import migrations_engine.routes.projects as projects_routes_module  # noqa: E402
import migrations_engine.routes.reconciliation as reconciliation_routes_module  # noqa: E402
import migrations_engine.routes.runs as runs_routes_module  # noqa: E402
import migrations_engine.routes.users as users_routes_module  # noqa: E402

deps_module.SessionLocal = SessionLocal
for module in [
    deps_module,
    access_module,
    fibers_module,
    auth_routes_module,
    users_routes_module,
    projects_routes_module,
    runs_routes_module,
    analysis_routes_module,
    gates_routes_module,
    codegen_routes_module,
    mapping_routes_module,
    mapping_snapshots_routes_module,
    lookup_routes_module,
    reconciliation_routes_module,
    feeds_routes_module,
    feed_slice_approval_routes_module,
    fibers_routes_module,
    app_module,
]:
    importlib.reload(module)

app = app_module.app

client = TestClient(app)

_SOURCE_VALUES = ["DB", "SAV", "CUR"]
_DEST_CSV = "id,label\n1,Database\n2,Savings\n3,Current"


class FakeLookupAdapter:
    def call(self, system_prompt: str, user_prompt: str, response_model):
        payload = json.loads(user_prompt)
        dest_rows = payload["destination_rows"]
        first_id = dest_rows[0]["entry_id"] if dest_rows else "no-entry"
        proposals = [
            {"source_value": value, "dest_entry_id": first_id, "confidence_score": 0.9}
            for value in payload["source_values"]
        ]
        return response_model.model_validate({"proposals": proposals})


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
                    display_name=settings.bootstrap_admin_display_name,
                    password_hash=hash_password(settings.bootstrap_admin_password),
                    role=CENTRAL_TEAM_ROLE,
                    status="active",
                )
            )
        if db.scalar(select(User).where(User.email == "stakeholder-fiber@example.com")) is None:
            db.add(
                User(
                    user_id=str(uuid.uuid4()),
                    email="stakeholder-fiber@example.com",
                    display_name="Fiber Stakeholder",
                    password_hash=hash_password("pass12345"),
                    role=PROJECT_STAKEHOLDER_ROLE,
                    status="active",
                )
            )
        if db.scalar(select(User).where(User.email == "auditor-fiber@example.com")) is None:
            db.add(
                User(
                    user_id=str(uuid.uuid4()),
                    email="auditor-fiber@example.com",
                    display_name="Fiber Auditor",
                    password_hash=hash_password("pass12345"),
                    role=READ_ONLY_AUDITOR_ROLE,
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
    return _login("stakeholder-fiber@example.com", "pass12345")


@pytest.fixture
def auditor_token() -> str:
    return _login("auditor-fiber@example.com", "pass12345")


def _seed_project_and_feed() -> tuple[str, str]:
    project_id = str(uuid.uuid4())
    definition_id = str(uuid.uuid4())
    feed_id = str(uuid.uuid4())
    with SessionLocal() as db:
        db.add(ProjectDefinition(definition_id=definition_id, project_id=project_id, name="Fiber AI", status="active"))
        db.add(ProjectRegistry(project_id=project_id, name="Fiber AI", definition_id=definition_id, status="active"))
        db.add(
            Feed(
                source_definition_id=feed_id,
                project_id=project_id,
                source_type="csv",
                source_contract_version="v1",
                source_details={"label": "Lookup Feed", "encoding": "utf-8"},
                status="active",
            )
        )
        db.commit()
    return project_id, feed_id


def _create_lookup_fiber(project_id: str, feed_id: str, *, token: str) -> str:
    response = client.post(
        f"/projects/{project_id}/feeds/{feed_id}/fibers",
        json={"fiber_type": "lookup", "fiber_key": "account_type"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 201, response.text
    fiber_id = response.json()["fiber_id"]
    with SessionLocal() as db:
        fiber = db.get(ProjectFiber, fiber_id)
        assert fiber is not None
        fiber.status = "deferred"
        db.commit()
    return fiber_id


def test_lookup_inputs_transitions_fiber_and_creates_lookup_rows(monkeypatch: pytest.MonkeyPatch, admin_token: str) -> None:
    project_id, feed_id = _seed_project_and_feed()
    fiber_id = _create_lookup_fiber(project_id, feed_id, token=admin_token)
    monkeypatch.setattr(fibers_module, "get_adapter", lambda task: FakeLookupAdapter())

    response = client.post(
        f"/projects/{project_id}/feeds/{feed_id}/fibers/{fiber_id}/lookup-inputs",
        json={"source_values": _SOURCE_VALUES, "destination_lookup_csv": _DEST_CSV},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "mapped"
    assert len(body["proposed_mappings"]) == 3

    with SessionLocal() as db:
        fiber = db.get(ProjectFiber, fiber_id)
        assert fiber is not None
        assert fiber.status == "mapped"

    source_response = client.get(
        f"/projects/{project_id}/feeds/{feed_id}/fibers/{fiber_id}/source-entries",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert source_response.status_code == 200, source_response.text
    assert {row["source_value"] for row in source_response.json()} == set(_SOURCE_VALUES)

    dest_entries_response = client.get(
        f"/projects/{project_id}/feeds/{feed_id}/fibers/{fiber_id}/dest-feed/entries",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert dest_entries_response.status_code == 200, dest_entries_response.text
    assert len(dest_entries_response.json()) == 3

    mappings_response = client.get(
        f"/projects/{project_id}/feeds/{feed_id}/fibers/{fiber_id}/mappings",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert mappings_response.status_code == 200, mappings_response.text
    assert len(mappings_response.json()) == 3
    assert all(row["status"] == "proposed" for row in mappings_response.json())
    assert all(row["mapped_by"] == "ai" for row in mappings_response.json())


def test_lookup_inputs_rejects_non_lookup_fiber(admin_token: str) -> None:
    project_id, feed_id = _seed_project_and_feed()
    with SessionLocal() as db:
        fiber = ProjectFiber(
            fiber_id=str(uuid.uuid4()),
            feed_id=feed_id,
            project_id=project_id,
            fiber_type="domain_object",
            fiber_key="account_type",
            status="deferred",
            source="manual",
        )
        db.add(fiber)
        db.commit()
        fiber_id = fiber.fiber_id

    response = client.post(
        f"/projects/{project_id}/feeds/{feed_id}/fibers/{fiber_id}/lookup-inputs",
        json={"source_values": _SOURCE_VALUES, "destination_lookup_csv": _DEST_CSV},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "fiber_not_lookup"


def test_lookup_inputs_rejects_already_mapped_fiber(monkeypatch: pytest.MonkeyPatch, admin_token: str) -> None:
    project_id, feed_id = _seed_project_and_feed()
    fiber_id = _create_lookup_fiber(project_id, feed_id, token=admin_token)
    monkeypatch.setattr(fibers_module, "get_adapter", lambda task: FakeLookupAdapter())

    first = client.post(
        f"/projects/{project_id}/feeds/{feed_id}/fibers/{fiber_id}/lookup-inputs",
        json={"source_values": _SOURCE_VALUES, "destination_lookup_csv": _DEST_CSV},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert first.status_code == 200, first.text

    second = client.post(
        f"/projects/{project_id}/feeds/{feed_id}/fibers/{fiber_id}/lookup-inputs",
        json={"source_values": _SOURCE_VALUES, "destination_lookup_csv": _DEST_CSV},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "fiber_not_deferred"


def test_lookup_inputs_requires_central_team(admin_token: str, stakeholder_token: str) -> None:
    project_id, feed_id = _seed_project_and_feed()
    fiber_id = _create_lookup_fiber(project_id, feed_id, token=admin_token)

    response = client.post(
        f"/projects/{project_id}/feeds/{feed_id}/fibers/{fiber_id}/lookup-inputs",
        json={"source_values": _SOURCE_VALUES, "destination_lookup_csv": _DEST_CSV},
        headers={"Authorization": f"Bearer {stakeholder_token}"},
    )
    assert response.status_code == 403


def test_patch_mapping_updates_operator_selection(
    monkeypatch: pytest.MonkeyPatch,
    admin_token: str,
    stakeholder_token: str,
) -> None:
    project_id, feed_id = _seed_project_and_feed()
    fiber_id = _create_lookup_fiber(project_id, feed_id, token=admin_token)
    monkeypatch.setattr(fibers_module, "get_adapter", lambda task: FakeLookupAdapter())

    response = client.post(
        f"/projects/{project_id}/feeds/{feed_id}/fibers/{fiber_id}/lookup-inputs",
        json={"source_values": ["X"], "destination_lookup_csv": "id,label\n1,One\n2,Two"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200, response.text

    mappings_response = client.get(
        f"/projects/{project_id}/feeds/{feed_id}/fibers/{fiber_id}/mappings",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    mapping_id = mappings_response.json()[0]["mapping_id"]
    entries_response = client.get(
        f"/projects/{project_id}/feeds/{feed_id}/fibers/{fiber_id}/dest-feed/entries",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    dest_entry_id = entries_response.json()[-1]["entry_id"]

    with SessionLocal() as db:
        membership = db.scalar(select(ProjectMembership).where(ProjectMembership.project_id == project_id))
        if membership is None:
            stakeholder = db.scalar(select(User).where(User.email == "stakeholder-fiber@example.com"))
            assert stakeholder is not None
            db.add(ProjectMembership(project_id=project_id, user_id=stakeholder.user_id))
            db.commit()

    patch_response = client.patch(
        f"/projects/{project_id}/feeds/{feed_id}/fibers/{fiber_id}/mappings/{mapping_id}",
        json={"dest_entry_id": dest_entry_id, "status": "overridden"},
        headers={"Authorization": f"Bearer {stakeholder_token}"},
    )
    assert patch_response.status_code == 200, patch_response.text
    body = patch_response.json()
    assert body["mapped_by"] == "operator"
    assert body["dest_entry_id"] == dest_entry_id
    assert body["status"] == "overridden"


def test_patch_mapping_rejects_auditor(monkeypatch: pytest.MonkeyPatch, admin_token: str, auditor_token: str) -> None:
    project_id, feed_id = _seed_project_and_feed()
    fiber_id = _create_lookup_fiber(project_id, feed_id, token=admin_token)
    monkeypatch.setattr(fibers_module, "get_adapter", lambda task: FakeLookupAdapter())

    response = client.post(
        f"/projects/{project_id}/feeds/{feed_id}/fibers/{fiber_id}/lookup-inputs",
        json={"source_values": ["X"], "destination_lookup_csv": "id,label\n1,One"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200, response.text

    mapping_id = client.get(
        f"/projects/{project_id}/feeds/{feed_id}/fibers/{fiber_id}/mappings",
        headers={"Authorization": f"Bearer {admin_token}"},
    ).json()[0]["mapping_id"]

    patch_response = client.patch(
        f"/projects/{project_id}/feeds/{feed_id}/fibers/{fiber_id}/mappings/{mapping_id}",
        json={"dest_entry_id": "any-id", "status": "confirmed"},
        headers={"Authorization": f"Bearer {auditor_token}"},
    )
    assert patch_response.status_code == 403
