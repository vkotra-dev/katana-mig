from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from migrations_engine.app import app
from migrations_engine.auth.passwords import hash_password
from migrations_engine.config import get_settings
from migrations_engine.db.models import AuthSession, ProjectDefinition, ProjectMembership, User
from migrations_engine.db.session import SessionLocal
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


def _make_user(role: str) -> tuple[str, str, str]:
    user_id = str(uuid.uuid4())
    email = f"{role[:4]}-{user_id[:8]}@example.com"
    password = "test-password"
    with SessionLocal() as db:
        db.add(
            User(
                user_id=user_id,
                email=email,
                password_hash=hash_password(password),
                role=role,
                status="active",
            )
        )
        db.commit()
    return user_id, email, password


def _cleanup_user(user_id: str) -> None:
    with SessionLocal() as db:
        for row in db.scalars(select(AuthSession).where(AuthSession.user_id == user_id)):
            db.delete(row)
        for row in db.scalars(select(ProjectMembership).where(ProjectMembership.user_id == user_id)):
            db.delete(row)
        user = db.get(User, user_id)
        if user is not None:
            db.delete(user)
        db.commit()


@pytest.fixture
def stakeholder() -> tuple[str, str]:
    user_id, email, password = _make_user(PROJECT_STAKEHOLDER_ROLE)
    token = _login(email, password)
    yield user_id, token
    _cleanup_user(user_id)


@pytest.fixture
def auditor_token() -> str:
    user_id, email, password = _make_user(READ_ONLY_AUDITOR_ROLE)
    token = _login(email, password)
    yield token
    _cleanup_user(user_id)


def _create_project(token: str, body: dict[str, object]) -> dict[str, object]:
    response = client.post("/projects", headers={"Authorization": f"Bearer {token}"}, json=body)
    assert response.status_code == 201, response.text
    return response.json()


def _project_definition_rows(project_id: str) -> list[ProjectDefinition]:
    with SessionLocal() as db:
        return list(db.scalars(select(ProjectDefinition).where(ProjectDefinition.project_id == project_id)))


def test_create_full_domain_config_roundtrips(admin_token: str) -> None:
    payload = {
        "name": "Full Project",
        "goal": "Migrate CRM",
        "execution_environments": ["STG", "UAT", "PROD"],
        "constraints": ["GDPR"],
        "assumptions": ["Replica stable"],
        "unresolved_questions": ["PII present?"],
        "canonical_terms": ["customer_id"],
        "lexicon_scope": {"domain": "finance"},
        "environment": "STG",
        "domain_config": {
            "target_db_engine": "mssql",
            "staging_schema": "stg",
            "dry_run": False,
            "sample_policy": {"max_rows": 1000},
            "destination_schema_ddl": "CREATE TABLE t (id INT);",
            "environments": ["dev", "uat", "prod"],
        },
    }
    project = _create_project(admin_token, payload)

    assert project["name"] == "Full Project"
    assert project["status"] == "active"
    assert project["execution_environments"] == ["STG", "UAT", "PROD"]
    assert project["lexicon_scope"] == {"domain": "finance"}
    assert project["domain_config"]["target_db_engine"] == "mssql"
    assert project["domain_config"]["destination_schema_ddl"] == "CREATE TABLE t (id INT);"
    assert project["domain_config"]["environments"] == ["dev", "uat", "prod"]

    with SessionLocal() as db:
        definition = db.scalar(
            select(ProjectDefinition).where(ProjectDefinition.project_id == project["project_id"])
        )
    assert definition is not None
    assert definition.domain_config == {
        "target_db_engine": "mssql",
        "staging_schema": "stg",
        "dry_run": False,
        "sample_policy": {"max_rows": 1000},
        "destination_schema_ddl": "CREATE TABLE t (id INT);",
        "environments": ["dev", "uat", "prod"],
    }


def test_create_without_domain_config_returns_null(admin_token: str) -> None:
    project = _create_project(admin_token, {"name": "Minimal"})
    assert project["domain_config"] is None


def test_stakeholder_is_auto_membered(stakeholder: tuple[str, str]) -> None:
    user_id, token = stakeholder
    project = _create_project(token, {"name": "Stakeholder Project"})
    with SessionLocal() as db:
        membership = db.scalar(
            select(ProjectMembership).where(
                ProjectMembership.project_id == project["project_id"],
                ProjectMembership.user_id == user_id,
            )
        )
    assert membership is not None


def test_auditor_cannot_create_project(auditor_token: str) -> None:
    response = client.post(
        "/projects",
        headers={"Authorization": f"Bearer {auditor_token}"},
        json={"name": "Blocked"},
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "forbidden"


def test_list_excludes_archived_by_default(admin_token: str) -> None:
    active = _create_project(admin_token, {"name": f"Active-{uuid.uuid4().hex[:6]}"})
    archived = _create_project(admin_token, {"name": f"Archived-{uuid.uuid4().hex[:6]}"})
    archive_response = client.post(
        f"/projects/{archived['project_id']}/archive",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert archive_response.status_code == 200, archive_response.text

    listed = client.get("/projects", headers={"Authorization": f"Bearer {admin_token}"})
    assert listed.status_code == 200
    ids = {item["project_id"] for item in listed.json()}
    assert active["project_id"] in ids
    assert archived["project_id"] not in ids

    listed_all = client.get(
        "/projects?include_archived=true",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert listed_all.status_code == 200
    ids_all = {item["project_id"] for item in listed_all.json()}
    assert archived["project_id"] in ids_all


def test_stakeholder_sees_only_member_projects(
    admin_token: str,
    stakeholder: tuple[str, str],
) -> None:
    user_id, stakeholder_token = stakeholder
    member = _create_project(admin_token, {"name": f"Member-{uuid.uuid4().hex[:6]}"})
    other = _create_project(admin_token, {"name": f"Other-{uuid.uuid4().hex[:6]}"})
    add_member = client.post(
        f"/projects/{member['project_id']}/members",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"user_id": user_id},
    )
    assert add_member.status_code == 200, add_member.text

    listed = client.get("/projects", headers={"Authorization": f"Bearer {stakeholder_token}"})
    assert listed.status_code == 200
    ids = {item["project_id"] for item in listed.json()}
    assert member["project_id"] in ids
    assert other["project_id"] not in ids


def test_get_project_requires_membership_for_stakeholder(
    admin_token: str,
    stakeholder: tuple[str, str],
) -> None:
    _, stakeholder_token = stakeholder
    project = _create_project(admin_token, {"name": f"Private-{uuid.uuid4().hex[:6]}"})

    response = client.get(
        f"/projects/{project['project_id']}",
        headers={"Authorization": f"Bearer {stakeholder_token}"},
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "forbidden"


def test_get_project_returns_definition_and_registry_fields(admin_token: str) -> None:
    project = _create_project(
        admin_token,
        {
            "name": "Readable",
            "constraints": ["GDPR"],
            "execution_environments": ["PROD"],
            "domain_config": {
                "target_db_engine": "postgresql",
                "destination_schema_ddl": "create table x(id int);",
            },
        },
    )
    response = client.get(
        f"/projects/{project['project_id']}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["constraints"] == ["GDPR"]
    assert body["execution_environments"] == ["PROD"]
    assert body["domain_config"]["target_db_engine"] == "postgresql"


def test_update_clones_definition_and_preserves_previous_row(admin_token: str) -> None:
    project = _create_project(
        admin_token,
        {
            "name": "Before Update",
            "goal": "Initial",
            "domain_config": {
                "target_db_engine": "mssql",
                "staging_schema": "stg",
                "sample_policy": {"max_rows": 5},
            },
        },
    )
    before_rows = _project_definition_rows(project["project_id"])
    assert len(before_rows) == 1
    original_definition_id = before_rows[0].definition_id
    original_goal = before_rows[0].goal

    response = client.patch(
        f"/projects/{project['project_id']}",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "name": "After Update",
            "goal": "Replanned",
            "execution_environments": ["DEV", "PROD"],
            "domain_config": {
                "target_db_engine": "oracle",
                "destination_schema_ddl": "create table y(id int);",
            },
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["name"] == "After Update"
    assert body["goal"] == "Replanned"
    assert body["execution_environments"] == ["DEV", "PROD"]
    assert body["domain_config"]["target_db_engine"] == "oracle"
    assert body["domain_config"]["staging_schema"] == "stg"
    assert body["domain_config"]["sample_policy"] == {"max_rows": 5}

    with SessionLocal() as db:
        rows = list(
            db.scalars(select(ProjectDefinition).where(ProjectDefinition.project_id == project["project_id"]))
        )
        registry = db.get(ProjectDefinition, original_definition_id)
    assert len(rows) == 2
    assert registry is not None
    assert registry.goal == original_goal


def test_update_rejected_for_archived_project(admin_token: str) -> None:
    project = _create_project(admin_token, {"name": "Archive Me"})
    archive_response = client.post(
        f"/projects/{project['project_id']}/archive",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert archive_response.status_code == 200, archive_response.text

    update = client.patch(
        f"/projects/{project['project_id']}",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"goal": "Blocked"},
    )
    assert update.status_code == 409
    assert update.json()["error"]["code"] == "project_archived"


def test_archive_marks_project_and_is_idempotently_blocked(admin_token: str) -> None:
    project = _create_project(admin_token, {"name": "Archive Target"})
    response = client.post(
        f"/projects/{project['project_id']}/archive",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "archived"
    assert response.json()["archived_at"] is not None

    second = client.post(
        f"/projects/{project['project_id']}/archive",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "project_already_archived"


def test_auditor_cannot_mutate_projects(
    admin_token: str,
    auditor_token: str,
) -> None:
    project = _create_project(admin_token, {"name": "Protected"})

    create = client.post(
        "/projects",
        headers={"Authorization": f"Bearer {auditor_token}"},
        json={"name": "Blocked"},
    )
    update = client.patch(
        f"/projects/{project['project_id']}",
        headers={"Authorization": f"Bearer {auditor_token}"},
        json={"goal": "Blocked"},
    )
    archive = client.post(
        f"/projects/{project['project_id']}/archive",
        headers={"Authorization": f"Bearer {auditor_token}"},
    )

    assert create.status_code == 403
    assert update.status_code == 403
    assert archive.status_code == 403


def test_unauthenticated_requests_are_rejected() -> None:
    assert client.post("/projects", json={"name": "X"}).status_code == 401
    assert client.get("/projects").status_code == 401
