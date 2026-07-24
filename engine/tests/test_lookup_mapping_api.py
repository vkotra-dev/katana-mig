from __future__ import annotations

from datetime import UTC, datetime
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from sqlite_test_support import Base, SessionLocal, TEST_ENGINE
from migrations_engine.app import app  # noqa: E402
from migrations_engine.auth.passwords import hash_password  # noqa: E402
from migrations_engine.config import get_settings  # noqa: E402
from migrations_engine.db.models import (  # noqa: E402
    FeedSlice,
    LookupSnapshot,
    LookupValueMap,
    ProjectDefinition,
    ProjectFiber,
    ProjectMembership,
    ProjectRegistry,
    SourceDefinition,
    SourceSlice,
    SourceValueSummary,
    User,
)
from migrations_engine.mapping.snapshots import FieldBinding, create_approved_mapping_snapshot  # noqa: E402
from migrations_engine.roles import CENTRAL_TEAM_ROLE, PROJECT_STAKEHOLDER_ROLE  # noqa: E402

client = TestClient(app)


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


def _seed_project() -> tuple[str, str]:
    project_id = str(uuid.uuid4())
    definition_id = str(uuid.uuid4())
    source_definition_id = str(uuid.uuid4())
    with SessionLocal() as db:
        admin_user = db.scalar(select(User).where(User.role == CENTRAL_TEAM_ROLE))
        stakeholder_user = db.scalar(select(User).where(User.email == "stakeholder@example.com"))
        assert admin_user is not None
        assert stakeholder_user is not None
        db.add(
            ProjectDefinition(
                definition_id=definition_id,
                project_id=project_id,
                name="Lookup API Project",
                status="active",
            )
        )
        db.add(
            ProjectRegistry(
                project_id=project_id,
                name="Lookup API Project",
                definition_id=definition_id,
                status="active",
            )
        )
        db.flush()
        db.add(ProjectMembership(project_id=project_id, user_id=stakeholder_user.user_id))
        db.add(
            SourceDefinition(
                source_definition_id=source_definition_id,
                project_id=project_id,
                source_type="csv",
                source_contract_version="v1",
                destination_object_references=["Customer"],
                source_details={"label": "Customer Extract", "encoding": "utf-8"},
                status="active",
            )
        )
        db.add(
            SourceSlice(
                source_slice_id=str(uuid.uuid4()),
                source_definition_id=source_definition_id,
                source_contract_version="v1",
                source_slice_version="v1",
                source_schema_artifact=None,
                masking_policy={},
                header_csv="STATUS_CODE",
                slice_payload=None,
                status="approved",
                parse_warnings=[],
                file_storage_path="/tmp/source.csv",
                approved_at=datetime.now(UTC),
                approved_by_user_id=admin_user.user_id,
            )
        )
        db.add(
            SourceValueSummary(
                source_definition_id=source_definition_id,
                source_slice_version="v1",
                field_name="STATUS_CODE",
                value_counts={"A": 4, "B": 1},
            )
        )
        create_approved_mapping_snapshot(
            db,
            project_id=project_id,
            destination_object_name="Customer",
            mapping_snapshot_version="v1",
            field_bindings=[
                FieldBinding(
                    source_field="STATUS_CODE",
                    destination_field="status_id",
                    lookup_name="status_code",
                ),
            ],
            approved_by_user_id=admin_user.user_id,
            source_definition_id=source_definition_id,
        )
        db.commit()
    return project_id, source_definition_id


def test_lookup_routes_enforce_auth_and_contract(admin_token: str, stakeholder_token: str) -> None:
    project_id, source_definition_id = _seed_project()

    forbidden = client.post(
        f"/projects/{project_id}/lookup-maps",
        headers={"Authorization": f"Bearer {stakeholder_token}"},
        json={
            "lookup_name": "STATUS_CODE",
            "destination_table": [{"id": "ACTIVE", "label": "Active"}],
        },
    )
    assert forbidden.status_code == 403
    assert forbidden.json()["error"]["code"] == "forbidden"

    create = client.post(
        f"/projects/{project_id}/lookup-maps",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "lookup_name": "status_code",
            "destination_table": [{"id": "ACTIVE", "label": "Active"}],
            "source_value_map": {"A": "ACTIVE", "B": "ACTIVE"},
        },
    )
    assert create.status_code == 201, create.text
    assert create.json()["lookup_name"] == "status_code"

    mapping_snapshot = client.get(
        f"/projects/{project_id}/sources/{source_definition_id}/mapping-snapshot",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert mapping_snapshot.status_code == 200, mapping_snapshot.text
    assert mapping_snapshot.json()["mapping_snapshot_version"] == "v1"

    mapping_snapshots = client.get(
        f"/projects/{project_id}/sources/{source_definition_id}/mapping-snapshots",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert mapping_snapshots.status_code == 200, mapping_snapshots.text
    snapshots_list = mapping_snapshots.json()
    assert isinstance(snapshots_list, list)
    assert len(snapshots_list) == 1
    assert snapshots_list[0]["destination_object_name"] == "Customer"

    generate = client.post(
        f"/projects/{project_id}/sources/{source_definition_id}/lookup-snapshots",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "lookup_name": "status_code",
        },
    )
    assert generate.status_code == 201, generate.text
    assert generate.json()["lookup_snapshot_version"] == "v1"

    approve = client.post(
        f"/projects/{project_id}/lookup-snapshots/{generate.json()['lookup_snapshot_id']}/approve",
        headers={"Authorization": f"Bearer {stakeholder_token}"},
    )
    assert approve.status_code == 200, approve.text
    assert approve.json()["status"] == "approved"


def test_mapping_snapshots_list_endpoint(admin_token: str) -> None:
    project_id, source_definition_id = _seed_project()
    with SessionLocal() as db:
        source_definition_id_empty = str(uuid.uuid4())
        db.add(
            SourceDefinition(
                source_definition_id=source_definition_id_empty,
                project_id=project_id,
                source_type="csv",
                source_contract_version="v1",
                destination_object_references=["Customer"],
                source_details={"label": "Empty Source", "encoding": "utf-8"},
                status="active",
            )
        )
        db.commit()

    # 1. 0 tables test:
    res = client.get(
        f"/projects/{project_id}/sources/{source_definition_id_empty}/mapping-snapshots",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res.status_code == 200
    assert res.json() == []

    # 2. 1 table test:
    res = client.get(
        f"/projects/{project_id}/sources/{source_definition_id}/mapping-snapshots",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res.status_code == 200
    assert len(res.json()) == 1
    assert res.json()[0]["destination_object_name"] == "Customer"

    # 3. 2 tables test:
    with SessionLocal() as db:
        admin_user = db.scalar(select(User).where(User.role == CENTRAL_TEAM_ROLE))
        create_approved_mapping_snapshot(
            db,
            project_id=project_id,
            destination_object_name="Address",
            mapping_snapshot_version="v2",
            field_bindings=[],
            approved_by_user_id=admin_user.user_id,
            source_definition_id=source_definition_id,
        )
        db.commit()

    res = client.get(
        f"/projects/{project_id}/sources/{source_definition_id}/mapping-snapshots",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res.status_code == 200
    snapshots = res.json()
    assert len(snapshots) == 2
    names = [s["destination_object_name"] for s in snapshots]
    assert names == ["Address", "Customer"]


def test_patch_lookup_value_map(admin_token: str) -> None:
    project_id, _source_definition_id = _seed_project()

    # Create a lookup value map first
    create = client.post(
        f"/projects/{project_id}/lookup-maps",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "lookup_name": "status_code",
            "destination_table": [{"id": "ACTIVE", "label": "Active"}, {"id": "BLOCKED", "label": "Blocked"}],
            "source_value_map": {"A": "ACTIVE", "B": "BLOCKED"},
        },
    )
    assert create.status_code == 201, create.text
    lookup_map_id = create.json()["lookup_value_map_id"]

    # Patch it
    patch = client.patch(
        f"/projects/{project_id}/lookup-maps/{lookup_map_id}",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"source_value_map": {"A": "ACTIVE", "B": "ACTIVE"}},
    )
    assert patch.status_code == 200, patch.text
    assert patch.json()["source_value_map"] == {"A": "ACTIVE", "B": "ACTIVE"}

    # Verify it persists
    result_list = client.get(
        f"/projects/{project_id}/lookup-maps",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert result_list.status_code == 200
    maps = result_list.json()
    updated = [m for m in maps if m["lookup_value_map_id"] == lookup_map_id]
    assert len(updated) == 1
    assert updated[0]["source_value_map"] == {"A": "ACTIVE", "B": "ACTIVE"}


def test_patch_lookup_value_map_forbidden(admin_token: str, stakeholder_token: str) -> None:
    project_id, _source_definition_id = _seed_project()

    # Create first
    create = client.post(
        f"/projects/{project_id}/lookup-maps",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "lookup_name": "status_code",
            "destination_table": [{"id": "ACTIVE"}],
            "source_value_map": {"A": "ACTIVE"},
        },
    )
    assert create.status_code == 201
    lookup_map_id = create.json()["lookup_value_map_id"]

    # Stakeholder cannot patch
    patch = client.patch(
        f"/projects/{project_id}/lookup-maps/{lookup_map_id}",
        headers={"Authorization": f"Bearer {stakeholder_token}"},
        json={"source_value_map": {"A": "BLOCKED"}},
    )
    assert patch.status_code == 403
    assert patch.json()["error"]["code"] == "forbidden"


def test_patch_lookup_value_map_not_found(admin_token: str) -> None:
    project_id, _source_definition_id = _seed_project()
    fake_id = str(uuid.uuid4())

    patch = client.patch(
        f"/projects/{project_id}/lookup-maps/{fake_id}",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"source_value_map": {"A": "B"}},
    )
    assert patch.status_code == 404


def test_patch_lookup_value_map_approved(admin_token: str) -> None:
    project_id, _source_definition_id = _seed_project()

    # Create a lookup value map
    create = client.post(
        f"/projects/{project_id}/lookup-maps",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "lookup_name": "status_code",
            "destination_table": [{"id": "ACTIVE"}],
            "source_value_map": {"A": "ACTIVE"},
        },
    )
    assert create.status_code == 201
    lookup_map_id = create.json()["lookup_value_map_id"]

    # Approve the lookup map
    with SessionLocal() as db:
        db_item = db.get(LookupValueMap, lookup_map_id)
        db_item.status = "approved"
        db.commit()

    # Patch should fail with 409
    patch = client.patch(
        f"/projects/{project_id}/lookup-maps/{lookup_map_id}",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"source_value_map": {"A": "BLOCKED"}},
    )
    assert patch.status_code == 409
    assert patch.json()["error"]["code"] == "lookup_map_approved"


def test_get_lookup_maps_returns_unmapped_row_count(admin_token: str) -> None:
    project_id, source_definition_id = _seed_project()

    # Store a lookup value map directly in the DB with an unmapped (empty) value
    # We can't use the API create endpoint because it strips empty values
    with SessionLocal() as db:
        db.add(
            LookupValueMap(
                lookup_value_map_id=str(uuid.uuid4()),
                project_id=project_id,
                lookup_name="status_code",
                destination_table=[{"id": "ACTIVE", "label": "Active"}],
                source_value_map={"A": "ACTIVE", "B": ""},  # B is unmapped (empty string)
                status="draft",
            )
        )
        db.add(
            FeedSlice(
                source_slice_id=str(uuid.uuid4()),
                source_definition_id=source_definition_id,
                source_contract_version="v1",
                source_slice_version="v1",
                source_schema_artifact=None,
                masking_policy={},
                header_csv="STATUS_CODE",
                slice_payload=None,
                status="approved",
                parse_warnings=[],
                file_storage_path="/tmp/source.csv",
                data_profile={
                    "STATUS_CODE": {"A": 100, "B": 250, "C": 50},
                    "OTHER_COL": {"X": 10},
                },
                approved_at=datetime.now(UTC),
                approved_by_user_id=db.scalar(select(User).where(User.role == CENTRAL_TEAM_ROLE)).user_id,
            )
        )
        db.add(
            ProjectFiber(
                fiber_id=str(uuid.uuid4()),
                feed_id=source_definition_id,
                project_id=project_id,
                fiber_type="lookup",
                fiber_key="status_code",
                status="operator_triggered",
                source="manual",
            )
        )
        db.commit()

    # Fetch with feed_id to trigger data_profile lookup
    result = client.get(
        f"/projects/{project_id}/lookup-maps?feed_id={source_definition_id}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert result.status_code == 200
    maps = result.json()
    assert len(maps) >= 1, f"Expected >=1 maps, got {len(maps)}: {maps}"
    status_map = [m for m in maps if m["lookup_name"] == "status_code"][0]
    # B is unmapped and has count 250 in data_profile
def test_lookup_value_map_response_includes_destination_mappings(admin_token: str) -> None:
    project_id, _source_definition_id = _seed_project()

    create = client.post(
        f"/projects/{project_id}/lookup-maps",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "lookup_name": "status_code",
            "destination_table": [
                {"id": "ACTIVE", "label": "Active"},
            ],
            "source_value_map": {"A": "ACTIVE"},
            "destination_mappings": [
                {
                    "dest_id": "ACTIVE",
                    "dest_label": "Active",
                    "dest_row": {"id": "ACTIVE", "label": "Active"},
                    "source_values": ["A"],
                    "status": "draft",
                }
            ],
        },
    )
    assert create.status_code == 201, create.text
    data = create.json()
    assert len(data["destination_mappings"]) == 1
    assert data["destination_mappings"][0]["dest_id"] == "ACTIVE"
    assert data["destination_mappings"][0]["source_values"] == ["A"]


def test_patch_add_source_value(admin_token: str) -> None:
    project_id, _source_definition_id = _seed_project()

    create = client.post(
        f"/projects/{project_id}/lookup-maps",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "lookup_name": "status_code",
            "destination_table": [
                {"id": "ACTIVE", "label": "Active"},
                {"id": "BLOCKED", "label": "Blocked"},
            ],
            "source_value_map": {"A": "ACTIVE"},
        },
    )
    assert create.status_code == 201, create.text
    lookup_map_id = create.json()["lookup_value_map_id"]

    # Add a source value to the BLOCKED destination
    patch = client.patch(
        f"/projects/{project_id}/lookup-maps/{lookup_map_id}",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"add_source_value": {"dest_id": "BLOCKED", "source_value": "B"}},
    )
    assert patch.status_code == 200, patch.text
    data = patch.json()
    assert data["source_value_map"]["B"] == "BLOCKED"
    dest_mappings = data["destination_mappings"]
    blocked_group = next((g for g in dest_mappings if g["dest_id"] == "BLOCKED"), None)
    assert blocked_group is not None
    assert "B" in blocked_group["source_values"]
    assert blocked_group["dest_label"] == "Blocked"


def test_patch_add_source_value_stacks_into_existing_group(admin_token: str) -> None:
    """Adding a second, different source value to a dest_id that already has one
    source value must append to the SAME group, not create a duplicate group."""
    project_id, _source_definition_id = _seed_project()

    create = client.post(
        f"/projects/{project_id}/lookup-maps",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "lookup_name": "status_code",
            "destination_table": [{"id": "ACTIVE", "label": "Active"}],
            "source_value_map": {"A": "ACTIVE"},
            "destination_mappings": [
                {
                    "dest_id": "ACTIVE",
                    "dest_label": "Active",
                    "dest_row": {},
                    "source_values": ["A"],
                    "status": "draft",
                },
            ],
        },
    )
    assert create.status_code == 201, create.text
    lookup_map_id = create.json()["lookup_value_map_id"]

    # ACTIVE already has "A". Add a second, different source value "B" to ACTIVE.
    patch = client.patch(
        f"/projects/{project_id}/lookup-maps/{lookup_map_id}",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"add_source_value": {"dest_id": "ACTIVE", "source_value": "B"}},
    )
    assert patch.status_code == 200, patch.text
    data = patch.json()

    active_groups = [g for g in data["destination_mappings"] if g["dest_id"] == "ACTIVE"]
    assert len(active_groups) == 1, f"expected exactly one ACTIVE group, got {len(active_groups)}: {active_groups}"
    assert set(active_groups[0]["source_values"]) == {"A", "B"}


def test_patch_add_source_value_stacks_when_destination_mappings_preseeded(admin_token: str) -> None:
    """Control case: when destination_mappings is explicitly seeded at create time
    (not left to be inferred from source_value_map), does add_source_value stack correctly?"""
    project_id, _source_definition_id = _seed_project()

    create = client.post(
        f"/projects/{project_id}/lookup-maps",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "lookup_name": "status_code",
            "destination_table": [{"id": "ACTIVE", "label": "Active"}],
            "source_value_map": {"A": "ACTIVE"},
            "destination_mappings": [
                {"dest_id": "ACTIVE", "dest_label": "Active", "dest_row": {}, "source_values": ["A"], "status": "draft"},
            ],
        },
    )
    assert create.status_code == 201, create.text
    lookup_map_id = create.json()["lookup_value_map_id"]

    patch = client.patch(
        f"/projects/{project_id}/lookup-maps/{lookup_map_id}",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"add_source_value": {"dest_id": "ACTIVE", "source_value": "B"}},
    )
    assert patch.status_code == 200, patch.text
    data = patch.json()

    active_groups = [g for g in data["destination_mappings"] if g["dest_id"] == "ACTIVE"]
    assert len(active_groups) == 1, f"expected exactly one ACTIVE group, got {len(active_groups)}: {active_groups}"
    assert set(active_groups[0]["source_values"]) == {"A", "B"}


def test_patch_remove_source_value_from_preseeded_group(admin_token: str) -> None:
    """When destination_mappings already has a group with 2+ source values (the
    normal state once stacking works), removing one value must actually persist
    — not silently no-op due to in-place-mutation-not-detected-by-SQLAlchemy."""
    project_id, _source_definition_id = _seed_project()

    create = client.post(
        f"/projects/{project_id}/lookup-maps",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "lookup_name": "status_code",
            "destination_table": [{"id": "ACTIVE", "label": "Active"}],
            "source_value_map": {"A": "ACTIVE", "B": "ACTIVE"},
            "destination_mappings": [
                {"dest_id": "ACTIVE", "dest_label": "Active", "dest_row": {}, "source_values": ["A", "B"], "status": "draft"},
            ],
        },
    )
    assert create.status_code == 201, create.text
    lookup_map_id = create.json()["lookup_value_map_id"]

    patch = client.patch(
        f"/projects/{project_id}/lookup-maps/{lookup_map_id}",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"remove_source_value": {"dest_id": "ACTIVE", "source_value": "B"}},
    )
    assert patch.status_code == 200, patch.text
    data = patch.json()

    active_groups = [g for g in data["destination_mappings"] if g["dest_id"] == "ACTIVE"]
    assert len(active_groups) == 1, f"expected exactly one ACTIVE group, got {len(active_groups)}: {active_groups}"
    assert active_groups[0]["source_values"] == ["A"], active_groups[0]["source_values"]


def test_patch_move_source_value_between_existing_groups(admin_token: str) -> None:
    """Moving a source value from one existing, populated group to another
    existing, populated group must persist both the removal from the old
    group and the addition to the new group (both exercise the
    in-place-mutation SQLAlchemy bug)."""
    project_id, _source_definition_id = _seed_project()

    create = client.post(
        f"/projects/{project_id}/lookup-maps",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "lookup_name": "status_code",
            "destination_table": [
                {"id": "ACTIVE", "label": "Active"},
                {"id": "BLOCKED", "label": "Blocked"},
            ],
            "source_value_map": {"A": "ACTIVE", "B": "BLOCKED"},
            "destination_mappings": [
                {
                    "dest_id": "ACTIVE",
                    "dest_label": "Active",
                    "dest_row": {},
                    "source_values": ["A", "C"],
                    "status": "draft",
                },
                {
                    "dest_id": "BLOCKED",
                    "dest_label": "Blocked",
                    "dest_row": {},
                    "source_values": ["B"],
                    "status": "draft",
                },
            ],
        },
    )
    assert create.status_code == 201, create.text
    lookup_map_id = create.json()["lookup_value_map_id"]

    patch = client.patch(
        f"/projects/{project_id}/lookup-maps/{lookup_map_id}",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "move_source_value": {
                "source_value": "C",
                "old_dest_id": "ACTIVE",
                "new_dest_id": "BLOCKED",
            }
        },
    )
    assert patch.status_code == 200, patch.text
    data = patch.json()

    active_group = next(g for g in data["destination_mappings"] if g["dest_id"] == "ACTIVE")
    blocked_group = next(g for g in data["destination_mappings"] if g["dest_id"] == "BLOCKED")
    assert active_group["source_values"] == ["A"], active_group["source_values"]
    assert set(blocked_group["source_values"]) == {"B", "C"}, blocked_group["source_values"]
    assert data["source_value_map"]["C"] == "BLOCKED"


def test_patch_remove_source_value(admin_token: str) -> None:
    project_id, _source_definition_id = _seed_project()

    create = client.post(
        f"/projects/{project_id}/lookup-maps",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "lookup_name": "status_code",
            "destination_table": [
                {"id": "ACTIVE", "label": "Active"},
                {"id": "BLOCKED", "label": "Blocked"},
            ],
            "source_value_map": {"A": "ACTIVE", "B": "BLOCKED"},
        },
    )
    assert create.status_code == 201
    lookup_map_id = create.json()["lookup_value_map_id"]

    # Remove source value B from BLOCKED
    patch = client.patch(
        f"/projects/{project_id}/lookup-maps/{lookup_map_id}",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"remove_source_value": {"dest_id": "BLOCKED", "source_value": "B"}},
    )
    assert patch.status_code == 200, patch.text
    data = patch.json()
    assert "B" not in data["source_value_map"]
    # After removing B, BLOCKED group still exists in destination_mappings
    dest_mappings = data["destination_mappings"]
    blocked_group = next((g for g in dest_mappings if g["dest_id"] == "BLOCKED"), None)
    if blocked_group:
        assert "B" not in blocked_group["source_values"]
        assert blocked_group["dest_label"] == "Blocked"


def test_patch_destination_mappings_overwrite(admin_token: str) -> None:
    project_id, _source_definition_id = _seed_project()

    create = client.post(
        f"/projects/{project_id}/lookup-maps",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "lookup_name": "status_code",
            "destination_table": [
                {"id": "ACTIVE", "label": "Active"},
                {"id": "BLOCKED", "label": "Blocked"},
            ],
            "source_value_map": {"A": "ACTIVE"},
        },
    )
    assert create.status_code == 201
    lookup_map_id = create.json()["lookup_value_map_id"]

    # Overwrite destination_mappings
    patch = client.patch(
        f"/projects/{project_id}/lookup-maps/{lookup_map_id}",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "destination_mappings": [
                {
                    "dest_id": "ACTIVE",
                    "dest_label": "Active",
                    "dest_row": {"id": "ACTIVE", "label": "Active"},
                    "source_values": ["A", "C"],
                    "status": "draft",
                },
                {
                    "dest_id": "BLOCKED",
                    "dest_label": "Blocked",
                    "dest_row": {"id": "BLOCKED", "label": "Blocked"},
                    "source_values": ["B"],
                    "status": "draft",
                },
            ]
        },
    )
    assert patch.status_code == 200, patch.text
    data = patch.json()
    assert data["source_value_map"] == {"A": "ACTIVE", "C": "ACTIVE", "B": "BLOCKED"}
    assert len(data["destination_mappings"]) == 2
    active_group = next(g for g in data["destination_mappings"] if g["dest_id"] == "ACTIVE")
    assert set(active_group["source_values"]) == {"A", "C"}


def test_patch_move_source_value(admin_token: str) -> None:
    project_id, _source_definition_id = _seed_project()

    create = client.post(
        f"/projects/{project_id}/lookup-maps",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "lookup_name": "status_code",
            "destination_table": [
                {"id": "ACTIVE", "label": "Active"},
                {"id": "BLOCKED", "label": "Blocked"},
            ],
            "source_value_map": {"A": "ACTIVE", "B": "ACTIVE"},
        },
    )
    assert create.status_code == 201
    lookup_map_id = create.json()["lookup_value_map_id"]

    # Move A from ACTIVE to BLOCKED
    patch = client.patch(
        f"/projects/{project_id}/lookup-maps/{lookup_map_id}",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "move_source_value": {
                "source_value": "A",
                "old_dest_id": "ACTIVE",
                "new_dest_id": "BLOCKED",
            }
        },
    )
    assert patch.status_code == 200, patch.text
    data = patch.json()
    assert data["source_value_map"]["A"] == "BLOCKED"
    active_group = next(g for g in data["destination_mappings"] if g["dest_id"] == "ACTIVE")
    blocked_group = next(g for g in data["destination_mappings"] if g["dest_id"] == "BLOCKED")
    assert active_group["dest_label"] == "Active"
    assert blocked_group["dest_label"] == "Blocked"
    assert "A" in blocked_group["source_values"]


def test_create_lookup_value_map_stores_destination_mappings(admin_token: str) -> None:
    project_id, _source_definition_id = _seed_project()

    create = client.post(
        f"/projects/{project_id}/lookup-maps",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "lookup_name": "status_code",
            "destination_table": [
                {"id": "ACTIVE", "label": "Active"},
                {"id": "BLOCKED", "label": "Blocked"},
            ],
            "source_value_map": {"A": "ACTIVE", "B": "BLOCKED"},
            "destination_mappings": [
                {
                    "dest_id": "ACTIVE",
                    "dest_label": "Active",
                    "dest_row": {"id": "ACTIVE", "label": "Active"},
                    "source_values": ["A"],
                    "status": "draft",
                },
                {
                    "dest_id": "BLOCKED",
                    "dest_label": "Blocked",
                    "dest_row": {"id": "BLOCKED", "label": "Blocked"},
                    "source_values": ["B"],
                    "status": "draft",
                },
            ],
        },
    )
    assert create.status_code == 201, create.text
    data = create.json()
    assert len(data["destination_mappings"]) == 2
    active = next(g for g in data["destination_mappings"] if g["dest_id"] == "ACTIVE")
    assert active["source_values"] == ["A"]


def test_patch_lookup_value_map_resets_approved_snapshots_to_draft(
    admin_token: str, stakeholder_token: str
) -> None:
    project_id, source_definition_id = _seed_project()

    # Seed project creates SourceValueSummary with A and B; map both to ACTIVE
    # so generate_lookup_snapshot does not reject unmapped values.
    create = client.post(
        f"/projects/{project_id}/lookup-maps",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "lookup_name": "status_code",
            "destination_table": [{"id": "ACTIVE", "label": "Active"}],
            "source_value_map": {"A": "ACTIVE", "B": "ACTIVE"},
        },
    )
    assert create.status_code == 201, create.text
    lookup_map_id = create.json()["lookup_value_map_id"]

    generate = client.post(
        f"/projects/{project_id}/sources/{source_definition_id}/lookup-snapshots",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"lookup_name": "status_code"},
    )
    assert generate.status_code == 201, generate.text
    snapshot_id = generate.json()["lookup_snapshot_id"]

    approve = client.post(
        f"/projects/{project_id}/lookup-snapshots/{snapshot_id}/approve",
        headers={"Authorization": f"Bearer {stakeholder_token}"},
    )
    assert approve.status_code == 200, approve.text
    assert approve.json()["status"] == "approved"

    # add_source_value should reset the approved snapshot to draft
    patch_add = client.patch(
        f"/projects/{project_id}/lookup-maps/{lookup_map_id}",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"add_source_value": {"dest_id": "ACTIVE", "source_value": "B"}},
    )
    assert patch_add.status_code == 200, patch_add.text

    with SessionLocal() as db:
        snapshot = db.get(LookupSnapshot, snapshot_id)
        assert snapshot.status == "draft"
        assert snapshot.approved_at is None

    # Re-approve, then confirm remove_source_value also resets it
    reapprove = client.post(
        f"/projects/{project_id}/lookup-snapshots/{snapshot_id}/approve",
        headers={"Authorization": f"Bearer {stakeholder_token}"},
    )
    assert reapprove.status_code == 200, reapprove.text

    patch_remove = client.patch(
        f"/projects/{project_id}/lookup-maps/{lookup_map_id}",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"remove_source_value": {"dest_id": "ACTIVE", "source_value": "B"}},
    )
    assert patch_remove.status_code == 200, patch_remove.text

    with SessionLocal() as db:
        snapshot = db.get(LookupSnapshot, snapshot_id)
        assert snapshot.status == "draft"

