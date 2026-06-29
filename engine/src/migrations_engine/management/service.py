from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..api.deps import AuthApiError
from ..api.schemas import (
    MembershipResponse,
    ProjectMemberResponse,
    UserCreateRequest,
    UserResponse,
    UserUpdateRequest,
)
from ..auth.passwords import hash_password
from ..db.models import ProjectMembership, ProjectRegistry, User, new_id
from ..roles import PROJECT_STAKEHOLDER_ROLE
from .access import is_valid_platform_role
from .platform import ensure_platform_project, record_management_audit


def list_users(db: Session) -> list[UserResponse]:
    users = db.scalars(
        select(User).where(User.soft_deleted_at.is_(None)).order_by(User.email)
    ).all()
    return [_user_response(user) for user in users]


def get_user(db: Session, *, user_id: str) -> UserResponse:
    user = _get_active_user(db, user_id)
    return _user_response(user)


def create_user(db: Session, *, actor: User, body: UserCreateRequest) -> UserResponse:
    if not is_valid_platform_role(body.role):
        raise AuthApiError("invalid_role", "Role is not valid.", 422)

    normalized_email = str(body.email).strip().lower()
    existing = db.scalar(select(User).where(User.email == normalized_email))
    if existing is not None:
        raise AuthApiError("duplicate_email", "A user with this email already exists.", 409)

    user = User(
        user_id=new_id(),
        email=normalized_email,
        display_name=body.display_name,
        password_hash=hash_password(body.password),
        role=body.role,
        status="active",
    )
    db.add(user)
    db.flush()
    platform_project_id = ensure_platform_project(db)
    record_management_audit(
        db,
        project_id=platform_project_id,
        actor_user_id=actor.user_id,
        event_type="user.created",
        payload={"user_id": user.user_id, "email": user.email, "role": user.role},
    )
    db.commit()
    db.refresh(user)
    return _user_response(user)


def update_user(
    db: Session,
    *,
    actor: User,
    user_id: str,
    body: UserUpdateRequest,
) -> UserResponse:
    user = _get_user_record(db, user_id)
    if user.soft_deleted_at is not None:
        raise AuthApiError("user_not_found", "User not found.", 404)

    changes: dict[str, object] = {}
    if body.display_name is not None:
        user.display_name = body.display_name
        changes["display_name"] = body.display_name
    if body.role is not None:
        if not is_valid_platform_role(body.role):
            raise AuthApiError("invalid_role", "Role is not valid.", 422)
        user.role = body.role
        changes["role"] = body.role
    if body.status is not None:
        user.status = body.status
        changes["status"] = body.status

    if changes:
        platform_project_id = ensure_platform_project(db)
        record_management_audit(
            db,
            project_id=platform_project_id,
            actor_user_id=actor.user_id,
            event_type="user.updated",
            payload={"user_id": user.user_id, "changes": changes},
        )
    db.commit()
    db.refresh(user)
    return _user_response(user)


def soft_delete_user(db: Session, *, actor: User, user_id: str) -> None:
    user = _get_user_record(db, user_id)
    if user.soft_deleted_at is not None:
        raise AuthApiError("user_not_found", "User not found.", 404)

    now = datetime.now(UTC)
    user.soft_deleted_at = now
    user.status = "disabled"
    user.session_version += 1
    platform_project_id = ensure_platform_project(db)
    record_management_audit(
        db,
        project_id=platform_project_id,
        actor_user_id=actor.user_id,
        event_type="user.soft_deleted",
        payload={"user_id": user.user_id},
    )
    db.commit()


def list_project_members(db: Session, *, project_id: str) -> list[ProjectMemberResponse]:
    _get_project(db, project_id)
    rows = db.scalars(
        select(ProjectMembership).where(ProjectMembership.project_id == project_id)
    ).all()
    return [
        ProjectMemberResponse(
            project_id=row.project_id,
            user_id=row.user_id,
            created_at=row.created_at,
        )
        for row in rows
    ]


def add_project_member(
    db: Session,
    *,
    actor: User,
    project_id: str,
    user_id: str,
) -> MembershipResponse:
    _get_project(db, project_id)
    user = _get_user_record(db, user_id)
    if user.soft_deleted_at is not None:
        raise AuthApiError("user_not_found", "User not found.", 404)
    if user.role != PROJECT_STAKEHOLDER_ROLE:
        raise AuthApiError(
            "not_stakeholder",
            "Only project_stakeholder users can be assigned project membership.",
            422,
        )

    existing = db.scalar(
        select(ProjectMembership).where(
            ProjectMembership.project_id == project_id,
            ProjectMembership.user_id == user_id,
        )
    )
    if existing is not None:
        return MembershipResponse(
            project_id=project_id,
            user_id=user_id,
            warning="User is already a member of this project.",
        )

    db.add(ProjectMembership(project_id=project_id, user_id=user_id))
    record_management_audit(
        db,
        project_id=project_id,
        actor_user_id=actor.user_id,
        event_type="project_membership.added",
        payload={"project_id": project_id, "user_id": user_id},
    )
    db.commit()
    return MembershipResponse(project_id=project_id, user_id=user_id)


def remove_project_member(
    db: Session,
    *,
    actor: User,
    project_id: str,
    user_id: str,
) -> None:
    _get_project(db, project_id)
    membership = db.scalar(
        select(ProjectMembership).where(
            ProjectMembership.project_id == project_id,
            ProjectMembership.user_id == user_id,
        )
    )
    if membership is None:
        raise AuthApiError("membership_not_found", "Project membership not found.", 404)

    db.delete(membership)
    record_management_audit(
        db,
        project_id=project_id,
        actor_user_id=actor.user_id,
        event_type="project_membership.removed",
        payload={"project_id": project_id, "user_id": user_id},
    )
    db.commit()


def _get_project(db: Session, project_id: str) -> ProjectRegistry:
    project = db.get(ProjectRegistry, project_id)
    if project is None or project.soft_deleted_at is not None:
        raise AuthApiError("project_not_found", "Project not found.", 404)
    return project


def _get_user_record(db: Session, user_id: str) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise AuthApiError("user_not_found", "User not found.", 404)
    return user


def _get_active_user(db: Session, user_id: str) -> User:
    user = _get_user_record(db, user_id)
    if user.soft_deleted_at is not None:
        raise AuthApiError("user_not_found", "User not found.", 404)
    return user


def _user_response(user: User) -> UserResponse:
    return UserResponse(
        user_id=user.user_id,
        email=user.email,
        display_name=user.display_name,
        role=user.role,  # type: ignore[arg-type]
        status=user.status,  # type: ignore[arg-type]
        created_at=user.created_at,
        updated_at=user.updated_at,
    )
