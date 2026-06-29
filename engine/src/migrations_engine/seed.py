from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from typing import Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from .auth.passwords import hash_password
from .config import Settings, get_settings
from .db.models import User
from .db.session import SessionLocal
from .roles import CENTRAL_TEAM_ROLE, format_roles

ACTIVE_STATUS = "active"


@dataclass(frozen=True)
class SeedAdminResult:
    action: Literal["created", "role_assigned", "skipped"]
    email: str | None = None
    message: str | None = None


class BootstrapCredentialsError(RuntimeError):
    pass


class BootstrapUserNotFoundError(RuntimeError):
    pass


class BootstrapUserInactiveError(RuntimeError):
    pass


def users_exist(session: Session) -> bool:
    return session.scalar(select(User.user_id).limit(1)) is not None


def get_user_by_email(session: Session, email: str) -> User | None:
    normalized_email = email.strip().lower()
    if not normalized_email:
        return None
    return session.scalar(select(User).where(User.email == normalized_email))


def seed_admin_user(
    session: Session,
    *,
    email: str,
    password: str,
    display_name: str | None = None,
) -> SeedAdminResult:
    normalized_email = email.strip().lower()
    if not normalized_email or not password:
        raise BootstrapCredentialsError(
            "Bootstrap admin email and password are required when no users exist."
        )

    user = User(
        email=normalized_email,
        display_name=display_name or "Administrator",
        password_hash=hash_password(password),
        role=CENTRAL_TEAM_ROLE,
        status=ACTIVE_STATUS,
    )
    session.add(user)
    session.commit()
    return SeedAdminResult(action="created", email=normalized_email)


def assign_admin_role(session: Session, *, email: str) -> SeedAdminResult:
    normalized_email = email.strip().lower()
    if not normalized_email:
        raise BootstrapCredentialsError(
            "Bootstrap admin email is required to assign the central_team role."
        )

    user = get_user_by_email(session, normalized_email)
    if user is None:
        raise BootstrapUserNotFoundError(
            f"No user found with email {normalized_email!r}."
        )
    if user.soft_deleted_at is not None:
        raise BootstrapUserInactiveError(
            f"User {normalized_email!r} is soft-deleted and cannot be promoted."
        )
    if user.role == CENTRAL_TEAM_ROLE:
        return SeedAdminResult(
            action="skipped",
            email=normalized_email,
            message=f"{normalized_email} already has the {CENTRAL_TEAM_ROLE} role.",
        )

    user.role = CENTRAL_TEAM_ROLE
    session.commit()
    return SeedAdminResult(
        action="role_assigned",
        email=normalized_email,
        message=f"Assigned {CENTRAL_TEAM_ROLE} role to {normalized_email}.",
    )


def run_seed_admin(settings: Settings | None = None) -> SeedAdminResult:
    settings = settings or get_settings()
    with SessionLocal() as session:
        if not users_exist(session):
            return seed_admin_user(
                session,
                email=settings.bootstrap_admin_email,
                password=settings.bootstrap_admin_password,
                display_name=settings.bootstrap_admin_display_name or None,
            )

        if not settings.bootstrap_admin_email:
            return SeedAdminResult(
                action="skipped",
                message=(
                    "Users already exist. Set KATANA_BOOTSTRAP_ADMIN_EMAIL to assign "
                    f"the {CENTRAL_TEAM_ROLE} role to an existing user."
                ),
            )

        return assign_admin_role(session, email=settings.bootstrap_admin_email)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Bootstrap the first admin user or assign the central_team role to an "
            "existing bootstrap user."
        )
    )
    parser.add_argument(
        "--list-roles",
        action="store_true",
        help="List supported platform roles and exit.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.list_roles:
        print(format_roles())
        return 0

    try:
        result = run_seed_admin()
    except BootstrapCredentialsError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except BootstrapUserNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except BootstrapUserInactiveError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if result.message:
        print(result.message)
        return 0

    if result.action == "created":
        print(f"Created bootstrap admin user: {result.email}")
        return 0

    print("Bootstrap admin seed skipped: users already exist.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
