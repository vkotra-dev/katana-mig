from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from ..api.deps import get_current_user, get_db
from ..api.schemas import (
    SignOffStatusResponse,
    SignBindingRequest,
    UnsignBindingRequest,
    PokeRequest,
)
from ..db.models import User
from ..management.access import require_project_access
from ..management.sign_offs import (
    sign_binding,
    unsign_binding,
    sign_lookup,
    unsign_lookup,
    get_sign_off_status,
    push_for_review,
    poke_reviewer,
)

router = APIRouter(
    prefix="/projects/{project_id}/sources/{source_definition_id}",
    tags=["sign-offs"],
)


@router.post("/mapping/sign-off", response_model=SignOffStatusResponse)
def post_sign_binding(
    project_id: str,
    source_definition_id: str,
    body: SignBindingRequest,
    actor: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SignOffStatusResponse:
    require_project_access(db, user=actor, project_id=project_id)
    return sign_binding(
        db,
        actor=actor,
        project_id=project_id,
        source_definition_id=source_definition_id,
        destination_object_name=body.destination_object_name,
        source_field=body.source_field,
        destination_field=body.destination_field,
    )


@router.delete("/mapping/sign-off", response_model=SignOffStatusResponse)
def delete_unsign_binding(
    project_id: str,
    source_definition_id: str,
    body: UnsignBindingRequest,
    actor: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SignOffStatusResponse:
    require_project_access(db, user=actor, project_id=project_id)
    return unsign_binding(
        db,
        actor=actor,
        project_id=project_id,
        source_definition_id=source_definition_id,
        destination_object_name=body.destination_object_name,
        source_field=body.source_field,
        destination_field=body.destination_field,
    )


@router.post("/lookups/{lookup_value_map_id}/sign-off", response_model=SignOffStatusResponse)
def post_sign_lookup(
    project_id: str,
    source_definition_id: str,
    lookup_value_map_id: str,
    actor: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SignOffStatusResponse:
    require_project_access(db, user=actor, project_id=project_id)
    return sign_lookup(
        db,
        actor=actor,
        project_id=project_id,
        source_definition_id=source_definition_id,
        lookup_value_map_id=lookup_value_map_id,
    )


@router.delete("/lookups/{lookup_value_map_id}/sign-off", response_model=SignOffStatusResponse)
def delete_unsign_lookup(
    project_id: str,
    source_definition_id: str,
    lookup_value_map_id: str,
    actor: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SignOffStatusResponse:
    require_project_access(db, user=actor, project_id=project_id)
    return unsign_lookup(
        db,
        actor=actor,
        project_id=project_id,
        source_definition_id=source_definition_id,
        lookup_value_map_id=lookup_value_map_id,
    )


@router.get("/sign-off-status", response_model=SignOffStatusResponse)
def get_status(
    project_id: str,
    source_definition_id: str,
    actor: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SignOffStatusResponse:
    require_project_access(db, user=actor, project_id=project_id)
    return get_sign_off_status(
        db,
        project_id=project_id,
        source_definition_id=source_definition_id,
    )


@router.post("/push-for-review", response_model=SignOffStatusResponse)
def post_push_for_review(
    project_id: str,
    source_definition_id: str,
    actor: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SignOffStatusResponse:
    require_project_access(db, user=actor, project_id=project_id)
    return push_for_review(
        db,
        actor=actor,
        project_id=project_id,
        source_definition_id=source_definition_id,
    )


@router.post("/review/poke", status_code=status.HTTP_204_NO_CONTENT)
def post_poke(
    project_id: str,
    source_definition_id: str,
    body: PokeRequest,
    actor: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    require_project_access(db, user=actor, project_id=project_id)
    poke_reviewer(
        db,
        actor=actor,
        project_id=project_id,
        source_definition_id=source_definition_id,
        target_role=body.target_role,
    )
