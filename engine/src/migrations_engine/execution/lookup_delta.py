from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.orm import Session

from ..db.models import ChangeRequest, RunRecord, new_id
from ..mapping.constants import LOOKUP_DELTA_CHANGE_REQUEST_TYPE
from ..management.platform import record_management_audit


def open_lookup_delta_change_request(
    db: Session,
    *,
    run: RunRecord,
    lookup_name: str,
    unmapped_value: str,
    mapping_snapshot_version: str | None,
    lookup_snapshot_version: str | None,
    actor_user_id: str | None,
) -> ChangeRequest:
    change_request = ChangeRequest(
        change_request_id=new_id(),
        project_id=run.project_id,
        created_by_user_id=actor_user_id,
        change_request_type=LOOKUP_DELTA_CHANGE_REQUEST_TYPE,
        status="open",
        title=f"Lookup delta for {lookup_name}",
        description=(
            f"Run {run.run_id} encountered unmapped lookup value {unmapped_value!r} "
            f"for lookup {lookup_name!r}."
        ),
        payload={
            "run_id": run.run_id,
            "lookup_name": lookup_name,
            "unmapped_value": unmapped_value,
            "mapping_snapshot_version": mapping_snapshot_version,
            "lookup_snapshot_version": lookup_snapshot_version,
            "destination_object_name": run.destination_object_name,
        },
    )
    db.add(change_request)
    db.flush()
    record_management_audit(
        db,
        project_id=run.project_id,
        actor_user_id=actor_user_id,
        event_type="run_lookup_delta_opened",
        payload={
            "run_id": run.run_id,
            "change_request_id": change_request.change_request_id,
            "lookup_name": lookup_name,
            "unmapped_value": unmapped_value,
        },
    )
    return change_request


def mark_run_paused_for_lookup_delta(
    db: Session,
    *,
    run: RunRecord,
    change_request_id: str,
    last_completed_row: int | None,
) -> None:
    run.status = "awaiting_approval"
    run.pause_metadata = {
        "pause_reason": "lookup_delta",
        "change_request_id": change_request_id,
        "last_completed_row": last_completed_row,
        "paused_at": datetime.now(UTC).isoformat(),
    }
