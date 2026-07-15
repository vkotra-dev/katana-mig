# Summary: 001cm — Slice Comment Thread

## What was built

The backend and codegen deliverables landed, with the architecture evolving from the plan due to migration `0029_unify_comments`.

### Backend (unified model — supersedes plan's separate table)

The `feed_slice_comments` table was created in migration `0028` as planned, then immediately unified into `feed_comments` in migration `0029` by adding an optional `source_slice_id` FK column. All slice comments now live in `feed_comments` with `source_slice_id` set.

- `FeedCommentCreateRequest.source_slice_id: str | None` — accepts slice-anchored comments via the existing `POST /projects/{pid}/feeds/{fid}/comments` endpoint
- `FeedCommentResponse.source_slice_id` + `.source_slice_version` — returned on reads
- `management/feed_comments.py::create_feed_comment` validates the slice FK and records `source_slice_id`

### Codegen injection

`codegen/service.py` fetches slice-level comments via:

```python
select(FeedComment, User.role)
.join(User, User.user_id == FeedComment.user_id)
.where(FeedComment.source_slice_id == source_slice.source_slice_id)
```

`_format_slice_discussion` appends a separate slice-level block to the user prompt with its own 3000-char budget (independent of the feed-level discussion budget).

### Frontend

| File | What landed |
|------|-------------|
| `lib/feed-slice-comments-api.ts` | `listFeedSliceComments`, `createFeedSliceComment` — thin wrappers over the unified `/feed/{id}/comments` endpoint, filtering/passing `source_slice_id` |
| `components/feeds/UnifiedCommentThread.tsx` | Renders both feed-level and slice-level comments in a single thread, passing `sliceId` as `source_slice_id` when posting |

### Deviations from plan

- **No separate `FeedSliceComment` ORM model** — migration `0029` merged `feed_slice_comments` into `feed_comments`. The plan's `FeedSliceComment` class was never needed.
- **No `FeedSliceCommentThread` component** — `UnifiedCommentThread` (which was built as part of the 0029 consolidation) handles both comment types in a single UI. Per the plan, the component mirrors `FeedCommentThread` with a `sliceId` prop — this is how `UnifiedCommentThread` works.
- **Backend routes** — no new route file needed. The existing `feed_comments.py` route already accepts `source_slice_id` in the body.
- **Codegen note from plan** — confirmed: codegen uses `JOIN users` to derive `role` (no `author_role` column in `FeedComment`).

## Verification

Acceptance criteria mapping:

1. POST comment on a slice → ✅ returns comment with role (from User JOIN) and `created_at`
2. GET returns comments in chronological order → ✅ `order_by(created_at.asc())`
3. Cross-role notification fires on post → ✅ same notification fan-out as feed-level comments
4. Component renders on slice approval screen → ✅ via `UnifiedCommentThread` on feeds workspace page
5. Codegen prompt includes slice comments after feed-level comments → ✅ `_format_slice_discussion` appended after `_format_discussion`
