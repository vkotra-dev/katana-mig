from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

import re
from ..api.deps import AuthApiError
from ..api.schemas import (
    MappingDestinationColumnResponse,
    MappingFieldBindingResponse,
    MappingReviewResponse,
)
from ..db.models import ProjectDefinition, ProjectRegistry, Feed, MappingSnapshot
from ..management.source_analysis import get_latest_source_schema_artifact


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

    from ..ai.factory import get_adapter
    from ..ai.prompt import Prompt
    from .ai_schemas import SingleTableSchema

    prompt = Prompt("single_table_schema")
    adapter = get_adapter("destination_schema")
    if not adapter:
        raise AuthApiError("ai_adapter_unavailable", "AI adapter dependency is unavailable.", 503)

    prompt.set(ddl=ddl)
    sys_prompt, user_prompt = prompt.get_prompt()
    try:
        result = adapter.call(sys_prompt, user_prompt, SingleTableSchema)
        if not result.parsed.columns:
            raise AuthApiError("destination_schema_invalid", "Destination schema DDL has no parseable column definitions.", 422)
        return result.parsed.table_name, result.parsed.columns
    except Exception as e:
        raise AuthApiError("destination_schema_invalid", f"Could not parse DDL: {e}", 422)


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


def snapshot_to_response(
    snapshot: MappingSnapshot,
    db: Session,
    destination_fields: list[str] | None = None,
) -> MappingReviewResponse:
    fields = destination_fields if destination_fields is not None else (snapshot.destination_fields or [])
    
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

    destination_columns = (
        [MappingDestinationColumnResponse(**c) for c in snapshot.destination_columns]
        if snapshot.destination_columns is not None
        else None
    )

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
        destination_columns=destination_columns,
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

