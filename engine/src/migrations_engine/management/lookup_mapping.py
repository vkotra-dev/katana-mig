from __future__ import annotations

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
from ..db.models import (
    LookupSnapshot,
    LookupValueMap,
    MappingSnapshot,
    ProjectRegistry,
    SourceDefinition,
    SourceValueSummary,
    User,
    new_id,
)
from .platform import record_management_audit


def list_lookup_value_maps(
    db: Session,
    *,
    actor: User,
    project_id: str,
    source_definition_id: str,
) -> list[LookupValueMapResponse]:
    _require_central_team(actor)
    source_definition = _require_source_definition(db, project_id=project_id, source_definition_id=source_definition_id)

    rows = db.scalars(
        select(LookupValueMap)
        .where(LookupValueMap.source_definition_id == source_definition.source_definition_id)
        .order_by(LookupValueMap.created_at.desc())
    ).all()
    return [_lookup_value_map_response(row) for row in rows]


def create_lookup_value_map(
    db: Session,
    *,
    actor: User,
    project_id: str,
    source_definition_id: str,
    body: LookupValueMapCreateRequest,
) -> LookupValueMapResponse:
    _require_central_team(actor)
    source_definition = _require_source_definition(db, project_id=project_id, source_definition_id=source_definition_id)

    lookup_name = body.lookup_name.strip()
    if not lookup_name:
        raise AuthApiError("validation_error", "Lookup name is required.", 422)
    existing = db.scalar(
        select(LookupValueMap).where(
            LookupValueMap.source_definition_id == source_definition.source_definition_id,
            LookupValueMap.lookup_name == lookup_name,
            LookupValueMap.status == "draft",
        )
    )
    if existing is not None:
        raise AuthApiError(
            "lookup_value_map_exists",
            "A draft lookup table already exists for this lookup.",
            409,
        )

    lookup_value_map = LookupValueMap(
        lookup_value_map_id=new_id(),
        source_definition_id=source_definition.source_definition_id,
        lookup_name=lookup_name,
        destination_table=body.destination_table,
        status="draft",
    )
    db.add(lookup_value_map)
    db.commit()
    db.refresh(lookup_value_map)
    return _lookup_value_map_response(lookup_value_map)


def generate_lookup_snapshot(
    db: Session,
    *,
    actor: User,
    project_id: str,
    source_definition_id: str,
    body: LookupSnapshotGenerateRequest,
) -> LookupSnapshotResponse:
    _require_central_team(actor)
    source_definition = _require_source_definition(db, project_id=project_id, source_definition_id=source_definition_id)

    lookup_name = body.lookup_name.strip()
    lookup_value_map = _require_draft_lookup_value_map(
        db,
        source_definition_id=source_definition.source_definition_id,
        lookup_name=lookup_name,
    )
    source_fields = _lookup_source_fields(db, project_id=project_id, lookup_name=lookup_name)
    if not source_fields:
        raise AuthApiError(
            "lookup_name_not_bound",
            "No approved mapping snapshot binds this lookup name.",
            409,
        )

    source_values = _load_source_values(
        db,
        source_definition_id=source_definition.source_definition_id,
        source_fields=source_fields,
    )
    destination_ids = _destination_ids(lookup_value_map.destination_table)

    value_map: dict[str, str] = {}
    unmapped_values: list[str] = []
    for source_value in source_values:
        destination_row = destination_ids.get(source_value)
        if destination_row is None:
            unmapped_values.append(source_value)
            continue
        value_map[source_value] = destination_row

    if unmapped_values:
        raise AuthApiError(
            "lookup_snapshot_unmapped_values",
            f"Unmapped source values: {', '.join(unmapped_values)}",
            409,
        )

    snapshot = LookupSnapshot(
        lookup_snapshot_id=new_id(),
        project_id=project_id,
        lookup_name=lookup_name,
        lookup_snapshot_version=_next_lookup_snapshot_version(
            db=db,
            project_id=project_id,
            lookup_name=lookup_name,
        ),
        value_map=value_map,
        status="draft",
    )
    db.add(snapshot)
    db.commit()
    db.refresh(snapshot)
    return _lookup_snapshot_response(snapshot, source_definition_id=source_definition.source_definition_id)


def approve_lookup_snapshot(
    db: Session,
    *,
    actor: User,
    project_id: str,
    source_definition_id: str,
    lookup_snapshot_id: str,
) -> LookupSnapshotResponse:
    _require_central_team(actor)
    source_definition = _require_source_definition(db, project_id=project_id, source_definition_id=source_definition_id)
    snapshot = db.get(LookupSnapshot, lookup_snapshot_id)
    if snapshot is None or snapshot.project_id != project_id:
        raise AuthApiError("lookup_snapshot_not_found", "Lookup snapshot not found.", 404)
    if snapshot.status != "draft":
        raise AuthApiError("lookup_snapshot_not_draft", "Lookup snapshot is already approved.", 409)

    snapshot.status = "approved"
    snapshot.approved_at = datetime.now(UTC)
    snapshot.approved_by_user_id = actor.user_id
    record_management_audit(
        db,
        project_id=project_id,
        actor_user_id=actor.user_id,
        event_type="lookup_snapshot.approved",
        payload={
            "lookup_snapshot_id": snapshot.lookup_snapshot_id,
            "lookup_name": snapshot.lookup_name,
            "lookup_snapshot_version": snapshot.lookup_snapshot_version,
            "source_definition_id": source_definition.source_definition_id,
        },
    )
    db.commit()
    db.refresh(snapshot)
    return _lookup_snapshot_response(snapshot, source_definition_id=source_definition.source_definition_id)


def _lookup_value_map_response(lookup_value_map: LookupValueMap) -> LookupValueMapResponse:
    return LookupValueMapResponse(
        lookup_value_map_id=lookup_value_map.lookup_value_map_id,
        source_definition_id=lookup_value_map.source_definition_id,
        lookup_name=lookup_value_map.lookup_name,
        destination_table=lookup_value_map.destination_table,
        status=lookup_value_map.status,  # type: ignore[arg-type]
        created_at=lookup_value_map.created_at,
    )


def _lookup_snapshot_response(
    snapshot: LookupSnapshot,
    *,
    source_definition_id: str,
) -> LookupSnapshotResponse:
    return LookupSnapshotResponse(
        lookup_snapshot_id=snapshot.lookup_snapshot_id,
        project_id=snapshot.project_id,
        source_definition_id=source_definition_id,
        lookup_name=snapshot.lookup_name,
        lookup_snapshot_version=snapshot.lookup_snapshot_version,
        value_map=snapshot.value_map,
        status=snapshot.status,  # type: ignore[arg-type]
        approved_at=snapshot.approved_at,
        approved_by_user_id=snapshot.approved_by_user_id,
        created_at=snapshot.created_at,
    )


def _require_central_team(actor: User) -> None:
    if actor.role != "central_team":
        raise AuthApiError("forbidden", "Central team access is required.", 403)


def _require_project(db: Session, *, project_id: str) -> ProjectRegistry:
    project = db.get(ProjectRegistry, project_id)
    if project is None or project.soft_deleted_at is not None:
        raise AuthApiError("project_not_found", "Project not found.", 404)
    return project


def _require_source_definition(
    db: Session,
    *,
    project_id: str,
    source_definition_id: str,
) -> SourceDefinition:
    _require_project(db, project_id=project_id)
    source_definition = db.get(SourceDefinition, source_definition_id)
    if source_definition is None or source_definition.project_id != project_id:
        raise AuthApiError("source_definition_not_found", "Source definition not found.", 404)
    return source_definition


def _require_draft_lookup_value_map(
    db: Session,
    *,
    source_definition_id: str,
    lookup_name: str,
) -> LookupValueMap:
    lookup_value_map = db.scalar(
        select(LookupValueMap).where(
            LookupValueMap.source_definition_id == source_definition_id,
            LookupValueMap.lookup_name == lookup_name,
            LookupValueMap.status == "draft",
        )
    )
    if lookup_value_map is None:
        raise AuthApiError(
            "lookup_value_map_not_found",
            "Draft lookup table not found for this lookup.",
            404,
        )
    return lookup_value_map


def _lookup_source_fields(db: Session, *, project_id: str, lookup_name: str) -> list[str]:
    snapshots = db.scalars(
        select(MappingSnapshot)
        .where(
            MappingSnapshot.project_id == project_id,
            MappingSnapshot.status == "approved",
        )
        .order_by(MappingSnapshot.created_at.desc())
    ).all()
    source_fields: list[str] = []
    for snapshot in snapshots:
        for binding in snapshot.field_bindings:
            if str(binding.get("lookup_name")) != lookup_name:
                continue
            source_field = str(binding.get("source_field", "")).strip()
            if source_field and source_field not in source_fields:
                source_fields.append(source_field)
    return source_fields


def _load_source_values(
    db: Session,
    *,
    source_definition_id: str,
    source_fields: list[str],
) -> list[str]:
    source_values: list[str] = []
    for field_name in source_fields:
        summary = db.scalar(
            select(SourceValueSummary)
            .where(
                SourceValueSummary.source_definition_id == source_definition_id,
                SourceValueSummary.field_name == field_name,
            )
            .order_by(SourceValueSummary.created_at.desc())
        )
        if summary is None:
            raise AuthApiError(
                "source_values_not_found",
                f"No source value summary found for field {field_name!r}.",
                404,
            )
        for value in summary.value_counts.keys():
            normalized = str(value)
            if normalized not in source_values:
                source_values.append(normalized)
    return source_values


def _destination_ids(destination_table: list[dict[str, Any]]) -> dict[str, str]:
    ids: dict[str, str] = {}
    for row in destination_table:
        destination_id = str(row.get("id", "")).strip()
        if not destination_id:
            raise AuthApiError(
                "invalid_destination_table",
                "Each destination table row must include an id.",
                422,
            )
        ids[destination_id] = destination_id
    return ids


def _next_lookup_snapshot_version(*, db: Session, project_id: str, lookup_name: str) -> str:
    snapshots = db.scalars(
        select(LookupSnapshot)
        .where(
            LookupSnapshot.project_id == project_id,
            LookupSnapshot.lookup_name == lookup_name,
        )
        .order_by(LookupSnapshot.created_at.desc())
    ).all()
    if not snapshots:
        return "v1"

    max_version = 0
    for snapshot in snapshots:
        version = snapshot.lookup_snapshot_version.strip().lower()
        if not version.startswith("v"):
            continue
        try:
            max_version = max(max_version, int(version[1:]))
        except ValueError:
            continue
    return f"v{max_version + 1}" if max_version else "v1"
