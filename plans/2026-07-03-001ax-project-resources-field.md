# Project Resources Field Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the unused `project_records.environment` String(64) column with a `project_resources` Text column that stores free-form infrastructure notes per environment, and wire it through the full stack.

**Architecture:** One Alembic migration drops the old column and adds the new one. The ORM model, Pydantic schemas, and CRUD passthrough in the engine are updated in the same pass. The frontend removes `environment` from the type map and adds `projectResources`, then renders it as a read-only textarea in `ProjectDetailView`. `RunRecord.environment` and `RunCheckpoint.current_environment` are in different tables and are never touched.

**Tech Stack:** SQLAlchemy 2 / Alembic, Pydantic v2, FastAPI, Next.js / TypeScript, Vitest

## Global Constraints

- `RunRecord.environment` and `RunCheckpoint.current_environment` must not be modified
- `execution_environments` must not be modified — it powers the portfolio dashboard filter
- `project_resources` is nullable Text; no length limit
- `project_resources` may contain passwords and credentials; it must never appear in logs or exception messages
- The pre-fill template uses plain text with `== ENV ==` section headers

## Template Default

```
== DEV ==
Host/IP:
Port:
Database:
Username:
Password:
VPN:
Notes:

== STG ==
Host/IP:
Port:
Database:
Username:
Password:
VPN:
Notes:

== PROD ==
Host/IP:
Port:
Database:
Username:
Password:
VPN:
Notes:
```

## File Changes

| Action | Path |
|--------|------|
| Create | `engine/migrations/versions/0022_project_resources.py` |
| Modify | `engine/src/migrations_engine/db/models.py` |
| Modify | `engine/src/migrations_engine/api/schemas.py` |
| Modify | `engine/src/migrations_engine/management/projects.py` |
| Modify | `engine/tests/test_project_crud_api.py` |
| Modify | `web/lib/projects-api.ts` |
| Modify | `web/components/projects/ProjectDetailView.tsx` |

---

### Task 1: Engine — migration, model, schemas, CRUD

**Files:**
- Create: `engine/migrations/versions/0022_project_resources.py`
- Modify: `engine/src/migrations_engine/db/models.py`
- Modify: `engine/src/migrations_engine/api/schemas.py`
- Modify: `engine/src/migrations_engine/management/projects.py`
- Modify: `engine/tests/test_project_crud_api.py`

**Interfaces:**
- Produces: `ProjectDefinition.project_resources: str | None`, `ProjectCreateRequest.project_resources: str | None = None`, `ProjectUpdateRequest.project_resources: str | None = None`

- [ ] **Step 1: Write the failing tests**

In `engine/tests/test_project_crud_api.py`, update the create and read tests:

```python
# In test_create_project: replace environment with project_resources
body = {
    "name": "CRM Migration",
    "goal": "Migrate all CRM data",
    "project_resources": "== PROD ==\nHost/IP: 10.0.0.1\nPort: 5432",
    "execution_environments": ["STG", "UAT", "PROD"],
    # remove "environment" key
}

# Assert project_resources is returned
assert body["project_resources"] == "== PROD ==\nHost/IP: 10.0.0.1\nPort: 5432"
assert "environment" not in body  # old field gone
```

- [ ] **Step 2: Run the tests and confirm they fail**

Run: `cd engine && python -m pytest tests/test_project_crud_api.py -v -k "create or read"`
Expected: failures because `project_resources` field does not exist yet and `environment` is still present.

- [ ] **Step 3: Write the Alembic migration**

Create `engine/migrations/versions/0022_project_resources.py`:

```python
"""project_resources field

Revision ID: 0022
Revises: 0021
Create Date: 2026-07-03
"""

from alembic import op
import sqlalchemy as sa

revision = "0022"
down_revision = "0021"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_column("project_records", "environment")
    op.add_column(
        "project_records",
        sa.Column("project_resources", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("project_records", "project_resources")
    op.add_column(
        "project_records",
        sa.Column("environment", sa.String(length=64), nullable=True),
    )
```

- [ ] **Step 4: Update the ORM model**

In `engine/src/migrations_engine/db/models.py`, on the `ProjectRecord` class:

Replace:
```python
environment: Mapped[str | None] = mapped_column(String(64))
```
With:
```python
project_resources: Mapped[str | None] = mapped_column(Text)
```

Add `Text` to the SQLAlchemy imports if not already present.

Do NOT touch `RunRecord.environment` or `RunCheckpoint.current_environment`.

- [ ] **Step 5: Update Pydantic schemas**

In `engine/src/migrations_engine/api/schemas.py`:

In `ProjectDefinition`:
```python
# Replace:
environment: str | None
# With:
project_resources: str | None
```

In `ProjectCreateRequest`:
```python
# Replace:
environment: str | None = None
# With:
project_resources: str | None = None
```

In `ProjectUpdateRequest`:
```python
# Replace:
environment: str | None = None
# With:
project_resources: str | None = None
```

- [ ] **Step 6: Update CRUD passthrough**

In `engine/src/migrations_engine/management/projects.py`:

In the `create_project` function:
```python
# Replace:
environment=body.environment,
# With:
project_resources=body.project_resources,
```

In the `update_project` function:
```python
# Replace:
environment=body.environment if body.environment is not None else current_definition.environment,
# With:
project_resources=body.project_resources if body.project_resources is not None else current_definition.project_resources,
```

In the `_project_definition` (or equivalent mapping function):
```python
# Replace:
environment=definition.environment,
# With:
project_resources=definition.project_resources,
```

- [ ] **Step 7: Re-run the tests and confirm they pass**

Run: `cd engine && python -m pytest tests/test_project_crud_api.py -v`
Expected: all project CRUD tests pass; no reference to `environment` field on project responses.

- [ ] **Step 8: Commit**

```bash
git add engine/migrations/versions/0022_project_resources.py \
        engine/src/migrations_engine/db/models.py \
        engine/src/migrations_engine/api/schemas.py \
        engine/src/migrations_engine/management/projects.py \
        engine/tests/test_project_crud_api.py
git commit -m "feat(001ax): add project_resources text field, drop environment column"
```

---

### Task 2: Frontend — types and read-only display

**Files:**
- Modify: `web/lib/projects-api.ts`
- Modify: `web/components/projects/ProjectDetailView.tsx`

**Interfaces:**
- Consumes: `ProjectRecord.projectResources: string | null` (from Task 1 API)
- Produces: `projectResources` shown as a read-only textarea in `ProjectDetailView`

- [ ] **Step 1: Write the failing tests**

In `web/components/projects/__tests__/ProjectDetailView.test.tsx`, add:

```tsx
it("renders projectResources as a textarea", () => {
  render(<ProjectDetailView project={{ ...project, projectResources: "== PROD ==\nHost/IP: 10.0.0.1" }} />);
  const textarea = screen.getByRole("textbox", { name: /project resources/i });
  expect(textarea).toHaveValue("== PROD ==\nHost/IP: 10.0.0.1");
  expect(textarea).toHaveAttribute("readonly");
});

it("renders placeholder when projectResources is null", () => {
  render(<ProjectDetailView project={{ ...project, projectResources: null }} />);
  expect(screen.getByRole("textbox", { name: /project resources/i })).toHaveValue("");
});
```

- [ ] **Step 2: Run the tests and confirm they fail**

Run: `cd web && npm test -- components/projects/__tests__/ProjectDetailView.test.tsx`
Expected: `projectResources` does not exist on the type yet.

- [ ] **Step 3: Update frontend types**

In `web/lib/projects-api.ts`:

In `ProjectRecord` (camelCase interface):
```ts
// Replace:
environment: string | null;
// With:
projectResources: string | null;
```

In `ProjectCreateInput` / `ProjectUpdateInput`:
```ts
// Replace:
environment?: string | null;
// With:
projectResources?: string | null;
```

In the raw API response type (snake_case):
```ts
// Replace:
environment: string | null;
// With:
project_resources: string | null;
```

In the mapping function:
```ts
// Replace:
environment: record.environment,
// With:
projectResources: record.project_resources,
```

In the request builder:
```ts
// Replace:
environment: input.environment,
// With:
project_resources: input.projectResources,
```

- [ ] **Step 4: Update ProjectDetailView**

In `web/components/projects/ProjectDetailView.tsx`:

Replace the `environment` KeyValue row:
```tsx
<KeyValue label="Environment" value={project.environment ?? "—"} />
```

With a labelled textarea:
```tsx
<div className="flex flex-col gap-1">
  <label
    htmlFor="project-resources"
    className="text-sm font-medium text-slate-700"
  >
    Project Resources
  </label>
  <textarea
    id="project-resources"
    aria-label="Project Resources"
    readOnly
    rows={12}
    className="w-full rounded-md border border-outline-variant bg-surface px-3 py-2 font-mono text-sm text-slate-800"
    value={project.projectResources ?? ""}
  />
</div>
```

- [ ] **Step 5: Re-run the tests and confirm they pass**

Run: `cd web && npm test -- components/projects/__tests__/ProjectDetailView.test.tsx`
Expected: both new tests pass; existing tests pass.

- [ ] **Step 6: Run the full web test suite for regressions**

Run: `cd web && npm test`
Expected: all tests pass; no reference to the old `environment` field on project types.

- [ ] **Step 7: Commit**

```bash
git add web/lib/projects-api.ts web/components/projects/ProjectDetailView.tsx \
        web/components/projects/__tests__/ProjectDetailView.test.tsx
git commit -m "feat(001ax): wire projectResources to frontend types and detail view"
```

---

## Verification

1. Engine CRUD: `cd engine && python -m pytest tests/test_project_crud_api.py -v`
2. Full engine suite (no regressions): `cd engine && python -m pytest -v`
3. Frontend suite: `cd web && npm test`
4. Confirm `environment` no longer appears in project API responses or frontend types

## Commit Summary

```
feat(001ax): add project_resources text field, drop environment column
feat(001ax): wire projectResources to frontend types and detail view
```
