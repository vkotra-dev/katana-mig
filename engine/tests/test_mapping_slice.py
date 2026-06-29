from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select

from migrations_engine.db.models import (
    ChangeRequest,
    LookupSnapshot,
    MappingArtifact,
    ProjectDefinition,
    ProjectRegistry,
    RunRecord,
)
from migrations_engine.db.session import SessionLocal
from migrations_engine.mapping import (
    FieldBinding,
    LookupDeltaCRError,
    SnapshotImmutableError,
    create_approved_lookup_snapshot,
    create_approved_mapping_snapshot,
    execute_mapping_run,
    guard_snapshot_immutable,
)
from migrations_engine.mapping.constants import LOOKUP_DELTA_CHANGE_REQUEST_TYPE


@pytest.fixture
def mapping_project_id() -> str:
    project_id = str(uuid.uuid4())
    definition_id = str(uuid.uuid4())
    with SessionLocal() as db:
        db.add(
            ProjectDefinition(
                definition_id=definition_id,
                project_id=project_id,
                name="Mapping Project",
                status="active",
            )
        )
        db.add(
            ProjectRegistry(
                project_id=project_id,
                name="Mapping Project",
                definition_id=definition_id,
                status="active",
            )
        )
        db.commit()
    yield project_id


def _seed_snapshots(
    db,
    *,
    project_id: str,
    lookup_values: dict[str, str],
) -> None:
    create_approved_lookup_snapshot(
        db,
        project_id=project_id,
        lookup_name="status_map",
        lookup_snapshot_version="v1",
        value_map=lookup_values,
    )
    create_approved_mapping_snapshot(
        db,
        project_id=project_id,
        destination_object_name="Account",
        mapping_snapshot_version="v1",
        field_bindings=[
            FieldBinding(
                source_field="src_status",
                destination_field="status",
                lookup_name="status_map",
            )
        ],
    )
    db.commit()


def test_approved_mapping_path_produces_artifact(mapping_project_id: str) -> None:
    with SessionLocal() as db:
        _seed_snapshots(db, project_id=mapping_project_id, lookup_values={"A": "ACTIVE", "B": "INACTIVE"})
        result = execute_mapping_run(
            db,
            project_id=mapping_project_id,
            destination_object_name="Account",
            source_values=["A", "B"],
        )

        artifact = db.get(MappingArtifact, result.mapping_artifact_id)
        run = db.get(RunRecord, result.run_id)

    assert artifact is not None
    assert run is not None
    assert run.status == "completed"
    assert run.mapping_snapshot_version == "v1"
    assert run.lookup_snapshot_version == "v1"
    assert len(result.mapped_rows) == 2
    assert result.mapped_rows[0].destination_value == "ACTIVE"
    assert artifact.mapped_rows == [
        {
            "source_field": "src_status",
            "source_value": "A",
            "destination_field": "status",
            "destination_value": "ACTIVE",
        },
        {
            "source_field": "src_status",
            "source_value": "B",
            "destination_field": "status",
            "destination_value": "INACTIVE",
        },
    ]


def test_unmapped_value_raises_lookup_delta_cr(mapping_project_id: str) -> None:
    with SessionLocal() as db:
        _seed_snapshots(db, project_id=mapping_project_id, lookup_values={"A": "ACTIVE"})
        with pytest.raises(LookupDeltaCRError) as exc_info:
            execute_mapping_run(
                db,
                project_id=mapping_project_id,
                destination_object_name="Account",
                source_values=["A", "Z"],
            )
        change_request = db.get(ChangeRequest, exc_info.value.change_request_id)
        run = db.get(RunRecord, exc_info.value.run_id)

    assert exc_info.value.unmapped_value == "Z"
    assert change_request is not None
    assert change_request.change_request_type == LOOKUP_DELTA_CHANGE_REQUEST_TYPE
    assert change_request.status == "open"
    assert change_request.payload is not None
    assert change_request.payload["unmapped_value"] == "Z"
    assert run is not None
    assert run.status == "failed"
    assert run.mapping_snapshot_version == "v1"
    assert run.completion_metadata is not None
    assert run.completion_metadata["lookup_delta_change_request_id"] == change_request.change_request_id


def test_approved_snapshots_are_immutable(mapping_project_id: str) -> None:
    with SessionLocal() as db:
        snapshot = create_approved_lookup_snapshot(
            db,
            project_id=mapping_project_id,
            lookup_name="status_map",
            lookup_snapshot_version="v1",
            value_map={"A": "ACTIVE"},
        )
        db.commit()
        stored = db.scalar(
            select(LookupSnapshot).where(LookupSnapshot.lookup_snapshot_id == snapshot.lookup_snapshot_id)
        )

    assert stored is not None
    with pytest.raises(SnapshotImmutableError):
        guard_snapshot_immutable(snapshot, updates={"value_map": {"B": "NEW"}})
