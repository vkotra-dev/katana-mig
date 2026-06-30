from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Response, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..api.deps import (
    get_central_team_user,
    get_current_user,
    get_db,
    get_project_initiation_user,
)
from ..api.schemas import (
    MembershipResponse,
    ProjectCreateRequest,
    ProjectMemberResponse,
    ProjectResponse,
    ProjectUpdateRequest,
)
from ..db.models import User
from ..management.access import require_project_access
from ..management.projects import archive_project, create_project, get_project, list_projects, update_project
from ..management.service import add_project_member, list_project_members, remove_project_member

router = APIRouter(prefix="/projects", tags=["projects"])


class AddMemberRequest(BaseModel):
    user_id: str


@router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
def post_project(
    body: ProjectCreateRequest,
    actor: User = Depends(get_project_initiation_user),
    db: Session = Depends(get_db),
) -> ProjectResponse:
    return create_project(db, actor=actor, body=body)


@router.get("", response_model=list[ProjectResponse])
def get_projects(
    include_archived: bool = Query(default=False),
    actor: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[ProjectResponse]:
    return list_projects(db, actor=actor, include_archived=include_archived)


@router.get("/{project_id}", response_model=ProjectResponse)
def get_project_by_id(
    project_id: str,
    actor: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ProjectResponse:
    require_project_access(db, user=actor, project_id=project_id)
    return get_project(db, project_id=project_id)


@router.patch("/{project_id}", response_model=ProjectResponse)
def patch_project(
    project_id: str,
    body: ProjectUpdateRequest,
    actor: User = Depends(get_central_team_user),
    db: Session = Depends(get_db),
) -> ProjectResponse:
    return update_project(db, actor=actor, project_id=project_id, body=body)


@router.post("/{project_id}/archive", response_model=ProjectResponse)
def post_project_archive(
    project_id: str,
    actor: User = Depends(get_central_team_user),
    db: Session = Depends(get_db),
) -> ProjectResponse:
    return archive_project(db, actor=actor, project_id=project_id)


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
    return add_project_member(db, actor=actor, project_id=project_id, user_id=body.user_id)


@router.delete("/{project_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project_member(
    project_id: str,
    user_id: str,
    actor: User = Depends(get_central_team_user),
    db: Session = Depends(get_db),
) -> Response:
    remove_project_member(db, actor=actor, project_id=project_id, user_id=user_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
