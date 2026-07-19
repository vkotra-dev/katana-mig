from __future__ import annotations

from datetime import UTC, datetime
import os
from typing import Any, Literal
from jinja2 import Environment, FileSystemLoader

TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), "templates")
jinja_env = Environment(loader=FileSystemLoader(TEMPLATES_DIR), trim_blocks=True, lstrip_blocks=True)

from pydantic import BaseModel, Field
from sqlalchemy import case, or_, select, update
from sqlalchemy.orm import Session

from ..api.deps import AuthApiError
from ..api.schemas import (
    MigrationProjectConfig,
    CodegenArtifactResponse,
    CodegenTriggerResponse,
    DeliveryBundleResponse,
)
from ..db.models import (
    CodeGenerationArtifact,
    MappingSnapshot,
    ProjectDefinition,
    ProjectRegistry,
    Feed,
    FeedSlice,
    FeedComment,
    User,
    new_id,
)
from ..management.platform import record_management_audit
from ..ai.factory import get_adapter
from ..mapping.exceptions import SnapshotNotFoundError
from ..mapping.snapshots import select_latest_approved_lookup_snapshot
from .schema_analysis import get_schema_analysis


class GeneratedSQL(BaseModel):
    staging_ddl: str = Field(min_length=1)
    lookup_ddl: list[str] = Field(default_factory=list)
    seed_data: list[str] = Field(default_factory=list)
    stored_procedures: list[str] = Field(default_factory=list)
    notes: str | None = None



def generate_codegen_artifact(
    db: Session,
    *,
    actor: User,
    project_id: str,
    source_definition_id: str,
) -> CodegenTriggerResponse:
    source_definition = _get_source_definition(db, project_id=project_id, source_definition_id=source_definition_id)
    destination_object_name = _primary_destination_object_name(source_definition)
    project_definition = _get_project_definition(db, project_id=project_id)
    project_config = MigrationProjectConfig.model_validate(project_definition.domain_config or {})

    source_slice = _select_latest_approved_source_slice(db, source_definition_id=source_definition_id)
    mapping_snapshot = _select_latest_approved_mapping_snapshot(
        db,
        project_id=project_id,
        source_definition_id=source_definition_id,
        destination_object_name=destination_object_name,
    )
    lookup_snapshot_version = _select_lookup_snapshot_version(
        db,
        project_id=project_id,
        mapping_snapshot=mapping_snapshot,
    )

    try:
        adapter = get_adapter("script_generation", project_definition.model_policy)
    except TypeError:
        adapter = get_adapter("script_generation")
    comments = list(db.execute(
        select(FeedComment, User.role)
        .join(User, User.user_id == FeedComment.user_id)
        .where(FeedComment.feed_id == source_definition_id, FeedComment.source_slice_id.is_(None))
        .order_by(FeedComment.created_at.asc())
    ).all())

    slice_comments = list(db.execute(
        select(FeedComment, User.role)
        .join(User, User.user_id == FeedComment.user_id)
        .where(FeedComment.source_slice_id == source_slice.source_slice_id)
        .order_by(FeedComment.created_at.asc())
    ).all())

    system_prompt = _build_system_prompt(
        project_config=project_config,
        destination_object_name=destination_object_name,
        project_definition=project_definition,
        run_ref=f"{project_id}_{source_definition_id}",
    )
    user_prompt = _build_user_prompt(
        source_definition=source_definition,
        source_slice=source_slice,
        mapping_snapshot=mapping_snapshot,
        lookup_snapshot_version=lookup_snapshot_version,
        project_config=project_config,
        run_ref=f"{project_id}_{source_definition_id}",
        comments=comments,
        slice_comments=slice_comments,
    )

    from ..ai.logging import log_ai_call, backfill_artifact_id

    try:
        result = adapter.call(
            system=system_prompt,
            user=user_prompt,
            response_model=GeneratedSQL,
        )
        call_log = log_ai_call(
            db,
            project_id=project_id,
            call_type="codegen",
            model_id=adapter.model_id,
            system=system_prompt,
            user=user_prompt,
            raw_response=result.raw_response,
        )
        generated_sql = result.parsed
    except Exception as exc:
        log_ai_call(
            db,
            project_id=project_id,
            call_type="codegen",
            model_id=adapter.model_id,
            system=system_prompt,
            user=user_prompt,
            raw_response=None,
            error_detail=str(exc),
        )
        raise

    sql_bundle = _assemble_sql_bundle(generated_sql, staging_schema=project_config.staging_schema)
    _supersede_previous_artifacts(
        db,
        project_id=project_id,
        destination_object_name=destination_object_name,
    )

    codegen_artifact_id = new_id()
    artifact = CodeGenerationArtifact(
        codegen_artifact_id=codegen_artifact_id,
        project_id=project_id,
        destination_object_name=destination_object_name,
        run_id=None,
        source_slice_version=source_slice.source_slice_version,
        mapping_snapshot_version=mapping_snapshot.mapping_snapshot_version,
        lookup_snapshot_version=lookup_snapshot_version,
        sql_bundle=sql_bundle,
        compiled_system_prompt=system_prompt,
        compiled_user_prompt=user_prompt,
        raw_llm_response=generated_sql.model_dump_json(indent=2),
        status="active",
    )
    db.add(artifact)
    record_management_audit(
        db,
        project_id=project_id,
        actor_user_id=actor.user_id,
        event_type="codegen_artifact.generated",
        payload={
            "codegen_artifact_id": codegen_artifact_id,
            "source_definition_id": source_definition_id,
            "destination_object_name": destination_object_name,
            "source_slice_version": artifact.source_slice_version,
            "mapping_snapshot_version": artifact.mapping_snapshot_version,
            "lookup_snapshot_version": artifact.lookup_snapshot_version,
        },
    )
    db.commit()
    backfill_artifact_id(db, call_log.call_id, artifact.codegen_artifact_id)
    db.refresh(artifact)
    return _trigger_response(artifact)


def list_codegen_artifacts(
    db: Session,
    *,
    project_id: str,
    status: str | None = None,
) -> list[CodegenArtifactResponse]:
    stmt = select(CodeGenerationArtifact).where(CodeGenerationArtifact.project_id == project_id)
    if status is not None:
        stmt = stmt.where(CodeGenerationArtifact.status == status)
    rows = db.scalars(
        stmt.order_by(CodeGenerationArtifact.destination_object_name.asc(), CodeGenerationArtifact.created_at.desc())
    ).all()
    return [_artifact_response(row) for row in rows]


def get_codegen_artifact(
    db: Session,
    *,
    project_id: str,
    codegen_artifact_id: str,
) -> CodegenArtifactResponse:
    artifact = db.get(CodeGenerationArtifact, codegen_artifact_id)
    if artifact is None or artifact.project_id != project_id:
        raise AuthApiError("codegen_artifact_not_found", "Code generation artifact not found.", 404)
    return _artifact_response(artifact)


def build_delivery_bundle_text(
    db: Session,
    *,
    project_id: str,
) -> DeliveryBundleResponse:
    analysis = get_schema_analysis(db, project_id=project_id)
    sequence = analysis.destination_object_sequence if analysis is not None else None
    artifacts = db.scalars(
        select(CodeGenerationArtifact)
        .where(
            CodeGenerationArtifact.project_id == project_id,
            CodeGenerationArtifact.status == "active",
        )
        .order_by(CodeGenerationArtifact.destination_object_name.asc(), CodeGenerationArtifact.created_at.desc())
    ).all()
    lookup_artifacts = sorted(
        [artifact for artifact in artifacts if artifact.destination_object_name.startswith("0000_")],
        key=lambda artifact: (artifact.destination_object_name, artifact.created_at),
    )
    domain_artifacts = [artifact for artifact in artifacts if not artifact.destination_object_name.startswith("0000_")]
    if sequence is not None:
        positions = {name: index for index, name in enumerate(sequence)}
        domain_artifacts = sorted(
            domain_artifacts,
            key=lambda artifact: (
                positions.get(artifact.destination_object_name, len(sequence)),
                artifact.destination_object_name,
                artifact.created_at,
            ),
        )
    else:
        domain_artifacts = sorted(
            domain_artifacts,
            key=lambda artifact: (artifact.destination_object_name, artifact.created_at),
        )
    bundle_parts: list[str] = []
    for artifact in lookup_artifacts:
        bundle_parts.append(f"-- {artifact.destination_object_name}")
        if artifact.sql_bundle:
            bundle_parts.append(artifact.sql_bundle.strip())
    for index, artifact in enumerate(domain_artifacts, start=1):
        heading = f"-- [{index:02d}] {artifact.destination_object_name}" if sequence is not None else f"-- {artifact.destination_object_name}"
        bundle_parts.append(heading)
        if artifact.sql_bundle:
            bundle_parts.append(artifact.sql_bundle.strip())
    return DeliveryBundleResponse(
        sql_bundle="\n\n".join(bundle_parts).strip(),
        artifact_count=len(lookup_artifacts) + len(domain_artifacts),
    )


def _trigger_response(artifact: CodeGenerationArtifact) -> CodegenTriggerResponse:
    preview = (artifact.sql_bundle or "")[:500]
    return CodegenTriggerResponse(
        codegen_artifact_id=artifact.codegen_artifact_id,
        project_id=artifact.project_id,
        destination_object_name=artifact.destination_object_name,
        status=artifact.status,
        sql_bundle_preview=preview,
        source_slice_version=artifact.source_slice_version,
        mapping_snapshot_version=artifact.mapping_snapshot_version,
        lookup_snapshot_version=artifact.lookup_snapshot_version,
        compiled_system_prompt=artifact.compiled_system_prompt,
        compiled_user_prompt=artifact.compiled_user_prompt,
        raw_llm_response=artifact.raw_llm_response,
        created_at=artifact.created_at,
    )


def _artifact_response(artifact: CodeGenerationArtifact) -> CodegenArtifactResponse:
    return CodegenArtifactResponse(
        codegen_artifact_id=artifact.codegen_artifact_id,
        project_id=artifact.project_id,
        destination_object_name=artifact.destination_object_name,
        run_id=artifact.run_id,
        source_slice_version=artifact.source_slice_version,
        mapping_snapshot_version=artifact.mapping_snapshot_version,
        lookup_snapshot_version=artifact.lookup_snapshot_version,
        sql_bundle=artifact.sql_bundle,
        compiled_system_prompt=artifact.compiled_system_prompt,
        compiled_user_prompt=artifact.compiled_user_prompt,
        raw_llm_response=artifact.raw_llm_response,
        status=artifact.status,
        created_at=artifact.created_at,
        superseded_at=artifact.superseded_at,
    )


def _get_source_definition(db: Session, *, project_id: str, source_definition_id: str) -> Feed:
    source_definition = db.get(Feed, source_definition_id)
    if source_definition is None or source_definition.project_id != project_id:
        raise AuthApiError("source_not_found", "Source contract not found.", 404)
    return source_definition


def _get_project_definition(db: Session, *, project_id: str) -> ProjectDefinition:
    registry = db.get(ProjectRegistry, project_id)
    if registry is None:
        raise AuthApiError("project_not_found", "Project not found.", 404)
    project_definition = db.get(ProjectDefinition, registry.definition_id)
    if project_definition is None:
        raise AuthApiError("project_not_found", "Project not found.", 404)
    return project_definition


def _primary_destination_object_name(source_definition: Feed) -> str:
    references = source_definition.destination_object_references or []
    if not references:
        raise AuthApiError(
            "codegen_destination_object_missing",
            "Source contract has no destination object reference.",
            409,
        )
    destination_object_name = str(references[0]).strip()
    if not destination_object_name:
        raise AuthApiError(
            "codegen_destination_object_missing",
            "Source contract has no destination object reference.",
            409,
        )
    return destination_object_name


def _select_latest_approved_source_slice(db: Session, *, source_definition_id: str) -> FeedSlice:
    source_slice = db.scalar(
        select(FeedSlice)
        .where(
            FeedSlice.source_definition_id == source_definition_id,
            FeedSlice.status == "approved",
        )
        .order_by(FeedSlice.approved_at.is_(None), FeedSlice.approved_at.desc(), FeedSlice.created_at.desc())
    )
    if source_slice is None:
        raise AuthApiError("codegen_source_slice_missing", "An approved source slice is required.", 409)
    return source_slice


def _select_latest_approved_mapping_snapshot(
    db: Session,
    *,
    project_id: str,
    source_definition_id: str,
    destination_object_name: str,
) -> MappingSnapshot:
    mapping_snapshot = db.scalar(
        select(MappingSnapshot)
        .where(
            MappingSnapshot.project_id == project_id,
            or_(
                MappingSnapshot.source_definition_id == source_definition_id,
                MappingSnapshot.source_definition_id.is_(None)
            ),
            MappingSnapshot.destination_object_name == destination_object_name,
            MappingSnapshot.status == "approved",
        )
        .order_by(
            case(
                (MappingSnapshot.source_definition_id == source_definition_id, 0),
                else_=1
            ).asc(),
            MappingSnapshot.approved_at.is_(None),
            MappingSnapshot.approved_at.desc(),
            MappingSnapshot.created_at.desc()
        )
    )
    if mapping_snapshot is None:
        raise AuthApiError("mapping_not_found", "Mapping snapshot not found.", 404)
    return mapping_snapshot


def _select_lookup_snapshot_version(
    db: Session,
    *,
    project_id: str,
    mapping_snapshot: MappingSnapshot,
) -> str | None:
    lookup_names = sorted(
        {
            str(binding.get("lookup_name"))
            for binding in mapping_snapshot.field_bindings
            if binding.get("lookup_name")
        }
    )
    for lookup_name in lookup_names:
        try:
            snapshot = select_latest_approved_lookup_snapshot(
                db,
                project_id=project_id,
                lookup_name=lookup_name,
            )
        except SnapshotNotFoundError:
            continue
        return snapshot.lookup_snapshot_version
    return None


def _mig_upsert_log_ddl(staging_schema: str) -> str:
    return (
        f"IF OBJECT_ID(N'[{staging_schema}].[mig_upsert_log]', N'U') IS NULL\n"
        f"BEGIN\n"
        f"    CREATE TABLE [{staging_schema}].[mig_upsert_log] (\n"
        f"        [log_id]         BIGINT IDENTITY(1,1) PRIMARY KEY,\n"
        f"        [run_ref]        NVARCHAR(255) NOT NULL,\n"
        f"        [dest_table]     NVARCHAR(255) NOT NULL,\n"
        f"        [source_row_num] BIGINT        NULL,\n"
        f"        [dest_row_id]    NVARCHAR(255) NULL,\n"
        f"        [action]         NVARCHAR(10)  NOT NULL,\n"
        f"        [logged_at]      DATETIME2(0)  NOT NULL DEFAULT GETDATE()\n"
        f"    );\n"
        f"END;"
    )


def _assemble_sql_bundle(generated_sql: GeneratedSQL, *, staging_schema: str | None = None) -> str:
    parts: list[str] = []
    if staging_schema:
        parts.append(_mig_upsert_log_ddl(staging_schema))
    parts.append(generated_sql.staging_ddl.strip())
    parts.extend(s.strip() for s in generated_sql.lookup_ddl if s.strip())
    parts.extend(s.strip() for s in generated_sql.seed_data if s.strip())
    parts.extend(s.strip() for s in generated_sql.stored_procedures if s.strip())
    return "\n\nGO\n\n".join(parts).strip()

def _build_system_prompt(
    *,
    project_config: MigrationProjectConfig,
    destination_object_name: str,
    project_definition: ProjectDefinition,
    run_ref: str,
) -> str:
    template = jinja_env.get_template("system_prompt.txt.j2")
    base_prompt = template.render(
        project_config=project_config,
        destination_object_name=destination_object_name,
        project_definition=project_definition,
    ).strip()
    
    parts = [base_prompt, "", "RUN LOGGING REQUIREMENTS"]
    parts.append(
        f"Every staging table must include [_row_num] BIGINT IDENTITY(1,1) NOT NULL as its FIRST column.\n"
        f"Every data movement stored procedure must use MERGE (not standalone INSERT or UPDATE).\n"
        f"Every MERGE must include an OUTPUT clause that writes to [{project_config.staging_schema or 'stg'}].[mig_upsert_log]:\n"
        f"  OUTPUT\n"
        f"    '{run_ref}',\n"
        f"    '<dest_table_name>',\n"
        f"    src.[_row_num],\n"
        f"    CAST(inserted.<dest_pk_column> AS NVARCHAR(255)),\n"
        f"    $action\n"
        f"  INTO [{project_config.staging_schema or 'stg'}].[mig_upsert_log]\n"
        f"      (run_ref, dest_table, source_row_num, dest_row_id, action);\n"
        f"Replace <dest_table_name> with the actual destination table name and <dest_pk_column> with its primary key column."
    )
    return "\n".join(parts)

_MAX_COMMENT_CHARS = 400
_MAX_DISCUSSION_CHARS = 3000
_MAX_COMMENT_COUNT = 30


def _format_discussion(comments: list[tuple[FeedComment, str]]) -> str:
    if not comments:
        return ""
    recent = comments[-_MAX_COMMENT_COUNT:]
    lines = ["Feed discussion (context for mapping intent and business rules):"]
    total = len(lines[0])
    for fc, role in recent:
        content = " ".join((fc.body or "").split())  # collapse whitespace/newlines
        if len(content) > _MAX_COMMENT_CHARS:
            content = content[:_MAX_COMMENT_CHARS] + "…"
        line = f"[{role}] {fc.created_at.date() if fc.created_at else ''}: {content}"
        if total + len(line) + 1 > _MAX_DISCUSSION_CHARS:
            lines.append("[discussion truncated]")
            break
        lines.append(line)
        total += len(line) + 1
    return "\n".join(lines)


def _format_slice_discussion(comments: list[tuple[FeedComment, str]]) -> str:
    if not comments:
        return ""
    recent = comments[-_MAX_COMMENT_COUNT:]
    lines = ["Slice discussion (context for schema adjustments and anomalies):"]
    total = len(lines[0])
    for sc, role in recent:
        content = " ".join((sc.body or "").split())  # collapse whitespace/newlines
        if len(content) > _MAX_COMMENT_CHARS:
            content = content[:_MAX_COMMENT_CHARS] + "…"
        line = f"[{role}] {sc.created_at.date() if sc.created_at else ''}: {content}"
        if total + len(line) + 1 > _MAX_DISCUSSION_CHARS:
            lines.append("[discussion truncated]")
            break
        lines.append(line)
        total += len(line) + 1
    return "\n".join(lines)


def _build_user_prompt(
    *,
    source_definition: Feed,
    source_slice: FeedSlice,
    mapping_snapshot: MappingSnapshot,
    lookup_snapshot_version: str | None,
    project_config: MigrationProjectConfig,
    run_ref: str,
    comments: list[tuple[FeedComment, str]],
    slice_comments: list[tuple[FeedComment, str]],
) -> str:
    template = jinja_env.get_template("user_prompt.txt.j2")
    return template.render(
        source_definition=source_definition,
        source_slice=source_slice,
        mapping_snapshot=mapping_snapshot,
        lookup_snapshot_version=lookup_snapshot_version,
        project_config=project_config,
        run_ref=run_ref,
        discussion=_format_discussion(comments),
        slice_discussion=_format_slice_discussion(slice_comments),
    ).strip()


def _supersede_previous_artifacts(
    db: Session,
    *,
    project_id: str,
    destination_object_name: str,
) -> None:
    existing = list(
        db.scalars(
            select(CodeGenerationArtifact).where(
                CodeGenerationArtifact.project_id == project_id,
                CodeGenerationArtifact.destination_object_name == destination_object_name,
                CodeGenerationArtifact.status == "active",
            )
        )
    )
    if not existing:
        return
    now = datetime.now(UTC)
    db.execute(
        update(CodeGenerationArtifact)
        .where(
            CodeGenerationArtifact.project_id == project_id,
            CodeGenerationArtifact.destination_object_name == destination_object_name,
            CodeGenerationArtifact.status == "active",
        )
        .values(status="superseded", superseded_at=now)
    )
