# Plan: Task 002b8 — Version History for Mapping Fields

- **Task**: [002b8-version-history-for-mapping-fields.md](./002b8-version-history-for-mapping-fields.md)

---

## Step-by-Step Build Instructions (Agent Executable)

---

### Step 1: Create Alembic Migration

**File**: `engine/migrations/versions/0043_add_version_history.py` (new)

Read the latest migration (`engine/migrations/versions/0042_add_source_ddl_to_source_schema_artifact.py`) to confirm `down_revision = "0042"`. Create migration `0043` with:

```python
"""add version_history table

Revision ID: 0043
Revises: 0042
"""
from alembic import op
import sqlalchemy as sa

revision = "0043"
down_revision = "0042"


def upgrade() -> None:
    op.create_table(
        "version_history",
        sa.Column("version_id", sa.String(36), nullable=False),
        sa.Column("entity_type", sa.String(64), nullable=False, index=True),
        sa.Column("entity_id", sa.String(36), nullable=False, index=True),
        sa.Column("field_name", sa.String(128), nullable=False),
        sa.Column("old_value", sa.Text(), nullable=True),
        sa.Column("new_value", sa.Text(), nullable=True),
        sa.Column("changed_by", sa.String(36), nullable=True, index=True),
        sa.Column("changed_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("version_id"),
    )
    op.create_index(
        "ix_version_history_entity",
        "version_history",
        ["entity_type", "entity_id", "field_name"],
    )


def downgrade() -> None:
    op.drop_index("ix_version_history_entity", table_name="version_history")
    op.drop_table("version_history")
```

---

### Step 2: Add SQLAlchemy Model

**File**: `engine/src/migrations_engine/db/models.py`

Append the `VersionHistory` model after the `AICallLog` class at the end of the file:

```python
class VersionHistory(Base):
    __tablename__ = "version_history"

    version_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    entity_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    entity_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    field_name: Mapped[str] = mapped_column(String(128), nullable=False)
    old_value: Mapped[str | None] = mapped_column(Text)
    new_value: Mapped[str | None] = mapped_column(Text)
    changed_by: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        sa.Index("ix_version_history_entity", "entity_type", "entity_id", "field_name"),
    )
```

---

### Step 3: Add Schema Models

**File**: `engine/src/migrations_engine/api/schemas.py`

Append after the `AICallLogResponse` class at the end of the file:

```python
class VersionHistoryResponse(BaseModel):
    version_id: str
    field_name: str
    old_value: str | None
    new_value: str | None
    changed_by: str | None
    changed_at: datetime


class VersionHistoryCreateRequest(BaseModel):
    """Request to capture a version snapshot when updating a field."""
    field_name: str
    old_value: str | None = None
    new_value: str | None = None
```

---

### Step 4: Create Version History API Routes

**File**: `engine/src/migrations_engine/routes/versions.py` (new)

```python
"""Version history endpoints for mapping hints, codegen instructions,
transformation instructions, and SQL scripts."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..api.deps import get_current_user, get_db
from ..api.schemas import VersionHistoryResponse
from ..db.models import User, VersionHistory

router = APIRouter(tags=["versions"])


def _entity_route(entity_type: str) -> APIRouter:
    """Create a sub-router for a single entity (e.g. feed-hints, project-codegen)."""
    r = APIRouter()

    @r.get("/versions", response_model=list[VersionHistoryResponse])
    def get_entity_versions(
        actor: User = Depends(get_current_user),
        db: Session = Depends(get_db),
        limit: int = Query(default=50, le=200),
        offset: int = Query(default=0, ge=0),
    ) -> list[VersionHistoryResponse]:
        rows = (
            db.execute(
                select(VersionHistory)
                .where(
                    VersionHistory.entity_type == entity_type,
                )
                .order_by(VersionHistory.changed_at.desc())
                .limit(limit)
                .offset(offset)
            )
            .scalars()
            .all()
        )
        return rows

    return r


# Per-entity routes
router.include_router(_entity_route("feed_hints"), prefix="/feed-hints")
router.include_router(_entity_route("project_codegen"), prefix="/project-codegen")
router.include_router(_entity_route("feed_transformation"), prefix="/feed-transformation")
router.include_router(_entity_route("codegen_sql"), prefix="/codegen-sql")
```

Register in `engine/src/migrations_engine/app.py`:
```python
from .routes.versions import router as versions_router
# ... and add:
app.include_router(versions_router)
```

---

### Step 5: Add Version Capture to PATCH Handlers

**File**: `engine/src/migrations_engine/routes/feeds.py`

Import changes at top:
```python
from ..db.models import User, Feed, VersionHistory
from ..api.deps import AuthApiError, get_central_team_user, get_current_user, get_db
from datetime import datetime as _dt
```

In `patch_source_hints` (line ~151), replace the handler body to capture old value before writing:
```python
feed = db.get(Feed, source_definition_id)
if feed is None or feed.project_id != project_id:
    raise AuthApiError("feed_not_found", "Feed not found.", 404)
_old = feed.mapping_hints
feed.mapping_hints = body.mapping_hints
db.add(VersionHistory(
    entity_type="feed_hints",
    entity_id=source_definition_id,
    field_name="mapping_hints",
    old_value=_old,
    new_value=body.mapping_hints,
    changed_by=actor.user_id,
    changed_at=_dt.now(_dt.timezone.utc),
))
db.commit()
```

In `patch_source_transformation_instructions` (line ~180), same pattern:
```python
feed = db.get(Feed, source_definition_id)
if feed is None or feed.project_id != project_id:
    raise AuthApiError("feed_not_found", "Feed not found.", 404)
_old = feed.transformation_instructions
feed.transformation_instructions = body.transformation_instructions
db.add(VersionHistory(
    entity_type="feed_transformation",
    entity_id=source_definition_id,
    field_name="transformation_instructions",
    old_value=_old,
    new_value=body.transformation_instructions,
    changed_by=actor.user_id,
    changed_at=_dt.now(_dt.timezone.utc),
))
db.commit()
```

**File**: `engine/src/migrations_engine/routes/projects.py`

Import changes at top:
```python
from ..db.models import User, VersionHistory
from datetime import datetime as _dt
```

In `patch_codegen_instructions`, capture version snapshot before calling `update_project`:
```python
@router.patch("/{project_id}/codegen-instructions", response_model=ProjectResponse)
def patch_codegen_instructions(
    project_id: str,
    body: CodegenInstructionsRequest,
    actor: User = Depends(get_central_team_user),
    db: Session = Depends(get_db),
) -> ProjectResponse:
    require_project_access(db, user=actor, project_id=project_id)
    if body.codegen_instructions is not None:
        db.add(VersionHistory(
            entity_type="project_codegen",
            entity_id=project_id,
            field_name="codegen_instructions",
            old_value=None,
            new_value=body.codegen_instructions,
            changed_by=actor.user_id,
            changed_at=_dt.now(_dt.timezone.utc),
        ))
        db.commit()
    return update_project(
        db,
        actor=actor,
        project_id=project_id,
        body=ProjectUpdateRequest(codegen_instructions=body.codegen_instructions),
    )
```

**File**: `engine/src/migrations_engine/codegen/service.py`

In `generate_codegen_artifact`, after `db.add(artifact)` (line ~199), add:
```python
db.add(VersionHistory(
    entity_type="codegen_sql",
    entity_id=codegen_artifact_id,
    field_name="sql_bundle",
    old_value=None,
    new_value=sql_bundle,
    changed_by=actor.user_id,
    changed_at=datetime.now(UTC),
))
```
Also import `VersionHistory` from `..db.models`.

---

### Step 6: Add Frontend API Client Functions and UI

**File**: `web/lib/feeds-api.ts`

Add to the `FeedContractRecord` type:
```typescript
export interface VersionHistoryEntry {
  version_id: string;
  field_name: string;
  old_value: string | null;
  new_value: string | null;
  changed_by: string | null;
  changed_at: string;
}
```

Add function:
```typescript
export async function listVersionHistory(
  token: string,
  entityType: string,
  opts?: { limit?: number; offset?: number },
): Promise<VersionHistoryEntry[]> {
  const query = opts
    ? `?limit=${opts.limit}&offset=${opts.offset}`
    : "";
  const response = await requestJson<Array<VersionHistoryEntry>>(
    `/feed-hints/${entityType}/versions${query}`,
    { method: "GET", token },
  );
  return response;
}
```

**File**: `web/app/projects/[id]/feeds/[feedId]/page.tsx`

Add a "History" toggle near the mapping hints textarea that, when open, shows a collapsible list of version history entries fetched via `listVersionHistory`. Each entry displays `changed_by`, `changed_at`, and a collapsible old/new diff.

**File**: `web/app/projects/[id]/codegen/page.tsx`

Add similar version history toggle for codegen instructions.

---

## Files Modified

| File | Action |
|---|---|
| `engine/migrations/versions/0043_add_version_history.py` | **Create** |
| `engine/src/migrations_engine/db/models.py` | **Modify** — add `VersionHistory` model |
| `engine/src/migrations_engine/api/schemas.py` | **Modify** — add response/request schemas |
| `engine/src/migrations_engine/routes/versions.py` | **Create** |
| `engine/src/migrations_engine/app.py` | **Modify** — register new router |
| `engine/src/migrations_engine/routes/feeds.py` | **Modify** — add version capture in hints & transformation handlers |
| `engine/src/migrations_engine/routes/projects.py` | **Modify** — add version capture in codegen-instructions handler |
| `engine/src/migrations_engine/codegen/service.py` | **Modify** — add version capture on artifact creation |
| `web/lib/feeds-api.ts` | **Modify** — add `listVersionHistory` + types |
| `web/app/projects/[id]/feeds/[feedId]/page.tsx` | **Modify** — add version history UI |
| `web/app/projects/[id]/codegen/page.tsx` | **Modify** — add version history UI |
| `docs/domain/source-model.md` | **Modify** — add `VersionHistory` model section |
| `docs/domain/api.md` | **Modify** — add version history endpoint docs |

---

## Domain Doc Updates Required

- `docs/domain/source-model.md` — Add `VersionHistory` model section
- `docs/domain/api.md` — Add version history endpoint documentation
