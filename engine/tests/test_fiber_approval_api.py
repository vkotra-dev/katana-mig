from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

import sqlite_test_support  # noqa: F401

from migrations_engine.app import app
from migrations_engine.auth.passwords import hash_password
from migrations_engine.config import get_settings
from migrations_engine.db.models import (
    Feed,
    ProjectDefinition,
    ProjectFiber,
    ProjectMembership,
    ProjectRegistry,
    User,
)
from migrations_engine.db.session import SessionLocal
from migrations_engine.roles import CENTRAL_TEAM_ROLE, PROJECT_STAKEHOLDER_ROLE

client = TestClient(app)

_ADMIN_EMAIL = "admin-approval@example.com"
_ADMIN_PASSWORD = "admin-password-123"
_STAKEHOLDER_EMAIL = "stakeholder-approval@example.com"
_STAKEHOLDER_PASSWORD = "stakeholder-password-123"


@pytest.fixture(scope="module", autouse=True)
def _seed_users() -> None:
    from migrations_engine.db.base import Base
    from sqlite_test_support import TEST_ENGINE

    Base.metadata.create_all(bind=TEST_ENGINE)

    with SessionLocal() as db:
        if db.scalar(select(User).where(User.email == _ADMIN_EMAIL)) is None:
            db.add(
                User(
                    user_id=str(uuid.uuid4()),
                    email=_ADMIN_EMAIL,
                    display_name="Admin Approval",
                    password_hash=hash_password(_ADMIN_PASSWORD),
                    role=CENTRAL_TEAM_ROLE,
                    status="active",
                )
            )
        if db.scalar(select(User).where(User.email == _STAKEHOLDER_EMAIL)) is None:
            db.add(
                User(
                    user_id=str(uuid.uuid4()),
                    email=_STAKEHOLDER_EMAIL,
                    display_name="Stakeholder Approval",
                    password_hash=hash_password(_STAKEHOLDER_PASSWORD),
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
    return _login(_ADMIN_EMAIL, _ADMIN_PASSWORD)


@pytest.fixture
def stakeholder_token() -> str:
    return _login(_STAKEHOLDER_EMAIL, _STAKEHOLDER_PASSWORD)


def _make_project_and_feed() -> tuple[str, str]:
    project_id = str(uuid.uuid4())
    feed_id = str(uuid.uuid4())
    definition_id = str(uuid.uuid4())
    with SessionLocal() as db:
        db.add(
            ProjectDefinition(
                definition_id=definition_id,
                project_id=project_id,
                name=f"Approval Project {project_id[:8]}",
                status="active",
            )
        )
        db.add(
            ProjectRegistry(
                project_id=project_id,
                name=f"Approval Project {project_id[:8]}",
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
                source_details={"label": "Test Feed", "encoding": "utf-8"},
                status="active",
            )
        )
        admin_user = db.scalar(select(User).where(User.email == _ADMIN_EMAIL))
        st_user = db.scalar(select(User).where(User.email == _STAKEHOLDER_EMAIL))
        assert admin_user is not None
        assert st_user is not None
        db.add(ProjectMembership(project_id=project_id, user_id=admin_user.user_id))
        db.add(ProjectMembership(project_id=project_id, user_id=st_user.user_id))
        db.commit()
    return project_id, feed_id


def _seed_fiber(project_id: str, feed_id: str, status: str, fiber_key: str = "customer") -> str:
    fiber_id = str(uuid.uuid4())
    with SessionLocal() as db:
        db.add(
            ProjectFiber(
                fiber_id=fiber_id,
                feed_id=feed_id,
                project_id=project_id,
                fiber_type="domain_object",
                fiber_key=fiber_key,
                status=status,
                source="auto",
            )
        )
        db.commit()
    return fiber_id


def _add_stakeholder_membership(project_id: str) -> None:
    with SessionLocal() as db:
        stakeholder = db.scalar(select(User).where(User.email == _STAKEHOLDER_EMAIL))
        assert stakeholder is not None
        if db.scalar(
            select(ProjectMembership).where(
                ProjectMembership.project_id == project_id,
                ProjectMembership.user_id == stakeholder.user_id,
            )
        ) is None:
            db.add(ProjectMembership(project_id=project_id, user_id=stakeholder.user_id))
            db.commit()


def test_fiber_action_request_schema_has_optional_comment() -> None:
    from migrations_engine.api.schemas import FiberActionRequest

    req = FiberActionRequest()
    assert req.comment is None

    req_with = FiberActionRequest(comment="looks good")
    assert req_with.comment == "looks good"


def test_assign_transitions_mapped_to_operator_assigned(admin_token: str) -> None:
    project_id, feed_id = _make_project_and_feed()
    fiber_id = _seed_fiber(project_id, feed_id, status="mapped")

    response = client.post(
        f"/projects/{project_id}/feeds/{feed_id}/fibers/{fiber_id}/assign",
        json={},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "operator_assigned"
    assert body["fiber_id"] == fiber_id


def test_assign_with_comment(admin_token: str) -> None:
    project_id, feed_id = _make_project_and_feed()
    fiber_id = _seed_fiber(project_id, feed_id, status="mapped")

    response = client.post(
        f"/projects/{project_id}/feeds/{feed_id}/fibers/{fiber_id}/assign",
        json={"comment": "ready for business review"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "operator_assigned"


def test_assign_rejects_wrong_status(admin_token: str) -> None:
    project_id, feed_id = _make_project_and_feed()
    fiber_id = _seed_fiber(project_id, feed_id, status="created")

    response = client.post(
        f"/projects/{project_id}/feeds/{feed_id}/fibers/{fiber_id}/assign",
        json={},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 409, response.text
    assert response.json()["error"]["code"] == "fiber_not_ready"


def test_assign_requires_central_team(stakeholder_token: str) -> None:
    project_id, feed_id = _make_project_and_feed()
    fiber_id = _seed_fiber(project_id, feed_id, status="mapped")

    response = client.post(
        f"/projects/{project_id}/feeds/{feed_id}/fibers/{fiber_id}/assign",
        json={},
        headers={"Authorization": f"Bearer {stakeholder_token}"},
    )
    assert response.status_code == 403, response.text


def test_assign_requires_authentication() -> None:
    response = client.post("/projects/p/feeds/f/fibers/x/assign", json={})
    assert response.status_code == 401


def test_assign_returns_404_for_missing_fiber(admin_token: str) -> None:
    project_id, feed_id = _make_project_and_feed()

    response = client.post(
        f"/projects/{project_id}/feeds/{feed_id}/fibers/nonexistent/assign",
        json={},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 404


def test_approve_transitions_operator_assigned_to_business_approved(stakeholder_token: str) -> None:
    project_id, feed_id = _make_project_and_feed()
    _add_stakeholder_membership(project_id)
    fiber_id = _seed_fiber(project_id, feed_id, status="operator_assigned")

    response = client.post(
        f"/projects/{project_id}/feeds/{feed_id}/fibers/{fiber_id}/approve",
        json={},
        headers={"Authorization": f"Bearer {stakeholder_token}"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "business_approved"
    assert body["fiber_id"] == fiber_id


def test_approve_with_comment(stakeholder_token: str) -> None:
    project_id, feed_id = _make_project_and_feed()
    _add_stakeholder_membership(project_id)
    fiber_id = _seed_fiber(project_id, feed_id, status="operator_assigned")

    response = client.post(
        f"/projects/{project_id}/feeds/{feed_id}/fibers/{fiber_id}/approve",
        json={"comment": "LGTM"},
        headers={"Authorization": f"Bearer {stakeholder_token}"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "business_approved"


def test_approve_rejects_wrong_status(stakeholder_token: str) -> None:
    project_id, feed_id = _make_project_and_feed()
    _add_stakeholder_membership(project_id)
    fiber_id = _seed_fiber(project_id, feed_id, status="mapped")

    response = client.post(
        f"/projects/{project_id}/feeds/{feed_id}/fibers/{fiber_id}/approve",
        json={},
        headers={"Authorization": f"Bearer {stakeholder_token}"},
    )
    assert response.status_code == 409, response.text
    assert response.json()["error"]["code"] == "fiber_not_ready"


def test_approve_requires_project_stakeholder_role(admin_token: str) -> None:
    project_id, feed_id = _make_project_and_feed()
    fiber_id = _seed_fiber(project_id, feed_id, status="operator_assigned")

    response = client.post(
        f"/projects/{project_id}/feeds/{feed_id}/fibers/{fiber_id}/approve",
        json={},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 403, response.text


def test_approve_requires_project_membership(stakeholder_token: str) -> None:
    project_id, feed_id = _make_project_and_feed()
    fiber_id = _seed_fiber(project_id, feed_id, status="operator_assigned")

    with SessionLocal() as db:
        st_user = db.scalar(select(User).where(User.email == _STAKEHOLDER_EMAIL))
        assert st_user is not None
        db.query(ProjectMembership).filter(
            ProjectMembership.project_id == project_id,
            ProjectMembership.user_id == st_user.user_id
        ).delete()
        db.commit()

    response = client.post(
        f"/projects/{project_id}/feeds/{feed_id}/fibers/{fiber_id}/approve",
        json={},
        headers={"Authorization": f"Bearer {stakeholder_token}"},
    )
    assert response.status_code == 403, response.text


def test_approve_requires_authentication() -> None:
    response = client.post("/projects/p/feeds/f/fibers/x/approve", json={})
    assert response.status_code == 401


def test_trigger_transitions_business_approved_to_operator_triggered(admin_token: str) -> None:
    project_id, feed_id = _make_project_and_feed()
    fiber_id = _seed_fiber(project_id, feed_id, status="business_approved")

    response = client.post(
        f"/projects/{project_id}/feeds/{feed_id}/fibers/{fiber_id}/trigger",
        json={},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "operator_triggered"
    assert body["fiber_id"] == fiber_id


def test_trigger_with_comment(admin_token: str) -> None:
    project_id, feed_id = _make_project_and_feed()
    fiber_id = _seed_fiber(project_id, feed_id, status="business_approved")

    response = client.post(
        f"/projects/{project_id}/feeds/{feed_id}/fibers/{fiber_id}/trigger",
        json={"comment": "initiating codegen"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "operator_triggered"


def test_trigger_rejects_wrong_status(admin_token: str) -> None:
    project_id, feed_id = _make_project_and_feed()
    fiber_id = _seed_fiber(project_id, feed_id, status="operator_assigned")

    response = client.post(
        f"/projects/{project_id}/feeds/{feed_id}/fibers/{fiber_id}/trigger",
        json={},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 409, response.text
    assert response.json()["error"]["code"] == "fiber_not_ready"


def test_trigger_requires_central_team(stakeholder_token: str) -> None:
    project_id, feed_id = _make_project_and_feed()
    fiber_id = _seed_fiber(project_id, feed_id, status="business_approved")

    response = client.post(
        f"/projects/{project_id}/feeds/{feed_id}/fibers/{fiber_id}/trigger",
        json={},
        headers={"Authorization": f"Bearer {stakeholder_token}"},
    )
    assert response.status_code == 403, response.text


def test_trigger_requires_authentication() -> None:
    response = client.post("/projects/p/feeds/f/fibers/x/trigger", json={})
    assert response.status_code == 401


def test_trigger_logs_codegen_queued_when_all_fibers_triggered(
    admin_token: str, caplog: pytest.LogCaptureFixture
) -> None:
    import logging

    project_id, feed_id = _make_project_and_feed()
    fiber_a = _seed_fiber(project_id, feed_id, status="business_approved", fiber_key="invoice")
    _seed_fiber(project_id, feed_id, status="operator_triggered", fiber_key="invoice")

    with caplog.at_level(logging.INFO, logger="migrations_engine.management.fibers"):
        response = client.post(
            f"/projects/{project_id}/feeds/{feed_id}/fibers/{fiber_a}/trigger",
            json={},
            headers={"Authorization": f"Bearer {admin_token}"},
        )

    assert response.status_code == 200, response.text
    assert response.json()["status"] == "operator_triggered"
    assert any("codegen queued for invoice" in record.message for record in caplog.records)


def test_trigger_does_not_log_codegen_when_sibling_fiber_not_triggered(
    admin_token: str, caplog: pytest.LogCaptureFixture
) -> None:
    import logging

    project_id, feed_id = _make_project_and_feed()
    fiber_a = _seed_fiber(project_id, feed_id, status="business_approved", fiber_key="order")
    _seed_fiber(project_id, feed_id, status="business_approved", fiber_key="order")

    with caplog.at_level(logging.INFO, logger="migrations_engine.management.fibers"):
        response = client.post(
            f"/projects/{project_id}/feeds/{feed_id}/fibers/{fiber_a}/trigger",
            json={},
            headers={"Authorization": f"Bearer {admin_token}"},
        )

    assert response.status_code == 200, response.text
    assert not any("codegen queued" in record.message for record in caplog.records)


def test_full_approval_chain(admin_token: str, stakeholder_token: str) -> None:
    project_id, feed_id = _make_project_and_feed()
    _add_stakeholder_membership(project_id)
    fiber_id = _seed_fiber(project_id, feed_id, status="mapped", fiber_key="payment")

    assign_response = client.post(
        f"/projects/{project_id}/feeds/{feed_id}/fibers/{fiber_id}/assign",
        json={},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert assign_response.status_code == 200, assign_response.text
    assert assign_response.json()["status"] == "operator_assigned"

    approve_response = client.post(
        f"/projects/{project_id}/feeds/{feed_id}/fibers/{fiber_id}/approve",
        json={},
        headers={"Authorization": f"Bearer {stakeholder_token}"},
    )
    assert approve_response.status_code == 200, approve_response.text
    assert approve_response.json()["status"] == "business_approved"

    trigger_response = client.post(
        f"/projects/{project_id}/feeds/{feed_id}/fibers/{fiber_id}/trigger",
        json={},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert trigger_response.status_code == 200, trigger_response.text
    assert trigger_response.json()["status"] == "operator_triggered"
