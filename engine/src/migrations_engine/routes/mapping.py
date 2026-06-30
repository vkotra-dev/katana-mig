from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..api.deps import get_central_team_user, get_current_user, get_db
from ..api.schemas import MappingPatchRequest, MappingRejectRequest, MappingReviewResponse
from ..db.models import User
from ..management.access import require_project_access
from ..mapping.review import approve_mapping, get_mapping, patch_mapping, propose_mapping, reject_mapping

router = APIRouter(prefix="/projects/{project_id}/sources/{source_definition_id}/mapping", tags=["mapping"])


@router.post("/propose", response_model=MappingReviewResponse)
def post_mapping_propose(
    project_id: str,
    source_definition_id: str,
    actor: User = Depends(get_central_team_user),
    db: Session = Depends(get_db),
) -> MappingReviewResponse:
    require_project_access(db, user=actor, project_id=project_id)
    return propose_mapping(
        db,
        project_id=project_id,
        source_definition_id=source_definition_id,
        actor_user_id=actor.user_id,
    )


@router.get("", response_model=MappingReviewResponse)
def get_mapping_snapshot(
    project_id: str,
    source_definition_id: str,
    actor: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MappingReviewResponse:
    require_project_access(db, user=actor, project_id=project_id)
    return get_mapping(
        db,
        project_id=project_id,
        source_definition_id=source_definition_id,
    )


@router.patch("", response_model=MappingReviewResponse)
def patch_mapping_snapshot(
    project_id: str,
    source_definition_id: str,
    body: MappingPatchRequest,
    actor: User = Depends(get_central_team_user),
    db: Session = Depends(get_db),
) -> MappingReviewResponse:
    require_project_access(db, user=actor, project_id=project_id)
    return patch_mapping(
        db,
        project_id=project_id,
        source_definition_id=source_definition_id,
        actor_user_id=actor.user_id,
        field_bindings=body.field_bindings,
    )


@router.post("/approve", response_model=MappingReviewResponse)
def post_mapping_approve(
    project_id: str,
    source_definition_id: str,
    actor: User = Depends(get_central_team_user),
    db: Session = Depends(get_db),
) -> MappingReviewResponse:
    require_project_access(db, user=actor, project_id=project_id)
    return approve_mapping(
        db,
        project_id=project_id,
        source_definition_id=source_definition_id,
        actor_user_id=actor.user_id,
    )


@router.post("/reject", response_model=MappingReviewResponse)
def post_mapping_reject(
    project_id: str,
    source_definition_id: str,
    body: MappingRejectRequest,
    actor: User = Depends(get_central_team_user),
    db: Session = Depends(get_db),
) -> MappingReviewResponse:
    require_project_access(db, user=actor, project_id=project_id)
    return reject_mapping(
        db,
        project_id=project_id,
        source_definition_id=source_definition_id,
        actor_user_id=actor.user_id,
        reason=body.reason,
    )
