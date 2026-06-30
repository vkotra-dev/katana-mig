from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..api.deps import AuthApiError
from ..db.models import ProjectMembership, User
from ..roles import (
    CENTRAL_TEAM_ROLE,
    PLATFORM_ROLES,
    PROJECT_STAKEHOLDER_ROLE,
    READ_ONLY_AUDITOR_ROLE,
)


def is_valid_platform_role(role: str) -> bool:
    return role in {item[0] for item in PLATFORM_ROLES}


def require_central_team(user: User) -> None:
    if user.role != CENTRAL_TEAM_ROLE:
        raise AuthApiError("forbidden", "Central team access is required.", 403)


def require_non_auditor(user: User) -> None:
    if user.role == READ_ONLY_AUDITOR_ROLE:
        raise AuthApiError("forbidden", "Read-only auditors cannot perform this action.", 403)


def require_central_team_or_self(actor: User, target_user_id: str) -> None:
    if actor.user_id != target_user_id:
        require_central_team(actor)


def require_project_access(db: Session, *, user: User, project_id: str) -> None:
    if not user_has_project_access(db, user=user, project_id=project_id):
        raise AuthApiError("forbidden", "Access to this project requires membership.", 403)


def user_has_project_access(db: Session, *, user: User, project_id: str) -> bool:
    if user.role in {CENTRAL_TEAM_ROLE, READ_ONLY_AUDITOR_ROLE}:
        return True
    if user.role != PROJECT_STAKEHOLDER_ROLE:
        return False
    membership = db.scalar(
        select(ProjectMembership.user_id).where(
            ProjectMembership.project_id == project_id,
            ProjectMembership.user_id == user.user_id,
        )
    )
    return membership is not None
