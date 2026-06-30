from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select

from migrations_engine.api.deps import AuthApiError
from migrations_engine.api.schemas import (
    LookupSnapshotGenerateRequest,
    LookupValueMapCreateRequest,
)
from migrations_engine.db.base import Base
from migrations_engine.db.models import (
    AuditEvent,
    LookupSnapshot,
    ProjectDefinition,
    ProjectRegistry,
    SourceDefinition,
    SourceValueSummary,
    User,
)
from migrations_engine.db.session import SessionLocal, engine
from migrations_engine.mapping import FieldBinding, create_approved_mapping_snapshot
from migrations_engine.management.lookup_mapping import (
    approve_lookup_snapshot,
    create_lookup_value_map,
    generate_lookup_snapshot,
)


def _seed_lookup_context() -> tuple[str, str, str]:
    Base.metadata.create_all(bind=engine)
    project_id = str(uuid.uuid4())
    definition_id = str(uuid.uuid4())
    source_definition_id = str(uuid.uuid4())
    user_id = str(uuid.uuid4())

    with SessionLocal() as db:
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
                status="active",
            )
        )
        db.add(
            User(
                user_id=user_id,
                email=f"central-{user_id[:8]}@example.com",
                display_name="Central",
                password_hash="hash",
                role="central_team",
                status="active",
            )
        )
        create_approved_mapping_snapshot(
            db,
            project_id=project_id,
            destination_object_name="Account",
            mapping_snapshot_version="v1",
            field_bindings=[
                FieldBinding(
                    source_field="status_code",
                    destination_field="status_id",
                    lookup_name="status_map",
                )
            ],
        )
        db.add(
            SourceValueSummary(
                source_definition_id=source_definition_id,
                source_slice_version="v1",
                field_name="status_code",
                value_counts={"ACTIVE": 2, "BLOCKED": 1},
            )
        )
        db.commit()

    return project_id, source_definition_id, user_id


def test_generate_lookup_snapshot_and_approve_flow() -> None:
    project_id, source_definition_id, user_id = _seed_lookup_context()

    with SessionLocal() as db:
        actor = db.get(User, user_id)
        assert actor is not None
        created_map = create_lookup_value_map(
            db,
            actor=actor,
            project_id=project_id,
            source_definition_id=source_definition_id,
            body=LookupValueMapCreateRequest(
                lookup_name="status_map",
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
            body=LookupSnapshotGenerateRequest(lookup_name="status_map"),
        )
        approved = approve_lookup_snapshot(
            db,
            actor=actor,
            project_id=project_id,
            source_definition_id=source_definition_id,
            lookup_snapshot_id=snapshot.lookup_snapshot_id,
        )
        audit_event = db.scalar(
            select(AuditEvent).where(
                AuditEvent.project_id == project_id,
                AuditEvent.event_type == "lookup_snapshot.approved",
            )
        )

    assert created_map.status == "draft"
    assert snapshot.status == "draft"
    assert snapshot.value_map == {"ACTIVE": "ACTIVE", "BLOCKED": "BLOCKED"}
    assert approved.status == "approved"
    assert approved.approved_by_user_id == user_id
    assert approved.approved_at is not None
    assert audit_event is not None
    assert audit_event.event_payload is not None
    assert audit_event.event_payload["lookup_snapshot_id"] == snapshot.lookup_snapshot_id


def test_generate_lookup_snapshot_rejects_unmapped_source_values() -> None:
    project_id, source_definition_id, user_id = _seed_lookup_context()

    with SessionLocal() as db:
        actor = db.get(User, user_id)
        assert actor is not None
        create_lookup_value_map(
            db,
            actor=actor,
            project_id=project_id,
            source_definition_id=source_definition_id,
            body=LookupValueMapCreateRequest(
                lookup_name="status_map",
                destination_table=[{"id": "ACTIVE", "label": "Active"}],
            ),
        )
        db.add(
            SourceValueSummary(
                source_definition_id=source_definition_id,
                source_slice_version="v2",
                field_name="status_code",
                value_counts={"ACTIVE": 1, "MISSING": 1},
            )
        )
        db.commit()

        with pytest.raises(AuthApiError) as exc_info:
            generate_lookup_snapshot(
                db,
                actor=actor,
                project_id=project_id,
                source_definition_id=source_definition_id,
                body=LookupSnapshotGenerateRequest(lookup_name="status_map"),
            )

    assert exc_info.value.code == "lookup_snapshot_unmapped_values"
