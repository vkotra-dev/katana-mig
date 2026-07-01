from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..api.deps import get_central_team_user, get_current_user, get_db
from ..api.schemas import (
    FeedSliceApprovalCountResponse,
    FeedSliceApprovalItemResponse,
    FeedSliceRejectRequest,
    FeedSliceResubmitRequest,
    FeedSliceResponse,
)
from ..db.models import User
from ..management.feeds import (
    approve_source_slice,
    count_pending_approvals,
    list_pending_approvals,
    reject_source_slice,
    resubmit_source_slice,
)

router = APIRouter(tags=["approvals"])


@router.get("/approvals", response_model=list[FeedSliceApprovalItemResponse])
def get_approvals(
    actor: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[FeedSliceApprovalItemResponse]:
    return list_pending_approvals(db, actor=actor)


@router.get("/approvals/count", response_model=FeedSliceApprovalCountResponse)
def get_approvals_count(
    actor: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FeedSliceApprovalCountResponse:
    return count_pending_approvals(db, actor=actor)


@router.post(
    "/projects/{project_id}/sources/{source_definition_id}/slices/{source_slice_id}/approve",
    response_model=FeedSliceResponse,
)
def post_source_slice_approve(
    project_id: str,
    source_definition_id: str,
    source_slice_id: str,
    actor: User = Depends(get_central_team_user),
    db: Session = Depends(get_db),
) -> FeedSliceResponse:
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
    actor: User = Depends(get_central_team_user),
    db: Session = Depends(get_db),
) -> FeedSliceResponse:
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
    return resubmit_source_slice(
        db,
        actor=actor,
        project_id=project_id,
        source_definition_id=source_definition_id,
        source_slice_id=source_slice_id,
        body=body,
    )
