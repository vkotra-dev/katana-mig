# 001cn — Codegen Instructions: Test Coverage & Completion Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Verify the already-implemented codegen instructions feature (DB columns, PATCH endpoints, frontend panels, Jinja2 injection) actually works end-to-end by applying pending migrations and adding the missing tests.

**Architecture:** All implementation code exists. This plan only covers: (1) running pending DB migrations, (2) backend API tests for the two PATCH endpoints and copy-project propagation, (3) fixing incomplete frontend test mocks and adding save-flow tests, (4) TASK_INDEX.md housekeeping.

**Tech Stack:** Python / FastAPI / SQLAlchemy / SQLite (tests), TypeScript / Next.js / Vitest / React Testing Library

## Global Constraints

- Backend tests use SQLite in-memory via `sqlite_test_support`; do NOT connect to MySQL in tests
- `test_project_crud_api.py` imports `SessionLocal` from `sqlite_test_support`; match that pattern
- `test_source_intake_api.py` creates its own `_sqlite_engine` and `_setup_sqlite_db` fixture; match that pattern
- Run backend tests from `engine/` with: `PYTHONPATH=src python -m pytest tests/<file> -v`
- Run frontend tests from `web/` with: `npx vitest run app/projects/\[id\]/codegen/page.test.tsx`
- Never mock `SessionLocal` or the DB engine in tests; the conftest hook patches it automatically for modules that define `_sqlite_engine` at module level

---

### Task 1: Apply pending DB migrations

**Files:**
- No code changes — runs alembic against the MySQL instance

**Interfaces:**
- Produces: `project_definitions.codegen_instructions TEXT NULL` and `source_definitions.transformation_instructions TEXT NULL` columns in MySQL

- [ ] **Step 1: Run alembic upgrade**

```bash
cd /Users/vjkotra/projects/katana/engine
alembic upgrade head
```

Expected output: lines for `0030_codegen_instructions` and `0031_transformation_instructions` in the upgrade log, ending with no errors.

- [ ] **Step 2: Verify columns exist**

```bash
cd /Users/vjkotra/projects/katana/engine
python -c "
from dotenv import load_dotenv; load_dotenv()
from migrations_engine.db.session import engine
from sqlalchemy import inspect
insp = inspect(engine)
pd_cols = [c['name'] for c in insp.get_columns('project_definitions')]
sd_cols = [c['name'] for c in insp.get_columns('source_definitions')]
assert 'codegen_instructions' in pd_cols, f'missing from project_definitions: {pd_cols}'
assert 'transformation_instructions' in sd_cols, f'missing from source_definitions: {sd_cols}'
print('OK — both columns present')
"
```

Expected: `OK — both columns present`

- [ ] **Step 3: Commit (no code change — nothing to commit)**

Migration files already committed in 0030 and 0031. If alembic applied cleanly, this task is done.

---

### Task 2: Backend tests — PATCH codegen-instructions endpoint

**Files:**
- Modify: `engine/tests/test_project_crud_api.py` (append two tests at the end)

**Interfaces:**
- Consumes: existing `_create_project(token, body)` helper, `admin_token` fixture, `SessionLocal` from `sqlite_test_support`, `ProjectDefinition` model
- Produces: two new test functions covering PATCH save and copy propagation

- [ ] **Step 1: Write the failing tests**

Append to `engine/tests/test_project_crud_api.py`:

```python
def test_patch_codegen_instructions_saves_and_roundtrips(admin_token: str) -> None:
    project = _create_project(admin_token, {"name": "Codegen Instr Test"})
    project_id = project["project_id"]

    response = client.patch(
        f"/projects/{project_id}/codegen-instructions",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"codegen_instructions": "Use snake_case for all columns."},
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["codegen_instructions"] == "Use snake_case for all columns."

    # Value persists in a new project_definition row (copy-on-write)
    with SessionLocal() as db:
        rows = list(
            db.scalars(
                select(ProjectDefinition)
                .where(ProjectDefinition.project_id == project_id)
                .order_by(ProjectDefinition.created_at.desc())
            )
        )
    assert rows[0].codegen_instructions == "Use snake_case for all columns."


def test_copy_project_carries_codegen_instructions(admin_token: str) -> None:
    project = _create_project(admin_token, {"name": "Source With Standards"})
    project_id = project["project_id"]

    client.patch(
        f"/projects/{project_id}/codegen-instructions",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"codegen_instructions": "All dates must use DATE type."},
    )

    response = client.post(
        f"/projects/{project_id}/copy",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"name": "Copied Project", "stakeholder_user_ids": []},
    )
    assert response.status_code == 201, response.text
    new_id = response.json()["project_id"]

    get_response = client.get(
        f"/projects/{new_id}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert get_response.status_code == 200
    assert get_response.json()["codegen_instructions"] == "All dates must use DATE type."
```

- [ ] **Step 2: Run to verify they fail**

```bash
cd /Users/vjkotra/projects/katana/engine
PYTHONPATH=src python -m pytest tests/test_project_crud_api.py::test_patch_codegen_instructions_saves_and_roundtrips tests/test_project_crud_api.py::test_copy_project_carries_codegen_instructions -v
```

Expected: both FAIL (missing `codegen_instructions` key in response or 404 if schema not applied to SQLite).

If they error with `no such column`, the SQLite schema needs updating — but the `Base.metadata.create_all` in the conftest reads from the current models, so if models.py already has the column it should be present. Confirm by re-running; if it fails with column error, check that `ProjectDefinition.codegen_instructions` is in `engine/src/migrations_engine/db/models.py` line 56.

- [ ] **Step 3: Verify models are correct (read-only check)**

```bash
grep -n "codegen_instructions" /Users/vjkotra/projects/katana/engine/src/migrations_engine/db/models.py
```

Expected: at least one line showing `codegen_instructions: Mapped[str | None] = mapped_column(Text, nullable=True)`

- [ ] **Step 4: Run tests again — expect PASS**

```bash
cd /Users/vjkotra/projects/katana/engine
PYTHONPATH=src python -m pytest tests/test_project_crud_api.py::test_patch_codegen_instructions_saves_and_roundtrips tests/test_project_crud_api.py::test_copy_project_carries_codegen_instructions -v
```

Expected: both PASS.

- [ ] **Step 5: Commit**

```bash
git add engine/tests/test_project_crud_api.py
git commit -m "test: add PATCH codegen-instructions and copy propagation tests"
```

---

### Task 3: Backend tests — PATCH transformation-instructions endpoint

**Files:**
- Modify: `engine/tests/test_source_intake_api.py` (append two tests at the end)

**Interfaces:**
- Consumes: existing `_create_project(token, name)` helper, `admin_token` fixture, `SessionLocal` from the module-level setup
- Produces: tests for PATCH on the feed transformation-instructions endpoint and copy propagation

- [ ] **Step 1: Write the failing tests**

Append to `engine/tests/test_source_intake_api.py`:

```python
def test_patch_transformation_instructions_saves_and_roundtrips(admin_token: str) -> None:
    project = _create_project(admin_token, f"TransInstr-{uuid.uuid4().hex[:6]}")
    project_id = project["project_id"]

    # Create a source feed
    create_resp = client.post(
        f"/projects/{project_id}/sources",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"source_type": "csv", "label": "Claims Extract", "encoding": "utf-8"},
    )
    assert create_resp.status_code == 201, create_resp.text
    source_id = create_resp.json()["source_definition_id"]

    # PATCH transformation instructions
    patch_resp = client.patch(
        f"/projects/{project_id}/sources/{source_id}/transformation-instructions",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"transformation_instructions": "Map claim_no to external_claim_id."},
    )
    assert patch_resp.status_code == 200, patch_resp.text
    assert patch_resp.json()["transformation_instructions"] == "Map claim_no to external_claim_id."

    # Verify persisted
    with SessionLocal() as db:
        from migrations_engine.db.models import Feed
        feed = db.get(Feed, source_id)
    assert feed is not None
    assert feed.transformation_instructions == "Map claim_no to external_claim_id."


def test_patch_transformation_instructions_can_be_cleared(admin_token: str) -> None:
    project = _create_project(admin_token, f"TransInstrClear-{uuid.uuid4().hex[:6]}")
    project_id = project["project_id"]

    create_resp = client.post(
        f"/projects/{project_id}/sources",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"source_type": "csv", "label": "Orders Extract", "encoding": "utf-8"},
    )
    source_id = create_resp.json()["source_definition_id"]

    client.patch(
        f"/projects/{project_id}/sources/{source_id}/transformation-instructions",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"transformation_instructions": "Some instructions."},
    )

    clear_resp = client.patch(
        f"/projects/{project_id}/sources/{source_id}/transformation-instructions",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"transformation_instructions": None},
    )
    assert clear_resp.status_code == 200, clear_resp.text
    assert clear_resp.json()["transformation_instructions"] is None
```

- [ ] **Step 2: Run to verify they fail**

```bash
cd /Users/vjkotra/projects/katana/engine
PYTHONPATH=src python -m pytest tests/test_source_intake_api.py::test_patch_transformation_instructions_saves_and_roundtrips tests/test_source_intake_api.py::test_patch_transformation_instructions_can_be_cleared -v
```

Expected: FAIL (404 or missing field in response until confirmed).

- [ ] **Step 3: Run tests again — expect PASS**

```bash
cd /Users/vjkotra/projects/katana/engine
PYTHONPATH=src python -m pytest tests/test_source_intake_api.py::test_patch_transformation_instructions_saves_and_roundtrips tests/test_source_intake_api.py::test_patch_transformation_instructions_can_be_cleared -v
```

Expected: both PASS.

- [ ] **Step 4: Commit**

```bash
git add engine/tests/test_source_intake_api.py
git commit -m "test: add PATCH transformation-instructions endpoint tests"
```

---

### Task 4: Fix frontend test mocks and add save-flow tests

**Files:**
- Modify: `web/app/projects/[id]/codegen/page.test.tsx`

**Interfaces:**
- Consumes: `saveCodegenInstructions` from `projects-api`, `saveTransformationInstructions` from `feeds-api`
- Produces: mocks for both save functions; two new `it()` blocks covering save flows

The current `vi.mock("../../../../lib/projects-api", ...)` only exports `getProject`, so any test that triggers `handleSaveGlobalInstructions` would call `undefined()` and throw. Same for `feeds-api` and `handleSaveFeedInstructions`. The existing tests avoid the save path; the new ones do not.

- [ ] **Step 1: Add mock functions to vi.hoisted**

In `page.test.tsx`, extend the `vi.hoisted` destructuring (currently ends at `getAllApprovedMappingSnapshotsMock`):

```typescript
const {
  loadUiSessionMock,
  listFeedContractsMock,
  listCodegenArtifactsMock,
  getSchemaAnalysisMock,
  triggerCodegenMock,
  downloadCodegenDeliveryBundleMock,
  triggerSchemaAnalysisMock,
  routerPushMock,
  getProjectMock,
  listFeedFibersMock,
  listFeedSlicesMock,
  getAllApprovedMappingSnapshotsMock,
  saveCodegenInstructionsMock,
  saveTransformationInstructionsMock,
} = vi.hoisted(() => ({
  loadUiSessionMock: vi.fn(),
  listFeedContractsMock: vi.fn(),
  listCodegenArtifactsMock: vi.fn(),
  getSchemaAnalysisMock: vi.fn(),
  triggerCodegenMock: vi.fn(),
  downloadCodegenDeliveryBundleMock: vi.fn(),
  triggerSchemaAnalysisMock: vi.fn(),
  routerPushMock: vi.fn(),
  getProjectMock: vi.fn(),
  listFeedFibersMock: vi.fn(),
  listFeedSlicesMock: vi.fn(),
  getAllApprovedMappingSnapshotsMock: vi.fn(),
  saveCodegenInstructionsMock: vi.fn(),
  saveTransformationInstructionsMock: vi.fn(),
}));
```

- [ ] **Step 2: Add the new mocks to the vi.mock factories**

Replace the existing `vi.mock("../../../../lib/projects-api", ...)` block:

```typescript
vi.mock("../../../../lib/projects-api", () => ({
  getProject: getProjectMock,
  saveCodegenInstructions: saveCodegenInstructionsMock,
}));
```

Replace the existing `vi.mock("../../../../lib/feeds-api", ...)` block:

```typescript
vi.mock("../../../../lib/feeds-api", () => ({
  listFeedContracts: listFeedContractsMock,
  listFeedFibers: listFeedFibersMock,
  listFeedSlices: listFeedSlicesMock,
  saveTransformationInstructions: saveTransformationInstructionsMock,
}));
```

- [ ] **Step 3: Wire up default mock return values in `beforeEach`**

In the `beforeEach` block, after the existing mock setup, add:

```typescript
saveCodegenInstructionsMock.mockResolvedValue({
  projectId: "project-1",
  name: "Project 1",
  goal: "Goal 1",
  repos: [],
  workspace: null,
  projectResources: null,
  executionEnvironments: [],
  modelPolicy: null,
  canonicalTerms: [],
  constraints: [],
  unresolvedQuestions: [],
  assumptions: [],
  domainConfig: null,
  lexiconScope: null,
  status: "active",
  createdAt: "2026-06-30T00:00:00Z",
  updatedAt: "2026-06-30T00:00:00Z",
  archivedAt: null,
  codegenInstructions: "Updated standards",
});
saveTransformationInstructionsMock.mockResolvedValue({
  sourceDefinitionId: "source-1",
  projectId: "project-1",
  sourceType: "csv",
  label: "Customer extract",
  encoding: "utf-8",
  destinationObjectReferences: ["Customer"],
  layoutInformation: null,
  copybookText: null,
  status: "active",
  createdAt: "2026-06-30T00:00:00Z",
  transformationInstructions: "Map field_a to col_a.",
});
```

- [ ] **Step 4: Add the two new test cases**

Append to the `describe("CodegenPage", ...)` block:

```typescript
it("saves coding standards when clicking Save Standards button", async () => {
  render(<CodegenPage params={Promise.resolve({ id: "project-1" })} />);

  await screen.findByText("Customer extract");

  const textarea = screen.getByPlaceholderText(/e.g. All date columns must use DATE type/i);
  fireEvent.change(textarea, { target: { value: "Use snake_case for all columns." } });

  const saveBtn = screen.getByRole("button", { name: "Save Standards" });
  fireEvent.click(saveBtn);

  await waitFor(() => {
    expect(saveCodegenInstructionsMock).toHaveBeenCalledWith(
      "token-1",
      "project-1",
      "Use snake_case for all columns."
    );
  });
  expect(await screen.findByText("Coding standards and global instructions saved.")).toBeInTheDocument();
});

it("saves feed transformation instructions when clicking Save button", async () => {
  render(<CodegenPage params={Promise.resolve({ id: "project-1" })} />);

  await screen.findByText("Customer extract");

  // Expand the feed row
  const toggleBtn = screen.getByText("▶");
  fireEvent.click(toggleBtn);

  const textarea = await screen.findByPlaceholderText(/e.g. Map claim_no -> external_claim_number/i);
  fireEvent.change(textarea, { target: { value: "Map field_a to col_a." } });

  const saveBtn = await screen.findByRole("button", { name: "Save Instructions" });
  fireEvent.click(saveBtn);

  await waitFor(() => {
    expect(saveTransformationInstructionsMock).toHaveBeenCalledWith(
      "token-1",
      "project-1",
      "source-1",
      "Map field_a to col_a."
    );
  });
  expect(await screen.findByText("Feed-specific transformation instructions saved.")).toBeInTheDocument();
});
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
cd /Users/vjkotra/projects/katana/web
npx vitest run "app/projects/\[id\]/codegen/page.test.tsx"
```

Expected: all existing tests still pass, the two new tests pass.

- [ ] **Step 6: Commit**

```bash
git add web/app/projects/\[id\]/codegen/page.test.tsx
git commit -m "test: add save-flow tests for codegen and transformation instructions"
```

---

### Task 5: TASK_INDEX.md housekeeping

**Files:**
- Modify: `tasks/TASK_INDEX.md`

**Interfaces:**
- None

- [ ] **Step 1: Remove the duplicate 001cn from the Ready section**

In `tasks/TASK_INDEX.md`, the Ready section currently contains:

```markdown
| [001cn-codegen-instructions](./001cn-codegen-instructions.md) | Project-wide coding standards + per-feed transformation instructions injected into AI codegen prompt |
```

Delete that row. The Completed section already has the correct entry pointing to `./completed/001cn-codegen-instructions.md`.

- [ ] **Step 2: Run a quick sanity check**

```bash
grep -n "001cn" /Users/vjkotra/projects/katana/tasks/TASK_INDEX.md
```

Expected: only one line, in the Completed section.

- [ ] **Step 3: Commit**

```bash
git add tasks/TASK_INDEX.md
git commit -m "chore: remove duplicate 001cn entry from Ready section"
```
