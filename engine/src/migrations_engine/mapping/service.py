from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from ..db.models import MappingArtifact, RunRecord, new_id
from .constants import MAPPING_STAGE
from .delta import create_lookup_delta_change_request
from .exceptions import LookupDeltaCRError, UnmappedLookupValueError
from .lookup import MappedRow, apply_lookup_value
from .snapshots import (
    parse_primary_field_binding,
    select_latest_approved_lookup_snapshot,
    select_latest_approved_mapping_snapshot,
)


@dataclass(frozen=True)
class MappingRunResult:
    run_id: str
    mapping_snapshot_version: str
    lookup_snapshot_version: str
    mapping_artifact_id: str
    mapped_rows: tuple[MappedRow, ...]


def execute_mapping_run(
    db: Session,
    *,
    project_id: str,
    destination_object_name: str,
    source_values: list[str],
    actor_user_id: str | None = None,
) -> MappingRunResult:
    mapping_snapshot = select_latest_approved_mapping_snapshot(
        db,
        project_id=project_id,
        destination_object_name=destination_object_name,
    )
    binding = parse_primary_field_binding(mapping_snapshot)
    lookup_snapshot = select_latest_approved_lookup_snapshot(
        db,
        project_id=project_id,
        lookup_name=binding.lookup_name,
    )

    run = RunRecord(
        run_id=new_id(),
        project_id=project_id,
        destination_object_name=destination_object_name,
        mapping_snapshot_version=mapping_snapshot.mapping_snapshot_version,
        lookup_snapshot_version=lookup_snapshot.lookup_snapshot_version,
        status="running",
        current_stage=MAPPING_STAGE,
        start_metadata={
            "pinned_at": datetime.now(UTC).isoformat(),
            "mapping_snapshot_version": mapping_snapshot.mapping_snapshot_version,
            "lookup_snapshot_version": lookup_snapshot.lookup_snapshot_version,
        },
    )
    db.add(run)
    db.flush()

    mapped_rows: list[MappedRow] = []
    for source_value in source_values:
        try:
            destination_value = apply_lookup_value(lookup_snapshot, source_value)
        except UnmappedLookupValueError as exc:
            change_request = create_lookup_delta_change_request(
                db,
                project_id=project_id,
                run_id=run.run_id,
                lookup_name=binding.lookup_name,
                unmapped_value=exc.unmapped_value,
                lookup_snapshot_version=lookup_snapshot.lookup_snapshot_version,
                mapping_snapshot_version=mapping_snapshot.mapping_snapshot_version,
                destination_object_name=destination_object_name,
                created_by_user_id=actor_user_id,
            )
            run.status = "failed"
            run.current_stage = MAPPING_STAGE
            run.completion_metadata = {
                "failure_reason": "unmapped_lookup_value",
                "unmapped_value": exc.unmapped_value,
                "lookup_name": binding.lookup_name,
                "lookup_delta_change_request_id": change_request.change_request_id,
                "mapping_snapshot_version": mapping_snapshot.mapping_snapshot_version,
                "lookup_snapshot_version": lookup_snapshot.lookup_snapshot_version,
            }
            db.commit()
            raise LookupDeltaCRError(
                change_request_id=change_request.change_request_id,
                unmapped_value=exc.unmapped_value,
                lookup_name=binding.lookup_name,
                run_id=run.run_id,
            ) from exc

        mapped_rows.append(
            MappedRow(
                source_field=binding.source_field,
                source_value=source_value,
                destination_field=binding.destination_field,
                destination_value=destination_value,
            )
        )

    serialized_rows = [
        {
            "source_field": row.source_field,
            "source_value": row.source_value,
            "destination_field": row.destination_field,
            "destination_value": row.destination_value,
        }
        for row in mapped_rows
    ]
    artifact = MappingArtifact(
        mapping_artifact_id=new_id(),
        run_id=run.run_id,
        project_id=project_id,
        destination_object_name=destination_object_name,
        mapping_snapshot_version=mapping_snapshot.mapping_snapshot_version,
        lookup_snapshot_version=lookup_snapshot.lookup_snapshot_version,
        mapped_rows=serialized_rows,
    )
    db.add(artifact)
    run.status = "completed"
    run.completion_metadata = {
        "mapping_artifact_id": artifact.mapping_artifact_id,
        "mapping_snapshot_version": mapping_snapshot.mapping_snapshot_version,
        "lookup_snapshot_version": lookup_snapshot.lookup_snapshot_version,
        "mapped_row_count": len(mapped_rows),
    }
    db.commit()
    db.refresh(run)
    db.refresh(artifact)

    return MappingRunResult(
        run_id=run.run_id,
        mapping_snapshot_version=mapping_snapshot.mapping_snapshot_version,
        lookup_snapshot_version=lookup_snapshot.lookup_snapshot_version,
        mapping_artifact_id=artifact.mapping_artifact_id,
        mapped_rows=tuple(mapped_rows),
    )
