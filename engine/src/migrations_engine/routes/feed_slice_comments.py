from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from ..api.deps import get_current_user, get_db
from ..api.schemas import FeedSliceCommentCreateRequest, FeedSliceCommentResponse
from ..db.models import User
from ..management.access import require_non_auditor, require_project_access
from ..management.feed_slice_comments import create_feed_slice_comment, list_feed_slice_comments

router = APIRouter(
    prefix="/projects/{project_id}/sources/{source_definition_id}/slices/{source_slice_id}/comments",
    tags=["feed-slice-comments"],
)


@router.get("", response_model=list[FeedSliceCommentResponse])
def get_feed_slice_comments(
    project_id: str,
    source_definition_id: str,
    source_slice_id: str,
    actor: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[FeedSliceCommentResponse]:
    require_project_access(db, user=actor, project_id=project_id)
    return list_feed_slice_comments(db, project_id=project_id, source_slice_id=source_slice_id)


@router.post("", response_model=FeedSliceCommentResponse, status_code=status.HTTP_201_CREATED)
def post_feed_slice_comment(
    project_id: str,
    source_definition_id: str,
    source_slice_id: str,
    body: FeedSliceCommentCreateRequest,
    actor: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FeedSliceCommentResponse:
    require_non_auditor(actor)
    require_project_access(db, user=actor, project_id=project_id)
    return create_feed_slice_comment(
        db,
        actor=actor,
        project_id=project_id,
        source_slice_id=source_slice_id,
        body=body,
    )
