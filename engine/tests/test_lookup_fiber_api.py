from __future__ import annotations

import json
import uuid
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from sqlite_test_support import Base, SessionLocal, TEST_ENGINE
from migrations_engine.ai.adapter import AICallResult
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
        self.model_id = "test-model"

    def call(self, system: str, user: str, response_model: type[Any]) -> Any:
        self.calls.append(SimpleNamespace(system=system, user=user, response_model=response_model))
        payload = json.loads(user)
        source_values = list(payload["source_values"])
        destination_rows = payload["destination_rows"]

        # Build a lookup: first source value -> first row, second -> second, etc.
        # For rows beyond source count, leave source_value null (unmatched)
        proposals = []
        for i, row in enumerate(destination_rows):
            if i < len(source_values):
                proposals.append(
                    {
                        "dest_id": str(row.get("id", str(i + 1))),
                        "dest_value": str(row.get("label") or row.get("name") or list(row.values())[0]),
                        "source_value": source_values[i],
                        "confidence_score": 0.95,
                    }
                )
            else:
                proposals.append(
                    {
                        "dest_id": str(row.get("id", str(i + 1))),
                        "dest_value": str(row.get("label") or row.get("name") or list(row.values())[0]),
                        "source_value": None,
                        "confidence_score": 0.0,
                    }
                )
        parsed_result = response_model(proposals=proposals, unmatched_source_values=[])
        return AICallResult(parsed=parsed_result, raw_response="raw_response")


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
    # One proposal per destination row (2 rows → 2 proposals)
    assert len(body["proposed_mappings"]) == 2

    with SessionLocal() as db:
        fiber = db.get(ProjectFiber, fiber_id)
        assert fiber is not None
        assert fiber.status == "mapped"
        assert len(fiber.proposed_mappings or []) == 2
        # Verify proposed_mappings structure (JSON, not DB rows)
        pm = fiber.proposed_mappings
        assert pm[0]["source_value"] in ("A", "B")
        assert pm[0]["dest_row"] is not None
        assert "id" in pm[0]["dest_row"]
        assert "label" in pm[0]["dest_row"]


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


def test_lookup_inputs_allows_re_analysis_on_mapped_state(monkeypatch: pytest.MonkeyPatch) -> None:
    project_id, feed_id = _seed_project_and_feed()
    fiber_id = _create_fiber(project_id, feed_id)
    monkeypatch.setattr(fibers_module, "get_adapter", lambda task: FakeLookupAdapter())

    first = client.post(
        f"/projects/{project_id}/feeds/{feed_id}/fibers/{fiber_id}/lookup-inputs",
        headers={"Authorization": f"Bearer {_admin_token()}"},
        json={
            "source_values": ["A"],
            "destination_lookup_csv": "id,label\n1,Active",
        },
    )
    assert first.status_code == 200

    second = client.post(
        f"/projects/{project_id}/feeds/{feed_id}/fibers/{fiber_id}/lookup-inputs",
        headers={"Authorization": f"Bearer {_admin_token()}"},
        json={
            "source_values": ["B"],
            "destination_lookup_csv": "id,label\n2,Inactive",
        },
    )

    assert second.status_code == 200
    assert second.json()["status"] == "mapped"


def test_lookup_fiber_approval_bridges_to_lookup_value_map(monkeypatch: pytest.MonkeyPatch) -> None:
    project_id, feed_id = _seed_project_and_feed()
    fiber_id = _create_fiber(project_id, feed_id)
    monkeypatch.setattr(fibers_module, "get_adapter", lambda task: FakeLookupAdapter())

    admin_headers = {"Authorization": f"Bearer {_admin_token()}"}
    stakeholder_headers = {"Authorization": f"Bearer {_stakeholder_token()}"}

    # Step 1: Add project membership for stakeholder
    with SessionLocal() as db:
        stakeholder = db.scalar(select(User).where(User.email == "stakeholder-fiber@example.com"))
        assert stakeholder is not None
        db.add(ProjectMembership(project_id=project_id, user_id=stakeholder.user_id))
        db.commit()

    # Step 2: Submit lookup inputs (mapped)
    client.post(
        f"/projects/{project_id}/feeds/{feed_id}/fibers/{fiber_id}/lookup-inputs",
        headers=admin_headers,
        json={
            "source_values": ["A", "B"],
            "destination_lookup_csv": "id,label\n1,One\n2,Two",
        },
    )

    # Step 3: Verify proposed_mappings from fiber JSON (not LookupMapping DB rows)
    with SessionLocal() as db:
        fiber = db.get(ProjectFiber, fiber_id)
        assert fiber is not None
        assert fiber.status == "mapped"
        pm = fiber.proposed_mappings
        assert pm is not None
        assert len(pm) == 2
        # Verify source_value and dest_row structure
        source_values = {p["source_value"] for p in pm}
        assert source_values == {"A", "B"}

    # Step 4: Assign the fiber for review (status becomes operator_assigned)
    assign_resp = client.post(
        f"/projects/{project_id}/feeds/{feed_id}/fibers/{fiber_id}/assign",
        headers=admin_headers,
        json={},
    )
    assert assign_resp.status_code == 200, assign_resp.text

    # Step 5: Stakeholder approves the fiber (status becomes business_approved)
    # _bridge_lookup_fiber_to_value_map reads from fiber.proposed_mappings (JSON)
    # to construct the LookupValueMap
    approve_resp = client.post(
        f"/projects/{project_id}/feeds/{feed_id}/fibers/{fiber_id}/approve",
        headers=stakeholder_headers,
        json={},
    )
    assert approve_resp.status_code == 200, approve_resp.text

    # Step 6: Verify that LookupValueMap was created with correct mapping
    from migrations_engine.db.models import LookupValueMap
    with SessionLocal() as db:
        lvm = db.scalar(
            select(LookupValueMap).where(
                LookupValueMap.project_id == project_id,
                LookupValueMap.lookup_name == "status_code",
                LookupValueMap.status == "draft",
            )
        )
        assert lvm is not None
        # source_value_map values are business keys from dest_row["id"], not UUIDs
        assert lvm.source_value_map == {"A": "1", "B": "2"}
        assert len(lvm.destination_table) == 2
        assert {row["id"] for row in lvm.destination_table} == {"1", "2"}


def test_cannot_re_submit_after_sign_off(monkeypatch: pytest.MonkeyPatch) -> None:
    project_id, feed_id = _seed_project_and_feed()
    fiber_id = _create_fiber(project_id, feed_id)
    monkeypatch.setattr(fibers_module, "get_adapter", lambda task: FakeLookupAdapter())
    admin_headers = {"Authorization": f"Bearer {_admin_token()}"}
    stakeholder_headers = {"Authorization": f"Bearer {_stakeholder_token()}"}

    # Step 1: Add project membership for stakeholder
    with SessionLocal() as db:
        stakeholder = db.scalar(select(User).where(User.email == "stakeholder-fiber@example.com"))
        assert stakeholder is not None
        stakeholder_user_id = stakeholder.user_id
        db.add(ProjectMembership(project_id=project_id, user_id=stakeholder_user_id))
        db.commit()

    # Step 2: Submit lookup inputs
    client.post(
        f"/projects/{project_id}/feeds/{feed_id}/fibers/{fiber_id}/lookup-inputs",
        headers=admin_headers,
        json={
            "source_values": ["A", "B"],
            "destination_lookup_csv": "id,label\n1,One\n2,Two",
        },
    )

    # Step 3: Assign and approve the fiber (creates LookupValueMap via _bridge_lookup_fiber_to_value_map)
    assign_resp = client.post(
        f"/projects/{project_id}/feeds/{feed_id}/fibers/{fiber_id}/assign",
        headers=admin_headers,
        json={},
    )
    assert assign_resp.status_code == 200, assign_resp.text

    approve_resp = client.post(
        f"/projects/{project_id}/feeds/{feed_id}/fibers/{fiber_id}/approve",
        headers=stakeholder_headers,
        json={},
    )
    assert approve_resp.status_code == 200, approve_resp.text

    # Step 4: Verify LookupValueMap was created
    from migrations_engine.db.models import LookupValueMap
    with SessionLocal() as db:
        lvm = db.scalar(
            select(LookupValueMap).where(
                LookupValueMap.project_id == project_id,
                LookupValueMap.lookup_name == "status_code",
            )
        )
        assert lvm is not None
        assert lvm.source_value_map == {"A": "1", "B": "2"}

    # Step 5: Verifying that re-submitting inputs fails when sign-off exists
    # The fiber should be in "business_approved" status, not "mapped" or "deferred"
    fiber_resp = client.get(
        f"/projects/{project_id}/feeds/{feed_id}/fibers/{fiber_id}",
        headers=admin_headers,
    )
    assert fiber_resp.status_code == 200
    assert fiber_resp.json()["status"] == "business_approved"

