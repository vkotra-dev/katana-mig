from __future__ import annotations

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from ..api.deps import AuthApiError, get_central_team_user, get_current_user, get_db
from ..api.schemas import RunCheckpointResponse, RunCreateRequest, RunResponse
from ..db.models import RunRecord, User
from ..execution.engine import execute_run, get_run, list_run_checkpoints, list_runs_for_project, pause_run
from ..management.access import require_project_access
from ..management.platform import record_management_audit
from ..db.models import SourceDefinition, new_id
from sqlalchemy import select

router = APIRouter(prefix="/projects/{project_id}/runs", tags=["runs"])


@router.post("", response_model=RunResponse, status_code=status.HTTP_201_CREATED)
def post_run(
    project_id: str,
    body: RunCreateRequest,
    actor: User = Depends(get_central_team_user),
    db: Session = Depends(get_db),
) -> RunResponse:
    source_definition = db.scalar(
        select(SourceDefinition).where(
            SourceDefinition.project_id == project_id,
            SourceDefinition.source_definition_id == body.source_definition_id,
        )
    )
    if source_definition is None:
        raise AuthApiError("source_definition_not_found", "Source definition not found.", 404)
    run = RunRecord(
        run_id=new_id(),
        project_id=project_id,
        destination_object_name=body.destination_object_name,
        source_definition_reference=body.source_definition_id,
        environment=body.environment,
        status="queued",
    )
    db.add(run)
    db.flush()
    record_management_audit(
        db,
        project_id=project_id,
        actor_user_id=actor.user_id,
        event_type="run_created",
        payload={
            "run_id": run.run_id,
            "source_definition_id": body.source_definition_id,
            "destination_object_name": body.destination_object_name,
        },
    )
    db.commit()
    return RunResponse.model_validate(get_run(db, project_id=project_id, run_id=run.run_id))


@router.get("", response_model=list[RunResponse])
def get_runs(
    project_id: str,
    actor: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[RunResponse]:
    require_project_access(db, user=actor, project_id=project_id)
    return [RunResponse.model_validate(item) for item in list_runs_for_project(db, project_id=project_id)]


@router.get("/{run_id}", response_model=RunResponse)
def get_run_by_id(
    project_id: str,
    run_id: str,
    actor: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> RunResponse:
    require_project_access(db, user=actor, project_id=project_id)
    return RunResponse.model_validate(get_run(db, project_id=project_id, run_id=run_id))


@router.post("/{run_id}/launch", response_model=RunResponse)
def post_run_launch(
    project_id: str,
    run_id: str,
    actor: User = Depends(get_central_team_user),
    db: Session = Depends(get_db),
) -> RunResponse:
    return RunResponse.model_validate(execute_run(db, run_id=run_id, actor_user_id=actor.user_id, resume=False))


@router.post("/{run_id}/pause", response_model=RunResponse)
def post_run_pause(
    project_id: str,
    run_id: str,
    actor: User = Depends(get_central_team_user),
    db: Session = Depends(get_db),
) -> RunResponse:
    return RunResponse.model_validate(pause_run(db, project_id=project_id, run_id=run_id, actor_user_id=actor.user_id))


@router.post("/{run_id}/resume", response_model=RunResponse)
def post_run_resume(
    project_id: str,
    run_id: str,
    actor: User = Depends(get_central_team_user),
    db: Session = Depends(get_db),
) -> RunResponse:
    return RunResponse.model_validate(
        execute_run(db, run_id=run_id, actor_user_id=actor.user_id, resume=True)
    )


@router.get("/{run_id}/checkpoints", response_model=list[RunCheckpointResponse])
def get_run_checkpoints(
    project_id: str,
    run_id: str,
    actor: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[RunCheckpointResponse]:
    require_project_access(db, user=actor, project_id=project_id)
    return [RunCheckpointResponse.model_validate(item) for item in list_run_checkpoints(db, project_id=project_id, run_id=run_id)]
