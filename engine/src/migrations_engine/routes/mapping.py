from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..api.deps import get_central_team_user, get_current_user, get_db
from ..api.schemas import MappingPatchRequest, MappingRevisionRequest, MappingReviewResponse
from ..db.models import User
from ..management.access import require_project_access, require_project_stakeholder
from ..mapping.review import approve_mapping, get_mapping, patch_mapping, reject_mapping, request_revision, unapprove_mapping
from ..mapping.proposal import propose_mapping
from ..roles import PM_ROLE, ADMIN_ROLE
from ..api.deps import AuthApiError

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
    destination_object_name: str | None = None,
    actor: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MappingReviewResponse:
    require_project_access(db, user=actor, project_id=project_id)
    return get_mapping(
        db,
        project_id=project_id,
        source_definition_id=source_definition_id,
        destination_object_name=destination_object_name,
    )


@router.patch("", response_model=MappingReviewResponse)
def patch_mapping_snapshot(
    project_id: str,
    source_definition_id: str,
    body: MappingPatchRequest,
    destination_object_name: str | None = None,
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
        destination_object_name=destination_object_name,
    )


@router.post("/approve", response_model=MappingReviewResponse)
def post_mapping_approve(
    project_id: str,
    source_definition_id: str,
    destination_object_name: str | None = None,
    actor: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MappingReviewResponse:
    require_project_access(db, user=actor, project_id=project_id)
    require_project_stakeholder(actor)
    return approve_mapping(
        db,
        project_id=project_id,
        source_definition_id=source_definition_id,
        actor_user_id=actor.user_id,
        destination_object_name=destination_object_name,
    )


@router.post("/revision", response_model=MappingReviewResponse)
def post_mapping_revision(
    project_id: str,
    source_definition_id: str,
    body: MappingRevisionRequest,
    destination_object_name: str | None = None,
    actor: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MappingReviewResponse:
    require_project_access(db, user=actor, project_id=project_id)
    require_project_stakeholder(actor)
    return request_revision(
        db,
        project_id=project_id,
        source_definition_id=source_definition_id,
        actor_user_id=actor.user_id,
        reason=body.reason,
        destination_object_name=destination_object_name,
    )


@router.post("/unapprove", response_model=MappingReviewResponse)
def post_mapping_unapprove(
    project_id: str,
    source_definition_id: str,
    destination_object_name: str | None = None,
    actor: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MappingReviewResponse:
    require_project_access(db, user=actor, project_id=project_id)
    if actor.role not in {PM_ROLE, ADMIN_ROLE}:
        raise AuthApiError("forbidden", "Only project managers or administrators can unapprove mappings.", 403)
    return unapprove_mapping(
        db,
        project_id=project_id,
        source_definition_id=source_definition_id,
        actor_user_id=actor.user_id,
        destination_object_name=destination_object_name,
    )


@router.post("/reject", response_model=MappingReviewResponse)
def post_mapping_reject(
    project_id: str,
    source_definition_id: str,
    destination_object_name: str | None = None,
    actor: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MappingReviewResponse:
    require_project_access(db, user=actor, project_id=project_id)
    if actor.role not in {PM_ROLE, ADMIN_ROLE}:
        raise AuthApiError("forbidden", "Only project managers or administrators can reject mappings.", 403)
    return reject_mapping(
        db,
        project_id=project_id,
        source_definition_id=source_definition_id,
        actor_user_id=actor.user_id,
        destination_object_name=destination_object_name,
    )
