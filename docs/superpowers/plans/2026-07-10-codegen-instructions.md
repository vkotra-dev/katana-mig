# Codegen Transformation Instructions — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add project-wide coding standards and per-feed transformation instructions that are injected into the AI SQL generation prompt, steering output without touching the field mapping layer.

**Architecture:** Two new nullable TEXT columns — `project_definitions.codegen_instructions` and `source_definitions.transformation_instructions` — stored directly on the ORM models. PATCH endpoints update each independently. The codegen service reads both and appends them to the system/user prompt blocks. The codegen page hosts both editing panels.

**Tech Stack:** Python/FastAPI (backend), SQLAlchemy + Alembic (persistence), Next.js/TypeScript (frontend), Tailwind CSS (styling).

## Global Constraints

- Alembic revisions must chain: `0030` → down_revision `0029`, `0031` → down_revision `0030`
- All new TEXT columns are nullable; absence means no instructions — never inject an empty header
- Role guard for all write paths: `admin` or `central_team`; read is unrestricted
- Copy-on-write persistence: both fields must be carried through `update_project()` and `copy_project()`
- Frontend textareas are read-only for roles other than `central_team` / `admin`

---

## File Map

| File | Action | Purpose |
|------|--------|---------|
| `engine/migrations/versions/0030_codegen_instructions.py` | Create | Add `project_definitions.codegen_instructions` |
| `engine/migrations/versions/0031_transformation_instructions.py` | Create | Add `source_definitions.transformation_instructions` |
| `engine/src/migrations_engine/db/models.py` | Modify | Add columns to `ProjectDefinition` and `Feed` ORM models |
| `engine/src/migrations_engine/api/schemas.py` | Modify | Add fields to `FeedResponse`, `ProjectResponse`; add two new request schemas |
| `engine/src/migrations_engine/management/projects.py` | Modify | Fix copy-on-write in `update_project()` and `copy_project()`; add `save_codegen_instructions()` |
| `engine/src/migrations_engine/management/feeds.py` | Modify | Add `save_transformation_instructions()` |
| `engine/src/migrations_engine/routes/projects.py` | Modify | Add `PATCH /{project_id}/codegen-instructions` route |
| `engine/src/migrations_engine/routes/feeds.py` | Modify | Add `PATCH /{source_definition_id}/transformation-instructions` route |
| `engine/src/migrations_engine/codegen/service.py` | Modify | Inject both instruction blocks into prompts |
| `web/lib/feeds-api.ts` | Modify | Add `transformationInstructions` to `FeedContractRecord` and mapper |
| `web/lib/codegen-api.ts` | Modify | Add `saveCodegenInstructions()` and `saveTransformationInstructions()` |
| `web/app/projects/[id]/codegen/page.tsx` | Modify | Add global instructions panel + per-feed expandable instruction rows |
| `docs/domain/project.md` | Modify | Document `codegen_instructions` on `ProjectDefinition` |
| `docs/domain/source-model.md` | Modify | Document `transformation_instructions` on `Feed` and updated prompt structure |

---

### Task 1: Database migrations and ORM model columns

**Files:**
- Create: `engine/migrations/versions/0030_codegen_instructions.py`
- Create: `engine/migrations/versions/0031_transformation_instructions.py`
- Modify: `engine/src/migrations_engine/db/models.py`

**Interfaces:**
- Produces: `ProjectDefinition.codegen_instructions: str | None` ORM column; `Feed.transformation_instructions: str | None` ORM column

- [ ] **Step 1: Verify the latest migration revision**

```bash
ls engine/migrations/versions/ | sort | tail -3
```

Expected output includes `0029_unify_comments.py` as the most recent numbered migration.

- [ ] **Step 2: Create migration 0030**

Create `engine/migrations/versions/0030_codegen_instructions.py`:

```python
"""add codegen_instructions to project_definitions

Revision ID: 0030
Revises: 0029
"""
from alembic import op
import sqlalchemy as sa

revision = "0030"
down_revision = "0029"


def upgrade() -> None:
    op.add_column(
        "project_definitions",
        sa.Column("codegen_instructions", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("project_definitions", "codegen_instructions")
```

- [ ] **Step 3: Create migration 0031**

Create `engine/migrations/versions/0031_transformation_instructions.py`:

```python
"""add transformation_instructions to source_definitions

Revision ID: 0031
Revises: 0030
"""
from alembic import op
import sqlalchemy as sa

revision = "0031"
down_revision = "0030"


def upgrade() -> None:
    op.add_column(
        "source_definitions",
        sa.Column("transformation_instructions", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("source_definitions", "transformation_instructions")
```

- [ ] **Step 4: Add ORM columns**

In `engine/src/migrations_engine/db/models.py`, find the `ProjectDefinition` model and add:
```python
codegen_instructions: Mapped[str | None] = mapped_column(Text, nullable=True)
```

In the same file, find the `Feed` model and add alongside `mapping_hints`:
```python
transformation_instructions: Mapped[str | None] = mapped_column(Text, nullable=True)
```

Use `grep -n "mapping_hints\|class ProjectDefinition\|class Feed" engine/src/migrations_engine/db/models.py` to locate the exact lines.

- [ ] **Step 5: Run migrations**

```bash
cd engine && alembic upgrade head
```

Expected: `Running upgrade 0029 -> 0030, Running upgrade 0030 -> 0031` with no errors.

- [ ] **Step 6: Verify columns exist**

```bash
cd engine && python -c "
from src.migrations_engine.db.models import ProjectDefinition, Feed
print(ProjectDefinition.codegen_instructions)
print(Feed.transformation_instructions)
"
```

Expected: both print a column descriptor without raising `AttributeError`.

- [ ] **Step 7: Commit**

```bash
git add engine/migrations/versions/0030_codegen_instructions.py \
        engine/migrations/versions/0031_transformation_instructions.py \
        engine/src/migrations_engine/db/models.py
git commit -m "feat: add codegen_instructions and transformation_instructions columns (0030, 0031)"
```

---

### Task 2: Response schemas and request schemas

**Files:**
- Modify: `engine/src/migrations_engine/api/schemas.py:258-270` (`FeedResponse`) and `:187-208` (`ProjectResponse`)

**Interfaces:**
- Consumes: ORM columns from Task 1
- Produces: `FeedResponse.transformation_instructions: str | None = None`; `ProjectResponse.codegen_instructions: str | None = None`; `CodegenInstructionsRequest`; `TransformationInstructionsRequest`

- [ ] **Step 1: Add `transformation_instructions` to `FeedResponse`**

In `engine/src/migrations_engine/api/schemas.py`, find `FeedResponse` (line ~258). After `mapping_hints: str | None = None`, add:

```python
transformation_instructions: str | None = None
```

- [ ] **Step 2: Add `codegen_instructions` to `ProjectResponse`**

In the same file, find `ProjectResponse` (line ~187). After `pm_user_id: str | None = None`, add:

```python
codegen_instructions: str | None = None
```

- [ ] **Step 3: Add two new request schemas**

After `FeedMappingHintsRequest`:

```python
class CodegenInstructionsRequest(BaseModel):
    codegen_instructions: str | None = None


class TransformationInstructionsRequest(BaseModel):
    transformation_instructions: str | None = None
```

- [ ] **Step 4: Check that `FeedResponse` is built from ORM via `from_attributes`**

```bash
grep -n "from_attributes\|model_config\|FeedResponse" engine/src/migrations_engine/api/schemas.py | head -20
```

If `FeedResponse` does not have `model_config = ConfigDict(from_attributes=True)`, check how `get_source_contract` builds its return value in `management/feeds.py` — it likely constructs `FeedResponse` manually. Confirm `transformation_instructions` is carried through in Task 3.

- [ ] **Step 5: Verify backend starts cleanly**

```bash
cd engine && python -m uvicorn src.migrations_engine.app:app --port 8001 --reload &
sleep 3 && curl -s http://localhost:8001/health | python -m json.tool
kill %1
```

Expected: `{"status": "ok"}` with no import errors.

- [ ] **Step 6: Commit**

```bash
git add engine/src/migrations_engine/api/schemas.py
git commit -m "feat: add codegen_instructions and transformation_instructions to response schemas"
```

---

### Task 3: Management layer — save functions and copy-on-write fixes

**Files:**
- Modify: `engine/src/migrations_engine/management/projects.py:176-212` (`update_project`), `:541-588` (`copy_project`)
- Modify: `engine/src/migrations_engine/management/feeds.py` (new `save_transformation_instructions`)

**Interfaces:**
- Consumes: `CodegenInstructionsRequest`, `TransformationInstructionsRequest` from Task 2
- Produces: `save_codegen_instructions(db, project_id, instructions) -> ProjectResponse`; `save_transformation_instructions(db, project_id, source_definition_id, instructions) -> FeedResponse`

- [ ] **Step 1: Fix `update_project()` copy-on-write**

In `engine/src/migrations_engine/management/projects.py`, in the `new_definition = ProjectDefinition(...)` constructor inside `update_project()` (around line 176), add after `status="active"`:

```python
codegen_instructions=current_definition.codegen_instructions,
```

This ensures that when any project field is updated, the global instructions are preserved in the new definition row.

- [ ] **Step 2: Fix `copy_project()` definition copy-on-write**

In the same file, in the `new_definition = ProjectDefinition(...)` constructor inside `copy_project()` (around line 541), add after `domain_config=source_definition.domain_config,`:

```python
codegen_instructions=source_definition.codegen_instructions,
```

- [ ] **Step 3: Fix `copy_project()` feed loop**

In the feed loop inside `copy_project()` (around line 575), add after `mapping_hints=feed.mapping_hints,`:

```python
transformation_instructions=feed.transformation_instructions,
```

- [ ] **Step 4: Add `save_codegen_instructions()` to `management/projects.py`**

Add a new function after `update_project()`:

```python
def save_codegen_instructions(
    db: Session,
    *,
    actor: User,
    project_id: str,
    codegen_instructions: str | None,
) -> ProjectResponse:
    registry, current_definition = _get_project_rows(db, project_id)
    if registry.archived_at is not None:
        raise AuthApiError("project_archived", "Cannot update an archived project.", 409)
    current_definition.codegen_instructions = codegen_instructions
    db.commit()
    db.refresh(current_definition)
    return get_project(db, actor=actor, project_id=project_id)
```

This mutates the current definition directly (no new row needed — `codegen_instructions` is not part of the immutable definition snapshot; it's a mutable annotation on the live definition). Verify whether this is the correct pattern by checking how `mapping_hints` is handled for feeds — if feeds mutate directly without copy-on-write, apply the same approach here.

> **Note on copy-on-write scope:** The existing `update_project()` creates a new `ProjectDefinition` row for fields like `goal`, `constraints`, etc. because those are part of the versioned snapshot. `codegen_instructions` is a mutable steering annotation — it's appropriate to mutate it in place on the current definition, like `mapping_hints` on feeds. The copy-on-write fix in Step 1 is still required so that when a *versioned update* happens, `codegen_instructions` isn't lost.

- [ ] **Step 5: Add `save_transformation_instructions()` to `management/feeds.py`**

```python
def save_transformation_instructions(
    db: Session,
    *,
    project_id: str,
    source_definition_id: str,
    transformation_instructions: str | None,
) -> FeedResponse:
    feed = db.get(Feed, source_definition_id)
    if feed is None or feed.project_id != project_id:
        raise AuthApiError("feed_not_found", "Feed not found.", 404)
    feed.transformation_instructions = transformation_instructions
    db.commit()
    db.refresh(feed)
    return get_source_contract(db, project_id=project_id, source_definition_id=source_definition_id)
```

Import `AuthApiError` from `..api.deps` if not already present in `feeds.py`.

- [ ] **Step 6: Confirm `get_source_contract` returns `transformation_instructions`**

Locate `get_source_contract` in `management/feeds.py`. If it constructs `FeedResponse` manually, ensure it passes `transformation_instructions=feed.transformation_instructions`. If it uses `FeedResponse.model_validate(feed, from_attributes=True)`, no change needed since the column is already on the ORM model.

- [ ] **Step 7: Confirm `get_project` returns `codegen_instructions`**

Locate `get_project` (or its equivalent builder) in `management/projects.py`. Same check: ensure `codegen_instructions=current_definition.codegen_instructions` is included in the `ProjectResponse` construction.

- [ ] **Step 8: Commit**

```bash
git add engine/src/migrations_engine/management/projects.py \
        engine/src/migrations_engine/management/feeds.py
git commit -m "feat: add save_codegen_instructions and save_transformation_instructions, fix copy-on-write"
```

---

### Task 4: API routes — two new PATCH endpoints

**Files:**
- Modify: `engine/src/migrations_engine/routes/projects.py`
- Modify: `engine/src/migrations_engine/routes/feeds.py`

**Interfaces:**
- Consumes: `save_codegen_instructions()` from Task 3; `save_transformation_instructions()` from Task 3; `CodegenInstructionsRequest`, `TransformationInstructionsRequest` from Task 2

- [ ] **Step 1: Add import for `CodegenInstructionsRequest` and `save_codegen_instructions` in `routes/projects.py`**

In `engine/src/migrations_engine/routes/projects.py`, add `CodegenInstructionsRequest` to the schemas import and `save_codegen_instructions` to the management import.

- [ ] **Step 2: Add `PATCH /{project_id}/codegen-instructions` route**

In `engine/src/migrations_engine/routes/projects.py`, add after the existing `patch_project_manager` route:

```python
@router.patch("/{project_id}/codegen-instructions", response_model=ProjectResponse)
def patch_codegen_instructions(
    project_id: str,
    body: CodegenInstructionsRequest,
    actor: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ProjectResponse:
    from ..roles import ADMIN_ROLE, CENTRAL_TEAM_ROLE
    if actor.role not in {ADMIN_ROLE, CENTRAL_TEAM_ROLE}:
        raise AuthApiError("forbidden", "Admin or central team access is required.", 403)
    require_project_access(db, user=actor, project_id=project_id)
    return save_codegen_instructions(
        db, actor=actor, project_id=project_id,
        codegen_instructions=body.codegen_instructions,
    )
```

- [ ] **Step 3: Add import for `TransformationInstructionsRequest` and `save_transformation_instructions` in `routes/feeds.py`**

Add `TransformationInstructionsRequest` to the schemas import and `save_transformation_instructions` to the management feeds import.

- [ ] **Step 4: Add `PATCH /{source_definition_id}/transformation-instructions` route**

In `engine/src/migrations_engine/routes/feeds.py`, add after the existing `patch_source_hints` route:

```python
@router.patch("/{source_definition_id}/transformation-instructions", response_model=FeedResponse)
def patch_transformation_instructions(
    project_id: str,
    source_definition_id: str,
    body: TransformationInstructionsRequest,
    actor: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FeedResponse:
    from ..roles import ADMIN_ROLE, CENTRAL_TEAM_ROLE
    if actor.role not in {ADMIN_ROLE, CENTRAL_TEAM_ROLE}:
        raise AuthApiError("forbidden", "Admin or central team access is required.", 403)
    require_project_access(db, user=actor, project_id=project_id)
    return save_transformation_instructions(
        db, project_id=project_id, source_definition_id=source_definition_id,
        transformation_instructions=body.transformation_instructions,
    )
```

- [ ] **Step 5: Smoke-test the routes**

```bash
cd engine && python -m uvicorn src.migrations_engine.app:app --port 8001 &
sleep 3
curl -s http://localhost:8001/openapi.json | python -m json.tool | grep -A2 "codegen-instructions\|transformation-instructions"
kill %1
```

Expected: both route paths appear in the OpenAPI spec.

- [ ] **Step 6: Commit**

```bash
git add engine/src/migrations_engine/routes/projects.py \
        engine/src/migrations_engine/routes/feeds.py
git commit -m "feat: add PATCH codegen-instructions and transformation-instructions routes"
```

---

### Task 5: Codegen prompt injection

**Files:**
- Modify: `engine/src/migrations_engine/codegen/service.py:387-393` (`_build_system_prompt`), `:439-475` (`_build_user_prompt`), `:111-112` (call site)

**Interfaces:**
- Consumes: `project_definition.codegen_instructions: str | None`; `source_definition.transformation_instructions: str | None`

- [ ] **Step 1: Extend `_build_system_prompt` signature**

In `engine/src/migrations_engine/codegen/service.py` at line 387, change:

```python
def _build_system_prompt(*, project_config: MigrationProjectConfig, destination_object_name: str) -> str:
    return (
        "You generate SQL bundles for migration delivery.\n"
        f"Destination object: {destination_object_name}\n"
        f"Target DB engine: {project_config.target_db_engine or 'unknown'}\n"
        f"Staging schema: {project_config.staging_schema or 'unknown'}"
    )
```

to:

```python
def _build_system_prompt(
    *,
    project_config: MigrationProjectConfig,
    destination_object_name: str,
    codegen_instructions: str | None,
) -> str:
    parts = [
        "You generate SQL bundles for migration delivery.",
        f"Destination object: {destination_object_name}",
        f"Target DB engine: {project_config.target_db_engine or 'unknown'}",
        f"Staging schema: {project_config.staging_schema or 'unknown'}",
        f"Destination schema: {project_config.destination_schema or 'unknown'}",
    ]
    if codegen_instructions and codegen_instructions.strip():
        parts.append("")
        parts.append("GLOBAL CODING STANDARDS")
        parts.append(codegen_instructions.strip())
    return "\n".join(parts)
```

- [ ] **Step 2: Update the call site**

At line ~112 in `generate_codegen_artifact`, change:

```python
system=_build_system_prompt(project_config=project_config, destination_object_name=destination_object_name),
```

to:

```python
system=_build_system_prompt(
    project_config=project_config,
    destination_object_name=destination_object_name,
    codegen_instructions=project_definition.codegen_instructions,
),
```

- [ ] **Step 3: Append transformation instructions in `_build_user_prompt`**

At the end of `_build_user_prompt` (line ~474), before the final `return "\n".join(lines)`, add:

```python
    ti = source_definition.transformation_instructions
    if ti and ti.strip():
        lines.append("")
        lines.append("FEED-SPECIFIC TRANSFORMATION INSTRUCTIONS")
        lines.append(ti.strip())
```

- [ ] **Step 4: Write a unit test for prompt injection**

Create or add to `engine/tests/codegen/test_service_prompts.py`:

```python
from migrations_engine.codegen.service import _build_system_prompt, _build_user_prompt
from migrations_engine.api.schemas import MigrationProjectConfig


def make_project_config(**kwargs):
    return MigrationProjectConfig(
        target_db_engine="sqlserver",
        staging_schema="stg",
        destination_schema="dbo",
        **kwargs,
    )


def test_system_prompt_includes_global_instructions():
    config = make_project_config()
    prompt = _build_system_prompt(
        project_config=config,
        destination_object_name="policy_master",
        codegen_instructions="All date columns must use DATE type, never DATETIME.",
    )
    assert "GLOBAL CODING STANDARDS" in prompt
    assert "All date columns must use DATE type" in prompt
    assert "Destination schema: dbo" in prompt


def test_system_prompt_omits_block_when_instructions_null():
    config = make_project_config()
    prompt = _build_system_prompt(
        project_config=config,
        destination_object_name="policy_master",
        codegen_instructions=None,
    )
    assert "GLOBAL CODING STANDARDS" not in prompt


def test_system_prompt_omits_block_when_instructions_blank():
    config = make_project_config()
    prompt = _build_system_prompt(
        project_config=config,
        destination_object_name="policy_master",
        codegen_instructions="   ",
    )
    assert "GLOBAL CODING STANDARDS" not in prompt
```

For `_build_user_prompt`, a full test requires Feed/FeedSlice/MappingSnapshot ORM objects. Defer to integration verification if test setup is heavy. At minimum, test the null case by calling `_build_user_prompt` with a mock `source_definition` that has `transformation_instructions=None` and asserting the result does not contain `FEED-SPECIFIC`.

- [ ] **Step 5: Run the tests**

```bash
cd engine && pytest tests/codegen/test_service_prompts.py -v
```

Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
git add engine/src/migrations_engine/codegen/service.py \
        engine/tests/codegen/test_service_prompts.py
git commit -m "feat: inject codegen_instructions and transformation_instructions into AI prompts"
```

---

### Task 6: Frontend API client functions

**Files:**
- Modify: `web/lib/feeds-api.ts:5-17` (`FeedContractRecord`)
- Modify: `web/lib/codegen-api.ts` (two new functions)

**Interfaces:**
- Produces: `FeedContractRecord.transformationInstructions?: string | null`; `saveCodegenInstructions(token, projectId, instructions)`; `saveTransformationInstructions(token, projectId, sourceDefinitionId, instructions)`

- [ ] **Step 1: Add `transformationInstructions` to `FeedContractRecord`**

In `web/lib/feeds-api.ts`, find `FeedContractRecord` (line 5-17). After `mappingHints?: string | null;`, add:

```typescript
  transformationInstructions?: string | null;
```

- [ ] **Step 2: Carry `transformationInstructions` through the mapper**

Find the function that maps an API response object to `FeedContractRecord` (around line 163 in `feeds-api.ts`). After the `mappingHints` line, add:

```typescript
  transformationInstructions: data.transformation_instructions ?? null,
```

- [ ] **Step 3: Add `saveCodegenInstructions` to `codegen-api.ts`**

In `web/lib/codegen-api.ts`, add after the existing functions:

```typescript
export async function saveCodegenInstructions(
  token: string,
  projectId: string,
  instructions: string | null,
): Promise<void> {
  const res = await fetch(
    `${API_BASE_URL}/projects/${projectId}/codegen-instructions`,
    {
      method: "PATCH",
      headers: authHeaders(token),
      body: JSON.stringify({ codegen_instructions: instructions }),
    },
  );
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new CodegenApiError(err.code ?? "unknown", err.message ?? res.statusText, res.status);
  }
}
```

- [ ] **Step 4: Add `saveTransformationInstructions` to `codegen-api.ts`**

```typescript
export async function saveTransformationInstructions(
  token: string,
  projectId: string,
  sourceDefinitionId: string,
  instructions: string | null,
): Promise<void> {
  const res = await fetch(
    `${API_BASE_URL}/projects/${projectId}/sources/${sourceDefinitionId}/transformation-instructions`,
    {
      method: "PATCH",
      headers: authHeaders(token),
      body: JSON.stringify({ transformation_instructions: instructions }),
    },
  );
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new CodegenApiError(err.code ?? "unknown", err.message ?? res.statusText, res.status);
  }
}
```

- [ ] **Step 5: TypeScript compile check**

```bash
cd web && npx tsc --noEmit
```

Expected: no new type errors.

- [ ] **Step 6: Commit**

```bash
git add web/lib/feeds-api.ts web/lib/codegen-api.ts
git commit -m "feat: add transformation/codegen instruction API client functions"
```

---

### Task 7: Frontend — codegen page panels

**Files:**
- Modify: `web/app/projects/[id]/codegen/page.tsx`

**Interfaces:**
- Consumes: `saveCodegenInstructions`, `saveTransformationInstructions` from Task 6; `FeedContractRecord.transformationInstructions` from Task 6; `project.codegenInstructions` from existing project fetch

- [ ] **Step 1: Read the current codegen page**

```bash
wc -l web/app/projects/[id]/codegen/page.tsx
```

Read the file to understand current state: where the project is loaded, where the sources table is, what state variables exist, and what the role variable is called.

- [ ] **Step 2: Add state for global instructions panel**

Near the top of the component (alongside existing state declarations), add:

```typescript
const [codegenInstructions, setCodegenInstructions] = useState<string>("");
const [codegenInstructionsSaving, setCodegenInstructionsSaving] = useState(false);
const [codegenInstructionsError, setCodegenInstructionsError] = useState<string | null>(null);
```

- [ ] **Step 3: Seed `codegenInstructions` from project load**

In the effect or data-loading function where the project is fetched, add:

```typescript
setCodegenInstructions(project.codegenInstructions ?? "");
```

Verify that the `ProjectRecord` type used by the projects API client includes `codegenInstructions`. If the type is fetched from `projects-api.ts`, add the field there. The backend `ProjectResponse` already exposes it after Task 2.

- [ ] **Step 4: Add the global instructions panel above the sources table**

Locate where the Sources table section begins. Insert before it:

```tsx
{/* Global coding standards panel */}
<div className="rounded-lg border border-neutral-200 bg-white p-4 mb-6">
  <h2 className="text-sm font-semibold text-neutral-900 mb-1">
    Coding Standards &amp; Global Instructions
  </h2>
  <p className="text-xs text-neutral-500 mb-3">
    Applied to all feeds in this project during SQL generation.
  </p>
  <textarea
    className="w-full rounded border border-neutral-200 bg-neutral-50 p-2 text-sm font-mono resize-y min-h-[96px] disabled:opacity-50"
    rows={4}
    value={codegenInstructions}
    onChange={(e) => setCodegenInstructions(e.target.value)}
    disabled={role !== "central_team" && role !== "admin"}
    placeholder="e.g. All date columns must use DATE type, never DATETIME. No default timestamps."
  />
  {(role === "central_team" || role === "admin") && (
    <div className="flex items-center gap-2 mt-2">
      <button
        className="rounded bg-neutral-900 px-3 py-1.5 text-xs font-medium text-white disabled:opacity-50"
        disabled={codegenInstructionsSaving}
        onClick={async () => {
          setCodegenInstructionsSaving(true);
          setCodegenInstructionsError(null);
          try {
            await saveCodegenInstructions(session.accessToken, projectId, codegenInstructions || null);
          } catch (err: unknown) {
            setCodegenInstructionsError(err instanceof Error ? err.message : "Save failed");
          } finally {
            setCodegenInstructionsSaving(false);
          }
        }}
      >
        {codegenInstructionsSaving ? "Saving…" : "Save"}
      </button>
      {codegenInstructionsError && (
        <span className="text-xs text-red-600">{codegenInstructionsError}</span>
      )}
    </div>
  )}
</div>
```

Import `saveCodegenInstructions` from `@/lib/codegen-api` at the top of the file.

- [ ] **Step 5: Add per-feed expansion state**

Add a set to track which feeds have the instructions panel open:

```typescript
const [expandedFeeds, setExpandedFeeds] = useState<Set<string>>(new Set());
const [feedInstructions, setFeedInstructions] = useState<Record<string, string>>({});
const [feedInstructionsSaving, setFeedInstructionsSaving] = useState<Record<string, boolean>>({});
const [feedInstructionsError, setFeedInstructionsError] = useState<Record<string, string | null>>({});
```

When feeds are loaded, seed `feedInstructions` from `source.transformationInstructions`:

```typescript
const initial: Record<string, string> = {};
for (const s of feeds) {
  initial[s.sourceDefinitionId] = s.transformationInstructions ?? "";
}
setFeedInstructions(initial);
```

- [ ] **Step 6: Add expandable instructions row in the sources table**

In the sources table, each feed row needs a toggle button and a collapsible instructions block below it. For each feed row `source`, append after the existing row `<tr>`:

```tsx
<tr>
  <td colSpan={/* number of columns in the table */} className="p-0 border-t-0">
    <button
      className="flex items-center gap-1 px-3 py-1 text-xs text-neutral-500 hover:text-neutral-700"
      onClick={() =>
        setExpandedFeeds((prev) => {
          const next = new Set(prev);
          next.has(source.sourceDefinitionId)
            ? next.delete(source.sourceDefinitionId)
            : next.add(source.sourceDefinitionId);
          return next;
        })
      }
    >
      <span>{expandedFeeds.has(source.sourceDefinitionId) ? "▲" : "▼"}</span>
      Feed-specific transformation instructions
    </button>
    {expandedFeeds.has(source.sourceDefinitionId) && (
      <div className="px-3 pb-3">
        <textarea
          className="w-full rounded border border-neutral-200 bg-neutral-50 p-2 text-sm font-mono resize-y min-h-[72px] disabled:opacity-50"
          rows={3}
          value={feedInstructions[source.sourceDefinitionId] ?? ""}
          onChange={(e) =>
            setFeedInstructions((prev) => ({
              ...prev,
              [source.sourceDefinitionId]: e.target.value,
            }))
          }
          disabled={role !== "central_team" && role !== "admin"}
          placeholder="e.g. Map claim_no → external_claim_number. Prepend 'OC' to form 15-char claim ID."
        />
        {(role === "central_team" || role === "admin") && (
          <div className="flex items-center gap-2 mt-2">
            <button
              className="rounded bg-neutral-900 px-3 py-1.5 text-xs font-medium text-white disabled:opacity-50"
              disabled={feedInstructionsSaving[source.sourceDefinitionId] ?? false}
              onClick={async () => {
                const id = source.sourceDefinitionId;
                setFeedInstructionsSaving((prev) => ({ ...prev, [id]: true }));
                setFeedInstructionsError((prev) => ({ ...prev, [id]: null }));
                try {
                  await saveTransformationInstructions(
                    session.accessToken,
                    projectId,
                    id,
                    feedInstructions[id] || null,
                  );
                } catch (err: unknown) {
                  setFeedInstructionsError((prev) => ({
                    ...prev,
                    [id]: err instanceof Error ? err.message : "Save failed",
                  }));
                } finally {
                  setFeedInstructionsSaving((prev) => ({ ...prev, [id]: false }));
                }
              }}
            >
              {feedInstructionsSaving[source.sourceDefinitionId] ? "Saving…" : "Save"}
            </button>
            {feedInstructionsError[source.sourceDefinitionId] && (
              <span className="text-xs text-red-600">
                {feedInstructionsError[source.sourceDefinitionId]}
              </span>
            )}
          </div>
        )}
      </div>
    )}
  </td>
</tr>
```

Import `saveTransformationInstructions` from `@/lib/codegen-api`.

- [ ] **Step 7: TypeScript compile check**

```bash
cd web && npx tsc --noEmit
```

Expected: no new type errors.

- [ ] **Step 8: Verify `ProjectRecord` type includes `codegenInstructions`**

```bash
grep -rn "codegenInstructions\|codegen_instructions" web/lib/ web/types/
```

If the project response type (`ProjectRecord` or similar) in `web/lib/projects-api.ts` does not include `codegenInstructions`, add it:
```typescript
codegenInstructions?: string | null;
```
and ensure the mapper passes it through from `data.codegen_instructions`.

- [ ] **Step 9: Commit**

```bash
git add web/app/projects/[id]/codegen/page.tsx web/lib/projects-api.ts
git commit -m "feat: add global and per-feed instruction panels to codegen page"
```

---

### Task 8: Domain page updates

**Files:**
- Modify: `docs/domain/project.md:61-77`
- Modify: `docs/domain/source-model.md`

**Interfaces:** None — documentation only.

- [ ] **Step 1: Update `docs/domain/project.md`**

Read `docs/domain/project.md` around lines 61-77 to find the `ProjectDefinition` field list. Add an entry for the new field:

```
- `codegen_instructions` (TEXT, nullable) — Natural-language global coding standards applied to all SQL generation for this project. Injected as a `GLOBAL CODING STANDARDS` block in the system prompt. Survives copy-on-write updates and project copy.
```

Place it alongside the other definition fields.

- [ ] **Step 2: Update `docs/domain/source-model.md`**

Read `docs/domain/source-model.md` to find the codegen artifact section. Add a subsection documenting:

```markdown
### Transformation Instructions

`Feed.transformation_instructions` (TEXT, nullable) — Natural-language per-feed rules injected into the codegen user prompt as a `FEED-SPECIFIC TRANSFORMATION INSTRUCTIONS` block. Copied when a project is duplicated. Examples: field renames, derived value rules, date format overrides.

#### Codegen Prompt Structure

1. **System prompt** — project context:
   - Destination object name
   - Target DB engine
   - Staging schema
   - Destination schema
   - `GLOBAL CODING STANDARDS` block (omitted if `codegen_instructions` is null/blank)

2. **User prompt** — feed-specific context:
   - Source contract, slice version, destination object, mapping snapshot version
   - Field bindings (source → destination, lookup reference)
   - Feed discussion thread
   - Slice discussion thread
   - `FEED-SPECIFIC TRANSFORMATION INSTRUCTIONS` block (omitted if `transformation_instructions` is null/blank)
```

- [ ] **Step 3: Commit**

```bash
git add docs/domain/project.md docs/domain/source-model.md
git commit -m "docs: update project.md and source-model.md for codegen instruction fields"
```

---

## Verification Checklist

After all tasks are complete, verify end-to-end:

1. Navigate to `/projects/[id]/codegen`. Global instructions textarea is visible above the sources table.
2. Type global instructions → click Save → no error → reload page → textarea shows saved text.
3. Click the chevron on a feed row → instructions textarea expands.
4. Type feed instructions → click Save → no error → reload page → expand same feed → saved text appears.
5. Click Generate SQL on a feed → inspect the API call payload (browser devtools → Network → the AI call) — both `GLOBAL CODING STANDARDS` and `FEED-SPECIFIC TRANSFORMATION INSTRUCTIONS` blocks appear in the system/user prompt.
6. Clear both instructions, save → Generate SQL again → neither block appears (no empty headers).
7. Log in as `project_stakeholder` → codegen page → textareas are read-only, no Save buttons visible.
8. Duplicate a project → new project's codegen page shows same global instructions as source. Feed instructions also copied.
9. Update any other project field (e.g. name) → verify `codegen_instructions` is not lost (still present on reload).
