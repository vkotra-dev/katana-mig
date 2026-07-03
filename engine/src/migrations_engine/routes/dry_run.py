from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..api.deps import get_central_team_user, get_current_user, get_db
from ..api.schemas import DryRunArtifactResponse, PushBackRequest, RunResponse
from ..db.models import User
from ..management.access import require_project_access
from ..management.dry_run import approve_dry_run, get_dry_run_artifact, push_back_dry_run

router = APIRouter(prefix="/projects/{project_id}/runs/{run_id}/dry-run", tags=["dry-run"])


@router.get("", response_model=DryRunArtifactResponse)
def read_dry_run_artifact(
    project_id: str,
    run_id: str,
    actor: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DryRunArtifactResponse:
    require_project_access(db, user=actor, project_id=project_id)
    return get_dry_run_artifact(db, project_id=project_id, run_id=run_id)


@router.post("/approve", response_model=RunResponse)
def post_approve_dry_run(
    project_id: str,
    run_id: str,
    actor: User = Depends(get_central_team_user),
    db: Session = Depends(get_db),
) -> RunResponse:
    require_project_access(db, user=actor, project_id=project_id)
    return approve_dry_run(db, project_id=project_id, run_id=run_id, actor_user_id=actor.user_id)


@router.post("/push-back", response_model=RunResponse)
def post_push_back_dry_run(
    project_id: str,
    run_id: str,
    body: PushBackRequest,
    actor: User = Depends(get_central_team_user),
    db: Session = Depends(get_db),
) -> RunResponse:
    require_project_access(db, user=actor, project_id=project_id)
    return push_back_dry_run(
        db,
        project_id=project_id,
        run_id=run_id,
        actor_user_id=actor.user_id,
        body=body,
    )
