from __future__ import annotations

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from ..api.deps import get_central_team_user, get_current_user, get_db
from ..api.schemas import UserCreateRequest, UserResponse, UserUpdateRequest
from ..db.models import User
from ..management.access import require_central_team_or_self
from ..management.service import (
    create_user,
    get_user,
    list_users,
    soft_delete_user,
    update_user,
)

router = APIRouter(prefix="/users", tags=["users"])


@router.get("", response_model=list[UserResponse])
def get_users(
    _actor: User = Depends(get_central_team_user),
    db: Session = Depends(get_db),
) -> list[UserResponse]:
    return list_users(db)


@router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def post_user(
    body: UserCreateRequest,
    actor: User = Depends(get_central_team_user),
    db: Session = Depends(get_db),
) -> UserResponse:
    return create_user(db, actor=actor, body=body)


@router.get("/{user_id}", response_model=UserResponse)
def get_user_by_id(
    user_id: str,
    actor: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> UserResponse:
    require_central_team_or_self(actor, user_id)
    return get_user(db, user_id=user_id)


@router.patch("/{user_id}", response_model=UserResponse)
def patch_user(
    user_id: str,
    body: UserUpdateRequest,
    actor: User = Depends(get_central_team_user),
    db: Session = Depends(get_db),
) -> UserResponse:
    return update_user(db, actor=actor, user_id=user_id, body=body)


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(
    user_id: str,
    actor: User = Depends(get_central_team_user),
    db: Session = Depends(get_db),
) -> Response:
    soft_delete_user(db, actor=actor, user_id=user_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
