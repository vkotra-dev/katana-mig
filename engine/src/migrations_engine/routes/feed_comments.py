from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from ..api.deps import get_current_user, get_db
from ..api.schemas import FeedCommentCreateRequest, FeedCommentResponse
from ..db.models import User
from ..management.access import require_non_auditor, require_project_access
from ..management.feed_comments import create_feed_comment, list_feed_comments

router = APIRouter(
    prefix="/projects/{project_id}/feeds/{feed_id}/comments",
    tags=["feed-comments"],
)


@router.get("", response_model=list[FeedCommentResponse])
def get_feed_comments(
    project_id: str,
    feed_id: str,
    actor: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[FeedCommentResponse]:
    require_project_access(db, user=actor, project_id=project_id)
    return list_feed_comments(db, project_id=project_id, feed_id=feed_id)


@router.post("", response_model=FeedCommentResponse, status_code=status.HTTP_201_CREATED)
def post_feed_comment(
    project_id: str,
    feed_id: str,
    body: FeedCommentCreateRequest,
    actor: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FeedCommentResponse:
    require_non_auditor(actor)
    require_project_access(db, user=actor, project_id=project_id)
    return create_feed_comment(
        db,
        actor=actor,
        project_id=project_id,
        feed_id=feed_id,
        body=body,
    )
