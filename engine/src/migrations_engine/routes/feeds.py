from __future__ import annotations

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..api.deps import get_central_team_user, get_current_user, get_db
from ..api.schemas import FeedCreateRequest, FeedResponse, FeedSliceResponse
from ..db.models import User
from ..management.access import require_project_access
from ..management.feeds import (
    create_source_contract,
    get_source_contract,
    get_source_slice,
    list_source_contracts,
    list_source_slices,
    upload_copybook,
    upload_source_slice,
)

router = APIRouter(prefix="/projects/{project_id}/sources", tags=["sources"])


class SourceFileUploadRequest(BaseModel):
    content: str


@router.post("", response_model=FeedResponse, status_code=status.HTTP_201_CREATED)
def post_source_contract(
    project_id: str,
    body: FeedCreateRequest,
    actor: User = Depends(get_central_team_user),
    db: Session = Depends(get_db),
) -> FeedResponse:
    return create_source_contract(db, actor=actor, project_id=project_id, body=body)


@router.get("", response_model=list[FeedResponse])
def get_source_contracts(
    project_id: str,
    actor: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[FeedResponse]:
    require_project_access(db, user=actor, project_id=project_id)
    return list_source_contracts(db, project_id=project_id)


@router.get("/{source_definition_id}", response_model=FeedResponse)
def get_source_contract_by_id(
    project_id: str,
    source_definition_id: str,
    actor: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FeedResponse:
    require_project_access(db, user=actor, project_id=project_id)
    return get_source_contract(db, project_id=project_id, source_definition_id=source_definition_id)


@router.post("/{source_definition_id}/copybook", response_model=FeedResponse)
def post_source_copybook(
    project_id: str,
    source_definition_id: str,
    body: SourceFileUploadRequest,
    actor: User = Depends(get_central_team_user),
    db: Session = Depends(get_db),
) -> FeedResponse:
    return upload_copybook(
        db,
        actor=actor,
        project_id=project_id,
        source_definition_id=source_definition_id,
        raw_bytes=body.content.encode("utf-8"),
    )


@router.post("/{source_definition_id}/slices", response_model=FeedSliceResponse)
def post_source_slice(
    project_id: str,
    source_definition_id: str,
    body: SourceFileUploadRequest,
    actor: User = Depends(get_central_team_user),
    db: Session = Depends(get_db),
) -> FeedSliceResponse:
    return upload_source_slice(
        db,
        actor=actor,
        project_id=project_id,
        source_definition_id=source_definition_id,
        raw_bytes=body.content.encode("utf-8"),
    )


@router.get("/{source_definition_id}/slices", response_model=list[FeedSliceResponse])
def get_source_slices(
    project_id: str,
    source_definition_id: str,
    actor: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[FeedSliceResponse]:
    require_project_access(db, user=actor, project_id=project_id)
    return list_source_slices(db, project_id=project_id, source_definition_id=source_definition_id)


@router.get("/{source_definition_id}/slices/{source_slice_id}", response_model=FeedSliceResponse)
def get_source_slice_by_id(
    project_id: str,
    source_definition_id: str,
    source_slice_id: str,
    actor: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FeedSliceResponse:
    require_project_access(db, user=actor, project_id=project_id)
    return get_source_slice(
        db,
        project_id=project_id,
        source_definition_id=source_definition_id,
        source_slice_id=source_slice_id,
    )
