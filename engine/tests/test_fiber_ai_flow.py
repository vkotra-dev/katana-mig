from __future__ import annotations

import importlib
import json
import uuid
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from sqlite_test_support import Base, SessionLocal, TEST_ENGINE

from migrations_engine.auth.passwords import hash_password  # noqa: E402
from migrations_engine.config import get_settings  # noqa: E402
from migrations_engine.db.models import (  # noqa: E402
    Feed,
    FeedSlice,
    ProjectDefinition,
    ProjectFiber,
    ProjectRegistry,
    User,
)
from migrations_engine.management import access as access_module  # noqa: E402
from migrations_engine.management import fibers as fibers_module  # noqa: E402
from migrations_engine.roles import CENTRAL_TEAM_ROLE, PROJECT_STAKEHOLDER_ROLE  # noqa: E402
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


class FakeFeedAnalysisAdapter:
    model_id = "claude-sonnet-4-6"

    def __init__(self, result: Any) -> None:
        self.result = result
        self.calls: list[SimpleNamespace] = []

    def call(self, system: str, user: str, response_model: type) -> Any:
        self.calls.append(SimpleNamespace(system=system, user=user, response_model=response_model))
        return self.result


class FakeFieldMappingAdapter:
    model_id = "claude-opus-4-8"

    def __init__(self, result: Any) -> None:
        self.result = result
        self.calls: list[SimpleNamespace] = []

    def call(self, system: str, user: str, response_model: type) -> Any:
        self.calls.append(SimpleNamespace(system=system, user=user, response_model=response_model))
        return self.result


@pytest.fixture(scope="module", autouse=True)
def _setup_db() -> None:
    Base.metadata.create_all(bind=TEST_ENGINE)

    settings = get_settings()
    if not settings.bootstrap_admin_email or not settings.bootstrap_admin_password:
        pytest.skip("bootstrap credentials not configured")

    with SessionLocal() as db:
        admin_email = settings.bootstrap_admin_email.strip().lower()
        if db.scalar(select(User).where(User.email == admin_email)) is None:
            db.add(
                User(
                    user_id=str(uuid.uuid4()),
                    email=admin_email,
                    display_name=settings.bootstrap_admin_display_name,
                    password_hash=hash_password(settings.bootstrap_admin_password),
                    role=CENTRAL_TEAM_ROLE,
                    status="active",
                )
            )
        if db.scalar(select(User).where(User.email == "stakeholder-fiber-ai@example.com")) is None:
            db.add(
                User(
                    user_id=str(uuid.uuid4()),
                    email="stakeholder-fiber-ai@example.com",
                    display_name="Fiber Stakeholder",
                    password_hash=hash_password("stakeholder-pass"),
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
    return _login("stakeholder-fiber-ai@example.com", "stakeholder-pass")


def _seed_project_and_feed(
    db,
    *,
    header_csv: str = "CUST_ID,ACCT_TYPE,SURNAME",
    destination_schema_ddl: str = "CREATE TABLE customers (id INT, name TEXT);",
    approved_slice: bool = True,
) -> tuple[User, str, str]:
    actor = User(
        user_id=str(uuid.uuid4()),
        email=f"central-{uuid.uuid4().hex[:8]}@example.com",
        display_name="Central Team",
        password_hash=hash_password("central-password"),
        role=CENTRAL_TEAM_ROLE,
        status="active",
    )
    project_id = str(uuid.uuid4())
    definition_id = str(uuid.uuid4())
    feed_id = str(uuid.uuid4())
    db.add(actor)
    db.add(
        ProjectDefinition(
            definition_id=definition_id,
            project_id=project_id,
            name="Fiber AI Flow Project",
            domain_config={"destination_schema_ddl": destination_schema_ddl},
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
                approved_by_user_id=actor.user_id,
            )
        )
    db.commit()
    return actor, project_id, feed_id


def test_analyze_feed_creates_lookup_and_domain_object_fibers(monkeypatch: pytest.MonkeyPatch) -> None:
    from migrations_engine.management.fibers import (
        _DomainObject,
        _FeedAnalysisResult,
        _FieldBinding,
        _FieldMappingResult,
        _LookupIdentified,
        analyze_feed,
    )

    feed_analysis_result = _FeedAnalysisResult(
        lookups=[_LookupIdentified(column_name="ACCT_TYPE", lookup_name="account_type")],
        domain_objects=[_DomainObject(destination_table="customers")],
    )
    field_mapping_result = _FieldMappingResult(
        field_bindings=[
            _FieldBinding(source_field="CUST_ID", destination_field="id", lookup_name=None),
            _FieldBinding(source_field="SURNAME", destination_field="name", lookup_name=None),
            _FieldBinding(source_field=None, destination_field="created_at", lookup_name=None),
        ]
    )

    feed_analysis_adapter = FakeFeedAnalysisAdapter(feed_analysis_result)
    field_mapping_adapter = FakeFieldMappingAdapter(field_mapping_result)

    def fake_get_adapter(task: str) -> Any:
        if task == "feed_analysis":
            return feed_analysis_adapter
        if task == "field_mapping":
            return field_mapping_adapter
        raise ValueError(f"Unexpected task: {task}")

    monkeypatch.setattr(fibers_module, "get_adapter", fake_get_adapter)

    with SessionLocal() as db:
        actor, project_id, feed_id = _seed_project_and_feed(db)
        responses = analyze_feed(db, feed_id=feed_id, project_id=project_id, actor=actor)

    assert len(responses) == 2
    lookup_fibers = [row for row in responses if row.fiber_type == "lookup"]
    domain_fibers = [row for row in responses if row.fiber_type == "domain_object"]

    assert len(lookup_fibers) == 1
    assert lookup_fibers[0].fiber_key == "account_type"
    assert lookup_fibers[0].status == "deferred"
    assert lookup_fibers[0].source == "auto"

    assert len(domain_fibers) == 1
    assert domain_fibers[0].fiber_key == "customers"
    assert domain_fibers[0].status == "mapped"
    assert domain_fibers[0].source == "auto"
    assert domain_fibers[0].field_bindings is not None
    assert len(domain_fibers[0].field_bindings) == 3


def test_analyze_feed_passes_correct_context_to_ai(monkeypatch: pytest.MonkeyPatch) -> None:
    from migrations_engine.management.fibers import (
        _DomainObject,
        _FeedAnalysisResult,
        _FieldBinding,
        _FieldMappingResult,
        _LookupIdentified,
        analyze_feed,
    )

    ddl = "CREATE TABLE orders (order_id INT, customer_id INT);"
    header = "ORDER_ID,CUSTOMER_ID,STATUS_CODE"

    feed_analysis_result = _FeedAnalysisResult(
        lookups=[_LookupIdentified(column_name="STATUS_CODE", lookup_name="order_status")],
        domain_objects=[_DomainObject(destination_table="orders")],
    )
    field_mapping_result = _FieldMappingResult(
        field_bindings=[
            _FieldBinding(source_field="ORDER_ID", destination_field="order_id", lookup_name=None),
            _FieldBinding(source_field="CUSTOMER_ID", destination_field="customer_id", lookup_name=None),
        ]
    )

    feed_analysis_adapter = FakeFeedAnalysisAdapter(feed_analysis_result)
    field_mapping_adapter = FakeFieldMappingAdapter(field_mapping_result)

    def fake_get_adapter(task: str) -> Any:
        if task == "feed_analysis":
            return feed_analysis_adapter
        return field_mapping_adapter

    monkeypatch.setattr(fibers_module, "get_adapter", fake_get_adapter)

    with SessionLocal() as db:
        actor, project_id, feed_id = _seed_project_and_feed(
            db,
            header_csv=header,
            destination_schema_ddl=ddl,
        )
        analyze_feed(db, feed_id=feed_id, project_id=project_id, actor=actor)

    assert len(feed_analysis_adapter.calls) == 1
    feed_analysis_call = feed_analysis_adapter.calls[0]
    feed_analysis_payload = json.loads(feed_analysis_call.user)
    assert feed_analysis_payload["source_headers"] == ["ORDER_ID", "CUSTOMER_ID", "STATUS_CODE"]
    assert feed_analysis_payload["destination_schema_ddl"] == ddl
    assert "data migration analyst" in feed_analysis_call.system.lower()

    assert len(field_mapping_adapter.calls) == 1
    field_mapping_call = field_mapping_adapter.calls[0]
    field_mapping_payload = json.loads(field_mapping_call.user)
    assert field_mapping_payload["source_columns"] == ["ORDER_ID", "CUSTOMER_ID", "STATUS_CODE"]
    assert field_mapping_payload["destination_table"] == "orders"
    assert field_mapping_payload["destination_schema_ddl"] == ddl
    assert "field mapper" in field_mapping_call.system.lower()


def test_analyze_feed_uses_correct_ai_slots(monkeypatch: pytest.MonkeyPatch) -> None:
    from migrations_engine.management.fibers import (
        _DomainObject,
        _FeedAnalysisResult,
        _FieldBinding,
        _FieldMappingResult,
        analyze_feed,
    )

    requested_tasks: list[str] = []
    feed_analysis_result = _FeedAnalysisResult(
        lookups=[],
        domain_objects=[_DomainObject(destination_table="customers")],
    )
    field_mapping_result = _FieldMappingResult(
        field_bindings=[_FieldBinding(source_field="ID", destination_field="id", lookup_name=None)]
    )

    def fake_get_adapter(task: str) -> Any:
        requested_tasks.append(task)
        if task == "feed_analysis":
            return FakeFeedAnalysisAdapter(feed_analysis_result)
        return FakeFieldMappingAdapter(field_mapping_result)

    monkeypatch.setattr(fibers_module, "get_adapter", fake_get_adapter)

    with SessionLocal() as db:
        actor, project_id, feed_id = _seed_project_and_feed(db)
        analyze_feed(db, feed_id=feed_id, project_id=project_id, actor=actor)

    assert "feed_analysis" in requested_tasks
    assert "field_mapping" in requested_tasks


def test_analyze_feed_with_multiple_domain_objects_calls_field_mapping_per_fiber(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from migrations_engine.management.fibers import (
        _DomainObject,
        _FeedAnalysisResult,
        _FieldBinding,
        _FieldMappingResult,
        analyze_feed,
    )

    feed_analysis_result = _FeedAnalysisResult(
        lookups=[],
        domain_objects=[
            _DomainObject(destination_table="customers"),
            _DomainObject(destination_table="accounts"),
        ],
    )
    field_mapping_result = _FieldMappingResult(
        field_bindings=[_FieldBinding(source_field="ID", destination_field="id", lookup_name=None)]
    )

    feed_analysis_adapter = FakeFeedAnalysisAdapter(feed_analysis_result)
    field_mapping_adapter = FakeFieldMappingAdapter(field_mapping_result)

    def fake_get_adapter(task: str) -> Any:
        if task == "feed_analysis":
            return feed_analysis_adapter
        return field_mapping_adapter

    monkeypatch.setattr(fibers_module, "get_adapter", fake_get_adapter)

    with SessionLocal() as db:
        actor, project_id, feed_id = _seed_project_and_feed(db)
        responses = analyze_feed(db, feed_id=feed_id, project_id=project_id, actor=actor)

    domain_fibers = [row for row in responses if row.fiber_type == "domain_object"]
    assert len(domain_fibers) == 2
    assert len(field_mapping_adapter.calls) == 2
    destination_tables = [json.loads(call.user)["destination_table"] for call in field_mapping_adapter.calls]
    assert set(destination_tables) == {"customers", "accounts"}


def test_analyze_feed_raises_409_when_no_approved_feed_slice(monkeypatch: pytest.MonkeyPatch) -> None:
    from migrations_engine.api.deps import AuthApiError
    from migrations_engine.management.fibers import analyze_feed

    monkeypatch.setattr(fibers_module, "get_adapter", lambda task: None)

    actor = User(
        user_id=str(uuid.uuid4()),
        email=f"central-{uuid.uuid4().hex[:8]}@example.com",
        display_name="Central Team",
        password_hash=hash_password("central-password"),
        role=CENTRAL_TEAM_ROLE,
        status="active",
    )
    project_id = str(uuid.uuid4())
    definition_id = str(uuid.uuid4())
    feed_id = str(uuid.uuid4())

    with SessionLocal() as db:
        db.add(actor)
        db.add(ProjectDefinition(definition_id=definition_id, project_id=project_id, name="P", domain_config={}))
        db.add(ProjectRegistry(project_id=project_id, name="P", definition_id=definition_id, status="active"))
        db.add(
            Feed(
                source_definition_id=feed_id,
                project_id=project_id,
                source_type="csv",
                source_contract_version="v1",
            )
        )
        db.commit()

        with pytest.raises(AuthApiError) as exc_info:
            analyze_feed(db, feed_id=feed_id, project_id=project_id, actor=actor)

    assert exc_info.value.status_code == 409
    assert exc_info.value.code == "feed_slice_not_ready"


def test_post_analyze_feed_returns_created_fibers(monkeypatch: pytest.MonkeyPatch, admin_token: str) -> None:
    from migrations_engine.management.fibers import (
        _DomainObject,
        _FeedAnalysisResult,
        _FieldBinding,
        _FieldMappingResult,
        _LookupIdentified,
    )

    feed_analysis_result = _FeedAnalysisResult(
        lookups=[_LookupIdentified(column_name="ACCT_TYPE", lookup_name="account_type")],
        domain_objects=[_DomainObject(destination_table="customers")],
    )
    field_mapping_result = _FieldMappingResult(
        field_bindings=[_FieldBinding(source_field="CUST_ID", destination_field="id", lookup_name=None)]
    )

    def fake_get_adapter(task: str) -> Any:
        if task == "feed_analysis":
            return FakeFeedAnalysisAdapter(feed_analysis_result)
        if task == "field_mapping":
            return FakeFieldMappingAdapter(field_mapping_result)
        raise ValueError(f"Unexpected task: {task}")

    monkeypatch.setattr(fibers_module, "get_adapter", fake_get_adapter)

    with SessionLocal() as db:
        _actor, project_id, feed_id = _seed_project_and_feed(db)

    response = client.post(
        f"/projects/{project_id}/feeds/{feed_id}/analyze",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert len(body) == 2
    assert {row["fiber_type"] for row in body} == {"lookup", "domain_object"}


def test_post_analyze_feed_requires_auth() -> None:
    with SessionLocal() as db:
        _actor, project_id, feed_id = _seed_project_and_feed(db)

    response = client.post(f"/projects/{project_id}/feeds/{feed_id}/analyze")

    assert response.status_code == 401


def test_post_analyze_feed_requires_central_team(stakeholder_token: str) -> None:
    with SessionLocal() as db:
        _actor, project_id, feed_id = _seed_project_and_feed(db)

    response = client.post(
        f"/projects/{project_id}/feeds/{feed_id}/analyze",
        headers={"Authorization": f"Bearer {stakeholder_token}"},
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "forbidden"


def test_post_analyze_feed_returns_409_without_approved_slice(admin_token: str) -> None:
    with SessionLocal() as db:
        _actor, project_id, feed_id = _seed_project_and_feed(db, approved_slice=False)

    response = client.post(
        f"/projects/{project_id}/feeds/{feed_id}/analyze",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "feed_slice_not_ready"

