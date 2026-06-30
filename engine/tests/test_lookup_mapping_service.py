from __future__ import annotations

from datetime import UTC, datetime
import uuid

import pytest
from sqlalchemy import select

from sqlite_test_support import Base, SessionLocal, TEST_ENGINE
from migrations_engine.api.deps import AuthApiError
from migrations_engine.auth.passwords import hash_password
from migrations_engine.db.models import (
    AuditEvent,
    LookupSnapshot,
    ProjectDefinition,
    ProjectRegistry,
    SourceDefinition,
    SourceSlice,
    SourceValueSummary,
    User,
)
from migrations_engine.management.lookup_mapping import (
    approve_lookup_snapshot,
    create_lookup_value_map,
    generate_lookup_snapshot,
    list_lookup_value_maps,
)
from migrations_engine.api.schemas import LookupSnapshotGenerateRequest, LookupValueMapCreateRequest
from migrations_engine.roles import CENTRAL_TEAM_ROLE


def _seed_project(db) -> tuple[User, str, str]:
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
    source_definition_id = str(uuid.uuid4())
    db.add(actor)
    db.add(
        ProjectDefinition(
            definition_id=definition_id,
            project_id=project_id,
            name="Lookup Project",
            status="active",
        )
    )
    db.add(
        ProjectRegistry(
            project_id=project_id,
            name="Lookup Project",
            definition_id=definition_id,
            status="active",
        )
    )
    db.add(
        SourceDefinition(
            source_definition_id=source_definition_id,
            project_id=project_id,
            source_type="csv",
            source_contract_version="v1",
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
            approved_by_user_id=actor.user_id,
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
    db.commit()
    return actor, project_id, source_definition_id


def test_lookup_mapping_service_persists_draft_and_lists_maps() -> None:
    Base.metadata.create_all(bind=TEST_ENGINE)

    with SessionLocal() as db:
        actor, project_id, source_definition_id = _seed_project(db)

        response = create_lookup_value_map(
            db,
            actor=actor,
            project_id=project_id,
            source_definition_id=source_definition_id,
            body=LookupValueMapCreateRequest(
                lookup_name="STATUS_CODE",
                destination_table=[
                    {"id": "ACTIVE", "label": "Active"},
                    {"id": "BLOCKED", "label": "Blocked"},
                ],
            ),
        )

        maps = list_lookup_value_maps(
            db,
            project_id=project_id,
            source_definition_id=source_definition_id,
        )

    assert response.status == "draft"
    assert response.destination_table[0]["id"] == "ACTIVE"
    assert len(maps) == 1
    assert maps[0].lookup_name == "STATUS_CODE"


def test_lookup_mapping_service_generates_and_approves_snapshot() -> None:
    Base.metadata.create_all(bind=TEST_ENGINE)

    with SessionLocal() as db:
        actor, project_id, source_definition_id = _seed_project(db)
        actor_user_id = actor.user_id
        create_lookup_value_map(
            db,
            actor=actor,
            project_id=project_id,
            source_definition_id=source_definition_id,
            body=LookupValueMapCreateRequest(
                lookup_name="STATUS_CODE",
                destination_table=[
                    {"id": "ACTIVE", "label": "Active"},
                    {"id": "BLOCKED", "label": "Blocked"},
                ],
            ),
        )

        snapshot = generate_lookup_snapshot(
            db,
            actor=actor,
            project_id=project_id,
            source_definition_id=source_definition_id,
            body=LookupSnapshotGenerateRequest(
                lookup_name="STATUS_CODE",
                value_map={"A": "ACTIVE", "B": "BLOCKED"},
            ),
        )
        approved = approve_lookup_snapshot(
            db,
            actor=actor,
            project_id=project_id,
            source_definition_id=source_definition_id,
            lookup_snapshot_id=snapshot.lookup_snapshot_id,
        )
        audit_events = list(db.scalars(select(AuditEvent).where(AuditEvent.project_id == project_id)))
        stored_snapshot = db.get(LookupSnapshot, snapshot.lookup_snapshot_id)

    assert snapshot.status == "draft"
    assert snapshot.lookup_snapshot_version == "v1"
    assert approved.status == "approved"
    assert stored_snapshot is not None
    assert stored_snapshot.approved_by_user_id == actor_user_id
    assert any(event.event_type == "lookup_snapshot.generated" for event in audit_events)
    assert any(event.event_type == "lookup_snapshot.approved" for event in audit_events)


def test_lookup_mapping_service_rejects_unmapped_values() -> None:
    Base.metadata.create_all(bind=TEST_ENGINE)

    with SessionLocal() as db:
        actor, project_id, source_definition_id = _seed_project(db)
        create_lookup_value_map(
            db,
            actor=actor,
            project_id=project_id,
            source_definition_id=source_definition_id,
            body=LookupValueMapCreateRequest(
                lookup_name="STATUS_CODE",
                destination_table=[{"id": "ACTIVE", "label": "Active"}],
            ),
        )

        with pytest.raises(AuthApiError) as exc_info:
            generate_lookup_snapshot(
                db,
                actor=actor,
                project_id=project_id,
                source_definition_id=source_definition_id,
                body=LookupSnapshotGenerateRequest(
                    lookup_name="STATUS_CODE",
                    value_map={"A": "ACTIVE"},
                ),
            )

    assert exc_info.value.code == "lookup_values_unmapped"
