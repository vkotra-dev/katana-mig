# Plan: 001cl — Review Page Sign-off, Inline Edit, Thread & Codegen Context

- **Task:** [tasks/001cl-review-page-edit-and-feed-thread.md](../tasks/001cl-review-page-edit-and-feed-thread.md)
- **Spec:** [docs/superpowers/specs/2026-07-09-review-signoff-thread-codegen-design.md](../docs/superpowers/specs/2026-07-09-review-signoff-thread-codegen-design.md)

## Execution Order

DB models → migrations → schemas → service layer → routes → codegen → frontend API → ReviewGrid → review page

---

## Step 1 — DB models: `current_ball_role` on `MappingSnapshot` + `MappingBindingSignOff` + `LookupSignOff`

**File:** `engine/src/migrations_engine/db/models.py`

On `MappingSnapshot`, add after `status`:
```python
current_ball_role: Mapped[str | None] = mapped_column(String(50), nullable=True)
```

Then add the two new tables:

```python
class MappingBindingSignOff(Base):
    __tablename__ = "mapping_binding_sign_offs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    mapping_snapshot_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("mapping_snapshots.mapping_snapshot_id"), nullable=False, index=True
    )
    destination_object_name: Mapped[str] = mapped_column(String(255), nullable=False)
    source_field: Mapped[str] = mapped_column(String(255), nullable=False)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.user_id"), nullable=False)
    role: Mapped[str] = mapped_column(String(50), nullable=False)
    signed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint(
            "mapping_snapshot_id", "destination_object_name", "source_field", "user_id",
            name="uq_mapping_binding_sign_off"
        ),
    )


class LookupSignOff(Base):
    __tablename__ = "lookup_sign_offs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    lookup_value_map_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("lookup_value_maps.lookup_value_map_id"), nullable=False, index=True
    )
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.user_id"), nullable=False)
    role: Mapped[str] = mapped_column(String(50), nullable=False)
    signed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("lookup_value_map_id", "user_id", name="uq_lookup_sign_off"),
    )
```

---

## Step 2 — Migration `0027_review_sign_offs.py`

**File:** `engine/migrations/versions/0027_review_sign_offs.py`

Check actual latest `down_revision` before writing — read the most recent migration file.

```python
"""add current_ball_role to mapping_snapshots, add sign-off tables

Revision ID: 0027
Revises: 0026
"""
from alembic import op
import sqlalchemy as sa

revision = "0027"
down_revision = "0026"  # verify against latest migration

def upgrade() -> None:
    # Fix 1: ball-holder column
    op.add_column(
        "mapping_snapshots",
        sa.Column("current_ball_role", sa.String(50), nullable=True),
    )

    op.create_table(
        "mapping_binding_sign_offs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("mapping_snapshot_id", sa.String(36), sa.ForeignKey("mapping_snapshots.mapping_snapshot_id"), nullable=False),
        sa.Column("destination_object_name", sa.String(255), nullable=False),
        sa.Column("source_field", sa.String(255), nullable=False),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.user_id"), nullable=False),
        sa.Column("role", sa.String(50), nullable=False),
        sa.Column("signed_at", sa.DateTime, nullable=False),
        sa.UniqueConstraint("mapping_snapshot_id", "destination_object_name", "source_field", "user_id", name="uq_mapping_binding_sign_off"),
    )
    op.create_index("ix_mapping_binding_sign_offs_snapshot", "mapping_binding_sign_offs", ["mapping_snapshot_id"])

    op.create_table(
        "lookup_sign_offs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("lookup_value_map_id", sa.String(36), sa.ForeignKey("lookup_value_maps.lookup_value_map_id"), nullable=False),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.user_id"), nullable=False),
        sa.Column("role", sa.String(50), nullable=False),
        sa.Column("signed_at", sa.DateTime, nullable=False),
        sa.UniqueConstraint("lookup_value_map_id", "user_id", name="uq_lookup_sign_off"),
    )
    op.create_index("ix_lookup_sign_offs_map", "lookup_sign_offs", ["lookup_value_map_id"])

def downgrade() -> None:
    op.drop_column("mapping_snapshots", "current_ball_role")
    op.drop_table("mapping_binding_sign_offs")
    op.drop_table("lookup_sign_offs")
```

---

## Step 3 — Schemas

**File:** `engine/src/migrations_engine/api/schemas.py`

```python
class BindingSignOffEntry(BaseModel):
    signed: bool
    signed_at: datetime | None = None
    user_id: str | None = None

class BindingSignOffStatus(BaseModel):
    central_team: BindingSignOffEntry
    project_stakeholder: BindingSignOffEntry

class SignOffStatusResponse(BaseModel):
    complete: bool
    current_ball_role: str | None = None          # from latest draft MappingSnapshot
    bindings: dict[str, dict[str, BindingSignOffStatus]]  # obj_name → source_field → status
    lookups: dict[str, dict[str, BindingSignOffEntry]]     # lookup_id → role → status

class SignBindingRequest(BaseModel):
    destination_object_name: str
    source_field: str

class UnsignBindingRequest(BaseModel):
    destination_object_name: str
    source_field: str

class PokeRequest(BaseModel):
    target_role: Literal["central_team", "project_stakeholder"]
```

---

## Step 4 — Sign-off service

**File:** `engine/src/migrations_engine/management/sign_offs.py` (new file)

Functions:
- `sign_binding(db, *, actor, project_id, source_definition_id, destination_object_name, source_field)` — upserts `MappingBindingSignOff`; validates actor role is `central_team` or `project_stakeholder`; gets latest snapshot_id for the feed
- `unsign_binding(db, *, actor, ...)` — deletes caller's row only
- `sign_lookup(db, *, actor, project_id, lookup_value_map_id)` — upserts `LookupSignOff`
- `unsign_lookup(db, *, actor, project_id, lookup_value_map_id)` — deletes caller's row
- `get_sign_off_status(db, *, project_id, source_definition_id) → SignOffStatusResponse` — resolves latest `lookup_value_map_id` per lookup name (Fix 2); reads `current_ball_role` from latest draft snapshot; builds full status dict
- `_latest_lookup_map_ids(db, source_definition_id) → list[str]` — subquery returning latest map per `lookup_name`, ordered by `created_at DESC`
- `_is_complete(db, mapping_snapshot_ids, latest_lookup_map_ids) → bool` — inner completeness check against resolved IDs
- `push_for_review(db, *, actor, project_id, source_definition_id)`:
  1. Fetch latest draft snapshot; **403 if `actor.role != snapshot.current_ball_role`** (Fix 3)
  2. **422 if `_is_complete(...)` is False** (Fix 3)
  3. Flip `snapshot.current_ball_role` to opposite role
  4. Create notification to all users of opposite role with project access
  5. Mark caller's unread review notifications for this feed as read
- `poke_reviewer(db, *, actor, project_id, source_definition_id, target_role)` — validates actor is PM (403 otherwise); creates `review.sign_off_reminder` notification for each active user with `target_role` who has project access

---

## Step 5 — `current_ball_role` lifecycle + binding sign-off reset

**File:** `engine/src/migrations_engine/mapping/review.py`

**`propose_mapping`:** after creating the snapshot, set `current_ball_role = "central_team"` (operator reviews first).

**`reject_mapping` (revision request):** set `snapshot.current_ball_role = "central_team"`.

**`approve_mapping`:** set `snapshot.current_ball_role = None`.

**`patch_mapping`:** after updating `field_bindings`, detect changed source fields (compare old vs new `destination_field` per `source_field`) and delete their sign-off rows:

```python
from ..db.models import MappingBindingSignOff

changed_fields = {b["source_field"] for b in new_bindings} - {b["source_field"] for b in old_bindings if b["destination_field"] == new_binding_map.get(b["source_field"])}
# simpler: compare old and new destination_field per source_field; flag any that changed

if changed_fields:
    db.execute(
        delete(MappingBindingSignOff).where(
            MappingBindingSignOff.mapping_snapshot_id == snapshot.mapping_snapshot_id,
            MappingBindingSignOff.source_field.in_(changed_fields),
        )
    )
```

---

## Step 6 — Routes

**File:** `engine/src/migrations_engine/routes/sign_offs.py` (new file)

```python
router = APIRouter(
    prefix="/projects/{project_id}/sources/{source_definition_id}",
    tags=["sign-offs"],
)

@router.post("/mapping/sign-off")
def post_sign_binding(...) -> SignOffStatusResponse: ...

@router.delete("/mapping/sign-off")
def delete_unsign_binding(...) -> SignOffStatusResponse: ...

@router.get("/sign-off-status")
def get_status(...) -> SignOffStatusResponse: ...

@router.post("/push-for-review")
def post_push_for_review(...): ...

@router.post("/review/poke")
def post_poke(...): ...
```

Lookup sign-off routes sit under the existing lookup router prefix or in this same file:

```python
@router.post("/lookups/{lookup_value_map_id}/sign-off")
def post_sign_lookup(...): ...

@router.delete("/lookups/{lookup_value_map_id}/sign-off")
def delete_unsign_lookup(...): ...
```

Register router in `app.py`.

---

## Step 7 — Codegen: inject feed comments with formatting constraints (Fix 4)

**File:** `engine/src/migrations_engine/codegen/service.py`

Add formatting helper before `_build_user_prompt`:

```python
_MAX_COMMENT_CHARS = 400
_MAX_DISCUSSION_CHARS = 3000
_MAX_COMMENT_COUNT = 30

def _format_discussion(comments: list[FeedComment]) -> str:
    if not comments:
        return ""
    recent = comments[-_MAX_COMMENT_COUNT:]
    lines = ["Feed discussion (context for mapping intent and business rules):"]
    total = len(lines[0])
    for c in recent:
        content = " ".join(c.content.split())  # collapse whitespace/newlines
        if len(content) > _MAX_COMMENT_CHARS:
            content = content[:_MAX_COMMENT_CHARS] + "…"
        line = f"[{c.author_role}] {c.created_at.date()}: {content}"
        if total + len(line) + 1 > _MAX_DISCUSSION_CHARS:
            lines.append("[discussion truncated]")
            break
        lines.append(line)
        total += len(line) + 1
    return "\n".join(lines)
```

In `generate_codegen_artifact`, fetch comments before building prompt:

```python
from ..db.models import FeedComment

comments = list(db.scalars(
    select(FeedComment)
    .where(FeedComment.source_definition_id == source_definition_id)
    .order_by(FeedComment.created_at.asc())
).all())
```

Update `_build_user_prompt` to accept `comments: list[FeedComment]` and append formatted block:

```python
discussion = _format_discussion(comments)
if discussion:
    lines.append("")
    lines.append(discussion)
```

---

## Step 8 — Frontend API helpers

**File:** `web/lib/sign-offs-api.ts` (new file)

```typescript
export interface BindingSignOffEntry {
  signed: boolean;
  signedAt: string | null;
  userId: string | null;
}

export interface BindingSignOffStatus {
  centralTeam: BindingSignOffEntry;
  projectStakeholder: BindingSignOffEntry;
}

export interface SignOffStatusRecord {
  complete: boolean;
  currentBallRole: "central_team" | "project_stakeholder" | null;
  bindings: Record<string, Record<string, BindingSignOffStatus>>;
  lookups: Record<string, Record<string, BindingSignOffEntry>>;
}

export async function getSignOffStatus(token, projectId, feedId): Promise<SignOffStatusRecord>
export async function signBinding(token, projectId, feedId, destObj, sourceField): Promise<SignOffStatusRecord>
export async function unsignBinding(token, projectId, feedId, destObj, sourceField): Promise<SignOffStatusRecord>
export async function signLookup(token, projectId, feedId, lookupId): Promise<SignOffStatusRecord>
export async function unsignLookup(token, projectId, feedId, lookupId): Promise<SignOffStatusRecord>
export async function pushForReview(token, projectId, feedId): Promise<void>
export async function pokeReviewer(token, projectId, feedId, targetRole): Promise<void>
```

---

## Step 9 — ReviewGrid: sign-off indicators + editable destination

**File:** `web/components/projects/ReviewGrid.tsx`

Add props:
```typescript
signOffStatus?: SignOffStatusRecord;
currentUserRole?: SessionRole;
editingEnabled?: boolean;
onSignBinding?: (tableName: string, sourceField: string) => void;
onUnsignBinding?: (tableName: string, sourceField: string) => void;
onDestinationFieldChange?: (tableName: string, sourceField: string, newDest: string) => void;
onSignLookup?: (lookupId: string) => void;
```

Per binding row:
- When `signOffStatus` provided: render two small chips `[OP]` and `[ST]` — green with checkmark if signed, grey with dash if not. Tooltip on hover shows `signed_at` and `user_id`.
- "Sign off" button rendered when `onSignBinding` is provided AND current user's role slot is unsigned.
- When `editingEnabled && onDestinationFieldChange`: render `<input type="text">` for destination field instead of plain text. `onChange` calls `onDestinationFieldChange`.

Per lookup group header:
- Same two chips using `signOffStatus.lookups[lookupId]`
- "Sign off" button when current user's slot is unsigned

---

## Step 10 — Review page: full wiring

**File:** `web/app/projects/[id]/feeds/[feedId]/review/page.tsx`

New state:
```typescript
const [signOffStatus, setSignOffStatus] = useState<SignOffStatusRecord | null>(null);
const [editingEnabled, setEditingEnabled] = useState(false);
const [pendingBindings, setPendingBindings] = useState<Record<string, Record<string, string>>>({});
const [lastPokeTime, setLastPokeTime] = useState<string | null>(null);
```

In `loadData`, after fetching snapshots:
```typescript
const status = await getSignOffStatus(token, projectId, feedId);
setSignOffStatus(status);
// Fix 1: gate on server-authoritative currentBallRole, not notification read state
setEditingEnabled(status.currentBallRole === session?.role);
```

No `listNotifications` call needed for the editing gate. `currentBallRole` is stable across refresh and notification read events.

Handlers:
- `handleSignBinding(tableName, sourceField)` → `signBinding(...)` → `setSignOffStatus`
- `handleUnsignBinding(tableName, sourceField)` → `unsignBinding(...)` → `setSignOffStatus`
- `handleSignLookup(lookupId)` → `signLookup(...)` → `setSignOffStatus`
- `handleDestinationChange(tableName, sourceField, newDest)` → update `pendingBindings`; clear sign-off chips for that binding in local state
- `handleSave()` → for each changed snapshot call `patchMappingSnapshot` → reload snapshots + sign-off status → clear `pendingBindings`
- `handlePushForReview()` → `pushForReview(...)` → success toast
- `handlePoke(targetRole)` → `pokeReviewer(...)` → `setLastPokeTime(new Date().toISOString())`

Progress bar rendered above ReviewGrid:
```tsx
<div>
  {signedCount}/{totalCount} bindings fully signed — {unsignedLookups} lookups pending
  <progress value={signedCount} max={totalCount} />
  {role === "pm" && (
    <>
      <button onClick={() => handlePoke("central_team")}>Poke Operator</button>
      <button onClick={() => handlePoke("project_stakeholder")}>Poke Stakeholder</button>
      {lastPokeTime && <span>Last poked {lastPokeTime}</span>}
    </>
  )}
</div>
```

"Save changes" button: visible when `Object.keys(pendingBindings).length > 0`
"Push for review" button: visible when `editingEnabled` (i.e. caller IS the ball holder); disabled unless `signOffStatus?.complete`. Server enforces both gates independently (Fix 3).

ReviewGrid props:
```tsx
<ReviewGrid
  ...existingProps
  signOffStatus={signOffStatus ?? undefined}
  currentUserRole={role}
  editingEnabled={editingEnabled}
  onSignBinding={handleSignBinding}
  onUnsignBinding={handleUnsignBinding}
  onDestinationFieldChange={handleDestinationChange}
  onSignLookup={handleSignLookup}
/>
```

---

## Step 11 — FeedCommentThread on review page

**File:** `web/app/projects/[id]/feeds/[feedId]/review/page.tsx`

Import and mount below `ReviewGrid`:
```tsx
import { FeedCommentThread } from "../../../../../../components/feeds/FeedCommentThread";

{session && (
  <FeedCommentThread feedId={feedId} projectId={projectId} token={session.accessToken} />
)}
```

No other changes — component is fully built.

---

## Step 12 — Tests

**Backend:**
- `sign_binding` creates row; duplicate call is idempotent (upsert)
- `unsign_binding` deletes only caller's row, not other party's
- `patch_mapping` with changed destination deletes sign-off rows for changed fields only
- `push_for_review` returns 422 when status is incomplete; creates notification on success
- `poke_reviewer` returns 403 for non-PM; creates notifications for each target-role user
- `get_sign_off_status` returns `complete: true` only when all bindings + lookups have both roles

**Frontend:**
- `ReviewGrid` renders OP/ST chips when `signOffStatus` provided
- "Sign off" button absent when user's slot is already signed
- Destination field is `<input>` when `editingEnabled`, plain text otherwise
- Progress bar counts correctly; "Push for review" disabled when incomplete

---

## Commit

`feat(001cl): per-binding sign-off, inbox-gated edit, review thread, codegen context`
