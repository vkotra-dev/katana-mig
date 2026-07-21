from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import case, or_, select
from sqlalchemy.orm import Session

import re
from ..api.deps import AuthApiError
from ..api.schemas import MappingFieldBindingResponse, MappingReviewResponse
from ..db.models import ProjectDefinition, ProjectRegistry, Feed, LookupSnapshot, MappingSnapshot, new_id
from ..management.source_analysis import get_latest_source_schema_artifact
from .ddl import parse_all_ddl_tables, parse_ddl
from .constants import APPROVED_SNAPSHOT_STATUS
from .exceptions import MappingError, SnapshotImmutableError, SnapshotNotFoundError, SnapshotVersionConflictError


@dataclass(frozen=True)
class FieldBinding:
    source_field: str
    destination_field: str
    lookup_name: str


def create_approved_mapping_snapshot(
    db: Session,
    *,
    project_id: str,
    destination_object_name: str,
    mapping_snapshot_version: str,
    field_bindings: list[FieldBinding],
    approved_by_user_id: str | None = None,
    source_definition_id: str | None = None,
) -> MappingSnapshot:
    existing_snapshot = db.scalar(
        select(MappingSnapshot).where(
            MappingSnapshot.project_id == project_id,
            MappingSnapshot.source_definition_id == source_definition_id,
            MappingSnapshot.destination_object_name == destination_object_name,
            MappingSnapshot.mapping_snapshot_version == mapping_snapshot_version,
        )
    )
    if existing_snapshot is not None:
        raise SnapshotVersionConflictError(
            f"Mapping snapshot version {mapping_snapshot_version!r} already exists for "
            f"{destination_object_name!r} in project {project_id}."
        )
    serialized_bindings = [
        {
            "source_field": binding.source_field,
            "destination_field": binding.destination_field,
            "lookup_name": binding.lookup_name,
        }
        for binding in field_bindings
    ]
    snapshot = MappingSnapshot(
        mapping_snapshot_id=new_id(),
        project_id=project_id,
        source_definition_id=source_definition_id,
        destination_object_name=destination_object_name,
        mapping_snapshot_version=mapping_snapshot_version,
        field_bindings=serialized_bindings,
        status=APPROVED_SNAPSHOT_STATUS,
        approved_at=datetime.now(UTC),
        approved_by_user_id=approved_by_user_id,
    )
    db.add(snapshot)
    db.flush()
    return snapshot


def create_approved_lookup_snapshot(
    db: Session,
    *,
    project_id: str,
    lookup_name: str,
    lookup_snapshot_version: str,
    value_map: dict[str, str],
    approved_by_user_id: str | None = None,
) -> LookupSnapshot:
    snapshot = LookupSnapshot(
        lookup_snapshot_id=new_id(),
        project_id=project_id,
        lookup_name=lookup_name,
        lookup_snapshot_version=lookup_snapshot_version,
        value_map=value_map,
        status=APPROVED_SNAPSHOT_STATUS,
        approved_at=datetime.now(UTC),
        approved_by_user_id=approved_by_user_id,
    )
    db.add(snapshot)
    db.flush()
    return snapshot


def select_latest_approved_mapping_snapshot(
    db: Session,
    *,
    project_id: str,
    destination_object_name: str,
    source_definition_id: str | None = None,
) -> MappingSnapshot:
    filters = [
        MappingSnapshot.project_id == project_id,
        MappingSnapshot.destination_object_name == destination_object_name,
        MappingSnapshot.status == APPROVED_SNAPSHOT_STATUS,
    ]
    if source_definition_id is not None:
        filters.append(
            or_(
                MappingSnapshot.source_definition_id == source_definition_id,
                MappingSnapshot.source_definition_id.is_(None)
            )
        )

    order_by_clauses = []
    if source_definition_id is not None:
        order_by_clauses.append(
            case(
                (MappingSnapshot.source_definition_id == source_definition_id, 0),
                else_=1
            ).asc()
        )
    order_by_clauses.extend([
        MappingSnapshot.created_at.desc(),
        MappingSnapshot.mapping_snapshot_id.desc()
    ])

    snapshots = db.scalars(
        select(MappingSnapshot)
        .where(*filters)
        .order_by(*order_by_clauses)
    ).all()
    if not snapshots:
        raise SnapshotNotFoundError(
            f"No approved mapping snapshot for {destination_object_name!r} in project {project_id}."
        )
    return snapshots[0]


def select_all_approved_mapping_snapshots(
    db: Session,
    *,
    project_id: str,
    source_definition_id: str,
) -> list[MappingSnapshot]:
    snapshots = db.scalars(
        select(MappingSnapshot)
        .where(
            MappingSnapshot.project_id == project_id,
            MappingSnapshot.source_definition_id == source_definition_id,
            MappingSnapshot.status == APPROVED_SNAPSHOT_STATUS,
        )
        .order_by(
            MappingSnapshot.destination_object_name.asc(),
            MappingSnapshot.created_at.desc(),
        )
    ).all()
    # Dedup in Python:
    seen = set()
    latest_snapshots = []
    for s in snapshots:
        if s.destination_object_name not in seen:
            seen.add(s.destination_object_name)
            latest_snapshots.append(s)
    return latest_snapshots


def select_all_feed_mapping_snapshots(
    db: Session,
    *,
    project_id: str,
    source_definition_id: str,
) -> list[MappingSnapshot]:
    """Returns latest snapshot per destination table, any status (draft or approved)."""
    snapshots = db.scalars(
        select(MappingSnapshot)
        .where(
            MappingSnapshot.project_id == project_id,
            MappingSnapshot.source_definition_id == source_definition_id,
        )
        .order_by(
            MappingSnapshot.destination_object_name.asc(),
            MappingSnapshot.created_at.desc(),
        )
    ).all()
    seen: set[str] = set()
    latest: list[MappingSnapshot] = []
    for s in snapshots:
        if s.destination_object_name not in seen:
            seen.add(s.destination_object_name)
            latest.append(s)
    return latest


def select_latest_approved_lookup_snapshot(
    db: Session,
    *,
    project_id: str,
    lookup_name: str,
) -> LookupSnapshot:
    snapshots = db.scalars(
        select(LookupSnapshot)
        .where(
            LookupSnapshot.project_id == project_id,
            LookupSnapshot.lookup_name == lookup_name,
            LookupSnapshot.status == APPROVED_SNAPSHOT_STATUS,
        )
        .order_by(LookupSnapshot.created_at.desc())
    ).all()
    if not snapshots:
        raise SnapshotNotFoundError(
            f"No approved lookup snapshot for {lookup_name!r} in project {project_id}."
        )
    return snapshots[0]


def parse_primary_field_binding(snapshot: MappingSnapshot) -> FieldBinding:
    if not snapshot.field_bindings:
        raise SnapshotNotFoundError("Mapping snapshot has no field bindings.")
    if len(snapshot.field_bindings) > 1:
        raise MappingError("Only single-field binding is supported.")
    binding = snapshot.field_bindings[0]
    return FieldBinding(
        source_field=str(binding["source_field"]),
        destination_field=str(binding["destination_field"]),
        lookup_name=str(binding["lookup_name"]),
    )


def guard_snapshot_immutable(snapshot: MappingSnapshot | LookupSnapshot, *, updates: dict[str, Any]) -> None:
    if snapshot.status == APPROVED_SNAPSHOT_STATUS and updates:
        raise SnapshotImmutableError("Approved snapshots are immutable.")

from ..management.source_analysis import get_latest_source_schema_artifact
from .ddl import parse_all_ddl_tables, parse_ddl
from ..api.schemas import MappingFieldBindingResponse, MappingReviewResponse
from ..db.models import ProjectDefinition, ProjectRegistry, Feed

_SNAPSHOT_VERSION_RE = re.compile(r"^v(?P<number>\d+)$")

def get_project_destination_schema(db: Session, *, project_id: str) -> tuple[str, list[str]]:
    registry = db.scalar(select(ProjectRegistry).where(ProjectRegistry.project_id == project_id))
    if registry is None:
        raise AuthApiError("project_not_found", "Project not found.", 404)

    definition = db.scalar(select(ProjectDefinition).where(ProjectDefinition.definition_id == registry.definition_id))
    if definition is None:
        raise AuthApiError("project_not_found", "Project not found.", 404)

    ddl = (definition.domain_config or {}).get("destination_schema_ddl")
    if not ddl:
        raise AuthApiError("destination_schema_missing", "Project has no destination schema DDL configured.", 409)

    return parse_ddl(ddl)


def get_source_definition(db: Session, *, project_id: str, source_definition_id: str) -> Feed:
    feed = db.scalar(
        select(Feed).where(
            Feed.project_id == project_id,
            Feed.source_definition_id == source_definition_id,
        )
    )
    if feed is None:
        raise AuthApiError("source_definition_not_found", "Feed not found.", 404)
    return feed


def latest_snapshot(
    db: Session,
    *,
    project_id: str,
    source_definition_id: str,
    destination_object_name: str,
) -> MappingSnapshot | None:
    return db.scalar(
        select(MappingSnapshot)
        .where(
            MappingSnapshot.project_id == project_id,
            MappingSnapshot.source_definition_id == source_definition_id,
            MappingSnapshot.destination_object_name == destination_object_name,
        )
        .order_by(MappingSnapshot.created_at.desc(), MappingSnapshot.mapping_snapshot_id.desc())
    )


def next_snapshot_version(
    db: Session,
    *,
    project_id: str,
    source_definition_id: str,
    destination_object_name: str,
) -> str:
    versions = db.scalars(
        select(MappingSnapshot.mapping_snapshot_version)
        .where(
            MappingSnapshot.project_id == project_id,
            MappingSnapshot.source_definition_id == source_definition_id,
            MappingSnapshot.destination_object_name == destination_object_name,
        )
        .order_by(MappingSnapshot.created_at.asc(), MappingSnapshot.mapping_snapshot_id.asc())
    ).all()
    highest = 0
    for version in versions:
        match = _SNAPSHOT_VERSION_RE.match(version)
        if match is None:
            continue
        highest = max(highest, int(match.group("number")))
    return f"v{highest + 1}"


def derive_destination_fields(db: Session, project_id: str, destination_object_name: str) -> list[str]:
    try:
        project_definition = get_project_definition(db, project_id=project_id)
        ddl = (project_definition.domain_config or {}).get("destination_schema_ddl")
        if not ddl:
            return []
        ddl_tables = parse_all_ddl_tables(ddl)
        return ddl_tables.get(destination_object_name) or []
    except Exception:
        return []


def snapshot_to_response(
    snapshot: MappingSnapshot,
    db: Session,
    destination_fields: list[str] | None = None,
) -> MappingReviewResponse:
    if destination_fields is None:
        destination_fields = derive_destination_fields(db, snapshot.project_id, snapshot.destination_object_name)
    fields = destination_fields if destination_fields else (snapshot.destination_fields or [])
    
    lookup_table_references: list[dict[str, str]] = []
    for binding in snapshot.field_bindings:
        b_type = binding.get("binding_type")
        ref_table = binding.get("reference_table_name")
        l_name = binding.get("lookup_name")
        if b_type == "lookup_fk" and ref_table:
            # Match: lookup_name -> destination_table_name
            lookup_table_references.append({
                "lookup_name": l_name or binding.get("source_field", ""),
                "destination_table_name": ref_table,
            })

    return MappingReviewResponse(
        mapping_snapshot_id=snapshot.mapping_snapshot_id,
        project_id=snapshot.project_id,
        destination_object_name=snapshot.destination_object_name,
        mapping_snapshot_version=snapshot.mapping_snapshot_version,
        field_bindings=[
            MappingFieldBindingResponse(
                source_field=str(binding.get("source_field", "")),
                destination_field=str(binding.get("destination_field", "")),
                lookup_name=binding.get("lookup_name"),
                binding_type=binding.get("binding_type"),
                reference_table_name=binding.get("reference_table_name"),
                destination_table_name=binding.get("destination_table_name"),
                destination_data_type=binding.get("destination_data_type"),
                nullable=binding.get("nullable"),
            )
            for binding in snapshot.field_bindings
        ],
        status=snapshot.status,
        current_ball_role=snapshot.current_ball_role,
        approved_at=snapshot.approved_at,
        approved_by_user_id=snapshot.approved_by_user_id,
        created_at=snapshot.created_at,
        destination_fields=fields,
        lookup_table_references=lookup_table_references,
    )


def latest_source_columns(
    db: Session,
    *,
    project_id: str,
    source_definition_id: str,
) -> list[str]:
    get_source_definition(db, project_id=project_id, source_definition_id=source_definition_id)
    artifact = get_latest_source_schema_artifact(
        db,
        project_id=project_id,
        source_definition_id=source_definition_id,
    )
    return [column.name for column in artifact.columns]


def get_project_definition(db: Session, *, project_id: str) -> ProjectDefinition:
    registry = db.get(ProjectRegistry, project_id)
    if registry is None:
        raise AuthApiError("project_not_found", "Project not found.", 404)

    project_definition = db.get(ProjectDefinition, registry.definition_id)
    if project_definition is None:
        raise AuthApiError("project_not_found", "Project not found.", 404)
    return project_definition

