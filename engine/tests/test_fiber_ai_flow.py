from __future__ import annotations

import uuid
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from sqlite_test_support import Base, SessionLocal, TEST_ENGINE
from migrations_engine.api.deps import AuthApiError
from migrations_engine.app import app
from migrations_engine.auth.passwords import hash_password
from migrations_engine.db.models import Feed, FeedSlice, ProjectDefinition, ProjectRegistry, User
from migrations_engine.roles import CENTRAL_TEAM_ROLE, PROJECT_STAKEHOLDER_ROLE

client = TestClient(app)
ADMIN_EMAIL = "fiber-admin@example.com"
ADMIN_PASSWORD = "fiber-admin-password"
STAKEHOLDER_EMAIL = "fiber-stakeholder@example.com"
STAKEHOLDER_PASSWORD = "fiber-stakeholder-password"


class FakeFeedAnalysisAdapter:
    def __init__(self, result: Any) -> None:
        self.result = result
        self.calls: list[SimpleNamespace] = []

    def call(self, system: str, user: str, response_model: type) -> Any:
        self.calls.append(SimpleNamespace(system=system, user=user, response_model=response_model))
        return self.result


class FakeFieldMappingAdapter:
    def __init__(self, result: Any) -> None:
        self.result = result
        self.calls: list[SimpleNamespace] = []

    def call(self, system: str, user: str, response_model: type) -> Any:
        self.calls.append(SimpleNamespace(system=system, user=user, response_model=response_model))
        return self.result


@pytest.fixture(scope="module", autouse=True)
def _setup_db() -> None:
    Base.metadata.create_all(bind=TEST_ENGINE)


@pytest.fixture(scope="module", autouse=True)
def _seed_users() -> None:
    Base.metadata.create_all(bind=TEST_ENGINE)

    with SessionLocal() as db:
        if db.scalar(select(User).where(User.email == ADMIN_EMAIL)) is None:
            db.add(
                User(
                    user_id=str(uuid.uuid4()),
                    email=ADMIN_EMAIL,
                    display_name="Fiber Admin",
                    password_hash=hash_password(ADMIN_PASSWORD),
                    role=CENTRAL_TEAM_ROLE,
                    status="active",
                )
            )
        if db.scalar(select(User).where(User.email == STAKEHOLDER_EMAIL)) is None:
            db.add(
                User(
                    user_id=str(uuid.uuid4()),
                    email=STAKEHOLDER_EMAIL,
                    display_name="Stakeholder",
                    password_hash=hash_password(STAKEHOLDER_PASSWORD),
                    role=PROJECT_STAKEHOLDER_ROLE,
                    status="active",
                )
            )
        db.commit()


def _login(email: str, password: str) -> str:
    response = client.post("/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


@pytest.fixture
def admin_token() -> str:
    return _login(ADMIN_EMAIL, ADMIN_PASSWORD)


@pytest.fixture
def stakeholder_token() -> str:
    return _login(STAKEHOLDER_EMAIL, STAKEHOLDER_PASSWORD)


def _seed_feed_with_slice(
    *,
    header_csv: str = "CUST_ID,ACCT_TYPE",
    approved_slice: bool = True,
) -> tuple[str, str]:
    project_id = str(uuid.uuid4())
    definition_id = str(uuid.uuid4())
    feed_id = str(uuid.uuid4())
    with SessionLocal() as db:
        db.add(
            ProjectDefinition(
                definition_id=definition_id,
                project_id=project_id,
                name="Fiber AI Flow Project",
                domain_config={"destination_schema_ddl": "CREATE TABLE customers (id INT, name TEXT);"},
                status="active",
            )
        )
        db.add(
            ProjectRegistry(
                project_id=project_id,
                name="Fiber AI Flow Project",
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
                source_details={"label": "Feed", "encoding": "utf-8"},
                status="active",
            )
        )
        if approved_slice:
            db.add(
                FeedSlice(
                    source_slice_id=str(uuid.uuid4()),
                    source_definition_id=feed_id,
                    source_contract_version="v1",
                    source_slice_version="v1",
                    header_csv=header_csv,
                    status="approved",
                    approved_at=datetime.now(UTC),
                )
            )
        db.commit()
    return project_id, feed_id


def _make_fake_get_adapter(feed_analysis_result: Any, field_mapping_result: Any):
    feed_adapter = FakeFeedAnalysisAdapter(feed_analysis_result)
    field_adapter = FakeFieldMappingAdapter(field_mapping_result)

    def fake(task: str) -> Any:
        if task == "feed_analysis":
            return feed_adapter
        if task == "field_mapping":
            return field_adapter
        raise ValueError(f"Unexpected task: {task}")

    return fake, feed_adapter, field_adapter


def test_analyze_feed_creates_lookup_and_domain_object_fibers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from migrations_engine.management.fibers import (
        _DomainObject,
        _FeedAnalysisResult,
        _FieldBinding,
        _FieldMappingResult,
        _LookupIdentified,
        analyze_feed,
    )

    fake_get_adapter, feed_adapter, field_adapter = _make_fake_get_adapter(
        _FeedAnalysisResult(
            lookups=[_LookupIdentified(column_name="ACCT_TYPE", lookup_name="account_type")],
            domain_objects=[_DomainObject(destination_table="customers")],
        ),
        _FieldMappingResult(
            field_bindings=[
                _FieldBinding(source_field="CUST_ID", destination_field="id", lookup_name=None),
            ]
        ),
    )
    monkeypatch.setattr("migrations_engine.management.fibers.get_adapter", fake_get_adapter)

    with SessionLocal() as db:
        actor = db.scalar(select(User).where(User.role == CENTRAL_TEAM_ROLE))
        assert actor is not None
        project_id, feed_id = _seed_feed_with_slice()
        responses = analyze_feed(db, feed_id=feed_id, project_id=project_id, actor=actor)

    assert len(responses) == 2
    lookup_fiber = next(row for row in responses if row.fiber_type == "lookup")
    domain_fiber = next(row for row in responses if row.fiber_type == "domain_object")
    assert lookup_fiber.status == "deferred"
    assert lookup_fiber.source == "auto"
    assert domain_fiber.status == "mapped"
    assert domain_fiber.field_bindings is not None
    assert domain_fiber.field_bindings[0]["destination_field"] == "id"
    assert len(feed_adapter.calls) == 1
    assert len(field_adapter.calls) == 1


def test_analyze_feed_requires_approved_slice(monkeypatch: pytest.MonkeyPatch) -> None:
    from migrations_engine.management.fibers import analyze_feed

    monkeypatch.setattr("migrations_engine.management.fibers.get_adapter", lambda task: None)

    with SessionLocal() as db:
        actor = db.scalar(select(User).where(User.role == CENTRAL_TEAM_ROLE))
        assert actor is not None
        project_id, feed_id = _seed_feed_with_slice(approved_slice=False)

        with pytest.raises(AuthApiError) as exc_info:
            analyze_feed(db, feed_id=feed_id, project_id=project_id, actor=actor)

    assert exc_info.value.status_code == 409
    assert exc_info.value.code == "feed_slice_not_ready"


def test_analyze_feed_api_requires_central_team(
    stakeholder_token: str,
) -> None:
    project_id, feed_id = _seed_feed_with_slice()

    response = client.post(
        f"/projects/{project_id}/feeds/{feed_id}/analyze",
        headers={"Authorization": f"Bearer {stakeholder_token}"},
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "forbidden"


def test_analyze_feed_api_returns_created_fibers(
    monkeypatch: pytest.MonkeyPatch,
    admin_token: str,
) -> None:
    from migrations_engine.management.fibers import (
        _DomainObject,
        _FeedAnalysisResult,
        _FieldBinding,
        _FieldMappingResult,
        _LookupIdentified,
    )

    fake_get_adapter, _, _ = _make_fake_get_adapter(
        _FeedAnalysisResult(
            lookups=[_LookupIdentified(column_name="ACCT_TYPE", lookup_name="account_type")],
            domain_objects=[_DomainObject(destination_table="customers")],
        ),
        _FieldMappingResult(
            field_bindings=[
                _FieldBinding(source_field="CUST_ID", destination_field="id", lookup_name=None),
            ]
        ),
    )
    monkeypatch.setattr("migrations_engine.management.fibers.get_adapter", fake_get_adapter)

    project_id, feed_id = _seed_feed_with_slice()

    response = client.post(
        f"/projects/{project_id}/feeds/{feed_id}/analyze",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert len(payload) == 2
    assert {row["fiber_type"] for row in payload} == {"lookup", "domain_object"}
    domain_fiber = next(row for row in payload if row["fiber_type"] == "domain_object")
    assert domain_fiber["status"] == "mapped"
    assert domain_fiber["field_bindings"] is not None


def test_analyze_feed_api_returns_409_without_approved_slice(
    monkeypatch: pytest.MonkeyPatch,
    admin_token: str,
) -> None:
    monkeypatch.setattr("migrations_engine.management.fibers.get_adapter", lambda task: None)
    project_id, feed_id = _seed_feed_with_slice(approved_slice=False)

    response = client.post(
        f"/projects/{project_id}/feeds/{feed_id}/analyze",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "feed_slice_not_ready"
