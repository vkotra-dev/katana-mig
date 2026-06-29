from __future__ import annotations

from fastapi import APIRouter, Depends, Response, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..api.deps import get_central_team_user, get_db
from ..api.schemas import MembershipResponse, ProjectMemberResponse
from ..db.models import User
from ..management.service import (
    add_project_member,
    list_project_members,
    remove_project_member,
)

router = APIRouter(prefix="/projects", tags=["projects"])


class AddMemberRequest(BaseModel):
    user_id: str


@router.get("/{project_id}/members", response_model=list[ProjectMemberResponse])
def get_project_members(
    project_id: str,
    _actor: User = Depends(get_central_team_user),
    db: Session = Depends(get_db),
) -> list[ProjectMemberResponse]:
    return list_project_members(db, project_id=project_id)


@router.post("/{project_id}/members", response_model=MembershipResponse)
def post_project_member(
    project_id: str,
    body: AddMemberRequest,
    actor: User = Depends(get_central_team_user),
    db: Session = Depends(get_db),
) -> MembershipResponse:
    return add_project_member(
        db,
        actor=actor,
        project_id=project_id,
        user_id=body.user_id,
    )


@router.delete("/{project_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project_member(
    project_id: str,
    user_id: str,
    actor: User = Depends(get_central_team_user),
    db: Session = Depends(get_db),
) -> Response:
    remove_project_member(db, actor=actor, project_id=project_id, user_id=user_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
