from __future__ import annotations

from fastapi import APIRouter, Depends, status, Query
from sqlalchemy.orm import Session

from ..api.deps import get_central_team_user, get_current_user, get_db
from ..api.schemas import (
    LookupSnapshotGenerateRequest,
    LookupSnapshotResponse,
    LookupValueMapCreateRequest,
    LookupValueMapPatchRequest,
    LookupValueMapResponse,
)
from ..db.models import User
from ..management.access import require_project_access, require_project_stakeholder
from ..management.lookup_mapping import (
    approve_lookup_snapshot,
    create_lookup_value_map,
    generate_lookup_snapshot,
    list_lookup_value_maps,
    update_lookup_value_map,
)

router = APIRouter(tags=["lookup"])


@router.post(
    "/projects/{project_id}/lookup-maps",
    response_model=LookupValueMapResponse,
    status_code=status.HTTP_201_CREATED,
)
def post_lookup_value_map(
    project_id: str,
    body: LookupValueMapCreateRequest,
    actor: User = Depends(get_central_team_user),
    db: Session = Depends(get_db),
) -> LookupValueMapResponse:
    require_project_access(db, user=actor, project_id=project_id)
    return create_lookup_value_map(
        db,
        actor=actor,
        project_id=project_id,
        body=body,
    )


@router.get("/projects/{project_id}/lookup-maps", response_model=list[LookupValueMapResponse])
def get_lookup_value_maps(
    project_id: str,
    feed_id: str | None = Query(default=None),
    actor: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[LookupValueMapResponse]:
    require_project_access(db, user=actor, project_id=project_id)
    return list_lookup_value_maps(
        db,
        project_id=project_id,
        feed_id=feed_id,
    )


@router.patch(
    "/projects/{project_id}/lookup-maps/{lookup_value_map_id}",
    response_model=LookupValueMapResponse,
)
def patch_lookup_value_map(
    project_id: str,
    lookup_value_map_id: str,
    body: LookupValueMapPatchRequest,
    actor: User = Depends(get_central_team_user),
    db: Session = Depends(get_db),
) -> LookupValueMapResponse:
    require_project_access(db, user=actor, project_id=project_id)
    return update_lookup_value_map(
        db,
        project_id=project_id,
        lookup_value_map_id=lookup_value_map_id,
        body=body,
    )


@router.post(
    "/projects/{project_id}/sources/{source_definition_id}/lookup-snapshots",
    response_model=LookupSnapshotResponse,
    status_code=status.HTTP_201_CREATED,
)
def post_lookup_snapshot(
    project_id: str,
    source_definition_id: str,
    body: LookupSnapshotGenerateRequest,
    actor: User = Depends(get_central_team_user),
    db: Session = Depends(get_db),
) -> LookupSnapshotResponse:
    require_project_access(db, user=actor, project_id=project_id)
    return generate_lookup_snapshot(
        db,
        actor=actor,
        project_id=project_id,
        source_definition_id=source_definition_id,
        body=body,
    )


@router.post(
    "/projects/{project_id}/lookup-snapshots/{lookup_snapshot_id}/approve",
    response_model=LookupSnapshotResponse,
)
def post_lookup_snapshot_approval(
    project_id: str,
    lookup_snapshot_id: str,
    actor: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> LookupSnapshotResponse:
    require_project_access(db, user=actor, project_id=project_id)
    require_project_stakeholder(actor)
    return approve_lookup_snapshot(
        db,
        actor=actor,
        project_id=project_id,
        source_definition_id="",  # approved globally in project scope
        lookup_snapshot_id=lookup_snapshot_id,
    )
