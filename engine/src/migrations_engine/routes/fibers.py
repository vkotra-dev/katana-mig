from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from ..api.deps import get_central_team_user, get_current_user, get_db
from ..api.schemas import (
    FiberCreateRequest,
    FiberResponse,
    LookupDestEntryResponse,
    LookupDestFeedCreateRequest,
    LookupDestFeedResponse,
    LookupInputsRequest,
    LookupMappingPatchRequest,
    LookupMappingResponse,
    LookupSourceEntriesCreateRequest,
    LookupSourceEntryResponse,
)
from ..db.models import User
from ..management.access import require_non_auditor, require_project_access
from ..management.fibers import (
    add_source_entries,
    analyze_feed,
    create_fiber,
    create_or_replace_dest_feed,
    get_fiber,
    list_dest_entries,
    list_fibers,
    list_mappings,
    list_source_entries,
    patch_mapping,
    submit_lookup_inputs,
)

router = APIRouter(prefix="/projects/{project_id}/feeds/{feed_id}/fibers", tags=["fibers"])
feeds_router = APIRouter(prefix="/projects/{project_id}/feeds/{feed_id}", tags=["fibers"])


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


@feeds_router.post("/analyze", response_model=list[FiberResponse], status_code=status.HTTP_200_OK)
def post_analyze_feed(
    project_id: str,
    feed_id: str,
    actor: User = Depends(get_central_team_user),
    db: Session = Depends(get_db),
) -> list[FiberResponse]:
    return analyze_feed(db, feed_id=feed_id, project_id=project_id, actor=actor)


@router.post("/{fiber_id}/lookup-inputs", response_model=FiberResponse, status_code=status.HTTP_200_OK)
def post_lookup_inputs(
    project_id: str,
    feed_id: str,
    fiber_id: str,
    body: LookupInputsRequest,
    actor: User = Depends(get_central_team_user),
    db: Session = Depends(get_db),
) -> FiberResponse:
    return submit_lookup_inputs(db, feed_id=feed_id, fiber_id=fiber_id, project_id=project_id, body=body)


@router.get("/{fiber_id}/source-entries", response_model=list[LookupSourceEntryResponse])
def get_source_entries(
    project_id: str,
    feed_id: str,
    fiber_id: str,
    actor: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[LookupSourceEntryResponse]:
    require_project_access(db, user=actor, project_id=project_id)
    return list_source_entries(db, feed_id=feed_id, fiber_id=fiber_id, project_id=project_id)


@router.post("/{fiber_id}/source-entries", response_model=list[LookupSourceEntryResponse], status_code=status.HTTP_201_CREATED)
def post_source_entries(
    project_id: str,
    feed_id: str,
    fiber_id: str,
    body: LookupSourceEntriesCreateRequest,
    actor: User = Depends(get_central_team_user),
    db: Session = Depends(get_db),
) -> list[LookupSourceEntryResponse]:
    return add_source_entries(db, feed_id=feed_id, fiber_id=fiber_id, project_id=project_id, body=body)


@router.post("/{fiber_id}/dest-feed", response_model=LookupDestFeedResponse, status_code=status.HTTP_201_CREATED)
def post_dest_feed(
    project_id: str,
    feed_id: str,
    fiber_id: str,
    body: LookupDestFeedCreateRequest,
    actor: User = Depends(get_central_team_user),
    db: Session = Depends(get_db),
) -> LookupDestFeedResponse:
    return create_or_replace_dest_feed(db, feed_id=feed_id, fiber_id=fiber_id, project_id=project_id, body=body)


@router.get("/{fiber_id}/dest-feed/entries", response_model=list[LookupDestEntryResponse])
def get_dest_feed_entries(
    project_id: str,
    feed_id: str,
    fiber_id: str,
    actor: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[LookupDestEntryResponse]:
    require_project_access(db, user=actor, project_id=project_id)
    return list_dest_entries(db, feed_id=feed_id, fiber_id=fiber_id, project_id=project_id)


@router.get("/{fiber_id}/mappings", response_model=list[LookupMappingResponse])
def get_mappings(
    project_id: str,
    feed_id: str,
    fiber_id: str,
    actor: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[LookupMappingResponse]:
    require_project_access(db, user=actor, project_id=project_id)
    return list_mappings(db, feed_id=feed_id, fiber_id=fiber_id, project_id=project_id)


@router.patch("/{fiber_id}/mappings/{mapping_id}", response_model=LookupMappingResponse, status_code=status.HTTP_200_OK)
def patch_mapping_by_id(
    project_id: str,
    feed_id: str,
    fiber_id: str,
    mapping_id: str,
    body: LookupMappingPatchRequest,
    actor: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> LookupMappingResponse:
    require_non_auditor(actor)
    require_project_access(db, user=actor, project_id=project_id)
    return patch_mapping(db, feed_id=feed_id, fiber_id=fiber_id, mapping_id=mapping_id, project_id=project_id, body=body)
