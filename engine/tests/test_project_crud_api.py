from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from sqlite_test_support import SessionLocal
from migrations_engine.app import app
from migrations_engine.auth.passwords import hash_password
from migrations_engine.config import get_settings
from migrations_engine.db.models import AuditEvent, AuthSession, Notification, ProjectDefinition, ProjectMembership, ProjectRegistry, User, Feed
from migrations_engine.roles import PROJECT_STAKEHOLDER_ROLE, READ_ONLY_AUDITOR_ROLE, ADMIN_ROLE, PM_ROLE

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
    return _login("pm@example.com", "pm-password")


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
        for row in db.scalars(select(AuditEvent).where(AuditEvent.actor_user_id == user_id)):
            db.delete(row)
        for row in db.scalars(select(Notification).where(Notification.user_id == user_id)):
            db.delete(row)
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
def pm_user() -> tuple[str, str]:
    user_id, email, password = _make_user("pm")
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
        "project_resources": "== PROD ==\nHost/IP: 10.0.0.1\nPort: 5432",
        "lexicon_scope": "finance domain vocabulary",
        "domain_config": {
            "target_db_engine": "mssql",
            "staging_schema": "stg",
            "destination_schema": "dbo",
            "dry_run": False,
            "sample_policy": {
                "strategy": "stratified",
                "max_rows": 1000,
                "stratified_column": "region",
            },
            "destination_schema_ddl": "CREATE TABLE t (id INT);",
            "environments": ["dev", "uat", "prod"],
        },
    }
    project = _create_project(admin_token, payload)

    assert project["name"] == "Full Project"
    assert project["status"] == "active"
    assert project["execution_environments"] == ["STG", "UAT", "PROD"]
    assert project["project_resources"] == "== PROD ==\nHost/IP: 10.0.0.1\nPort: 5432"
    assert project["lexicon_scope"] == "finance domain vocabulary"
    assert project["domain_config"]["target_db_engine"] == "mssql"
    assert project["domain_config"]["destination_schema"] == "dbo"
    assert project["domain_config"]["destination_schema_ddl"] == "CREATE TABLE t (id INT);"
    assert project["domain_config"]["environments"] == ["dev", "uat", "prod"]
    assert "environment" not in project

    with SessionLocal() as db:
        definition = db.scalar(
            select(ProjectDefinition).where(ProjectDefinition.project_id == project["project_id"])
        )
    assert definition is not None
    assert definition.domain_config == {
        "target_db_engine": "mssql",
        "staging_schema": "stg",
        "destination_schema": "dbo",
        "dry_run": False,
        "sample_policy": {
            "strategy": "stratified",
            "max_rows": 1000,
            "stratified_column": "region",
        },
        "destination_schema_ddl": "CREATE TABLE t (id INT);",
        "environments": ["dev", "uat", "prod"],
    }


def test_create_without_domain_config_returns_null(admin_token: str) -> None:
    project = _create_project(admin_token, {"name": "Minimal"})
    assert project["domain_config"] is None


def test_pm_is_assigned_via_pm_user_id(pm_user: tuple[str, str]) -> None:
    user_id, token = pm_user
    project = _create_project(token, {"name": "PM Project"})
    assert project["pm_user_id"] == user_id
    with SessionLocal() as db:
        membership = db.scalar(
            select(ProjectMembership).where(
                ProjectMembership.project_id == project["project_id"],
                ProjectMembership.user_id == user_id,
            )
        )
    assert membership is None


def test_stakeholder_cannot_create_project(stakeholder: tuple[str, str]) -> None:
    user_id, token = stakeholder
    response = client.post(
        "/projects",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": "Forbidden"},
    )
    assert response.status_code == 403


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
            "project_resources": "Prod resources",
            "lexicon_scope": "readable lexicon scope",
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
    assert body["project_resources"] == "Prod resources"
    assert body["lexicon_scope"] == "readable lexicon scope"
    assert body["domain_config"]["target_db_engine"] == "postgresql"
    assert "environment" not in body


def test_update_clones_definition_and_preserves_previous_row(admin_token: str) -> None:
    project = _create_project(
        admin_token,
        {
            "name": "Before Update",
            "goal": "Initial",
            "domain_config": {
                "target_db_engine": "mssql",
                "staging_schema": "stg",
                "destination_schema": "dbo",
                "sample_policy": {
                    "strategy": "random",
                    "max_rows": 5,
                    "stratified_column": None,
                },
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
                "destination_schema": "warehouse",
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
    assert body["domain_config"]["destination_schema"] == "warehouse"
    assert body["domain_config"]["sample_policy"] == {
        "strategy": "random",
        "max_rows": 5,
        "stratified_column": None,
    }

    with SessionLocal() as db:
        rows = list(
            db.scalars(select(ProjectDefinition).where(ProjectDefinition.project_id == project["project_id"]))
        )
        registry = db.get(ProjectDefinition, original_definition_id)
    assert len(rows) == 2
    assert registry is not None
    assert registry.goal == original_goal


def test_update_can_clear_project_resources_and_lexicon_scope(admin_token: str) -> None:
    project = _create_project(
        admin_token,
        {
            "name": "Clearable",
            "project_resources": "DEV notes",
            "lexicon_scope": "domain vocabulary",
            "model_policy": {
                "field_mapping": "claude-opus-4-8",
                "planning": "gpt-5",
            },
        },
    )

    response = client.patch(
        f"/projects/{project['project_id']}",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "project_resources": None,
            "lexicon_scope": None,
            "model_policy": None,
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["project_resources"] is None
    assert body["lexicon_scope"] is None

    with SessionLocal() as db:
        registry = db.scalar(select(ProjectRegistry).where(ProjectRegistry.project_id == project["project_id"]))
        assert registry is not None
        definition = db.get(ProjectDefinition, registry.definition_id)
        assert definition is not None
        assert definition.project_resources is None
        assert registry.lexicon_scope is None
        assert definition.model_policy is None


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


def test_copy_project_success(admin_token: str) -> None:
    payload = {
        "name": "Source Project",
        "goal": "Migrate Database",
        "constraints": ["PCI-DSS"],
        "domain_config": {
            "target_db_engine": "postgresql",
            "destination_schema": "public",
        },
    }
    src_project = _create_project(admin_token, payload)
    src_project_id = src_project["project_id"]

    feed_id = str(uuid.uuid4())
    with SessionLocal() as db:
        db.add(
            Feed(
                source_definition_id=feed_id,
                project_id=src_project_id,
                source_type="csv",
                source_contract_version="v1",
                source_details={"label": "Transactions", "encoding": "utf-8"},
                mapping_hints="map status_id to transaction_status",
                status="active",
            )
        )
        db.commit()

    copy_payload = {
        "name": "Cloned Project",
        "stakeholder_user_ids": []
    }
    response = client.post(
        f"/projects/{src_project_id}/copy",
        headers={"Authorization": f"Bearer {admin_token}"},
        json=copy_payload,
    )
    assert response.status_code == 201, response.text
    new_project = response.json()
    assert new_project["name"] == "Cloned Project"
    assert new_project["status"] == "active"
    assert new_project["constraints"] == ["PCI-DSS"]
    assert new_project["domain_config"]["target_db_engine"] == "postgresql"

    with SessionLocal() as db:
        feeds = db.scalars(
            select(Feed).where(Feed.project_id == new_project["project_id"])
        ).all()
    assert len(feeds) == 1
    assert feeds[0].source_type == "csv"
    assert feeds[0].mapping_hints == "map status_id to transaction_status"
    assert feeds[0].source_details == {"label": "Transactions", "encoding": "utf-8"}


def test_copy_project_archived_fails(admin_token: str) -> None:
    project = _create_project(admin_token, {"name": "Source to Archive"})
    project_id = project["project_id"]
    archive_response = client.post(
        f"/projects/{project_id}/archive",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert archive_response.status_code == 200

    response = client.post(
        f"/projects/{project_id}/copy",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"name": "Copy of Archived", "stakeholder_user_ids": []},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "project_archived"


def test_copy_project_stakeholders_not_copied_unless_specified(admin_token: str, stakeholder: tuple[str, str]) -> None:
    sh_id, sh_token = stakeholder
    project = _create_project(admin_token, {"name": "Stakeholder Source"})
    project_id = project["project_id"]
    add_member = client.post(
        f"/projects/{project_id}/members",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"user_id": sh_id},
    )
    assert add_member.status_code == 200

    response = client.post(
        f"/projects/{project_id}/copy",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"name": "Copy No Stakeholders", "stakeholder_user_ids": []},
    )
    assert response.status_code == 201
    new_project_id = response.json()["project_id"]

    get_res = client.get(
        f"/projects/{new_project_id}",
        headers={"Authorization": f"Bearer {sh_token}"},
    )
    assert get_res.status_code == 403

    response2 = client.post(
        f"/projects/{project_id}/copy",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"name": "Copy With Stakeholder", "stakeholder_user_ids": [sh_id]},
    )
    assert response2.status_code == 201
    new_project_id2 = response2.json()["project_id"]

    get_res2 = client.get(
        f"/projects/{new_project_id2}",
        headers={"Authorization": f"Bearer {sh_token}"},
    )
    assert get_res2.status_code == 200


def test_project_health_summaries(admin_token: str) -> None:
    project = _create_project(admin_token, {"name": "Health Test Project"})
    project_id = project["project_id"]

    list_res = client.get("/projects", headers={"Authorization": f"Bearer {admin_token}"})
    assert list_res.status_code == 200
    matched = [p for p in list_res.json() if p["project_id"] == project_id]
    assert len(matched) == 1
    p_data = matched[0]
    assert "health" in p_data
    assert p_data["health"]["feed_status"] == "healthy"
    assert p_data["health"]["mapping_status"] == "healthy"
    assert p_data["health"]["lookup_status"] == "healthy"


def test_assign_project_manager_workflow(pm_user: tuple[str, str]) -> None:
    # 1. PM1 creates a project
    pm1_user_id, pm1_token = pm_user
    project = _create_project(pm1_token, {"name": "Isolation Project"})
    project_id = project["project_id"]

    # PM1 can see their project
    get_res = client.get(f"/projects/{project_id}", headers={"Authorization": f"Bearer {pm1_token}"})
    assert get_res.status_code == 200
    assert get_res.json()["pm_user_id"] == pm1_user_id

    # 2. Create PM2, Admin, and Stakeholder
    pm2_user_id, pm2_email, pm2_pw = _make_user("pm")
    pm2_token = _login(pm2_email, pm2_pw)

    admin_user_id, admin_email, admin_pw = _make_user(ADMIN_ROLE)
    real_admin_token = _login(admin_email, admin_pw)

    sh_user_id, sh_email, sh_pw = _make_user(PROJECT_STAKEHOLDER_ROLE)

    try:
        # PM2 cannot see PM1's project
        get_res2 = client.get(f"/projects/{project_id}", headers={"Authorization": f"Bearer {pm2_token}"})
        assert get_res2.status_code == 403

        # PM2 list_projects does not include PM1's project
        list_res = client.get("/projects", headers={"Authorization": f"Bearer {pm2_token}"})
        assert list_res.status_code == 200
        assert not any(p["project_id"] == project_id for p in list_res.json())

        # 3. Non-admin (PM) cannot assign project manager
        assign_res = client.patch(
            f"/projects/{project_id}/manager",
            headers={"Authorization": f"Bearer {pm1_token}"},
            json={"pm_user_id": pm2_user_id},
        )
        assert assign_res.status_code == 403

        # 4. Admin assigning a non-PM user ID returns 422
        assign_res_bad = client.patch(
            f"/projects/{project_id}/manager",
            headers={"Authorization": f"Bearer {real_admin_token}"},
            json={"pm_user_id": sh_user_id},
        )
        assert assign_res_bad.status_code == 422
        assert assign_res_bad.json()["error"]["code"] == "invalid_role_for_pm"

        # 5. Admin successfully reassigns project to PM2
        assign_res_ok = client.patch(
            f"/projects/{project_id}/manager",
            headers={"Authorization": f"Bearer {real_admin_token}"},
            json={"pm_user_id": pm2_user_id},
        )
        assert assign_res_ok.status_code == 200
        assert assign_res_ok.json()["pm_user_id"] == pm2_user_id

        # 6. PM2 can now see the project, PM1 cannot
        get_res_pm2 = client.get(f"/projects/{project_id}", headers={"Authorization": f"Bearer {pm2_token}"})
        assert get_res_pm2.status_code == 200

        get_res_pm1 = client.get(f"/projects/{project_id}", headers={"Authorization": f"Bearer {pm1_token}"})
        assert get_res_pm1.status_code == 403

    finally:
        _cleanup_user(pm2_user_id)
        _cleanup_user(admin_user_id)
        _cleanup_user(sh_user_id)
