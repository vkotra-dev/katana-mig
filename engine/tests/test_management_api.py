from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from migrations_engine.app import app
from migrations_engine.auth.passwords import hash_password
from migrations_engine.config import get_settings
from migrations_engine.db.models import (
    AuthSession,
    ProjectDefinition,
    ProjectMembership,
    ProjectRegistry,
    User,
)
from migrations_engine.db.session import SessionLocal
from migrations_engine.management.access import user_has_project_access
from migrations_engine.roles import PROJECT_STAKEHOLDER_ROLE, READ_ONLY_AUDITOR_ROLE

client = TestClient(app)


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
def test_project_id() -> str:
    project_id = str(uuid.uuid4())
    definition_id = str(uuid.uuid4())
    with SessionLocal() as db:
        db.add(
            ProjectDefinition(
                definition_id=definition_id,
                project_id=project_id,
                name="Test Project",
                status="active",
            )
        )
        db.add(
            ProjectRegistry(
                project_id=project_id,
                name="Test Project",
                definition_id=definition_id,
                status="active",
            )
        )
        db.commit()
    yield project_id


@pytest.fixture
def stakeholder_user() -> tuple[str, str, str]:
    user_id = str(uuid.uuid4())
    email = f"stakeholder-{user_id[:8]}@example.com"
    password = "stakeholder-password"
    with SessionLocal() as db:
        db.add(
            User(
                user_id=user_id,
                email=email,
                display_name="Stakeholder",
                password_hash=hash_password(password),
                role=PROJECT_STAKEHOLDER_ROLE,
                status="active",
            )
        )
        db.commit()
    yield user_id, email, password
    with SessionLocal() as db:
        user = db.get(User, user_id)
        if user is not None:
            for session in db.scalars(
                select(AuthSession).where(AuthSession.user_id == user_id)
            ):
                db.delete(session)
            for membership in db.scalars(
                select(ProjectMembership).where(ProjectMembership.user_id == user_id)
            ):
                db.delete(membership)
            db.delete(user)
            db.commit()


@pytest.fixture
def auditor_user() -> tuple[str, str]:
    user_id = str(uuid.uuid4())
    email = f"auditor-{user_id[:8]}@example.com"
    password = "auditor-password"
    with SessionLocal() as db:
        db.add(
            User(
                user_id=user_id,
                email=email,
                display_name="Auditor",
                password_hash=hash_password(password),
                role=READ_ONLY_AUDITOR_ROLE,
                status="active",
            )
        )
        db.commit()
    yield email, password
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.email == email))
        if user is not None:
            for session in db.scalars(
                select(AuthSession).where(AuthSession.user_id == user.user_id)
            ):
                db.delete(session)
            db.delete(user)
            db.commit()


def test_admin_can_create_and_update_user(admin_token: str) -> None:
    email = f"new-user-{uuid.uuid4().hex[:8]}@example.com"
    create = client.post(
        "/users",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "email": email,
            "password": "new-user-password",
            "display_name": "New User",
            "role": "project_stakeholder",
        },
    )
    assert create.status_code == 201, create.text
    user_id = create.json()["user_id"]

    update = client.patch(
        f"/users/{user_id}",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"role": "read_only_auditor"},
    )
    assert update.status_code == 200
    assert update.json()["role"] == "read_only_auditor"


def test_admin_can_clear_display_name_and_cannot_change_own_role(admin_token: str) -> None:
    settings = get_settings()
    admin_email = settings.bootstrap_admin_email.strip().lower()
    with SessionLocal() as db:
        admin = db.scalar(select(User).where(User.email == admin_email))
        assert admin is not None
        admin_id = admin.user_id
        original_display_name = admin.display_name

    try:
        clear_display_name = client.patch(
            f"/users/{admin_id}",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"display_name": None},
        )
        assert clear_display_name.status_code == 200, clear_display_name.text
        assert clear_display_name.json()["display_name"] is None

        self_role_change = client.patch(
            f"/users/{admin_id}",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"role": "project_stakeholder"},
        )
        assert self_role_change.status_code == 403
        assert self_role_change.json()["error"]["code"] == "forbidden"
    finally:
        with SessionLocal() as db:
            admin = db.scalar(select(User).where(User.user_id == admin_id))
            assert admin is not None
            admin.display_name = original_display_name
            db.commit()


def test_admin_cannot_delete_self(admin_token: str) -> None:
    settings = get_settings()
    admin_email = settings.bootstrap_admin_email.strip().lower()
    with SessionLocal() as db:
        admin = db.scalar(select(User).where(User.email == admin_email))
        assert admin is not None
        admin_id = admin.user_id

    response = client.delete(
        f"/users/{admin_id}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "forbidden"


def test_non_admin_cannot_create_user(
    stakeholder_user: tuple[str, str, str],
    auditor_user: tuple[str, str],
) -> None:
    stakeholder_email, stakeholder_password = stakeholder_user[1], stakeholder_user[2]
    auditor_email, auditor_password = auditor_user

    stakeholder_token = _login(stakeholder_email, stakeholder_password)
    auditor_token = _login(auditor_email, auditor_password)

    for token in (stakeholder_token, auditor_token):
        response = client.post(
            "/users",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "email": f"blocked-{uuid.uuid4().hex[:8]}@example.com",
                "password": "blocked-password",
                "role": "project_stakeholder",
            },
        )
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "forbidden"


def test_membership_gates_stakeholder_project_access(
    admin_token: str,
    test_project_id: str,
    stakeholder_user: tuple[str, str, str],
) -> None:
    user_id, email, password = stakeholder_user
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.user_id == user_id))
        assert user is not None
        assert user_has_project_access(db, user=user, project_id=test_project_id) is False

    add = client.post(
        f"/projects/{test_project_id}/members",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"user_id": user_id},
    )
    assert add.status_code == 200, add.text

    duplicate = client.post(
        f"/projects/{test_project_id}/members",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"user_id": user_id},
    )
    assert duplicate.status_code == 200
    assert duplicate.json()["warning"] == "User is already a member of this project."

    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.user_id == user_id))
        assert user is not None
        assert user_has_project_access(db, user=user, project_id=test_project_id) is True

    stakeholder_token = _login(email, password)
    members = client.get(
        f"/projects/{test_project_id}/members",
        headers={"Authorization": f"Bearer {stakeholder_token}"},
    )
    assert members.status_code == 403

    remove = client.delete(
        f"/projects/{test_project_id}/members/{user_id}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert remove.status_code == 204

    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.user_id == user_id))
        assert user is not None
        assert user_has_project_access(db, user=user, project_id=test_project_id) is False


def test_admin_cannot_assign_non_stakeholder_membership(
    admin_token: str,
    test_project_id: str,
    auditor_user: tuple[str, str],
) -> None:
    with SessionLocal() as db:
        auditor = db.scalar(select(User).where(User.email == auditor_user[0]))
        assert auditor is not None
        auditor_id = auditor.user_id

    response = client.post(
        f"/projects/{test_project_id}/members",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"user_id": auditor_id},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "not_stakeholder"


def test_admin_cannot_add_member_to_archived_project(
    admin_token: str,
    test_project_id: str,
    stakeholder_user: tuple[str, str, str],
) -> None:
    user_id = stakeholder_user[0]

    archive = client.post(
        f"/projects/{test_project_id}/archive",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert archive.status_code == 200, archive.text

    response = client.post(
        f"/projects/{test_project_id}/members",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"user_id": user_id},
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "project_archived"
