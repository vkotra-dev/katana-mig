# Summary: 001cl — Review Page Sign-off, Inline Edit, Thread & Codegen Context

## What was built

All deliverables are fully implemented.

### Backend

| File | What landed |
|------|-------------|
| `db/models.py` | `MappingBindingSignOff`, `LookupSignOff` tables + `current_ball_role` on `MappingSnapshot` |
| `migrations/0027_review_sign_offs.py` | DDL for both sign-off tables and the new column |
| `management/sign_offs.py` | `sign_binding`, `unsign_binding`, `sign_lookup`, `unsign_lookup`, `get_sign_off_status`, `push_for_review`, `poke_reviewer` |
| `mapping/review.py` | `current_ball_role` set on propose/reject/approve; sign-off rows deleted on `patch_mapping` for changed fields |
| `routes/sign_offs.py` | POST/DELETE `/mapping/sign-off`, GET `/sign-off-status`, POST `/push-for-review`, POST `/review/poke`, POST/DELETE `/lookups/{id}/sign-off` |
| `app.py` | Router registered |
| `codegen/service.py` | Feed-level comments fetched via `FeedComment JOIN User` + `source_slice_id IS NULL` filter; `_format_discussion` with 3000-char budget |

### Frontend

| File | What landed |
|------|-------------|
| `lib/sign-offs-api.ts` | All 7 API helpers with manual camelCase mapper (preserves dynamic table/field names) |
| `components/projects/ReviewGrid.tsx` | OP/ST chips, sign button, unsign button, editable destination field input |
| `app/projects/[id]/feeds/[feedId]/review/page.tsx` | Full sign-off state, `editingEnabled` gate from `currentBallRole`, progress bar, PM poke button, `UnifiedCommentThread` mounted |

### Design decisions

- **`currentBallRole` as edit gate** — server-authoritative; does not depend on notification read state.
- **Sign-off reset** — `patch_mapping` deletes sign-off rows only for fields whose `destination_field` changed.
- **Push guard** — both role check and completeness enforced server-side independently of client disable.
- **Comment thread** — uses `UnifiedCommentThread` (also used on feeds workspace) rather than the lighter `FeedCommentThread` originally planned.

## Deviations from plan

- Codegen comment fetch uses `FeedComment.source_slice_id.is_(None)` to filter to feed-level comments only, using the unified `feed_comments` table (post-migration `0029`) rather than accessing a non-existent `author_role` column.
- `UnifiedCommentThread` used instead of `FeedCommentThread` (component was upgraded between planning and implementation).

## Verification

All 10 acceptance criteria in the task file pass.
