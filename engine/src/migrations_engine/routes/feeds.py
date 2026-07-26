from __future__ import annotations

from datetime import UTC, datetime as _dt

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..api.deps import AuthApiError, get_central_team_user, get_current_user, get_db
from ..api.schemas import FeedCreateRequest, FeedResponse, FeedSliceResponse, FeedMappingHintsRequest, TransformationInstructionsRequest
from ..db.models import User, Feed, VersionHistory
from ..management.access import require_project_access
from ..management.feeds import (
    create_source_contract,
    discard_feed,
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
    require_project_access(db, user=actor, project_id=project_id)
    return create_source_contract(db, actor=actor, project_id=project_id, body=body)


@router.get("", response_model=list[FeedResponse])
def get_source_contracts(
    project_id: str,
    include_discarded: bool = False,
    actor: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[FeedResponse]:
    require_project_access(db, user=actor, project_id=project_id)
    return list_source_contracts(db, project_id=project_id, include_discarded=include_discarded)


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
    require_project_access(db, user=actor, project_id=project_id)
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
    require_project_access(db, user=actor, project_id=project_id)
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
    masked: bool = True,
    actor: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[FeedSliceResponse]:
    require_project_access(db, user=actor, project_id=project_id)
    if not masked:
        from ..roles import ADMIN_ROLE, PM_ROLE, CENTRAL_TEAM_ROLE
        if actor.role not in {ADMIN_ROLE, PM_ROLE, CENTRAL_TEAM_ROLE}:
            raise AuthApiError("forbidden", "Only admin, PM, or operator can request unmasked data.", 403)
    return list_source_slices(db, project_id=project_id, source_definition_id=source_definition_id, masked=masked)


@router.get("/{source_definition_id}/slices/{source_slice_id}", response_model=FeedSliceResponse)
def get_source_slice_by_id(
    project_id: str,
    source_definition_id: str,
    source_slice_id: str,
    masked: bool = True,
    actor: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FeedSliceResponse:
    require_project_access(db, user=actor, project_id=project_id)
    if not masked:
        from ..roles import ADMIN_ROLE, PM_ROLE, CENTRAL_TEAM_ROLE
        if actor.role not in {ADMIN_ROLE, PM_ROLE, CENTRAL_TEAM_ROLE}:
            raise AuthApiError("forbidden", "Only admin, PM, or operator can request unmasked data.", 403)
    return get_source_slice(
        db,
        project_id=project_id,
        source_definition_id=source_definition_id,
        source_slice_id=source_slice_id,
        masked=masked,
    )


@router.delete("/{source_definition_id}", response_model=FeedResponse)
def delete_source_contract(
    project_id: str,
    source_definition_id: str,
    actor: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FeedResponse:
    from ..roles import ADMIN_ROLE, CENTRAL_TEAM_ROLE
    if actor.role not in {ADMIN_ROLE, CENTRAL_TEAM_ROLE}:
        raise AuthApiError("forbidden", "Admin or central team access is required.", 403)
    require_project_access(db, user=actor, project_id=project_id)
    return discard_feed(db, actor=actor, project_id=project_id, source_definition_id=source_definition_id)


@router.patch("/{source_definition_id}/hints", response_model=FeedResponse)
def patch_source_hints(
    project_id: str,
    source_definition_id: str,
    body: FeedMappingHintsRequest,
    actor: User = Depends(get_central_team_user),
    db: Session = Depends(get_db),
) -> FeedResponse:
    require_project_access(db, user=actor, project_id=project_id)
    feed = db.get(Feed, source_definition_id)
    if feed is None or feed.project_id != project_id:
        raise AuthApiError("feed_not_found", "Feed not found.", 404)
    _old = feed.mapping_hints
    feed.mapping_hints = body.mapping_hints
    db.add(VersionHistory(
        entity_type="hints",
        entity_id=source_definition_id,
        field_name="mapping_hints",
        old_value=_old,
        new_value=body.mapping_hints,
        changed_by=actor.user_id,
        changed_at=_dt.now(UTC),
    ))
    db.commit()
    db.refresh(feed)
    return get_source_contract(db, project_id=project_id, source_definition_id=source_definition_id)


@router.patch("/{source_definition_id}/transformation-instructions", response_model=FeedResponse)
def patch_source_transformation_instructions(
    project_id: str,
    source_definition_id: str,
    body: TransformationInstructionsRequest,
    actor: User = Depends(get_central_team_user),
    db: Session = Depends(get_db),
) -> FeedResponse:
    require_project_access(db, user=actor, project_id=project_id)
    feed = db.get(Feed, source_definition_id)
    if feed is None or feed.project_id != project_id:
        raise AuthApiError("feed_not_found", "Feed not found.", 404)
    _old = feed.transformation_instructions
    feed.transformation_instructions = body.transformation_instructions
    db.add(VersionHistory(
        entity_type="transformation",
        entity_id=source_definition_id,
        field_name="transformation_instructions",
        old_value=_old,
        new_value=body.transformation_instructions,
        changed_by=actor.user_id,
        changed_at=_dt.now(UTC),
    ))
    db.commit()
    db.refresh(feed)
    return get_source_contract(db, project_id=project_id, source_definition_id=source_definition_id)
