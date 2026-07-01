from __future__ import annotations

from datetime import UTC, datetime
from typing import cast

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..api.deps import AuthApiError
from ..api.schemas import (
    LatestRunSummary,
    MigrationProjectConfig,
    ProjectCreateRequest,
    ProjectResponse,
    ProjectStatus,
    ProjectUpdateRequest,
)
from ..db.models import ProjectDefinition, ProjectMembership, ProjectRegistry, RunRecord, Feed, User, new_id
from ..roles import PROJECT_STAKEHOLDER_ROLE
from .platform import record_management_audit


def create_project(db: Session, *, actor: User, body: ProjectCreateRequest) -> ProjectResponse:
    project_id = new_id()
    definition_id = new_id()
    domain_config = _dump_domain_config(body.domain_config)

    definition = ProjectDefinition(
        definition_id=definition_id,
        project_id=project_id,
        name=body.name,
        goal=body.goal,
        repos=body.repos,
        workspace=body.workspace,
        environment=body.environment,
        execution_environments=body.execution_environments,
        model_policy=body.model_policy,
        canonical_terms=body.canonical_terms,
        constraints=body.constraints,
        unresolved_questions=body.unresolved_questions,
        assumptions=body.assumptions,
        domain_config=domain_config,
        status="active",
    )
    registry = ProjectRegistry(
        project_id=project_id,
        name=body.name,
        definition_id=definition_id,
        lexicon_scope=body.lexicon_scope,
        status="active",
    )
    db.add(definition)
    db.add(registry)
    db.flush()

    auto_member = actor.role == PROJECT_STAKEHOLDER_ROLE
    if auto_member:
        db.add(ProjectMembership(project_id=project_id, user_id=actor.user_id))

    record_management_audit(
        db,
        project_id=project_id,
        actor_user_id=actor.user_id,
        event_type="project.created",
        payload={
            "project_id": project_id,
            "name": body.name,
            "auto_member_user_id": actor.user_id if auto_member else None,
        },
    )
    db.commit()
    db.refresh(registry)
    db.refresh(definition)
    return _project_response(registry, definition)


def list_projects(
    db: Session,
    *,
    actor: User,
    include_archived: bool = False,
) -> list[ProjectResponse]:
    stmt = select(ProjectRegistry, ProjectDefinition).join(
        ProjectDefinition,
        ProjectRegistry.definition_id == ProjectDefinition.definition_id,
    )
    if not include_archived:
        stmt = stmt.where(ProjectRegistry.archived_at.is_(None))
    stmt = stmt.where(ProjectRegistry.soft_deleted_at.is_(None))

    if actor.role == PROJECT_STAKEHOLDER_ROLE:
        stmt = stmt.join(
            ProjectMembership,
            (ProjectMembership.project_id == ProjectRegistry.project_id)
            & (ProjectMembership.user_id == actor.user_id),
        )

    stmt = stmt.order_by(ProjectRegistry.name)
    rows = db.execute(stmt).all()
    latest_run_summary_by_project = _load_latest_run_summaries(db, [registry.project_id for registry, _ in rows])
    return [
        _project_response(registry, definition, latest_run_summary_by_project.get(registry.project_id))
        for registry, definition in rows
    ]


def get_project(db: Session, *, project_id: str) -> ProjectResponse:
    registry, definition = _get_project_rows(db, project_id)
    return _project_response(registry, definition)


def update_project(
    db: Session,
    *,
    actor: User,
    project_id: str,
    body: ProjectUpdateRequest,
) -> ProjectResponse:
    registry, current_definition = _get_project_rows(db, project_id)
    if registry.archived_at is not None:
        raise AuthApiError("project_archived", "Cannot update an archived project.", 409)

    new_definition_id = new_id()
    new_definition = ProjectDefinition(
        definition_id=new_definition_id,
        project_id=project_id,
        name=body.name if body.name is not None else current_definition.name,
        goal=body.goal if body.goal is not None else current_definition.goal,
        repos=body.repos if body.repos is not None else current_definition.repos,
        workspace=body.workspace if body.workspace is not None else current_definition.workspace,
        environment=body.environment if body.environment is not None else current_definition.environment,
        execution_environments=(
            body.execution_environments
            if body.execution_environments is not None
            else current_definition.execution_environments
        ),
        model_policy=body.model_policy if body.model_policy is not None else current_definition.model_policy,
        canonical_terms=body.canonical_terms if body.canonical_terms is not None else current_definition.canonical_terms,
        constraints=body.constraints if body.constraints is not None else current_definition.constraints,
        unresolved_questions=(
            body.unresolved_questions
            if body.unresolved_questions is not None
            else current_definition.unresolved_questions
        ),
        assumptions=body.assumptions if body.assumptions is not None else current_definition.assumptions,
        domain_config=(
            _merge_domain_config(current_definition.domain_config, body.domain_config)
            if body.domain_config is not None
            else current_definition.domain_config
        ),
        status="active",
    )
    db.add(new_definition)
    db.flush()

    if body.name is not None:
        registry.name = body.name
    registry.definition_id = new_definition_id
    if body.lexicon_scope is not None:
        registry.lexicon_scope = body.lexicon_scope

    record_management_audit(
        db,
        project_id=project_id,
        actor_user_id=actor.user_id,
        event_type="project.updated",
        payload={
            "project_id": project_id,
            "new_definition_id": new_definition_id,
            "changed_fields": list(body.model_dump(exclude_none=True).keys()),
        },
    )
    db.commit()
    db.refresh(registry)
    db.refresh(new_definition)
    return _project_response(registry, new_definition)


def archive_project(db: Session, *, actor: User, project_id: str) -> ProjectResponse:
    registry, definition = _get_project_rows(db, project_id)
    if registry.archived_at is not None:
        raise AuthApiError("project_already_archived", "Project is already archived.", 409)

    registry.archived_at = datetime.now(UTC)
    registry.status = "archived"

    record_management_audit(
        db,
        project_id=project_id,
        actor_user_id=actor.user_id,
        event_type="project.archived",
        payload={"project_id": project_id},
    )
    db.commit()
    db.refresh(registry)
    db.refresh(definition)
    return _project_response(registry, definition)


def _dump_domain_config(domain_config: MigrationProjectConfig | None) -> dict[str, object] | None:
    if domain_config is None:
        return None
    return domain_config.model_dump(exclude_unset=True)


def _merge_domain_config(
    current_domain_config: dict[str, object] | None,
    patch_domain_config: MigrationProjectConfig,
) -> dict[str, object]:
    merged = dict(current_domain_config or {})
    merged.update(patch_domain_config.model_dump(exclude_unset=True))
    return merged


def _get_project_rows(db: Session, project_id: str) -> tuple[ProjectRegistry, ProjectDefinition]:
    registry = db.get(ProjectRegistry, project_id)
    if registry is None or registry.soft_deleted_at is not None:
        raise AuthApiError("project_not_found", "Project not found.", 404)
    definition = db.get(ProjectDefinition, registry.definition_id)
    if definition is None:
        raise AuthApiError("project_not_found", "Project not found.", 404)
    return registry, definition


def _load_latest_run_summaries(
    db: Session,
    project_ids: list[str],
) -> dict[str, LatestRunSummary]:
    if not project_ids:
        return {}

    latest_subquery = (
        select(
            RunRecord.project_id.label("project_id"),
            func.max(RunRecord.updated_at).label("updated_at"),
        )
        .where(RunRecord.project_id.in_(project_ids))
        .group_by(RunRecord.project_id)
        .subquery()
    )

    stmt = (
        select(RunRecord, Feed.source_type)
        .join(
            latest_subquery,
            (RunRecord.project_id == latest_subquery.c.project_id)
            & (RunRecord.updated_at == latest_subquery.c.updated_at),
        )
        .outerjoin(
            Feed,
            Feed.source_definition_id == RunRecord.source_definition_reference,
        )
    )

    result: dict[str, LatestRunSummary] = {}
    for run, source_type in db.execute(stmt).all():
        result[run.project_id] = LatestRunSummary(
            current_stage=run.current_stage,
            run_status=run.status,
            source_type=source_type,
            stage_entered_at=run.updated_at,
        )
    return result


def _project_response(
    registry: ProjectRegistry,
    definition: ProjectDefinition,
    latest_run_summary: LatestRunSummary | None = None,
) -> ProjectResponse:
    return ProjectResponse(
        project_id=registry.project_id,
        name=registry.name,
        goal=definition.goal,
        repos=definition.repos,
        workspace=definition.workspace,
        environment=definition.environment,
        execution_environments=definition.execution_environments,
        model_policy=definition.model_policy,
        canonical_terms=definition.canonical_terms,
        constraints=definition.constraints,
        unresolved_questions=definition.unresolved_questions,
        assumptions=definition.assumptions,
        domain_config=definition.domain_config,  # type: ignore[arg-type]
        lexicon_scope=registry.lexicon_scope,
        status=cast(ProjectStatus, registry.status),
        created_at=registry.created_at,
        updated_at=registry.updated_at,
        archived_at=registry.archived_at,
        latest_run_summary=latest_run_summary,
    )
