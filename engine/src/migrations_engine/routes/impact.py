from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..api.deps import get_central_team_user, get_current_user, get_db
from ..api.schemas import ImpactReportResponse, RunResponse
from ..db.models import User
from ..management.access import require_project_access
from ..management.impact import acknowledge_impact, get_impact_report

router = APIRouter(prefix="/projects/{project_id}/runs/{run_id}/impact", tags=["impact"])


@router.get("", response_model=ImpactReportResponse)
def read_impact_report(
    project_id: str,
    run_id: str,
    actor: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ImpactReportResponse:
    require_project_access(db, user=actor, project_id=project_id)
    return get_impact_report(db, project_id=project_id, run_id=run_id)


@router.post("/acknowledge", response_model=RunResponse)
def post_acknowledge_impact(
    project_id: str,
    run_id: str,
    actor: User = Depends(get_central_team_user),
    db: Session = Depends(get_db),
) -> RunResponse:
    require_project_access(db, user=actor, project_id=project_id)
    return acknowledge_impact(db, project_id=project_id, run_id=run_id, actor_user_id=actor.user_id)
