from __future__ import annotations

import re
from datetime import UTC, datetime

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..api.deps import AuthApiError
from ..api.schemas import MappingFieldBindingResponse, MappingReviewResponse
from ..db.models import MappingSnapshot, ProjectDefinition, ProjectRegistry, SourceDefinition, new_id
from ..management.platform import record_management_audit
from ..management.source_analysis import get_latest_source_schema_artifact

try:
    from ..ai.factory import get_adapter
except ModuleNotFoundError:  # pragma: no cover - optional dependency in tests
    get_adapter = None  # type: ignore[assignment]


_SNAPSHOT_VERSION_RE = re.compile(r"^v(?P<number>\d+)$")
_TABLE_RE = re.compile(
    r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?(?:[\w$]+\.)?\"?(?P<table>[\w$]+)\"?",
    re.IGNORECASE,
)
_COLUMN_RE = re.compile(r'^\s*["`]?(?P<name>[A-Za-z_][\w$]*)["`]?\s+[A-Za-z]')
_CONSTRAINT_PREFIXES = ("CONSTRAINT", "PRIMARY", "UNIQUE", "FOREIGN", "CHECK")


class _ProposedBinding(BaseModel):
    source_field: str
    destination_field: str


class _FieldMappingProposal(BaseModel):
    bindings: list[_ProposedBinding]


def _parse_ddl(ddl: str) -> tuple[str, list[str]]:
    lines = [line.rstrip() for line in ddl.splitlines() if line.strip()]
    if not lines:
        raise ValueError("Could not parse table name from destination_schema_ddl.")

    table_match = _TABLE_RE.search(lines[0])
    if table_match is None:
        for line in lines:
            table_match = _TABLE_RE.search(line)
            if table_match is not None:
                break
    if table_match is None:
        raise ValueError("Could not parse table name from destination_schema_ddl.")

    columns: list[str] = []
    for line in lines[1:]:
        stripped = line.strip().rstrip(",")
        if not stripped or stripped.startswith(")") or stripped.startswith("--"):
            continue
        if stripped.upper().startswith(_CONSTRAINT_PREFIXES):
            continue
        column_match = _COLUMN_RE.match(line)
        if column_match is None:
            continue
        column_name = column_match.group("name")
        if column_name not in columns:
            columns.append(column_name)

    if not columns:
        raise ValueError("Destination schema DDL has no parseable column definitions.")
    return table_match.group("table"), columns


def _get_project_destination_schema(db: Session, *, project_id: str) -> tuple[str, list[str]]:
    registry = db.scalar(select(ProjectRegistry).where(ProjectRegistry.project_id == project_id))
    if registry is None:
        raise AuthApiError("project_not_found", "Project not found.", 404)

    definition = db.scalar(select(ProjectDefinition).where(ProjectDefinition.definition_id == registry.definition_id))
    if definition is None:
        raise AuthApiError("project_not_found", "Project not found.", 404)

    ddl: str | None = None
    if definition.domain_config is not None:
        ddl = definition.domain_config.get("destination_schema_ddl")
    if not ddl:
        raise AuthApiError(
            "destination_schema_missing",
            "Project has no destination schema DDL configured.",
            409,
        )

    try:
        table_name, columns = _parse_ddl(ddl)
    except ValueError as exc:
        raise AuthApiError("destination_schema_invalid", str(exc), 422) from exc
    return table_name, columns


def _get_source_definition(db: Session, *, project_id: str, source_definition_id: str) -> SourceDefinition:
    source_definition = db.get(SourceDefinition, source_definition_id)
    if source_definition is None or source_definition.project_id != project_id:
        raise AuthApiError("source_not_found", "Source contract not found.", 404)
    return source_definition


def _latest_snapshot(db: Session, *, project_id: str, destination_object_name: str) -> MappingSnapshot | None:
    return db.scalar(
        select(MappingSnapshot)
        .where(
            MappingSnapshot.project_id == project_id,
            MappingSnapshot.destination_object_name == destination_object_name,
        )
        .order_by(MappingSnapshot.created_at.desc(), MappingSnapshot.mapping_snapshot_id.desc())
    )


def _next_snapshot_version(db: Session, *, project_id: str, destination_object_name: str) -> str:
    versions = db.scalars(
        select(MappingSnapshot.mapping_snapshot_version)
        .where(
            MappingSnapshot.project_id == project_id,
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


def _snapshot_to_response(snapshot: MappingSnapshot, destination_fields: list[str]) -> MappingReviewResponse:
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
            )
            for binding in snapshot.field_bindings
        ],
        status=snapshot.status,
        approved_at=snapshot.approved_at,
        approved_by_user_id=snapshot.approved_by_user_id,
        created_at=snapshot.created_at,
        destination_fields=destination_fields,
    )


def _latest_source_columns(
    db: Session,
    *,
    project_id: str,
    source_definition_id: str,
) -> list[str]:
    _get_source_definition(db, project_id=project_id, source_definition_id=source_definition_id)
    artifact = get_latest_source_schema_artifact(
        db,
        project_id=project_id,
        source_definition_id=source_definition_id,
    )
    return [column.name for column in artifact.columns]


def propose_mapping(
    db: Session,
    *,
    project_id: str,
    source_definition_id: str,
    actor_user_id: str,
) -> MappingReviewResponse:
    if get_adapter is None:
        raise AuthApiError("ai_adapter_unavailable", "AI adapter dependency is unavailable.", 503)

    destination_object_name, destination_fields = _get_project_destination_schema(db, project_id=project_id)
    source_columns = _latest_source_columns(
        db,
        project_id=project_id,
        source_definition_id=source_definition_id,
    )
    adapter = get_adapter("field_mapping")
    proposal = adapter.call(
        (
            "You are a data migration specialist. Given source column names and destination "
            "field names, propose the best semantic field-to-field mapping. Return ONLY a JSON "
            "object with a 'bindings' array where each item has 'source_field' and "
            "'destination_field'."
        ),
        (
            f"Source columns: {source_columns!r}\n"
            f"Destination fields: {destination_fields!r}\n"
            "Map each source column to the most semantically appropriate destination field."
        ),
        _FieldMappingProposal,
    )
    snapshot = MappingSnapshot(
        mapping_snapshot_id=new_id(),
        project_id=project_id,
        destination_object_name=destination_object_name,
        mapping_snapshot_version=_next_snapshot_version(
            db,
            project_id=project_id,
            destination_object_name=destination_object_name,
        ),
        field_bindings=[
            {
                "source_field": binding.source_field,
                "destination_field": binding.destination_field,
                "lookup_name": None,
            }
            for binding in proposal.bindings
        ],
        status="draft",
        approved_at=None,
        approved_by_user_id=None,
    )
    db.add(snapshot)
    record_management_audit(
        db,
        project_id=project_id,
        actor_user_id=actor_user_id,
        event_type="mapping_proposed",
        payload={
            "mapping_snapshot_id": snapshot.mapping_snapshot_id,
            "destination_object_name": destination_object_name,
            "model_id": getattr(adapter, "model_id", None),
        },
    )
    db.commit()
    db.refresh(snapshot)
    return _snapshot_to_response(snapshot, destination_fields)


def get_mapping(
    db: Session,
    *,
    project_id: str,
    source_definition_id: str,
) -> MappingReviewResponse:
    destination_object_name, destination_fields = _get_project_destination_schema(db, project_id=project_id)
    _get_source_definition(db, project_id=project_id, source_definition_id=source_definition_id)
    snapshot = _latest_snapshot(
        db,
        project_id=project_id,
        destination_object_name=destination_object_name,
    )
    if snapshot is None:
        raise AuthApiError("mapping_not_found", "No mapping snapshot exists yet.", 404)
    return _snapshot_to_response(snapshot, destination_fields)


def patch_mapping(
    db: Session,
    *,
    project_id: str,
    source_definition_id: str,
    actor_user_id: str,
    field_bindings: list[MappingFieldBindingResponse],
) -> MappingReviewResponse:
    destination_object_name, destination_fields = _get_project_destination_schema(db, project_id=project_id)
    _get_source_definition(db, project_id=project_id, source_definition_id=source_definition_id)
    snapshot = _latest_snapshot(
        db,
        project_id=project_id,
        destination_object_name=destination_object_name,
    )
    if snapshot is None:
        raise AuthApiError("mapping_not_found", "No mapping snapshot exists yet.", 404)
    if snapshot.status != "draft":
        raise AuthApiError(
            "mapping_not_editable",
            f"Cannot edit a mapping snapshot with status '{snapshot.status}'.",
            422,
        )

    invalid_fields = [binding.destination_field for binding in field_bindings if binding.destination_field not in destination_fields]
    if invalid_fields:
        raise AuthApiError(
            "mapping_invalid_destination_field",
            f"Unknown destination fields: {', '.join(sorted(set(invalid_fields)))}.",
            422,
        )

    snapshot.field_bindings = [
        {
            "source_field": binding.source_field,
            "destination_field": binding.destination_field,
            "lookup_name": binding.lookup_name,
        }
        for binding in field_bindings
    ]
    record_management_audit(
        db,
        project_id=project_id,
        actor_user_id=actor_user_id,
        event_type="mapping_updated",
        payload={
            "mapping_snapshot_id": snapshot.mapping_snapshot_id,
            "mapping_snapshot_version": snapshot.mapping_snapshot_version,
            "destination_object_name": destination_object_name,
            "binding_count": len(field_bindings),
        },
    )
    db.commit()
    db.refresh(snapshot)
    return _snapshot_to_response(snapshot, destination_fields)


def approve_mapping(
    db: Session,
    *,
    project_id: str,
    source_definition_id: str,
    actor_user_id: str,
) -> MappingReviewResponse:
    destination_object_name, destination_fields = _get_project_destination_schema(db, project_id=project_id)
    source_definition = _get_source_definition(db, project_id=project_id, source_definition_id=source_definition_id)
    snapshot = _latest_snapshot(
        db,
        project_id=project_id,
        destination_object_name=destination_object_name,
    )
    if snapshot is None:
        raise AuthApiError("mapping_not_found", "No mapping snapshot exists yet.", 404)
    if snapshot.status != "draft":
        raise AuthApiError(
            "mapping_not_approvable",
            f"Cannot approve a mapping snapshot with status '{snapshot.status}'.",
            422,
        )

    snapshot.status = "approved"
    snapshot.approved_at = datetime.now(UTC)
    snapshot.approved_by_user_id = actor_user_id
    source_definition.destination_object_references = [destination_object_name]
    record_management_audit(
        db,
        project_id=project_id,
        actor_user_id=actor_user_id,
        event_type="mapping_approved",
        payload={
            "mapping_snapshot_id": snapshot.mapping_snapshot_id,
            "mapping_snapshot_version": snapshot.mapping_snapshot_version,
            "destination_object_name": destination_object_name,
        },
    )
    db.commit()
    db.refresh(snapshot)
    return _snapshot_to_response(snapshot, destination_fields)


def reject_mapping(
    db: Session,
    *,
    project_id: str,
    source_definition_id: str,
    actor_user_id: str,
    reason: str,
) -> MappingReviewResponse:
    destination_object_name, destination_fields = _get_project_destination_schema(db, project_id=project_id)
    _get_source_definition(db, project_id=project_id, source_definition_id=source_definition_id)
    snapshot = _latest_snapshot(
        db,
        project_id=project_id,
        destination_object_name=destination_object_name,
    )
    if snapshot is None:
        raise AuthApiError("mapping_not_found", "No mapping snapshot exists yet.", 404)
    if snapshot.status != "draft":
        raise AuthApiError(
            "mapping_not_rejectable",
            f"Cannot reject a mapping snapshot with status '{snapshot.status}'.",
            422,
        )

    snapshot.status = "rejected"
    record_management_audit(
        db,
        project_id=project_id,
        actor_user_id=actor_user_id,
        event_type="mapping_rejected",
        payload={
            "mapping_snapshot_id": snapshot.mapping_snapshot_id,
            "destination_object_name": destination_object_name,
            "reason": reason,
        },
    )
    db.commit()
    db.refresh(snapshot)
    return _snapshot_to_response(snapshot, destination_fields)
