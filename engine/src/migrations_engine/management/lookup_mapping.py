from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..api.deps import AuthApiError
from ..api.schemas import (
    LookupSnapshotGenerateRequest,
    LookupSnapshotResponse,
    LookupValueMapCreateRequest,
    LookupValueMapResponse,
)
from ..db.models import LookupSnapshot, LookupValueMap, SourceDefinition, User, new_id
from .platform import record_management_audit
from .source_analysis import list_source_value_summaries

_SNAPSHOT_VERSION_RE = re.compile(r"^v(?P<number>\d+)$")


def create_lookup_value_map(
    db: Session,
    *,
    actor: User,
    project_id: str,
    source_definition_id: str,
    body: LookupValueMapCreateRequest,
) -> LookupValueMapResponse:
    source_definition = _get_source_definition(db, project_id=project_id, source_definition_id=source_definition_id)
    lookup_name = body.lookup_name.strip()
    destination_table = [_normalize_destination_row(row) for row in body.destination_table]

    draft = db.scalar(
        select(LookupValueMap)
        .where(
            LookupValueMap.source_definition_id == source_definition.source_definition_id,
            LookupValueMap.lookup_name == lookup_name,
            LookupValueMap.status == "draft",
        )
        .order_by(LookupValueMap.created_at.desc(), LookupValueMap.lookup_value_map_id.desc())
    )
    if draft is None:
        draft = LookupValueMap(
            lookup_value_map_id=new_id(),
            source_definition_id=source_definition.source_definition_id,
            lookup_name=lookup_name,
            destination_table=destination_table,
            status="draft",
        )
        db.add(draft)
    else:
        draft.destination_table = destination_table

    record_management_audit(
        db,
        project_id=project_id,
        actor_user_id=actor.user_id,
        event_type="lookup_value_map_saved",
        payload={
            "source_definition_id": source_definition_id,
            "lookup_name": lookup_name,
            "destination_row_count": len(destination_table),
        },
    )
    db.commit()
    db.refresh(draft)
    return _lookup_value_map_response(draft)


def list_lookup_value_maps(
    db: Session,
    *,
    project_id: str,
    source_definition_id: str,
) -> list[LookupValueMapResponse]:
    _get_source_definition(db, project_id=project_id, source_definition_id=source_definition_id)
    rows = db.scalars(
        select(LookupValueMap)
        .where(LookupValueMap.source_definition_id == source_definition_id)
        .order_by(LookupValueMap.created_at.asc(), LookupValueMap.lookup_value_map_id.asc())
    ).all()
    return [_lookup_value_map_response(row) for row in rows]


def generate_lookup_snapshot(
    db: Session,
    *,
    actor: User,
    project_id: str,
    source_definition_id: str,
    body: LookupSnapshotGenerateRequest,
) -> LookupSnapshotResponse:
    source_definition = _get_source_definition(db, project_id=project_id, source_definition_id=source_definition_id)
    lookup_name = body.lookup_name.strip()
    lookup_map = _latest_lookup_value_map(
        db,
        source_definition_id=source_definition.source_definition_id,
        lookup_name=lookup_name,
    )

    source_values = list_source_value_summaries(
        db,
        project_id=project_id,
        source_definition_id=source_definition.source_definition_id,
        field_name=lookup_name,
    )
    if not source_values:
        raise AuthApiError("source_analysis_not_found", "Source analysis has not been run for this lookup field.", 404)

    destination_ids = {
        _extract_destination_id(row)
        for row in lookup_map.destination_table
        if _extract_destination_id(row)
    }
    value_map = {key: value.strip() for key, value in body.value_map.items() if value.strip()}
    source_value_keys = sorted({key for summary in source_values for key in summary.value_counts.keys()})

    unmapped_values = [value for value in source_value_keys if value not in value_map]
    invalid_destination_values = sorted(
        {
            destination_id
            for destination_id in value_map.values()
            if destination_id not in destination_ids
        }
    )
    if unmapped_values or invalid_destination_values:
        parts: list[str] = []
        if unmapped_values:
            parts.append(f"unmapped values: {', '.join(unmapped_values)}")
        if invalid_destination_values:
            parts.append(f"invalid destination ids: {', '.join(invalid_destination_values)}")
        message = "Lookup values must be mapped before a snapshot can be generated."
        if parts:
            message = f"{message} {'; '.join(parts)}"
        raise AuthApiError("lookup_values_unmapped", message, 409)

    snapshot = LookupSnapshot(
        lookup_snapshot_id=new_id(),
        project_id=project_id,
        lookup_name=lookup_name,
        lookup_snapshot_version=_next_snapshot_version(
            db,
            project_id=project_id,
            lookup_name=lookup_name,
        ),
        value_map=value_map,
        status="draft",
        approved_at=None,
        approved_by_user_id=None,
    )
    db.add(snapshot)
    record_management_audit(
        db,
        project_id=project_id,
        actor_user_id=actor.user_id,
        event_type="lookup_snapshot.generated",
        payload={
            "source_definition_id": source_definition_id,
            "lookup_name": lookup_name,
            "lookup_snapshot_id": snapshot.lookup_snapshot_id,
            "lookup_snapshot_version": snapshot.lookup_snapshot_version,
            "value_count": len(value_map),
        },
    )
    db.commit()
    db.refresh(snapshot)
    return _lookup_snapshot_response(snapshot, source_definition_id=source_definition_id)


def approve_lookup_snapshot(
    db: Session,
    *,
    actor: User,
    project_id: str,
    source_definition_id: str,
    lookup_snapshot_id: str,
) -> LookupSnapshotResponse:
    _get_source_definition(db, project_id=project_id, source_definition_id=source_definition_id)
    snapshot = db.get(LookupSnapshot, lookup_snapshot_id)
    if snapshot is None or snapshot.project_id != project_id or snapshot.lookup_name is None:
        raise AuthApiError("lookup_snapshot_not_found", "Lookup snapshot not found.", 404)
    if snapshot.status == "approved":
        return _lookup_snapshot_response(snapshot, source_definition_id=source_definition_id)

    snapshot.status = "approved"
    snapshot.approved_at = datetime.now(UTC)
    snapshot.approved_by_user_id = actor.user_id
    record_management_audit(
        db,
        project_id=project_id,
        actor_user_id=actor.user_id,
        event_type="lookup_snapshot.approved",
        payload={
            "source_definition_id": source_definition_id,
            "lookup_name": snapshot.lookup_name,
            "lookup_snapshot_id": snapshot.lookup_snapshot_id,
            "lookup_snapshot_version": snapshot.lookup_snapshot_version,
        },
    )
    db.commit()
    db.refresh(snapshot)
    return _lookup_snapshot_response(snapshot, source_definition_id=source_definition_id)


def _get_source_definition(db: Session, *, project_id: str, source_definition_id: str) -> SourceDefinition:
    source_definition = db.get(SourceDefinition, source_definition_id)
    if source_definition is None or source_definition.project_id != project_id:
        raise AuthApiError("source_not_found", "Source contract not found.", 404)
    return source_definition


def _latest_lookup_value_map(
    db: Session,
    *,
    source_definition_id: str,
    lookup_name: str,
) -> LookupValueMap:
    lookup_map = db.scalar(
        select(LookupValueMap)
        .where(
            LookupValueMap.source_definition_id == source_definition_id,
            LookupValueMap.lookup_name == lookup_name,
        )
        .order_by(LookupValueMap.created_at.desc(), LookupValueMap.lookup_value_map_id.desc())
    )
    if lookup_map is None:
        raise AuthApiError("lookup_map_not_found", "Lookup draft has not been created.", 404)
    return lookup_map


def _next_snapshot_version(
    db: Session,
    *,
    project_id: str,
    lookup_name: str,
) -> str:
    versions = db.scalars(
        select(LookupSnapshot.lookup_snapshot_version)
        .where(
            LookupSnapshot.project_id == project_id,
            LookupSnapshot.lookup_name == lookup_name,
        )
        .order_by(LookupSnapshot.created_at.asc(), LookupSnapshot.lookup_snapshot_id.asc())
    ).all()
    highest = 0
    for version in versions:
        match = _SNAPSHOT_VERSION_RE.match(version)
        if match is None:
            continue
        highest = max(highest, int(match.group("number")))
    return f"v{highest + 1}"


def _normalize_destination_row(row: dict[str, Any]) -> dict[str, Any]:
    return dict(row)


def _extract_destination_id(row: dict[str, Any]) -> str:
    for key in ("id", "value", "code", "key", "destination_id"):
        value = row.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _lookup_value_map_response(row: LookupValueMap) -> LookupValueMapResponse:
    return LookupValueMapResponse(
        lookup_value_map_id=row.lookup_value_map_id,
        source_definition_id=row.source_definition_id,
        lookup_name=row.lookup_name,
        destination_table=row.destination_table,
        status=row.status,
        created_at=row.created_at,
    )


def _lookup_snapshot_response(row: LookupSnapshot, *, source_definition_id: str) -> LookupSnapshotResponse:
    return LookupSnapshotResponse(
        lookup_snapshot_id=row.lookup_snapshot_id,
        project_id=row.project_id,
        source_definition_id=source_definition_id,
        lookup_name=row.lookup_name,
        lookup_snapshot_version=row.lookup_snapshot_version,
        value_map=row.value_map,
        status=row.status,
        approved_at=row.approved_at,
        approved_by_user_id=row.approved_by_user_id,
        created_at=row.created_at,
    )
