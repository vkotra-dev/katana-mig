from __future__ import annotations

from datetime import UTC, datetime
import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..api.deps import AuthApiError
from ..api.schemas import FeedCommentCreateRequest, FeedCommentResponse
from ..db.models import Feed, FeedComment, ProjectMembership, User, new_id
from ..management.notifications import create_notification
from ..roles import CENTRAL_TEAM_ROLE, PROJECT_STAKEHOLDER_ROLE

_LOGGER = logging.getLogger(__name__)


def list_feed_comments(
    db: Session,
    *,
    project_id: str,
    feed_id: str,
) -> list[FeedCommentResponse]:
    _require_feed_in_project(db, project_id=project_id, feed_id=feed_id)

    rows = db.execute(
        select(FeedComment, User)
        .join(User, FeedComment.user_id == User.user_id)
        .where(FeedComment.feed_id == feed_id)
        .order_by(FeedComment.created_at.asc(), FeedComment.comment_id.asc())
    ).all()
    return [
        FeedCommentResponse(
            comment_id=comment.comment_id,
            feed_id=comment.feed_id,
            user_id=comment.user_id,
            display_name=user.display_name,
            role=user.role,
            body=comment.body,
            created_at=comment.created_at,
        )
        for comment, user in rows
    ]


def create_feed_comment(
    db: Session,
    *,
    actor: User,
    project_id: str,
    feed_id: str,
    body: FeedCommentCreateRequest,
) -> FeedCommentResponse:
    _require_feed_in_project(db, project_id=project_id, feed_id=feed_id)

    comment = FeedComment(
        comment_id=new_id(),
        feed_id=feed_id,
        user_id=actor.user_id,
        body=body.body.strip(),
        created_at=datetime.now(UTC),
    )
    db.add(comment)
    db.flush()

    response = FeedCommentResponse(
        comment_id=comment.comment_id,
        feed_id=comment.feed_id,
        user_id=comment.user_id,
        display_name=actor.display_name,
        role=actor.role,
        body=comment.body,
        created_at=comment.created_at,
    )

    try:
        recipient_ids = _get_notification_recipients(db, project_id=project_id, commenter_role=actor.role)
        for recipient_id in recipient_ids:
            create_notification(
                db,
                user_id=recipient_id,
                project_id=project_id,
                event_type="feed_comment_added",
                deep_link=f"/projects/{project_id}/feeds/{feed_id}",
                payload={"feed_id": feed_id, "comment_id": comment.comment_id},
            )
    except Exception:  # noqa: BLE001
        _LOGGER.exception("Comment notification fan-out failed for feed %s", feed_id)

    db.commit()
    db.refresh(comment)
    return response


def _require_feed_in_project(db: Session, *, project_id: str, feed_id: str) -> Feed:
    feed = db.scalar(
        select(Feed).where(
            Feed.source_definition_id == feed_id,
            Feed.project_id == project_id,
        )
    )
    if feed is None:
        raise AuthApiError("not_found", "Feed not found in this project.", 404)
    return feed


def _get_notification_recipients(
    db: Session,
    *,
    project_id: str,
    commenter_role: str,
) -> list[str]:
    if commenter_role == CENTRAL_TEAM_ROLE:
        rows = db.scalars(
            select(User.user_id)
            .join(ProjectMembership, User.user_id == ProjectMembership.user_id)
            .where(
                ProjectMembership.project_id == project_id,
                User.role == PROJECT_STAKEHOLDER_ROLE,
                User.status == "active",
            )
        ).all()
        return list(rows)

    rows = db.scalars(
        select(User.user_id).where(
            User.role == CENTRAL_TEAM_ROLE,
            User.status == "active",
        )
    ).all()
    return list(rows)
