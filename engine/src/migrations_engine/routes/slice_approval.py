from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..api.deps import get_central_team_user, get_current_user, get_db
from ..api.schemas import (
    SourceSliceApprovalCountResponse,
    SourceSliceApprovalItemResponse,
    SourceSliceRejectRequest,
    SourceSliceResubmitRequest,
    SourceSliceResponse,
)
from ..db.models import User
from ..management.sources import (
    approve_source_slice,
    count_pending_approvals,
    list_pending_approvals,
    reject_source_slice,
    resubmit_source_slice,
)

router = APIRouter(tags=["approvals"])


@router.get("/approvals", response_model=list[SourceSliceApprovalItemResponse])
def get_approvals(
    actor: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[SourceSliceApprovalItemResponse]:
    return list_pending_approvals(db, actor=actor)


@router.get("/approvals/count", response_model=SourceSliceApprovalCountResponse)
def get_approvals_count(
    actor: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SourceSliceApprovalCountResponse:
    return count_pending_approvals(db, actor=actor)


@router.post(
    "/projects/{project_id}/sources/{source_definition_id}/slices/{source_slice_id}/approve",
    response_model=SourceSliceResponse,
)
def post_source_slice_approve(
    project_id: str,
    source_definition_id: str,
    source_slice_id: str,
    actor: User = Depends(get_central_team_user),
    db: Session = Depends(get_db),
) -> SourceSliceResponse:
    return approve_source_slice(
        db,
        actor=actor,
        project_id=project_id,
        source_definition_id=source_definition_id,
        source_slice_id=source_slice_id,
    )


@router.post(
    "/projects/{project_id}/sources/{source_definition_id}/slices/{source_slice_id}/reject",
    response_model=SourceSliceResponse,
)
def post_source_slice_reject(
    project_id: str,
    source_definition_id: str,
    source_slice_id: str,
    body: SourceSliceRejectRequest,
    actor: User = Depends(get_central_team_user),
    db: Session = Depends(get_db),
) -> SourceSliceResponse:
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
    response_model=SourceSliceResponse,
)
def post_source_slice_resubmit(
    project_id: str,
    source_definition_id: str,
    source_slice_id: str,
    body: SourceSliceResubmitRequest,
    actor: User = Depends(get_central_team_user),
    db: Session = Depends(get_db),
) -> SourceSliceResponse:
    return resubmit_source_slice(
        db,
        actor=actor,
        project_id=project_id,
        source_definition_id=source_definition_id,
        source_slice_id=source_slice_id,
        body=body,
    )
