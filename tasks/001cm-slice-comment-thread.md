# Task: 001cm — Slice Comment Thread

## Status
Ready

## Background

`FeedComment` (001ao) is keyed on `source_definition_id` — feed-level discussion about mapping intent and workflow. But there is no comment thread at the **slice** level. A slice is a specific upload/batch of a feed. Discussions about that data (suspicious values, unexpected row counts, masking questions, data quality flags) are distinct from mapping discussions and belong at the slice level.

This was an intended feature that was not captured in 001ao and was not part of 001cc (feed slice approval data profile).

## Model

`FeedSliceComment` — same pattern as `FeedComment`:

```
id                  UUID PK
source_slice_id     FK → source_slices.source_slice_id  (index)
author_user_id      FK → users.user_id
author_role         VARCHAR
content             TEXT
created_at          TIMESTAMP
```

Migration: `0028_slice_comments.py`

## API

```
GET  /projects/{project_id}/sources/{feed_id}/slices/{slice_id}/comments
POST /projects/{project_id}/sources/{feed_id}/slices/{slice_id}/comments
Body: { content: str }
```

Same cross-role notification pattern as `FeedComment`: central_team comment notifies project_stakeholders; stakeholder comment notifies all central_team users. Notification failure never blocks the comment.

## Frontend

- `FeedSliceCommentThread` component — mirrors `FeedCommentThread` with `sliceId` prop instead of `feedId`
- Wire into the slice approval screen (`web/app/projects/[id]/feeds/[feedId]/page.tsx` approval card, or the standalone slice review screen if one exists)
- API helpers `listSliceComments` + `createSliceComment` in `web/lib/feeds-api.ts`

## Codegen Context

After 001cl lands, extend `codegen/service.py` `_build_user_prompt` to also include slice comments for the source slice in use:

```python
slice_comments = db.scalars(
    select(FeedSliceComment)
    .where(FeedSliceComment.source_slice_id == source_slice.source_slice_id)
    .order_by(FeedSliceComment.created_at.asc())
).all()
```

Append after feed-level comments:
```
Slice data discussion (context about this specific batch):
[central_team] 2026-07-09: Row 47 has blank INSURED_NAME — confirmed valid, insured is the policy entity
```

## Files Changed

**Backend:**
- `engine/src/migrations_engine/db/models.py` — `FeedSliceComment`
- `engine/migrations/versions/0028_slice_comments.py` (new)
- `engine/src/migrations_engine/api/schemas.py` — `FeedSliceCommentResponse`, `FeedSliceCommentCreateRequest`
- `engine/src/migrations_engine/management/slice_comments.py` (new)
- `engine/src/migrations_engine/routes/slice_comments.py` (new)
- `engine/src/migrations_engine/codegen/service.py` — extend prompt with slice comments

**Frontend:**
- `web/lib/feeds-api.ts` — `listSliceComments`, `createSliceComment`
- `web/components/feeds/FeedSliceCommentThread.tsx` (new)
- Slice approval screen — mount `FeedSliceCommentThread`

## Depends On

001cl (slice comment codegen injection extends the pattern established there)

## Verification

1. POST comment on a slice → returns comment with author_role and created_at
2. GET returns comments in chronological order
3. Cross-role notification fires on post (operator comment → stakeholders notified)
4. `FeedSliceCommentThread` renders on slice approval screen; submit clears textarea
5. Codegen prompt includes slice comments after feed-level comments
6. All tests pass
