from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..api.deps import AuthApiError
from ..api.deps import get_current_user, get_db
from ..api.schemas import MappingSnapshotResponse
from ..db.models import User
from ..management.access import require_project_access
from ..management.sources import get_source_contract
from ..mapping.snapshots import select_latest_approved_mapping_snapshot
from ..mapping.exceptions import SnapshotNotFoundError

router = APIRouter(prefix="/projects/{project_id}/sources/{source_definition_id}", tags=["mapping-snapshots"])


@router.get("/mapping-snapshot", response_model=MappingSnapshotResponse)
def get_latest_mapping_snapshot(
    project_id: str,
    source_definition_id: str,
    actor: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MappingSnapshotResponse:
    require_project_access(db, user=actor, project_id=project_id)
    source_contract = get_source_contract(db, project_id=project_id, source_definition_id=source_definition_id)

    if not source_contract.destination_object_references:
        raise AuthApiError("mapping_snapshot_not_found", "Source contract has no destination object reference.", 404)

    try:
        mapping_snapshot = select_latest_approved_mapping_snapshot(
            db,
            project_id=project_id,
            destination_object_name=source_contract.destination_object_references[0],
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
            }
            for binding in mapping_snapshot.field_bindings
        ],
        status=mapping_snapshot.status,
        approved_at=mapping_snapshot.approved_at,
        approved_by_user_id=mapping_snapshot.approved_by_user_id,
        created_at=mapping_snapshot.created_at,
    )
