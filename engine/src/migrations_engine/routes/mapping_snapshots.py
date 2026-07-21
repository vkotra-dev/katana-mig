from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..api.deps import AuthApiError
from ..api.deps import get_current_user, get_db
from ..api.schemas import MappingSnapshotResponse
from ..db.models import User
from ..management.access import require_project_access
from ..management.feeds import get_source_contract
from ..mapping.snapshots import select_latest_approved_mapping_snapshot, select_all_approved_mapping_snapshots, select_all_feed_mapping_snapshots
from ..mapping.exceptions import SnapshotNotFoundError
from ..mapping.review_repository import derive_destination_fields

router = APIRouter(prefix="/projects/{project_id}/sources/{source_definition_id}", tags=["mapping-snapshots"])


@router.get("/mapping-snapshot", response_model=MappingSnapshotResponse)
def get_latest_mapping_snapshot(
    project_id: str,
    source_definition_id: str,
    destination_object_name: str | None = None,
    actor: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MappingSnapshotResponse:
    require_project_access(db, user=actor, project_id=project_id)
    source_contract = get_source_contract(db, project_id=project_id, source_definition_id=source_definition_id)

    if not source_contract.destination_object_references:
        raise AuthApiError("mapping_snapshot_not_found", "Source contract has no destination object reference.", 404)

    target_table = destination_object_name
    if not target_table:
        target_table = source_contract.destination_object_references[0]

    try:
        mapping_snapshot = select_latest_approved_mapping_snapshot(
            db,
            project_id=project_id,
            destination_object_name=target_table,
            source_definition_id=source_definition_id,
        )
    except SnapshotNotFoundError as exc:
        raise AuthApiError("mapping_snapshot_not_found", str(exc), 404) from exc
    return MappingSnapshotResponse(
        mapping_snapshot_id=mapping_snapshot.mapping_snapshot_id,
        project_id=mapping_snapshot.project_id,
        destination_object_name=mapping_snapshot.destination_object_name,
        mapping_snapshot_version=mapping_snapshot.mapping_snapshot_version,
        field_bindings=[
            {
                "source_field": str(binding.get("source_field", "")),
                "destination_field": str(binding.get("destination_field", "")),
                "lookup_name": binding.get("lookup_name"),
                "binding_type": binding.get("binding_type"),
                "reference_table_name": binding.get("reference_table_name"),
            }
            for binding in mapping_snapshot.field_bindings
        ],
        status=mapping_snapshot.status,
        approved_at=mapping_snapshot.approved_at,
        approved_by_user_id=mapping_snapshot.approved_by_user_id,
        created_at=mapping_snapshot.created_at,
        destination_fields=derive_destination_fields(db, mapping_snapshot.project_id, mapping_snapshot.destination_object_name) or (mapping_snapshot.destination_fields or []),
    )


@router.get("/mapping-snapshots", response_model=list[MappingSnapshotResponse])
def list_approved_mapping_snapshots(
    project_id: str,
    source_definition_id: str,
    any_status: bool = False,
    actor: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[MappingSnapshotResponse]:
    require_project_access(db, user=actor, project_id=project_id)
    if any_status:
        snapshots = select_all_feed_mapping_snapshots(
            db,
            project_id=project_id,
            source_definition_id=source_definition_id,
        )
    else:
        snapshots = select_all_approved_mapping_snapshots(
            db,
            project_id=project_id,
            source_definition_id=source_definition_id,
        )
    return [
        MappingSnapshotResponse(
            mapping_snapshot_id=s.mapping_snapshot_id,
            project_id=s.project_id,
            destination_object_name=s.destination_object_name,
            mapping_snapshot_version=s.mapping_snapshot_version,
            field_bindings=[
                {
                    "source_field": str(binding.get("source_field", "")),
                    "destination_field": str(binding.get("destination_field", "")),
                    "lookup_name": binding.get("lookup_name"),
                    "binding_type": binding.get("binding_type"),
                    "reference_table_name": binding.get("reference_table_name"),
                }
                for binding in s.field_bindings
            ],
            status=s.status,
            approved_at=s.approved_at,
            approved_by_user_id=s.approved_by_user_id,
            created_at=s.created_at,
            destination_fields=derive_destination_fields(db, s.project_id, s.destination_object_name) or (s.destination_fields or []),
        )
        for s in snapshots
    ]
