from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..api.deps import get_current_user, get_db
from ..api.schemas import (
    ChangeRequestDetail,
    ChangeRequestResolveRequest,
    ChangeRequestResolveResponse,
    ChangeRequestSummary,
)
from ..db.models import User
from ..management.access import require_project_access
from ..management.change_requests import get_change_request, list_change_requests, resolve_change_request

router = APIRouter(prefix="/projects", tags=["change-requests"])


@router.get("/{project_id}/change-requests", response_model=list[ChangeRequestSummary])
def get_change_requests(
    project_id: str,
    actor: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[ChangeRequestSummary]:
    require_project_access(db, user=actor, project_id=project_id)
    return list_change_requests(db, project_id=project_id)


@router.get("/{project_id}/change-requests/{cr_id}", response_model=ChangeRequestDetail)
def get_change_request_by_id(
    project_id: str,
    cr_id: str,
    actor: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ChangeRequestDetail:
    require_project_access(db, user=actor, project_id=project_id)
    return get_change_request(db, project_id=project_id, change_request_id=cr_id)


@router.post("/{project_id}/change-requests/{cr_id}/resolve", response_model=ChangeRequestResolveResponse)
def post_resolve_change_request(
    project_id: str,
    cr_id: str,
    body: ChangeRequestResolveRequest,
    actor: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ChangeRequestResolveResponse:
    return resolve_change_request(
        db,
        actor=actor,
        project_id=project_id,
        change_request_id=cr_id,
        accepted_value=body.accepted_value,
    )
