# Task: 001cl — Review Page Sign-off, Inline Edit, Thread & Codegen Context

**Plan:** [plans/2026-07-09-001cl-review-signoff-thread-codegen.md](../plans/2026-07-09-001cl-review-signoff-thread-codegen.md)
**Spec:** [docs/superpowers/specs/2026-07-09-review-signoff-thread-codegen-design.md](../docs/superpowers/specs/2026-07-09-review-signoff-thread-codegen-design.md)

## Status
Ready

## Problem

Three gaps block the mapping review workflow:

1. **No per-binding accountability.** Approve/reject is a single gesture by one stakeholder. No record of who confirmed which field mapping was correct.
2. **No conversation on the review page.** `FeedCommentThread` is wired to the fiber page only. Operator, stakeholder, and PM cannot discuss specific bindings where the decisions are being made.
3. **Codegen has no human context.** The AI prompt receives bindings and config but none of the discussion that explains *why* a mapping is what it is.

## Solution

### Multi-party sign-off (persisted)

Two new tables:
- `MappingBindingSignOff` — keyed on `(mapping_snapshot_id, destination_object_name, source_field, user_id)`
- `LookupSignOff` — keyed on `(lookup_value_map_id, user_id)`

Required signatories per item: **operator (central_team) + stakeholder (project_stakeholder)**. Both must sign each binding and each lookup. Sign-offs persist across sessions. Editing a binding resets both parties' sign-offs for that binding.

"Push for review" is only enabled when all bindings and all lookups have both sign-offs.

### PM: read-only observer + poke

PM sees sign-off status chips per row (read-only). PM can poke a lagging party via a "Poke [role]" button — fires a `review.sign_off_reminder` notification (reuses 001at notification infrastructure). "Last poked [time]" label updates after poke. PM also participates in the comment thread.

### Inbox-gated destination field editing

On review page load, check `listNotifications` for unread items with `deepLink` containing this feed's `/review` URL. If found: destination fields become editable text inputs; "Save changes" button appears. Save calls `patchMappingSnapshot` (full binding replacement, same as 001bq workspace pattern) then reloads snapshots and sign-off status.

### FeedCommentThread

Mount `FeedCommentThread` below the mapping grid. All roles can comment. Cross-role notifications fire on post (existing 001ao behaviour). No backend change needed.

### Codegen context injection

`codegen/service.py` fetches feed comments and appends them to `_build_user_prompt` after the field bindings section. Gives the AI the human rationale behind mapping decisions.

## Files Changed

**Backend:**
- `engine/src/migrations_engine/db/models.py` — `MappingBindingSignOff`, `LookupSignOff` models
- `engine/migrations/versions/0027_review_sign_offs.py` (new)
- `engine/src/migrations_engine/api/schemas.py` — sign-off schemas, `PokeRequest`
- `engine/src/migrations_engine/management/sign_offs.py` (new) — sign, unsign, status, push, poke
- `engine/src/migrations_engine/mapping/review.py` — reset sign-offs on patch
- `engine/src/migrations_engine/routes/sign_offs.py` (new) — sign-off + poke + push routes
- `engine/src/migrations_engine/codegen/service.py` — inject comments into prompt

**Frontend:**
- `web/lib/sign-offs-api.ts` (new) — sign, unsign, status, push, poke API helpers
- `web/components/projects/ReviewGrid.tsx` — sign-off chips, sign button, editable destination
- `web/app/projects/[id]/feeds/[feedId]/review/page.tsx` — full wiring: sign-off state, inbox check, progress bar, PM poke, FeedCommentThread

## Out of Scope

- Slice-level comments (001cm)
- Dropdown with DDL-sourced valid destination columns (free-text for now)
- Per-table bulk sign-off
- Comment editing or deletion

## Verification

1. Operator signs a binding → OP chip green; ST chip grey; push locked
2. Stakeholder signs same binding → both chips green
3. Editing a signed binding → both chips reset
4. All items fully signed → "Push for review" unlocks
5. PM clicks "Poke Stakeholder" → stakeholder receives notification; "Last poked" label updates
6. PM can post comments; other roles notified
7. No inbox item for feed → review page read-only (existing approve/reject still works)
8. Inbox item present → destination fields editable; save calls patchMappingSnapshot
9. Codegen prompt contains feed comment thread after field bindings
10. All tests pass
