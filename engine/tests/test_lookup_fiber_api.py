from __future__ import annotations

import json
import uuid
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from sqlite_test_support import Base, SessionLocal, TEST_ENGINE
from migrations_engine.app import app
from migrations_engine.auth.passwords import hash_password
from migrations_engine.config import get_settings
from migrations_engine.db.models import Feed, ProjectDefinition, ProjectFiber, ProjectMembership, ProjectRegistry, User
from migrations_engine.management import fibers as fibers_module
from migrations_engine.roles import CENTRAL_TEAM_ROLE, PROJECT_STAKEHOLDER_ROLE

client = TestClient(app)


class FakeLookupAdapter:
    def __init__(self) -> None:
        self.calls: list[SimpleNamespace] = []

    def call(self, system: str, user: str, response_model: type[Any]) -> Any:
        self.calls.append(SimpleNamespace(system=system, user=user, response_model=response_model))
        payload = json.loads(user)
        destination_rows = payload["destination_rows"]
        dest_entry_id = destination_rows[0]["entry_id"] if destination_rows else "missing-entry"
        return response_model(
            proposals=[
                {"source_value": value, "dest_entry_id": dest_entry_id, "confidence_score": 0.9}
                for value in payload["source_values"]
            ]
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
                    display_name="Stakeholder Fiber",
                    password_hash=hash_password("stakeholder-fiber-pass"),
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


def _admin_token() -> str:
    settings = get_settings()
    assert settings.bootstrap_admin_email is not None
    assert settings.bootstrap_admin_password is not None
    return _login(settings.bootstrap_admin_email, settings.bootstrap_admin_password)


def _stakeholder_token() -> str:
    return _login("stakeholder-fiber@example.com", "stakeholder-fiber-pass")


def _seed_project_and_feed() -> tuple[str, str]:
    project_id = str(uuid.uuid4())
    definition_id = str(uuid.uuid4())
    feed_id = str(uuid.uuid4())
    with SessionLocal() as db:
        db.add(
            ProjectDefinition(
                definition_id=definition_id,
                project_id=project_id,
                name="Lookup Fiber Project",
                status="active",
            )
        )
        db.add(
            ProjectRegistry(
                project_id=project_id,
                name="Lookup Fiber Project",
                definition_id=definition_id,
                status="active",
            )
        )
        db.add(
            Feed(
                source_definition_id=feed_id,
                project_id=project_id,
                source_type="csv",
                source_contract_version="v1",
                source_details={"label": "Customer Feed", "encoding": "utf-8"},
                status="active",
            )
        )
        db.commit()
    return project_id, feed_id


def _create_fiber(project_id: str, feed_id: str, *, fiber_type: str = "lookup") -> str:
    response = client.post(
        f"/projects/{project_id}/feeds/{feed_id}/fibers",
        headers={"Authorization": f"Bearer {_admin_token()}"},
        json={"fiber_type": fiber_type, "fiber_key": "status_code"},
    )
    assert response.status_code == 201, response.text
    return response.json()["fiber_id"]


def test_lookup_inputs_creates_lookup_entities_and_maps_rows(monkeypatch: pytest.MonkeyPatch) -> None:
    project_id, feed_id = _seed_project_and_feed()
    fiber_id = _create_fiber(project_id, feed_id)
    fake = FakeLookupAdapter()
    monkeypatch.setattr(fibers_module, "get_adapter", lambda task: fake)

    response = client.post(
        f"/projects/{project_id}/feeds/{feed_id}/fibers/{fiber_id}/lookup-inputs",
        headers={"Authorization": f"Bearer {_admin_token()}"},
        json={
            "source_values": ["A", "B", "C"],
            "destination_lookup_csv": "id,label\n1,Active\n2,Blocked",
        },
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "mapped"
    assert body["fiber_id"] == fiber_id
    assert len(body["proposed_mappings"]) == 3

    with SessionLocal() as db:
        fiber = db.get(ProjectFiber, fiber_id)
        assert fiber is not None
        assert fiber.status == "mapped"
        assert len(fiber.proposed_mappings or []) == 3

    source_entries = client.get(
        f"/projects/{project_id}/feeds/{feed_id}/fibers/{fiber_id}/source-entries",
        headers={"Authorization": f"Bearer {_admin_token()}"},
    )
    assert source_entries.status_code == 200, source_entries.text
    assert {row["source_value"] for row in source_entries.json()} == {"A", "B", "C"}

    dest_entries = client.get(
        f"/projects/{project_id}/feeds/{feed_id}/fibers/{fiber_id}/dest-feed/entries",
        headers={"Authorization": f"Bearer {_admin_token()}"},
    )
    assert dest_entries.status_code == 200, dest_entries.text
    assert len(dest_entries.json()) == 2

    mappings = client.get(
        f"/projects/{project_id}/feeds/{feed_id}/fibers/{fiber_id}/mappings",
        headers={"Authorization": f"Bearer {_admin_token()}"},
    )
    assert mappings.status_code == 200, mappings.text
    assert len(mappings.json()) == 3
    assert all(row["status"] == "proposed" for row in mappings.json())
    assert all(row["mapped_by"] == "ai" for row in mappings.json())


def test_lookup_inputs_rejects_wrong_fiber_type(monkeypatch: pytest.MonkeyPatch) -> None:
    project_id, feed_id = _seed_project_and_feed()
    fiber_id = _create_fiber(project_id, feed_id, fiber_type="domain_object")
    monkeypatch.setattr(fibers_module, "get_adapter", lambda task: FakeLookupAdapter())

    response = client.post(
        f"/projects/{project_id}/feeds/{feed_id}/fibers/{fiber_id}/lookup-inputs",
        headers={"Authorization": f"Bearer {_admin_token()}"},
        json={
            "source_values": ["A"],
            "destination_lookup_csv": "id,label\n1,Active",
        },
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "fiber_not_lookup"


def test_lookup_inputs_rejects_fiber_outside_deferred_state(monkeypatch: pytest.MonkeyPatch) -> None:
    project_id, feed_id = _seed_project_and_feed()
    fiber_id = _create_fiber(project_id, feed_id)
    monkeypatch.setattr(fibers_module, "get_adapter", lambda task: FakeLookupAdapter())

    client.post(
        f"/projects/{project_id}/feeds/{feed_id}/fibers/{fiber_id}/lookup-inputs",
        headers={"Authorization": f"Bearer {_admin_token()}"},
        json={
            "source_values": ["A"],
            "destination_lookup_csv": "id,label\n1,Active",
        },
    )
    response = client.post(
        f"/projects/{project_id}/feeds/{feed_id}/fibers/{fiber_id}/lookup-inputs",
        headers={"Authorization": f"Bearer {_admin_token()}"},
        json={
            "source_values": ["A"],
            "destination_lookup_csv": "id,label\n1,Active",
        },
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "fiber_not_deferred"


def test_dest_feed_replacement_overwrites_previous_rows() -> None:
    project_id, feed_id = _seed_project_and_feed()
    fiber_id = _create_fiber(project_id, feed_id)
    headers = {"Authorization": f"Bearer {_admin_token()}"}

    first = client.post(
        f"/projects/{project_id}/feeds/{feed_id}/fibers/{fiber_id}/dest-feed",
        headers=headers,
        json={"columns": ["id", "label"], "rows": [{"id": "1", "label": "One"}, {"id": "2", "label": "Two"}]},
    )
    assert first.status_code == 201, first.text

    second = client.post(
        f"/projects/{project_id}/feeds/{feed_id}/fibers/{fiber_id}/dest-feed",
        headers=headers,
        json={"columns": ["code"], "rows": [{"code": "X"}]},
    )
    assert second.status_code == 201, second.text
    assert second.json()["columns"] == ["code"]

    entries = client.get(
        f"/projects/{project_id}/feeds/{feed_id}/fibers/{fiber_id}/dest-feed/entries",
        headers=headers,
    )
    assert entries.status_code == 200, entries.text
    assert len(entries.json()) == 1
    assert entries.json()[0]["row_data"]["code"] == "X"


def test_patch_mapping_updates_dest_entry_and_sets_operator(monkeypatch: pytest.MonkeyPatch) -> None:
    project_id, feed_id = _seed_project_and_feed()
    fiber_id = _create_fiber(project_id, feed_id)
    monkeypatch.setattr(fibers_module, "get_adapter", lambda task: FakeLookupAdapter())
    headers = {"Authorization": f"Bearer {_admin_token()}"}

    client.post(
        f"/projects/{project_id}/feeds/{feed_id}/fibers/{fiber_id}/lookup-inputs",
        headers=headers,
        json={
            "source_values": ["A", "B"],
            "destination_lookup_csv": "id,label\n1,One\n2,Two",
        },
    )
    mappings = client.get(
        f"/projects/{project_id}/feeds/{feed_id}/fibers/{fiber_id}/mappings",
        headers=headers,
    )
    mapping_id = mappings.json()[0]["mapping_id"]

    dest_entries = client.get(
        f"/projects/{project_id}/feeds/{feed_id}/fibers/{fiber_id}/dest-feed/entries",
        headers=headers,
    )
    dest_entry_id = dest_entries.json()[-1]["entry_id"]

    response = client.patch(
        f"/projects/{project_id}/feeds/{feed_id}/fibers/{fiber_id}/mappings/{mapping_id}",
        headers=headers,
        json={"dest_entry_id": dest_entry_id, "status": "overridden"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["dest_entry_id"] == dest_entry_id
    assert response.json()["status"] == "overridden"
    assert response.json()["mapped_by"] == "operator"


def test_patch_mapping_allows_project_member_but_not_auditor(monkeypatch: pytest.MonkeyPatch) -> None:
    project_id, feed_id = _seed_project_and_feed()
    fiber_id = _create_fiber(project_id, feed_id)
    monkeypatch.setattr(fibers_module, "get_adapter", lambda task: FakeLookupAdapter())

    with SessionLocal() as db:
        stakeholder = db.scalar(select(User).where(User.email == "stakeholder-fiber@example.com"))
        assert stakeholder is not None
        db.add(ProjectMembership(project_id=project_id, user_id=stakeholder.user_id))
        db.commit()

    admin_headers = {"Authorization": f"Bearer {_admin_token()}"}
    client.post(
        f"/projects/{project_id}/feeds/{feed_id}/fibers/{fiber_id}/lookup-inputs",
        headers=admin_headers,
        json={
            "source_values": ["A"],
            "destination_lookup_csv": "id,label\n1,One",
        },
    )
    mapping_id = client.get(
        f"/projects/{project_id}/feeds/{feed_id}/fibers/{fiber_id}/mappings",
        headers=admin_headers,
    ).json()[0]["mapping_id"]
    dest_entry_id = client.get(
        f"/projects/{project_id}/feeds/{feed_id}/fibers/{fiber_id}/dest-feed/entries",
        headers=admin_headers,
    ).json()[0]["entry_id"]

    stakeholder_response = client.patch(
        f"/projects/{project_id}/feeds/{feed_id}/fibers/{fiber_id}/mappings/{mapping_id}",
        headers={"Authorization": f"Bearer {_stakeholder_token()}"},
        json={"dest_entry_id": dest_entry_id, "status": "confirmed"},
    )
    assert stakeholder_response.status_code == 200, stakeholder_response.text
    assert stakeholder_response.json()["mapped_by"] == "operator"
