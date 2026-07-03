from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..api.deps import AuthApiError
from ..api.schemas import (
    ChangeRequestDetail,
    ChangeRequestPayload,
    ChangeRequestResolveResponse,
    ChangeRequestSummary,
)
from ..db.models import ChangeRequest, LookupSnapshot, LookupValueMap, RunRecord, User, new_id
from ..mapping.constants import LOOKUP_DELTA_CHANGE_REQUEST_TYPE
from ..management.access import require_project_access
from ..management.platform import record_management_audit
from ..roles import PROJECT_STAKEHOLDER_ROLE

_SNAPSHOT_VERSION_RE = re.compile(r"^v(?P<number>\d+)$")


def list_change_requests(db: Session, *, project_id: str) -> list[ChangeRequestSummary]:
    rows = db.scalars(
        select(ChangeRequest)
        .where(ChangeRequest.project_id == project_id, ChangeRequest.status == "open")
        .order_by(ChangeRequest.created_at.desc(), ChangeRequest.change_request_id.desc())
    ).all()
    return [_summary(cr) for cr in rows]


def get_change_request(db: Session, *, project_id: str, change_request_id: str) -> ChangeRequestDetail:
    cr = _get_cr(db, project_id=project_id, change_request_id=change_request_id)
    return _detail(cr)


def resolve_change_request(
    db: Session,
    *,
    actor: User,
    project_id: str,
    change_request_id: str,
    accepted_value: str,
) -> ChangeRequestResolveResponse:
    if actor.role != PROJECT_STAKEHOLDER_ROLE:
        raise AuthApiError("forbidden", "Only project stakeholders can resolve change requests.", 403)
    require_project_access(db, user=actor, project_id=project_id)

    cr = _get_cr(db, project_id=project_id, change_request_id=change_request_id)
    if cr.status != "open":
        raise AuthApiError("cr_not_open", "This change request is already closed.", 409)
    if cr.change_request_type != LOOKUP_DELTA_CHANGE_REQUEST_TYPE:
        raise AuthApiError("cr_wrong_type", "This change request is not a lookup delta CR.", 409)

    payload: dict[str, Any] = cr.payload or {}
    run_id = str(payload.get("run_id") or "")
    lookup_name = str(payload.get("lookup_name") or "")
    unmapped_value = str(payload.get("unmapped_value") or "")
    if not run_id or not lookup_name or not unmapped_value:
        raise AuthApiError("change_request_invalid", "Change request payload is invalid.", 422)

    run = db.get(RunRecord, run_id)
    if run is None or run.project_id != project_id:
        raise AuthApiError("run_not_found", "Run record not found.", 404)

    source_definition_id = run.source_definition_reference
    if not source_definition_id:
        raise AuthApiError("source_not_found", "Run has no source definition reference.", 404)

    lookup_value_map = db.scalar(
        select(LookupValueMap)
        .where(
            LookupValueMap.source_definition_id == source_definition_id,
            LookupValueMap.lookup_name == lookup_name,
        )
        .order_by(LookupValueMap.created_at.desc(), LookupValueMap.lookup_value_map_id.desc())
    )
    if lookup_value_map is None:
        raise AuthApiError("lookup_map_not_found", "Lookup value map not found for this lookup.", 404)

    new_source_value_map = dict(lookup_value_map.source_value_map)
    new_source_value_map[unmapped_value] = accepted_value.strip()
    lookup_value_map.source_value_map = new_source_value_map

    new_version = _next_snapshot_version(db, project_id=project_id, lookup_name=lookup_name)
    snapshot = LookupSnapshot(
        lookup_snapshot_id=new_id(),
        project_id=project_id,
        lookup_name=lookup_name,
        lookup_snapshot_version=new_version,
        value_map=dict(new_source_value_map),
        status="approved",
        approved_at=datetime.now(UTC),
        approved_by_user_id=actor.user_id,
    )
    db.add(snapshot)

    run.status = "queued"
    run.pause_metadata = None

    now = datetime.now(UTC)
    cr.status = "resolved"
    cr.closed_at = now

    record_management_audit(
        db,
        project_id=project_id,
        actor_user_id=actor.user_id,
        event_type="change_request.resolved",
        payload={
            "change_request_id": change_request_id,
            "lookup_name": lookup_name,
            "unmapped_value": unmapped_value,
            "accepted_value": accepted_value.strip(),
            "run_id": run_id,
            "lookup_snapshot_version": new_version,
        },
    )
    db.commit()

    return ChangeRequestResolveResponse(change_request_id=cr.change_request_id, status="resolved")


def _get_cr(db: Session, *, project_id: str, change_request_id: str) -> ChangeRequest:
    cr = db.get(ChangeRequest, change_request_id)
    if cr is None or cr.project_id != project_id:
        raise AuthApiError("change_request_not_found", "Change request not found.", 404)
    return cr


def _next_snapshot_version(db: Session, *, project_id: str, lookup_name: str) -> str:
    versions = db.scalars(
        select(LookupSnapshot.lookup_snapshot_version).where(
            LookupSnapshot.project_id == project_id,
            LookupSnapshot.lookup_name == lookup_name,
        )
    ).all()
    highest = 0
    for version in versions:
        match = _SNAPSHOT_VERSION_RE.match(version)
        if match:
            highest = max(highest, int(match.group("number")))
    return f"v{highest + 1}"


def _summary(cr: ChangeRequest) -> ChangeRequestSummary:
    return ChangeRequestSummary(
        change_request_id=cr.change_request_id,
        project_id=cr.project_id,
        change_request_type=cr.change_request_type,
        status=cr.status,
        title=cr.title,
        created_at=cr.created_at,
    )


def _detail(cr: ChangeRequest) -> ChangeRequestDetail:
    raw_payload: dict[str, Any] | None = cr.payload
    parsed_payload: ChangeRequestPayload | None = None
    if raw_payload and cr.change_request_type == LOOKUP_DELTA_CHANGE_REQUEST_TYPE:
        parsed_payload = ChangeRequestPayload(
            run_id=str(raw_payload.get("run_id", "")),
            lookup_name=str(raw_payload.get("lookup_name", "")),
            unmapped_value=str(raw_payload.get("unmapped_value", "")),
            destination_object_name=str(raw_payload.get("destination_object_name", "")),
        )
    return ChangeRequestDetail(
        change_request_id=cr.change_request_id,
        project_id=cr.project_id,
        change_request_type=cr.change_request_type,
        status=cr.status,
        title=cr.title,
        payload=parsed_payload,
        created_at=cr.created_at,
        updated_at=cr.updated_at,
    )
