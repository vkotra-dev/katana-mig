from __future__ import annotations

import logging
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..api.deps import AuthApiError
from ..api.schemas import (
    NotificationCountResponse,
    NotificationEventType,
    NotificationMarkAllResponse,
    NotificationResponse,
)
from ..db.models import Notification, User, new_id

_LOGGER = logging.getLogger(__name__)


def send_notification_email(user_email: str, event_type: str, deep_link: str | None) -> None:
    _LOGGER.info(
        "notification email stub: email=%s event_type=%s deep_link=%s",
        user_email,
        event_type,
        deep_link,
    )


def _to_response(notification: Notification) -> NotificationResponse:
    return NotificationResponse(
        notification_id=notification.notification_id,
        user_id=notification.user_id,
        project_id=notification.project_id,
        event_type=notification.event_type,  # type: ignore[arg-type]
        deep_link=notification.deep_link,
        read=notification.read,
        payload=notification.payload,
        read_at=notification.read_at,
        created_at=notification.created_at,
    )


def create_notification(
    db: Session,
    *,
    user_id: str,
    project_id: str,
    event_type: NotificationEventType | str,
    deep_link: str,
    payload: dict[str, object] | None,
) -> str:
    notification = Notification(
        notification_id=new_id(),
        user_id=user_id,
        project_id=project_id,
        event_type=event_type,
        deep_link=deep_link,
        read=False,
        payload=payload,
        read_at=None,
    )
    db.add(notification)
    db.flush()

    user_email = db.scalar(select(User.email).where(User.user_id == user_id))
    if user_email is not None:
        send_notification_email(user_email, event_type, deep_link)

    return notification.notification_id


def list_notifications(db: Session, *, actor: User) -> list[NotificationResponse]:
    rows = db.scalars(
        select(Notification)
        .where(Notification.user_id == actor.user_id)
        .order_by(Notification.read.asc(), Notification.created_at.desc())
    ).all()
    return [_to_response(notification) for notification in rows]


def get_notification_count(db: Session, *, actor: User) -> NotificationCountResponse:
    unread_count = db.scalar(
        select(func.count(Notification.notification_id)).where(
            Notification.user_id == actor.user_id,
            Notification.read.is_(False),
        )
    )
    return NotificationCountResponse(unread_count=int(unread_count or 0))


def mark_notification_read(db: Session, *, actor: User, notification_id: str) -> NotificationResponse:
    notification = db.scalar(
        select(Notification).where(
            Notification.notification_id == notification_id,
            Notification.user_id == actor.user_id,
        )
    )
    if notification is None:
        raise AuthApiError("notification_not_found", "Notification not found.", 404)
    if not notification.read:
        notification.read = True
        notification.read_at = datetime.now(UTC)
        db.commit()
        db.refresh(notification)
    return _to_response(notification)


def mark_all_notifications_read(db: Session, *, actor: User) -> NotificationMarkAllResponse:
    rows = db.scalars(
        select(Notification).where(
            Notification.user_id == actor.user_id,
            Notification.read.is_(False),
        )
    ).all()
    for notification in rows:
        notification.read = True
        notification.read_at = datetime.now(UTC)
    db.commit()
    return NotificationMarkAllResponse(marked_count=len(rows))
