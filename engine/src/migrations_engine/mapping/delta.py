from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.orm import Session

from ..db.models import ChangeRequest, new_id
from .constants import LOOKUP_DELTA_CHANGE_REQUEST_TYPE


def create_lookup_delta_change_request(
    db: Session,
    *,
    project_id: str,
    run_id: str,
    lookup_name: str,
    unmapped_value: str,
    lookup_snapshot_version: str,
    mapping_snapshot_version: str,
    destination_object_name: str,
    created_by_user_id: str | None = None,
) -> ChangeRequest:
    change_request = ChangeRequest(
        change_request_id=new_id(),
        project_id=project_id,
        created_by_user_id=created_by_user_id,
        change_request_type=LOOKUP_DELTA_CHANGE_REQUEST_TYPE,
        status="open",
        title=f"Unmapped lookup value for {lookup_name}",
        description=(
            f"Run {run_id} encountered unmapped lookup value {unmapped_value!r} "
            f"while applying lookup snapshot {lookup_snapshot_version}."
        ),
        payload={
            "run_id": run_id,
            "lookup_name": lookup_name,
            "unmapped_value": unmapped_value,
            "lookup_snapshot_version": lookup_snapshot_version,
            "mapping_snapshot_version": mapping_snapshot_version,
            "destination_object_name": destination_object_name,
            "raised_at": datetime.now(UTC).isoformat(),
        },
    )
    db.add(change_request)
    db.flush()
    return change_request
