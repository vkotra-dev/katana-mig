from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from ..api.deps import get_central_team_user, get_current_user, get_db
from ..api.schemas import FiberCreateRequest, FiberResponse
from ..db.models import User
from ..management.access import require_project_access
from ..management.fibers import create_fiber, get_fiber, list_fibers

router = APIRouter(prefix="/projects/{project_id}/feeds/{feed_id}/fibers", tags=["fibers"])


@router.post("", response_model=FiberResponse, status_code=status.HTTP_201_CREATED)
def post_fiber(
    project_id: str,
    feed_id: str,
    body: FiberCreateRequest,
    actor: User = Depends(get_central_team_user),
    db: Session = Depends(get_db),
) -> FiberResponse:
    return create_fiber(db, actor=actor, project_id=project_id, feed_id=feed_id, body=body)


@router.get("", response_model=list[FiberResponse])
def get_fibers(
    project_id: str,
    feed_id: str,
    actor: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[FiberResponse]:
    require_project_access(db, user=actor, project_id=project_id)
    return list_fibers(db, project_id=project_id, feed_id=feed_id)


@router.get("/{fiber_id}", response_model=FiberResponse)
def get_fiber_by_id(
    project_id: str,
    feed_id: str,
    fiber_id: str,
    actor: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FiberResponse:
    require_project_access(db, user=actor, project_id=project_id)
    return get_fiber(db, project_id=project_id, feed_id=feed_id, fiber_id=fiber_id)
