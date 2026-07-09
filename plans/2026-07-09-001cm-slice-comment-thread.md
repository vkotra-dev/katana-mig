# Plan: 001cm — Slice Comment Thread

- **Task:** [tasks/001cm-slice-comment-thread.md](../tasks/001cm-slice-comment-thread.md)
- **Depends on:** 001cl (codegen injection pattern)

## Pattern

Mirrors `FeedComment` / `feed_comments.py` exactly. Key conventions from the existing implementation:
- PK field is `comment_id` (not `id`)
- Body field is `body` (not `content`)
- No `author_role` column stored — role is derived at query time via `JOIN users`
- Notifications use a fresh `SessionLocal()` per recipient, wrapped in `try/except` so failures never block the comment
- `role` returned in response comes from `User.role` at read time

## Execution Order

DB model → migration → schemas → management service → routes → codegen extension → frontend API → component → mount

---

## Step 1 — DB model: `FeedSliceComment`

**File:** `engine/src/migrations_engine/db/models.py`

Add after `FeedComment` (line ~305):

```python
class FeedSliceComment(Base):
    __tablename__ = "feed_slice_comments"

    comment_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    source_slice_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("source_slices.source_slice_id"), nullable=False, index=True
    )
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.user_id"), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
```

---

## Step 2 — Migration `0028_slice_comments.py`

**File:** `engine/migrations/versions/0028_slice_comments.py`

Verify `down_revision` before writing — run `ls engine/migrations/versions/ | sort | tail -1` to confirm the current head. Expected to be `"0027"` after 001cl lands; if implementing standalone first, use whatever the current latest is.

```python
"""add feed_slice_comments table

Revision ID: 0028
Revises: 0027
"""
from alembic import op
import sqlalchemy as sa

revision = "0028"
down_revision = "0027"

def upgrade() -> None:
    op.create_table(
        "feed_slice_comments",
        sa.Column("comment_id", sa.String(36), primary_key=True),
        sa.Column(
            "source_slice_id",
            sa.String(36),
            sa.ForeignKey("source_slices.source_slice_id"),
            nullable=False,
        ),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.user_id"), nullable=False),
        sa.Column("body", sa.Text, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_feed_slice_comments_slice", "feed_slice_comments", ["source_slice_id"])

def downgrade() -> None:
    op.drop_index("ix_feed_slice_comments_slice", "feed_slice_comments")
    op.drop_table("feed_slice_comments")
```

---

## Step 3 — Schemas

**File:** `engine/src/migrations_engine/api/schemas.py`

```python
class FeedSliceCommentCreateRequest(BaseModel):
    body: str

class FeedSliceCommentResponse(BaseModel):
    comment_id: str
    source_slice_id: str
    user_id: str
    display_name: str | None
    role: str
    body: str
    created_at: datetime
```

---

## Step 4 — Management service: `slice_comments.py`

**File:** `engine/src/migrations_engine/management/slice_comments.py` (new)

Mirror `feed_comments.py` exactly. Replace `feed_id` / `FeedComment` / `feed_comments` with `source_slice_id` / `FeedSliceComment` / `feed_slice_comments`.

**Authorization pattern:** `feed_comments.py` uses `_require_feed_in_project` which checks the data chain (`Feed.project_id == project_id`) rather than actor membership — no separate membership guard exists. `_require_slice_in_project` follows the same pattern and is consistent.

```python
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


def list_slice_comments(
    db: Session,
    *,
    project_id: str,
    feed_id: str,
    source_slice_id: str,
) -> list[FeedSliceCommentResponse]:
    _require_slice_in_project(db, project_id=project_id, feed_id=feed_id, source_slice_id=source_slice_id)
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


def create_slice_comment(
    db: Session,
    *,
    actor: User,
    project_id: str,
    feed_id: str,
    source_slice_id: str,
    body: FeedSliceCommentCreateRequest,
) -> FeedSliceCommentResponse:
    _require_slice_in_project(db, project_id=project_id, feed_id=feed_id, source_slice_id=source_slice_id)
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
                    event_type="feed_slice_comment_added",
                    deep_link=f"/projects/{project_id}/feeds/{feed_id}",
                    payload={
                        "feed_id": feed_id,
                        "source_slice_id": source_slice_id,
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
    db: Session, *, project_id: str, feed_id: str, source_slice_id: str
) -> FeedSlice:
    feed = db.scalar(
        select(Feed).where(Feed.source_definition_id == feed_id, Feed.project_id == project_id)
    )
    if feed is None:
        raise AuthApiError("not_found", "Feed not found in this project.", 404)
    # Verify slice belongs to feed
    slc = db.scalar(
        select(FeedSlice).where(
            FeedSlice.source_slice_id == source_slice_id,
            FeedSlice.source_definition_id == feed_id,
        )
    )
    if slc is None:
        raise AuthApiError("not_found", "Slice not found in this feed.", 404)
    return slc


def _get_notification_recipients(
    db: Session, *, project_id: str, commenter_role: str
) -> list[str]:
    # Same cross-role logic as FeedComment
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
```

---

## Step 5 — Routes: `slice_comments.py`

**File:** `engine/src/migrations_engine/routes/slice_comments.py` (new)

```python
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..api.deps import get_current_user, get_db
from ..api.schemas import FeedSliceCommentCreateRequest, FeedSliceCommentResponse
from ..db.models import User
from ..management.slice_comments import create_slice_comment, list_slice_comments

router = APIRouter(
    prefix="/projects/{project_id}/sources/{feed_id}/slices/{source_slice_id}/comments",
    tags=["slice-comments"],
)


@router.get("", response_model=list[FeedSliceCommentResponse])
def get_slice_comments(
    project_id: str,
    feed_id: str,
    source_slice_id: str,
    actor: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[FeedSliceCommentResponse]:
    return list_slice_comments(
        db, project_id=project_id, feed_id=feed_id, source_slice_id=source_slice_id
    )


@router.post("", response_model=FeedSliceCommentResponse, status_code=201)
def post_slice_comment(
    project_id: str,
    feed_id: str,
    source_slice_id: str,
    body: FeedSliceCommentCreateRequest,
    actor: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FeedSliceCommentResponse:
    return create_slice_comment(
        db,
        actor=actor,
        project_id=project_id,
        feed_id=feed_id,
        source_slice_id=source_slice_id,
        body=body,
    )
```

Register in `app.py`:
```python
from .routes.slice_comments import router as slice_comments_router
app.include_router(slice_comments_router)
```

---

## Step 6 — Codegen: extend prompt with slice comments

**File:** `engine/src/migrations_engine/codegen/service.py`

Requires 001cl to have landed (which added `_format_discussion` and established the comments parameter pattern).

Fetch slice comments in `generate_codegen_artifact`, after the feed-level comment fetch. `source_slice` is already in scope at `service.py:80` (`source_slice = _select_latest_approved_source_slice(...)`):

```python
from ..db.models import FeedSliceComment

slice_comments_raw = list(db.execute(
    select(FeedSliceComment, User)
    .join(User, FeedSliceComment.user_id == User.user_id)
    .where(FeedSliceComment.source_slice_id == source_slice.source_slice_id)
    .order_by(FeedSliceComment.created_at.asc())
).all())
```

Add a second formatting helper with its own independent budget (each section can reach 3000 chars — feed-level and slice-level budgets are not shared, so the combined discussion block can be up to ~6000 chars; this is intentional to give each context layer full coverage):

```python
def _format_slice_discussion(rows: list[tuple[FeedSliceComment, User]]) -> str:
    if not rows:
        return ""
    recent = rows[-_MAX_COMMENT_COUNT:]
    lines = ["Slice data discussion (context about this specific batch):"]
    total = len(lines[0])
    for comment, user in recent:
        content = " ".join(comment.body.split())
        if len(content) > _MAX_COMMENT_CHARS:
            content = content[:_MAX_COMMENT_CHARS] + "…"
        line = f"[{user.role}] {comment.created_at.date()}: {content}"
        if total + len(line) + 1 > _MAX_DISCUSSION_CHARS:
            lines.append("[discussion truncated]")
            break
        lines.append(line)
        total += len(line) + 1
    return "\n".join(lines)
```

Append after feed-level discussion in `_build_user_prompt`:
```python
slice_discussion = _format_slice_discussion(slice_comments_raw)
if slice_discussion:
    lines.append("")
    lines.append(slice_discussion)
```

Note: `FeedComment` in 001cl also derives role via User join at query time — update 001cl's codegen fetch to use the same `JOIN users` pattern if not already done.

---

## Step 7 — Frontend API helpers

**File:** `web/lib/feeds-api.ts`

Add alongside existing `listFeedComments` / `createFeedComment`:

```typescript
export interface FeedSliceCommentRecord {
  commentId: string;
  sourceSliceId: string;
  userId: string;
  displayName: string | null;
  role: string;
  body: string;
  createdAt: string;
}

function mapSliceComment(r: unknown): FeedSliceCommentRecord {
  const d = r as Record<string, unknown>;
  return {
    commentId: d.comment_id as string,
    sourceSliceId: d.source_slice_id as string,
    userId: d.user_id as string,
    displayName: (d.display_name as string | null) ?? null,
    role: d.role as string,
    body: d.body as string,
    createdAt: d.created_at as string,
  };
}

export async function listSliceComments(
  token: string,
  projectId: string,
  feedId: string,
  sliceId: string,
): Promise<FeedSliceCommentRecord[]> {
  const data = await requestJson<unknown[]>(
    `/projects/${projectId}/sources/${feedId}/slices/${sliceId}/comments`,
    { token },
  );
  return data.map(mapSliceComment);
}

export async function createSliceComment(
  token: string,
  projectId: string,
  feedId: string,
  sliceId: string,
  body: string,
): Promise<FeedSliceCommentRecord> {
  const data = await requestJson<unknown>(
    `/projects/${projectId}/sources/${feedId}/slices/${sliceId}/comments`,
    { method: "POST", token, body: JSON.stringify({ body }) },
  );
  return mapSliceComment(data);
}
```

---

## Step 8 — `FeedSliceCommentThread` component

**File:** `web/components/feeds/FeedSliceCommentThread.tsx` (new)

Mirror `web/components/feeds/FeedCommentThread.tsx` exactly (confirmed path; test at `web/components/feeds/__tests__/FeedCommentThread.test.tsx`). Replace:
- `feedId` prop → `sliceId` prop (keep `feedId` + `projectId` for the API call)
- `listFeedComments` → `listSliceComments`
- `createFeedComment` → `createSliceComment`
- `FeedCommentRecord` → `FeedSliceCommentRecord`
- `comment.body` field name is the same (`body` in both models)

Props:
```typescript
interface FeedSliceCommentThreadProps {
  projectId: string;
  feedId: string;
  sliceId: string;
  token: string;
}
```

---

## Step 9 — Mount in feed workspace (slice approval card)

**File:** `web/app/projects/[id]/feeds/[feedId]/page.tsx`

Find where the approved slice preview card is rendered (the card that shows `preview_rows` and the approve button). Add `FeedSliceCommentThread` below the slice data preview:

```tsx
import { FeedSliceCommentThread } from "../../../../../components/feeds/FeedSliceCommentThread";

// Below the slice preview table, inside the `latestSlice.status === "approved"` block:
{latestSlice?.status === "approved" && session && (
  <FeedSliceCommentThread
    projectId={id}
    feedId={feedId}
    sliceId={latestSlice.sourceSliceId}
    token={session.accessToken}
  />
)}
```

`latestSlice` is the existing variable (`const latestSlice = slices[slices.length - 1]`) already used by the preview table — no new state needed.

---

## Step 10 — Tests

**Backend:**
- `list_slice_comments` returns empty list for new slice
- `create_slice_comment` returns response with derived `role` from User join
- Empty body raises 422
- Slice not in feed raises 404; feed not in project raises 404
- Cross-role notification fires on create; notification failure does not block comment
- `FeedSliceComment` rows for a slice do not appear in `list_feed_comments` (no cross-contamination)

**Frontend:**
- `FeedSliceCommentThread` renders comment list and submit form
- Submit clears textarea on success
- API helpers map snake_case → camelCase correctly

---

## Note on 001cl codegen fix

`FeedComment` has no `author_role` column — role is on `User`. When 001cl's `generate_codegen_artifact` fetches comments for `_format_discussion`, it must use a `JOIN users` (same pattern as `list_feed_comments`) rather than accessing a non-existent `.author_role` attribute. Verify this is handled correctly when implementing 001cl Step 7.

---

## Commit

`feat(001cm): FeedSliceComment model + thread + codegen context`
