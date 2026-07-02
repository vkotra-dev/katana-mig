from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..api.deps import get_current_user, get_db
from ..api.schemas import NotificationCountResponse, NotificationMarkAllResponse, NotificationResponse
from ..db.models import User
from ..management.notifications import (
    get_notification_count,
    list_notifications,
    mark_all_notifications_read,
    mark_notification_read,
)

router = APIRouter(tags=["notifications"])


@router.get("/notifications", response_model=list[NotificationResponse])
def get_notifications(
    actor: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[NotificationResponse]:
    return list_notifications(db, actor=actor)


@router.get("/notifications/count", response_model=NotificationCountResponse)
def get_notifications_count(
    actor: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> NotificationCountResponse:
    return get_notification_count(db, actor=actor)


@router.post("/notifications/{notification_id}/read", response_model=NotificationResponse)
def post_notification_read(
    notification_id: str,
    actor: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> NotificationResponse:
    return mark_notification_read(db, actor=actor, notification_id=notification_id)


@router.post("/notifications/read-all", response_model=NotificationMarkAllResponse)
def post_notifications_read_all(
    actor: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> NotificationMarkAllResponse:
    return mark_all_notifications_read(db, actor=actor)
