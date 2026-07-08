from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..api.deps import get_central_team_user, get_current_user, get_db
from ..api.schemas import (
    FeedSliceRejectRequest,
    FeedSliceResubmitRequest,
    FeedSliceResponse,
)
from ..db.models import User
from ..management.access import require_project_access, require_project_stakeholder
from ..management.feeds import (
    approve_source_slice,
    reject_source_slice,
    resubmit_source_slice,
)

router = APIRouter(tags=["approvals"])


@router.post(
    "/projects/{project_id}/sources/{source_definition_id}/slices/{source_slice_id}/approve",
    response_model=FeedSliceResponse,
)
def post_source_slice_approve(
    project_id: str,
    source_definition_id: str,
    source_slice_id: str,
    actor: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FeedSliceResponse:
    require_project_access(db, user=actor, project_id=project_id)
    require_project_stakeholder(actor)
    return approve_source_slice(
        db,
        actor=actor,
        project_id=project_id,
        source_definition_id=source_definition_id,
        source_slice_id=source_slice_id,
    )


@router.post(
    "/projects/{project_id}/sources/{source_definition_id}/slices/{source_slice_id}/reject",
    response_model=FeedSliceResponse,
)
def post_source_slice_reject(
    project_id: str,
    source_definition_id: str,
    source_slice_id: str,
    body: FeedSliceRejectRequest,
    actor: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FeedSliceResponse:
    require_project_access(db, user=actor, project_id=project_id)
    require_project_stakeholder(actor)
    return reject_source_slice(
        db,
        actor=actor,
        project_id=project_id,
        source_definition_id=source_definition_id,
        source_slice_id=source_slice_id,
        body=body,
    )


@router.post(
    "/projects/{project_id}/sources/{source_definition_id}/slices/{source_slice_id}/resubmit",
    response_model=FeedSliceResponse,
)
def post_source_slice_resubmit(
    project_id: str,
    source_definition_id: str,
    source_slice_id: str,
    body: FeedSliceResubmitRequest,
    actor: User = Depends(get_central_team_user),
    db: Session = Depends(get_db),
) -> FeedSliceResponse:
    require_project_access(db, user=actor, project_id=project_id)
    return resubmit_source_slice(
        db,
        actor=actor,
        project_id=project_id,
        source_definition_id=source_definition_id,
        source_slice_id=source_slice_id,
        body=body,
    )
