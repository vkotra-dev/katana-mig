# Design: Review Page Sign-off, Inline Edit, Thread & Codegen Context

**Date:** 2026-07-09
**Tasks:** 001cl (review sign-off + thread + codegen), 001cm (slice comment thread)
**Rev:** 2 — four corrections applied (ball-holder column, lookup reset rule, push gating, LLM formatting)

---

## Problem

Three gaps block the mapping review workflow from being trustworthy and auditable:

1. **No per-binding accountability.** The review page is read-only for all except the stakeholder's approve/reject. There is no record of who confirmed which field mapping was correct.
2. **No conversation at the review layer.** `FeedCommentThread` (001ao) is wired only to the fiber page. The review page has no comment thread.
3. **Codegen has no human context.** The AI prompt receives field bindings and config but none of the human discussion explaining *why* a binding is what it is.

A fourth gap (slice-level comments on the data approval screen) is tracked separately as `001cm`.

---

## Scope

### In scope (001cl)
- Multi-party sign-off per binding and per lookup, persisted
- `current_ball_role` column on `MappingSnapshot` — explicit ball-holder tracking
- Ball-holder-gated destination field editing on the review page
- "Push for review" gated on complete sign-off AND caller holding the ball
- PM read-only sign-off observer + poke (targeted notification) + thread participant
- `FeedCommentThread` on the review page
- Feed comment thread injected into codegen AI prompt with formatting constraints

### Out of scope
- Slice-level comments (001cm)
- Dropdown with DDL-sourced destination columns (free-text edit for now)
- Comment editing or deletion
- Sign-off delegation or proxy

---

## Data Model

### `current_ball_role` on `MappingSnapshot`

Add `current_ball_role: VARCHAR(50) | NULL` to `MappingSnapshot`.

| Event | `current_ball_role` value |
|---|---|
| `propose_mapping` (AI proposes) | `"central_team"` — operator reviews first |
| `push_for_review` | flips to opposite role (`"project_stakeholder"` ↔ `"central_team"`) |
| `reject_mapping` (revision request) | `"central_team"` — operator must fix |
| `approve_mapping` | `NULL` — workflow complete |

**Editing gate:** `editingEnabled = (session.role === snapshot.currentBallRole)`. No notification fetch needed. Survives page refresh, tab changes, and notification read events.

**Migration:** `ALTER TABLE mapping_snapshots ADD COLUMN current_ball_role VARCHAR(50)`. Applied in migration `0027` alongside sign-off tables.

### `MappingBindingSignOff`

```
id                      UUID PK
mapping_snapshot_id     FK → mapping_snapshots
destination_object_name VARCHAR
source_field            VARCHAR
user_id                 FK → users
role                    VARCHAR   -- central_team | project_stakeholder
signed_at               TIMESTAMP

UNIQUE (mapping_snapshot_id, destination_object_name, source_field, user_id)
INDEX  (mapping_snapshot_id)
```

### `LookupSignOff`

```
id                  UUID PK
lookup_value_map_id FK → lookup_value_maps
user_id             FK → users
role                VARCHAR   -- central_team | project_stakeholder
signed_at           TIMESTAMP

UNIQUE (lookup_value_map_id, user_id)
INDEX  (lookup_value_map_id)
```

### Reset rules

**Binding reset:** When `patch_mapping` updates bindings, delete `MappingBindingSignOff` rows for every changed binding (both parties' rows). Detected by comparing old vs new `destination_field` per `source_field`.

```sql
DELETE FROM mapping_binding_sign_offs
WHERE mapping_snapshot_id = :sid
  AND destination_object_name = :obj
  AND source_field IN (:changed_fields)
```

**Lookup reset:** `LookupValueMap` is immutable — every "edit" creates a new record with a new `lookup_value_map_id`. A new map therefore has no `LookupSignOff` rows by construction. No explicit DELETE needed. However, `get_sign_off_status` must resolve the *latest* active `lookup_value_map_id` per lookup name when querying sign-off state, so stale sign-offs on superseded maps are never surfaced.

```python
# Resolve latest map per lookup_name
latest_map_ids = db.scalars(
    select(LookupValueMap.lookup_value_map_id)
    .where(LookupValueMap.source_definition_id == source_definition_id)
    .distinct(LookupValueMap.lookup_name)
    .order_by(LookupValueMap.lookup_name, LookupValueMap.created_at.desc())
).all()
```

### Poke tracking

No separate table. Poke fires a notification with `event_type = "review.sign_off_reminder"` and `deep_link → /projects/{id}/feeds/{feedId}/review`. PM sees "Last poked [time]" by querying the most recent notification of this type for the feed.

---

## Completeness Rule

A feed is **fully signed off** when:
- Every binding in every draft snapshot has both `central_team` and `project_stakeholder` rows in `MappingBindingSignOff`
- Every latest active `LookupValueMap` for the feed has both roles in `LookupSignOff`

Checked server-side on the push endpoint (hard gate) and client-side to enable the button (soft gate).

---

## API

### Sign-off endpoints

```
POST /projects/{project_id}/sources/{feed_id}/mapping/sign-off
Body: { destination_object_name, source_field }
Auth: central_team or project_stakeholder only
Effect: upsert MappingBindingSignOff for current user

DELETE /projects/{project_id}/sources/{feed_id}/mapping/sign-off
Body: { destination_object_name, source_field }
Auth: current user's own row only

POST /projects/{project_id}/sources/{feed_id}/lookups/{lookup_id}/sign-off
Auth: central_team or project_stakeholder only
Effect: upsert LookupSignOff for current user

DELETE /projects/{project_id}/sources/{feed_id}/lookups/{lookup_id}/sign-off
Auth: current user's own row only
```

### Status endpoint

```
GET /projects/{project_id}/sources/{feed_id}/sign-off-status
Returns:
{
  complete: bool,
  currentBallRole: "central_team" | "project_stakeholder" | null,
  bindings: {
    [destination_object_name]: {
      [source_field]: {
        central_team: { signed: bool, signed_at, user_id } | null,
        project_stakeholder: { signed: bool, signed_at, user_id } | null
      }
    }
  },
  lookups: {
    [lookup_value_map_id]: {
      central_team: { signed: bool, signed_at, user_id } | null,
      project_stakeholder: { signed: bool, signed_at, user_id } | null
    }
  }
}
```

`currentBallRole` is read from the latest draft `MappingSnapshot` for this feed.

### Push for review

```
POST /projects/{project_id}/sources/{feed_id}/push-for-review
Auth: central_team or project_stakeholder

Server-side hard gates (in order):
  1. 403 if actor.role !== snapshot.current_ball_role
  2. 422 if completeness check fails (not all items signed by both parties)

Effect:
  - flip snapshot.current_ball_role to opposite role
  - create notification to all users of opposite role with project access
  - mark caller's unread review notifications for this feed as read
```

### Poke

```
POST /projects/{project_id}/sources/{feed_id}/review/poke
Body: { target_role: "central_team" | "project_stakeholder" }
Auth: pm only — 403 for any other role
Effect: create review.sign_off_reminder notification for each user with target_role who has project access
```

---

## Review Page UI

### Ball-holder-gated editing

On load, fetch `getSignOffStatus`. Response includes `currentBallRole`. Set:

```typescript
const editingEnabled = signOffStatus.currentBallRole === session.role;
```

No notification fetch required. Editing access is determined entirely by server-side state. Stable across refresh and notification read events.

`pendingBindings: Record<tableName, Record<sourceField, newDestField>>` tracks changes. "Save changes" button appears when entries exist. Save calls `patchMappingSnapshot` (full binding replacement) then reloads snapshots and sign-off status. Client-side sign-off chips for changed bindings reset immediately on input change.

### Sign-off indicators

Each binding row shows two chips alongside existing cells:

```
[source_field] → [dest_field]  [OP ✓] [ST ✓]  [Sign off]
[source_field] → [dest_field]  [OP ✓] [ST —]  [Sign off]
[source_field] → [dest_field]  [OP —] [ST —]  [Sign off]  ← edited, both reset
```

- `OP` = central_team; `ST` = project_stakeholder
- ✓ = green chip (hover → signed_at + user display name); — = grey
- "Sign off" button visible only when the current user's role chip is unsigned
- Click → `POST .../mapping/sign-off` → refresh status

Lookup groups show the same two chips at the group header level.

### Progress counter

Above grid: **"5 / 12 bindings fully signed — 2 lookups pending"** with a progress bar.

### Push for review

Disabled (tooltip: "Sign off all items first") until `signOffStatus.complete`. Visible only to the ball holder (`editingEnabled === true`). On click → server validates ball + completeness → success toast "Review pushed to [opposite role]".

### PM controls

PM sees sign-off chips (read-only), progress counter, and two poke buttons:

```
[Poke Operator]   [Last poked 14:32]
[Poke Stakeholder]
```

Poke button calls `pokeReviewer(targetRole)`, updates `lastPokeTime` locally.

### Comment thread

`FeedCommentThread` mounts below the mapping grid. All roles can post.

---

## Codegen Context Injection

### Formatting constraints

Discussion context must not bloat or destabilize the prompt. Apply a dedicated helper:

```python
_MAX_COMMENT_CHARS = 400        # per comment, hard-truncate
_MAX_DISCUSSION_CHARS = 3000    # total budget for the discussion section
_MAX_COMMENT_COUNT = 30         # take the most recent N if more exist

def _format_discussion(comments: list[FeedComment]) -> str:
    """Return a structured discussion block within prompt budget constraints."""
    if not comments:
        return ""

    recent = comments[-_MAX_COMMENT_COUNT:]  # most recent N
    lines = ["Feed discussion (context for mapping intent and business rules):"]
    total = len(lines[0])

    for c in recent:
        # Sanitize: strip control chars and collapse internal newlines
        content = " ".join(c.content.split())
        # Hard-truncate per comment
        if len(content) > _MAX_COMMENT_CHARS:
            content = content[:_MAX_COMMENT_CHARS] + "…"
        line = f"[{c.author_role}] {c.created_at.date()}: {content}"
        if total + len(line) + 1 > _MAX_DISCUSSION_CHARS:
            lines.append("[discussion truncated — remaining comments omitted]")
            break
        lines.append(line)
        total += len(line) + 1

    return "\n".join(lines)
```

`_build_user_prompt` calls `_format_discussion(comments)` and appends the result after field bindings only if non-empty. No comments → no section added.

---

## Slice Comment Thread (001cm — separate task)

`FeedSliceComment` keyed on `source_slice_id`. Same pattern as `FeedComment`/`FeedCommentThread`. Wired into the slice approval screen. Also injected into the codegen prompt (after feed-level comments, within its own budget). Tracked separately.

---

## Verification

1. `propose_mapping` → `snapshot.current_ball_role = "central_team"`
2. Operator visits review page → destination fields editable; stakeholder visits same page → read-only
3. Operator signs a binding → OP chip green; ST chip grey; push locked
4. Stakeholder signs same binding → both chips green
5. Operator edits a signed binding → both chips immediately reset client-side; server confirms on reload
6. New lookup version created → old sign-offs on prior map not surfaced in status
7. All items signed by both roles → "Push for review" unlocks (ball holder only)
8. Non-ball-holder calls push-for-review → 403
9. Completeness fails → push-for-review → 422
10. Push succeeds → `current_ball_role` flips; opposite role receives notification
11. PM pokes operator → operator receives `review.sign_off_reminder`; "Last poked" updates
12. Codegen prompt: discussion section appears, each comment ≤ 400 chars, total ≤ 3000 chars
13. No comments → no discussion section in prompt
