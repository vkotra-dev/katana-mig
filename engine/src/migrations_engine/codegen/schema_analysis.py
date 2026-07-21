from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..ai.factory import get_adapter
from ..api.deps import AuthApiError
from ..api.schemas import MigrationProjectConfig, ProjectSchemaAnalysisResponse
from ..db.models import CodeGenerationArtifact, ProjectDefinition, ProjectRegistry, ProjectSchemaAnalysis


SYSTEM_PROMPT = (
    "You are a SQL DDL analyst. Given a multi-table DDL script, identify all destination objects "
    "(tables and views) and their FK/REFERENCES dependency relationships. Return JSON that matches "
    "the schema exactly."
)


class ObjectDependency(BaseModel):
    name: str
    depends_on: list[str]


class DDLAnalysisResult(BaseModel):
    objects: list[ObjectDependency]


def run_schema_analysis(db: Session, *, project_id: str) -> ProjectSchemaAnalysisResponse:
    project_definition = _get_project_definition(db, project_id=project_id)
    ddl = _destination_schema_ddl(project_definition)
    if not ddl:
        raise AuthApiError("missing_ddl", "Project has no destination_schema_ddl.", 422)

    try:
        adapter = get_adapter("schema_dependency", project_definition.model_policy)
    except TypeError:
        adapter = get_adapter("schema_dependency")
    from ..ai.logging import log_ai_call, backfill_artifact_id
    from ..ai.adapter import AIResponseValidationError

    try:
        result = adapter.call(SYSTEM_PROMPT, ddl, DDLAnalysisResult)
        call_log = log_ai_call(
            db,
            project_id=project_id,
            feature="codegen",
            call_type="schema_analysis",
            model_id=adapter.model_id,
            system=SYSTEM_PROMPT,
            user=ddl,
            raw_response=result.raw_response,
        )
        ai_result = result.parsed
    except AIResponseValidationError as exc:
        log_ai_call(
            db,
            project_id=project_id,
            feature="codegen",
            call_type="schema_analysis",
            model_id=adapter.model_id,
            system=SYSTEM_PROMPT,
            user=ddl,
            raw_response=exc.raw_response,
            error_detail=f"ValidationError: {exc.original}",
        )
        db.commit()
        raise
    except Exception as exc:
        log_ai_call(
            db,
            project_id=project_id,
            feature="codegen",
            call_type="schema_analysis",
            model_id=adapter.model_id,
            system=SYSTEM_PROMPT,
            user=ddl,
            raw_response=None,
            error_detail=str(exc),
        )
        db.commit()
        raise
    sequence = _topological_sort(ai_result.objects)

    record = db.scalar(select(ProjectSchemaAnalysis).where(ProjectSchemaAnalysis.project_id == project_id))
    analyzed_at = datetime.now(UTC)
    if record is None:
        record = ProjectSchemaAnalysis(
            project_id=project_id,
            destination_object_sequence=sequence,
            identified_count=len(sequence),
            analyzed_at=analyzed_at,
        )
        db.add(record)
    else:
        record.destination_object_sequence = sequence
        record.identified_count = len(sequence)
        record.analyzed_at = analyzed_at
    db.flush()
    db.commit()
    backfill_artifact_id(db, call_log.call_id, record.analysis_id)
    db.refresh(record)
    return _to_response(db, record)


def get_schema_analysis(db: Session, *, project_id: str) -> ProjectSchemaAnalysisResponse | None:
    record = db.scalar(select(ProjectSchemaAnalysis).where(ProjectSchemaAnalysis.project_id == project_id))
    if record is None:
        return None
    return _to_response(db, record)


def _to_response(db: Session, record: ProjectSchemaAnalysis) -> ProjectSchemaAnalysisResponse:
    processed_count = _processed_count(db, project_id=record.project_id, sequence=record.destination_object_sequence)
    return ProjectSchemaAnalysisResponse(
        analysis_id=record.analysis_id,
        project_id=record.project_id,
        destination_object_sequence=list(record.destination_object_sequence),
        identified_count=record.identified_count,
        processed_count=processed_count,
        analyzed_at=record.analyzed_at,
    )


def _processed_count(db: Session, *, project_id: str, sequence: list[str]) -> int:
    if not sequence:
        return 0
    active_names = set(
        db.scalars(
            select(CodeGenerationArtifact.destination_object_name).where(
                CodeGenerationArtifact.project_id == project_id,
                CodeGenerationArtifact.status == "active",
            )
        ).all()
    )
    return sum(1 for name in sequence if name in active_names)


def _get_project_definition(db: Session, *, project_id: str) -> ProjectDefinition:
    registry = db.get(ProjectRegistry, project_id)
    if registry is None:
        raise AuthApiError("project_not_found", "Project not found.", 404)
    project_definition = db.get(ProjectDefinition, registry.definition_id)
    if project_definition is None:
        raise AuthApiError("project_not_found", "Project not found.", 404)
    return project_definition


def _destination_schema_ddl(project_definition: ProjectDefinition) -> str | None:
    config = MigrationProjectConfig.model_validate(project_definition.domain_config or {})
    return config.destination_schema_ddl


def _topological_sort(objects: list[ObjectDependency]) -> list[str]:
    adjacency: dict[str, set[str]] = defaultdict(set)
    indegree: dict[str, int] = {}
    nodes: set[str] = set()

    for item in objects:
        name = item.name.strip()
        if not name:
            continue
        nodes.add(name)
        indegree.setdefault(name, 0)
        dependencies = {
            dependency.strip()
            for dependency in item.depends_on
            if dependency.strip() and dependency.strip() != name
        }
        for dependency in dependencies:
            nodes.add(dependency)
            adjacency[dependency].add(name)
            indegree.setdefault(dependency, 0)
            indegree[name] = indegree.get(name, 0) + 1

    ordered: list[str] = []
    ready = sorted(name for name in nodes if indegree.get(name, 0) == 0)
    seen: set[str] = set()

    while ready:
        name = ready.pop(0)
        if name in seen:
            continue
        seen.add(name)
        ordered.append(name)
        for dependent in sorted(adjacency.get(name, set())):
            indegree[dependent] -= 1
            if indegree[dependent] == 0:
                ready.append(dependent)
                ready.sort()

    if len(ordered) < len(nodes):
        ordered.extend(sorted(nodes - set(ordered)))

    return ordered
