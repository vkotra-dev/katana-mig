# Feed / FeedSlice Rename Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rename `SourceDefinition` → `Feed` and `SourceSlice` → `FeedSlice` across the entire codebase — model classes, schema classes, route files, URL prefixes, web types, and Alembic table names — with zero functional changes.

**Architecture:** DB migration renames the three tables (`source_definitions` → `feeds`, `source_slices` → `feed_slices`, `source_slice_rows` → `feed_slice_rows`). Python attribute names inside models that point to those tables are updated via SQLAlchemy's explicit column-name mapping. All Python class names, Pydantic schema names, route file names, and URL prefixes are updated. Web TypeScript types and API helpers follow the same pattern. No logic changes anywhere.

**Tech Stack:** FastAPI, SQLAlchemy 2, Alembic (batch ops for SQLite compat), Pydantic v2, pytest; Next.js App Router, TypeScript, Vitest

## Global Constraints

- Migration revision `"0018_feed_rename"` — `down_revision = "0017_notifications"` (001at migration runs in Wave 1 before 001aj)
- DB column names on the `feeds` and `feed_slices` tables stay as `source_definition_id` and `source_slice_id` respectively — only the **table** names change; explicit `mapped_column("source_definition_id", ...)` is used where the Python attribute name would differ
- Route prefix changes: `/projects/{id}/sources` → `/projects/{id}/feeds`; `/source-slices` → `/feed-slices`
- All engine tests must pass before committing each task
- All web tests must pass before committing Task 2
- No functional changes — pure rename

---

## Blast radius

| File | Change |
|---|---|
| `engine/src/migrations_engine/db/models.py` | Rename 3 classes; update `__tablename__`; update `ForeignKey()` strings |
| `engine/src/migrations_engine/api/schemas.py` | Rename 7 schema classes |
| `engine/src/migrations_engine/routes/sources.py` → `routes/feeds.py` | Rename file; update prefix and imports |
| `engine/src/migrations_engine/routes/slice_approval.py` → `routes/feed_slice_approval.py` | Rename file |
| `engine/src/migrations_engine/app.py` | Update router imports |
| `engine/src/migrations_engine/management/sources.py` → `management/feeds.py` | Rename file |
| `engine/src/migrations_engine/management/source_analysis.py` | Update imports only |
| `engine/src/migrations_engine/management/lookup_mapping.py` | Update imports |
| `engine/src/migrations_engine/management/projects.py` | Update imports |
| `engine/src/migrations_engine/management/reconciliation.py` | Update imports |
| `engine/src/migrations_engine/codegen/service.py` | Update imports |
| `engine/src/migrations_engine/execution/engine.py` | Update imports |
| `engine/src/migrations_engine/execution/inner_loop.py` | Update imports |
| `engine/src/migrations_engine/intake/csv_intake.py` | Update imports |
| `engine/src/migrations_engine/intake/fixed_intake.py` | Update imports |
| `engine/src/migrations_engine/mapping/review.py` | Update imports |
| `engine/src/migrations_engine/routes/runs.py` | Update imports |
| `engine/migrations/versions/0017_feed_rename.py` | Create — rename 3 tables |
| All 16 engine test files that import `SourceDefinition` or `SourceSlice` | Update imports + fixture references |
| `web/lib/sources-api.ts` → `web/lib/feeds-api.ts` | Rename file; rename types; update URL paths |
| `web/lib/sources-api.test.ts` → `web/lib/feeds-api.test.ts` | Rename file; update imports |
| `web/lib/slice-approval-api.ts` → `web/lib/feed-slice-approval-api.ts` | Rename file |
| `web/lib/codegen-api.ts`, `web/lib/lookup-api.ts`, `web/lib/mapping-api.ts`, `web/lib/runs-api.ts` | Update `sourceDefinitionId` references |
| `web/components/projects/SourceList.tsx` | Update import from feeds-api |
| `web/components/projects/AddSourceDialog.tsx` | Update import from feeds-api |
| `web/components/projects/SourceArtifactsPanel.tsx` | Update import from feeds-api |
| `web/components/approvals/ApprovalsInbox.tsx` | Update import from feed-slice-approval-api |
| All web component tests referencing source-api types | Update imports |

## Objective

Rename `SourceDefinition` to `Feed` and `SourceSlice` to `FeedSlice` across the codebase, docs, and UI vocabulary without changing behavior.

## Out of Scope

- No workflow redesign
- No new business rules for feeds or slices
- No schema changes beyond the rename itself where needed for compatibility

## File Changes

- See the blast radius table above for the exact backend, web, and docs files.

## Verification

- Run the focused backend tests that exercise renamed types and routes
- Run the relevant web tests for renamed labels and props
- Run the repo-level search checks the task plan calls out

## Pitfalls

- Keep code, docs, tests, and display strings renamed together
- Do not break database identifiers or URL parameters unless the plan explicitly covers that separately
- Avoid half-renamed hybrids that make the UI and API disagree

## Commit

- `chore(001aj): rename source vocabulary to feed`

---

### Task 1: Backend rename — models, migration, schemas, routes, services, tests

**Files:**
- Modify: `engine/src/migrations_engine/db/models.py`
- Create: `engine/migrations/versions/0017_feed_rename.py`
- Modify: `engine/src/migrations_engine/api/schemas.py`
- Rename+Modify: `engine/src/migrations_engine/routes/sources.py` → `routes/feeds.py`
- Rename+Modify: `engine/src/migrations_engine/routes/slice_approval.py` → `routes/feed_slice_approval.py`
- Modify: `engine/src/migrations_engine/app.py`
- Rename+Modify: `engine/src/migrations_engine/management/sources.py` → `management/feeds.py`
- Modify (imports only): all other engine source files listed in blast radius
- Modify (imports only): all 16 engine test files

**Interfaces:**
- Produces: `Feed` (was `SourceDefinition`), `FeedSlice` (was `SourceSlice`), `FeedSliceRow` (was `SourceSliceRow`) in `db/models.py`
- Produces: `FeedResponse`, `FeedCreateRequest`, `FeedSliceResponse` in `api/schemas.py`
- Produces: `/projects/{id}/feeds` route prefix

- [ ] **Step 1: Write the failing test**

Create `engine/tests/test_feed_rename.py`:

```python
from __future__ import annotations


def test_feed_model_class_exists() -> None:
    from migrations_engine.db.models import Feed
    assert Feed.__tablename__ == "feeds"


def test_feed_slice_model_class_exists() -> None:
    from migrations_engine.db.models import FeedSlice
    assert FeedSlice.__tablename__ == "feed_slices"


def test_feed_slice_row_model_class_exists() -> None:
    from migrations_engine.db.models import FeedSliceRow
    assert FeedSliceRow.__tablename__ == "feed_slice_rows"


def test_source_definition_does_not_exist() -> None:
    import migrations_engine.db.models as m
    assert not hasattr(m, "SourceDefinition")


def test_source_slice_does_not_exist() -> None:
    import migrations_engine.db.models as m
    assert not hasattr(m, "SourceSlice")


def test_feed_response_schema_exists() -> None:
    from migrations_engine.api.schemas import FeedResponse
    assert "source_definition_id" in FeedResponse.model_fields


def test_feed_slice_response_schema_exists() -> None:
    from migrations_engine.api.schemas import FeedSliceResponse
    assert "source_slice_id" in FeedSliceResponse.model_fields
```

- [ ] **Step 2: Run to verify tests fail**

```bash
cd /Users/vjkotra/projects/katana/engine/tests
python -m pytest test_feed_rename.py -v
```

Expected: FAIL — `ImportError: cannot import name 'Feed'`

- [ ] **Step 3: Rename model classes in `engine/src/migrations_engine/db/models.py`**

Make these three class renames in `db/models.py`:

```python
# Was: class SourceDefinition(Base):
class Feed(Base):
    __tablename__ = "feeds"
    # All fields unchanged — source_definition_id stays as the attribute name
    # because the DB column name is unchanged (only the table renames)
    source_definition_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    # ... rest of fields identical to old SourceDefinition ...
```

```python
# Was: class SourceSlice(Base):
class FeedSlice(Base):
    __tablename__ = "feed_slices"
    source_slice_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    source_definition_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("feeds.source_definition_id"), nullable=False
    )
    # ... rest of fields identical ...
```

```python
# Was: class SourceSliceRow(Base):
class FeedSliceRow(Base):
    __tablename__ = "feed_slice_rows"
    source_slice_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("feed_slices.source_slice_id"), nullable=False, index=True
    )
    # ... rest of fields identical ...
```

Also update ForeignKey references in `SourceSchemaArtifact`, `SourceValueSummary`, `LookupValueMap`, and `AuditEvent` — change only the table name in the ForeignKey string:

```python
# SourceSchemaArtifact — was ForeignKey("source_definitions.source_definition_id")
source_definition_id: Mapped[str] = mapped_column(
    String(36), ForeignKey("feeds.source_definition_id"), nullable=False
)

# SourceValueSummary — same change
source_definition_id: Mapped[str] = mapped_column(
    String(36), ForeignKey("feeds.source_definition_id"), nullable=False
)

# LookupValueMap — same change
source_definition_id: Mapped[str] = mapped_column(
    String(36), ForeignKey("feeds.source_definition_id"), nullable=False
)

# AuditEvent — update both
source_definition_id: Mapped[str | None] = mapped_column(
    String(36), ForeignKey("feeds.source_definition_id")
)
source_slice_id: Mapped[str | None] = mapped_column(
    String(36), ForeignKey("feed_slices.source_slice_id")
)
```

- [ ] **Step 4: Create Alembic migration `engine/migrations/versions/0017_feed_rename.py`**

```python
"""rename source tables to feeds

Revision ID: 0017_feed_rename
Revises: 0016_project_schema_analysis
Create Date: 2026-07-01
"""

from __future__ import annotations

from alembic import op


revision = "0018_feed_rename"
down_revision = "0017_notifications"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("source_slice_rows") as batch_op:
        batch_op.drop_constraint("fk_source_slice_rows_source_slice_id", type_="foreignkey")
    with op.batch_alter_table("source_slices") as batch_op:
        batch_op.drop_constraint("fk_source_slices_source_definition_id", type_="foreignkey")

    op.rename_table("source_definitions", "feeds")
    op.rename_table("source_slices", "feed_slices")
    op.rename_table("source_slice_rows", "feed_slice_rows")

    with op.batch_alter_table("feed_slices") as batch_op:
        batch_op.create_foreign_key(
            "fk_feed_slices_source_definition_id",
            "feeds",
            ["source_definition_id"],
            ["source_definition_id"],
        )
    with op.batch_alter_table("feed_slice_rows") as batch_op:
        batch_op.create_foreign_key(
            "fk_feed_slice_rows_source_slice_id",
            "feed_slices",
            ["source_slice_id"],
            ["source_slice_id"],
        )


def downgrade() -> None:
    with op.batch_alter_table("feed_slice_rows") as batch_op:
        batch_op.drop_constraint("fk_feed_slice_rows_source_slice_id", type_="foreignkey")
    with op.batch_alter_table("feed_slices") as batch_op:
        batch_op.drop_constraint("fk_feed_slices_source_definition_id", type_="foreignkey")

    op.rename_table("feed_slice_rows", "source_slice_rows")
    op.rename_table("feed_slices", "source_slices")
    op.rename_table("feeds", "source_definitions")

    with op.batch_alter_table("source_slices") as batch_op:
        batch_op.create_foreign_key(
            "fk_source_slices_source_definition_id",
            "source_definitions",
            ["source_definition_id"],
            ["source_definition_id"],
        )
    with op.batch_alter_table("source_slice_rows") as batch_op:
        batch_op.create_foreign_key(
            "fk_source_slice_rows_source_slice_id",
            "source_slices",
            ["source_slice_id"],
            ["source_slice_id"],
        )
```

**Note:** SQLite test databases use `sqlite_test_support.py` which calls `Base.metadata.create_all` — the migration is only applied in real Postgres deploys. The test DB is rebuilt fresh from models each run, so the renamed `__tablename__` values are picked up automatically. The migration is needed for production data continuity only.

- [ ] **Step 5: Rename schema classes in `engine/src/migrations_engine/api/schemas.py`**

Apply these renames (field names inside each class are unchanged):

| Old name | New name |
|---|---|
| `SourceContractCreateRequest` | `FeedCreateRequest` |
| `SourceContractResponse` | `FeedResponse` |
| `SourceSliceResponse` | `FeedSliceResponse` |
| `SourceSliceApprovalItemResponse` | `FeedSliceApprovalItemResponse` |
| `SourceSliceRejectRequest` | `FeedSliceRejectRequest` |
| `SourceSliceResubmitRequest` | `FeedSliceResubmitRequest` |
| `SourceSliceApprovalCountResponse` | `FeedSliceApprovalCountResponse` |

`SourceAnalysisResponse`, `SourceSchemaArtifactResponse`, `SourceSchemaColumnResponse`, `SourceValueSummaryResponse` — **keep unchanged** (these are about schema analysis, not the conceptual Feed rename).

- [ ] **Step 6: Rename and update route files**

**6a.** Copy `engine/src/migrations_engine/routes/sources.py` to `routes/feeds.py`, then delete the original:

```bash
cp engine/src/migrations_engine/routes/sources.py engine/src/migrations_engine/routes/feeds.py
rm engine/src/migrations_engine/routes/sources.py
```

In `routes/feeds.py`:
- Update imports: `SourceContractCreateRequest` → `FeedCreateRequest`, `SourceContractResponse` → `FeedResponse`, `SourceSliceResponse` → `FeedSliceResponse`
- Update import: `from ..management.sources import ...` → `from ..management.feeds import ...`
- Update import: `from ..db.models import ...` add `Feed` remove `SourceDefinition` (if referenced directly)
- Update router: `router = APIRouter(prefix="/projects/{project_id}/feeds", tags=["feeds"])`
- Update all function bodies: `SourceDefinition` → `Feed`, `SourceSlice` → `FeedSlice` (if referenced)
- Rename import functions that reference "source" in management.feeds — check those names

**6b.** Copy `engine/src/migrations_engine/routes/slice_approval.py` to `routes/feed_slice_approval.py`, then delete original:

```bash
cp engine/src/migrations_engine/routes/slice_approval.py engine/src/migrations_engine/routes/feed_slice_approval.py
rm engine/src/migrations_engine/routes/slice_approval.py
```

In `routes/feed_slice_approval.py`:
- Update all imports that reference old schema names (`SourceSliceApprovalItemResponse` → `FeedSliceApprovalItemResponse`, etc.)
- Update imports from management (if it imports from `management.sources` → change to `management.feeds`)

- [ ] **Step 7: Rename management sources file**

```bash
cp engine/src/migrations_engine/management/sources.py engine/src/migrations_engine/management/feeds.py
rm engine/src/migrations_engine/management/sources.py
```

In `management/feeds.py`:
- Replace all `SourceDefinition` → `Feed`, `SourceSlice` → `FeedSlice`, `SourceSliceRow` → `FeedSliceRow`
- Replace imports from `db.models` accordingly
- Replace schema imports: `SourceContractCreateRequest` → `FeedCreateRequest`, `SourceContractResponse` → `FeedResponse`, `SourceSliceResponse` → `FeedSliceResponse`

- [ ] **Step 8: Update `app.py` router imports**

In `engine/src/migrations_engine/app.py`:

```python
# Replace:
from .routes.sources import router as sources_router
from .routes.slice_approval import router as slice_approval_router
# With:
from .routes.feeds import router as feeds_router
from .routes.feed_slice_approval import router as feed_slice_approval_router
```

And in the `app.include_router(...)` calls:
```python
# Replace:
app.include_router(sources_router)
app.include_router(slice_approval_router)
# With:
app.include_router(feeds_router)
app.include_router(feed_slice_approval_router)
```

- [ ] **Step 9: Update import-only files**

In each of these files, replace `SourceDefinition` with `Feed`, `SourceSlice` with `FeedSlice`, `SourceSliceRow` with `FeedSliceRow` in import statements and any usages:

- `management/source_analysis.py` — update `from .sources import` → `from .feeds import` and class references
- `management/lookup_mapping.py` — update `SourceDefinition` → `Feed`
- `management/projects.py` — update `SourceDefinition` → `Feed`
- `management/reconciliation.py` — update any source references
- `codegen/service.py` — update `SourceDefinition` → `Feed`, `SourceSlice` → `FeedSlice`
- `execution/engine.py` — update `SourceSlice` → `FeedSlice`
- `execution/inner_loop.py` — update `SourceSlice` → `FeedSlice`
- `intake/csv_intake.py` — update `SourceDefinition` → `Feed`, `SourceSlice` → `FeedSlice`
- `intake/fixed_intake.py` — same
- `mapping/review.py` — update any source references
- `routes/runs.py` — update `SourceDefinition` → `Feed`, `SourceSlice` → `FeedSlice`

- [ ] **Step 10: Update all 16 engine test files**

In each test file, replace:
- `from migrations_engine.db.models import SourceDefinition` → `Feed`
- `from migrations_engine.db.models import SourceSlice` → `FeedSlice`
- `from migrations_engine.api.schemas import SourceContractResponse` → `FeedResponse`
- `SourceDefinition(...)` → `Feed(...)` in fixture creation
- `SourceSlice(...)` → `FeedSlice(...)` in fixture creation

Files to update:
```
engine/tests/test_codegen_artifact_model.py
engine/tests/test_codegen_service_api.py
engine/tests/test_execution_engine.py
engine/tests/test_gates_api.py
engine/tests/test_lookup_mapping_api.py
engine/tests/test_lookup_mapping_models.py
engine/tests/test_lookup_mapping_service.py
engine/tests/test_mapping_review_api.py
engine/tests/test_project_summary_api.py
engine/tests/test_reconciliation_api.py
engine/tests/test_runs_api.py
engine/tests/test_source_analysis_api.py
engine/tests/test_source_analysis_models.py
engine/tests/test_source_analysis_service.py
engine/tests/test_source_intake_api.py
engine/tests/test_source_slice_approval_api.py
```

Also rename the test files that have "source" in their name if desired, but it is **not required** — the test file name does not need to match the class name for the tests to pass.

- [ ] **Step 11: Run the rename test + full engine suite**

```bash
cd /Users/vjkotra/projects/katana/engine/tests
python -m pytest test_feed_rename.py -v
```

Expected: all 7 tests PASS.

```bash
python -m pytest -v
```

Expected: all tests PASS.

- [ ] **Step 12: Commit**

```bash
git add engine/src/migrations_engine/db/models.py \
        engine/src/migrations_engine/api/schemas.py \
        engine/src/migrations_engine/routes/feeds.py \
        engine/src/migrations_engine/routes/feed_slice_approval.py \
        engine/src/migrations_engine/management/feeds.py \
        engine/src/migrations_engine/management/source_analysis.py \
        engine/src/migrations_engine/management/lookup_mapping.py \
        engine/src/migrations_engine/management/projects.py \
        engine/src/migrations_engine/management/reconciliation.py \
        engine/src/migrations_engine/codegen/service.py \
        engine/src/migrations_engine/execution/engine.py \
        engine/src/migrations_engine/execution/inner_loop.py \
        engine/src/migrations_engine/intake/csv_intake.py \
        engine/src/migrations_engine/intake/fixed_intake.py \
        engine/src/migrations_engine/mapping/review.py \
        engine/src/migrations_engine/routes/runs.py \
        engine/src/migrations_engine/app.py \
        engine/migrations/versions/0017_feed_rename.py \
        engine/tests/test_feed_rename.py \
        engine/tests/
git commit -m "feat(001aj): rename SourceDefinition→Feed, SourceSlice→FeedSlice across backend"
```

---

### Task 2: Frontend rename — types, API helpers, components

**Files:**
- Rename+Modify: `web/lib/sources-api.ts` → `web/lib/feeds-api.ts`
- Rename+Modify: `web/lib/sources-api.test.ts` → `web/lib/feeds-api.test.ts`
- Rename+Modify: `web/lib/slice-approval-api.ts` → `web/lib/feed-slice-approval-api.ts`
- Modify: `web/lib/codegen-api.ts`, `codegen-api.test.ts`
- Modify: `web/lib/lookup-api.ts`, `lookup-api.test.ts`
- Modify: `web/lib/mapping-api.ts`, `mapping-api.test.ts`
- Modify: `web/lib/runs-api.ts`, `runs-api.test.ts`
- Modify: all web components that import from `sources-api` or `slice-approval-api`

**Interfaces:**
- Produces: `FeedRecord` (was `SourceContractRecord`), `FeedSliceRecord` (was `SourceSliceRecord`) in `feeds-api.ts`
- Produces: `listFeeds`, `getFeed`, `createFeed`, `uploadFeedSlice` functions at `/projects/{id}/feeds` URLs

- [ ] **Step 1: Write the failing tests**

Create `web/lib/__tests__/feeds-api.test.ts`:

```typescript
import { describe, expect, it, vi, beforeEach } from "vitest";
import { listFeeds, createFeed, type FeedRecord } from "../feeds-api";

const fetchMock = vi.fn();
vi.stubGlobal("fetch", fetchMock);

const FEED: FeedRecord = {
  sourceDefinitionId: "sd-1",
  projectId: "p-1",
  sourceType: "csv",
  label: "Customer Master",
  encoding: "utf-8",
  destinationObjectReferences: null,
  layoutInformation: null,
  copybookText: null,
  status: "active",
  createdAt: "2026-07-01T00:00:00Z",
};

beforeEach(() => vi.clearAllMocks());

describe("listFeeds", () => {
  it("calls /feeds and returns array", async () => {
    fetchMock.mockResolvedValue({ ok: true, status: 200, json: async () => [FEED] });
    const result = await listFeeds("tok", "p-1");
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/projects/p-1/feeds"),
      expect.anything(),
    );
    expect(result).toHaveLength(1);
    expect(result[0].label).toBe("Customer Master");
  });
});

describe("createFeed", () => {
  it("posts to /feeds", async () => {
    fetchMock.mockResolvedValue({ ok: true, status: 201, json: async () => FEED });
    const result = await createFeed("tok", "p-1", { sourceType: "csv", label: "Customer Master", encoding: "utf-8" });
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/projects/p-1/feeds"),
      expect.objectContaining({ method: "POST" }),
    );
    expect(result.label).toBe("Customer Master");
  });
});
```

- [ ] **Step 2: Run to verify tests fail**

```bash
cd /Users/vjkotra/projects/katana/web
npm test -- lib/__tests__/feeds-api.test.ts
```

Expected: FAIL — `listFeeds not exported`

- [ ] **Step 3: Create `web/lib/feeds-api.ts` from `sources-api.ts`**

```bash
cp web/lib/sources-api.ts web/lib/feeds-api.ts
```

In `feeds-api.ts`:
- Rename type `SourceContractRecord` → `FeedRecord`
- Rename type `SourceSliceRecord` → `FeedSliceRecord`
- Rename function `listSourceContracts` → `listFeeds`
- Rename function `getSourceContract` → `getFeed`
- Rename function `createSourceContract` → `createFeed`
- Rename function `uploadFeedSlice` → same (already good) or `uploadFeedSlice`
- Update URL strings: `/sources` → `/feeds`, `/source-slices` → `/feed-slices`
- Keep type `CreateSourceContractRequest` or rename to `CreateFeedRequest` — rename for consistency

Then delete the old file:
```bash
rm web/lib/sources-api.ts
```

Create `web/lib/feeds-api.ts` with the complete content (copy from sources-api.ts, apply renames above).

- [ ] **Step 4: Create `web/lib/feed-slice-approval-api.ts` from `slice-approval-api.ts`**

```bash
cp web/lib/slice-approval-api.ts web/lib/feed-slice-approval-api.ts
rm web/lib/slice-approval-api.ts
```

In `feed-slice-approval-api.ts`:
- Update type names containing `SourceSlice` → `FeedSlice`
- Update URL strings: `/source-slices` → `/feed-slices`

- [ ] **Step 5: Update all consumer files**

In each file below, update the import path and any type name references:

**`web/lib/codegen-api.ts`** and **`web/lib/codegen-api.test.ts`**:
- `sourceDefinitionId` field references — leave as-is (it's a DB field name, not a type name)
- Update any import from `sources-api` → `feeds-api`

**`web/lib/lookup-api.ts`** and **`web/lib/lookup-api.test.ts`**:
- Update import from `sources-api` → `feeds-api`
- Rename type references: `SourceContractRecord` → `FeedRecord`

**`web/lib/mapping-api.ts`** and **`web/lib/mapping-api.test.ts`**:
- Update import from `sources-api` → `feeds-api`
- Rename type references

**`web/lib/runs-api.ts`** and **`web/lib/runs-api.test.ts`**:
- Update import from `sources-api` → `feeds-api`
- Rename type references

**Component files** — update import paths:

```typescript
// In SourceList.tsx, AddSourceDialog.tsx, SourceArtifactsPanel.tsx:
// Replace:
import { listSourceContracts, ... } from "../../lib/sources-api";
// With:
import { listFeeds, ... } from "../../lib/feeds-api";
// And rename function call: listSourceContracts → listFeeds
```

```typescript
// In ApprovalsInbox.tsx:
// Replace:
import { ... } from "../lib/slice-approval-api";
// With:
import { ... } from "../lib/feed-slice-approval-api";
```

Also update the web app route pages that reference sources:
- `web/app/projects/[id]/sources/[sourceId]/lookup/page.tsx` — update imports
- `web/app/projects/[id]/sources/[sourceId]/mapping/page.tsx` — update imports
- Their test files — update imports

- [ ] **Step 6: Run the feeds-api test**

```bash
cd /Users/vjkotra/projects/katana/web
npm test -- lib/__tests__/feeds-api.test.ts
```

Expected: all tests PASS.

- [ ] **Step 7: Run the full web test suite**

```bash
cd /Users/vjkotra/projects/katana/web
npm test
```

Expected: all tests PASS. Fix any import errors that surface.

- [ ] **Step 8: Commit**

```bash
git add web/lib/feeds-api.ts \
        web/lib/feed-slice-approval-api.ts \
        web/lib/codegen-api.ts web/lib/codegen-api.test.ts \
        web/lib/lookup-api.ts web/lib/lookup-api.test.ts \
        web/lib/mapping-api.ts web/lib/mapping-api.test.ts \
        web/lib/runs-api.ts web/lib/runs-api.test.ts \
        web/components/ \
        web/app/
git commit -m "feat(001aj): rename source types and API helpers to Feed/FeedSlice in web layer"
```
