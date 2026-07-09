from __future__ import annotations

from datetime import UTC, datetime
import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..api.deps import AuthApiError
from ..api.schemas import FeedSliceCommentCreateRequest, FeedSliceCommentResponse
from ..db.models import Feed, FeedSlice, FeedSliceComment, ProjectMembership, User, new_id
from ..db.session import SessionLocal
from ..management.notifications import create_notification
from ..roles import CENTRAL_TEAM_ROLE, PROJECT_STAKEHOLDER_ROLE

_LOGGER = logging.getLogger(__name__)


def list_feed_slice_comments(
    db: Session,
    *,
    project_id: str,
    source_slice_id: str,
) -> list[FeedSliceCommentResponse]:
    _require_slice_in_project(db, project_id=project_id, source_slice_id=source_slice_id)

    rows = db.execute(
        select(FeedSliceComment, User)
        .join(User, FeedSliceComment.user_id == User.user_id)
        .where(FeedSliceComment.source_slice_id == source_slice_id)
        .order_by(FeedSliceComment.created_at.asc(), FeedSliceComment.comment_id.asc())
    ).all()
    return [
        FeedSliceCommentResponse(
            comment_id=comment.comment_id,
            source_slice_id=comment.source_slice_id,
            user_id=comment.user_id,
            display_name=user.display_name,
            role=user.role,
            body=comment.body,
            created_at=comment.created_at,
        )
        for comment, user in rows
    ]


def create_feed_slice_comment(
    db: Session,
    *,
    actor: User,
    project_id: str,
    source_slice_id: str,
    body: FeedSliceCommentCreateRequest,
) -> FeedSliceCommentResponse:
    slice_record = _require_slice_in_project(db, project_id=project_id, source_slice_id=source_slice_id)
    cleaned_body = body.body.strip()
    if not cleaned_body:
        raise AuthApiError("validation_error", "Comment body is required.", 422)

    comment = FeedSliceComment(
        comment_id=new_id(),
        source_slice_id=source_slice_id,
        user_id=actor.user_id,
        body=cleaned_body,
        created_at=datetime.now(UTC),
    )
    db.add(comment)
    db.flush()

    response = FeedSliceCommentResponse(
        comment_id=comment.comment_id,
        source_slice_id=comment.source_slice_id,
        user_id=comment.user_id,
        display_name=actor.display_name,
        role=actor.role,
        body=comment.body,
        created_at=comment.created_at,
    )

    try:
        recipient_ids = _get_notification_recipients(db, project_id=project_id, commenter_role=actor.role)
        for recipient_id in recipient_ids:
            with SessionLocal() as notification_db:
                create_notification(
                    notification_db,
                    user_id=recipient_id,
                    project_id=project_id,
                    event_type="slice_comment_added",
                    deep_link=f"/projects/{project_id}/feeds/{slice_record.source_definition_id}",
                    payload={
                        "feed_id": slice_record.source_definition_id,
                        "slice_id": source_slice_id,
                        "comment_id": comment.comment_id,
                    },
                )
                notification_db.commit()
    except Exception:  # noqa: BLE001
        _LOGGER.exception("Comment notification fan-out failed for slice %s", source_slice_id)

    db.commit()
    db.refresh(comment)
    return response


def _require_slice_in_project(
    db: Session,
    *,
    project_id: str,
    source_slice_id: str,
) -> FeedSlice:
    row = db.execute(
        select(FeedSlice, Feed)
        .join(Feed, Feed.source_definition_id == FeedSlice.source_definition_id)
        .where(
            FeedSlice.source_slice_id == source_slice_id,
            Feed.project_id == project_id,
        )
    ).first()
    if row is None:
        raise AuthApiError("not_found", "Slice not found in this project.", 404)
    return row[0]


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
