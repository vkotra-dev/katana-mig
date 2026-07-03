# Project Edit Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a project edit flow from the project detail screen so central-team users can update project metadata with the existing project update API.

**Architecture:** Keep the project detail page as the read-only summary and add an explicit Edit entry point that leads to a dedicated edit route. Build a focused `ProjectEditForm` component that owns field state, prefill logic, submit handling, and inline errors; the edit page fetches the current project and hands the record to that form. Reuse the existing project API client and error mapper rather than adding new transport code.

**Tech Stack:** Next.js App Router, React, Vitest, existing project API client.

## Global Constraints

- The project remains the stable top-level container for a migration effort.
- The destination schema remains client-owned and is not invented by Katana.
- `central_team` lands on the portfolio dashboard.
- `project_stakeholder` access is membership-scoped.
- Preserve the existing authenticated top nav and project shell.

## Task

- [001aw-project-edit](../tasks/001aw-project-edit.md)

## Domain

- [ui.md](/Users/vjkotra/projects/katana/docs/domain/ui.md)
- [project.md](/Users/vjkotra/projects/katana/docs/domain/project.md)
- [api.md](/Users/vjkotra/projects/katana/docs/domain/api.md)

## Current State

- The project list and project detail routes already exist.
- `web/app/projects/[id]/page.tsx` renders the overview summary and tabs but has no edit entry point.
- `web/lib/projects-api.ts` already exposes `updateProject(token, id, body)`.
- There is no shared project edit form component yet.

## Objective

Add a routeable project edit screen and expose it from the project detail page so central-team users can update project metadata without leaving the project shell.

## Out of Scope

- Project creation.
- Archive/delete behavior.
- Source, run, or approval workflows.
- Backend project API changes unless the UI needs a missing client helper.

## Blast Radius

- `engine/src/migrations_engine/api/schemas.py`
- `engine/src/migrations_engine/codegen/service.py`
- `engine/src/migrations_engine/management/fibers.py`
- `web/lib/projects-api.ts`
- `web/app/projects/[id]/page.tsx`
- `web/app/projects/[id]/edit/page.tsx`
- `web/components/projects/ProjectEditForm.tsx`
- `web/components/projects/ProjectDetailView.tsx`
- `web/components/projects/__tests__/ProjectEditForm.test.tsx`
- `web/app/projects/[id]/edit/page.test.tsx`
- `web/app/projects/[id]/page.test.tsx`
- `web/lib/projects-api.test.ts` only if the update client needs explicit coverage

## File Changes

- Add `SamplePolicy` Pydantic model and `destination_schema` field to `MigrationProjectConfig` in the engine.
- Add `SamplePolicy` TypeScript interface and `destinationSchema` field to the frontend domain config types.
- Add a dedicated project edit page under the project route tree.
- Extract a reusable form for project metadata fields so the edit page can prefill and submit cleanly.
- The form renders `destinationSchema` as a text input and replaces the raw JSON `samplePolicy` textarea with a "Sample Policy" section: strategy picklist (random / top_n / full / stratified), max rows number input, and a conditional stratified-column text input shown only when strategy is `stratified`.
- Update the project detail view to show `destinationSchema` and render sample policy as readable labelled values instead of raw JSON.
- Add an Edit entry point to the project detail header.
- Cover the form submit and navigation flow with Vitest.

## Tests

- The edit form renders with the project’s current values prefilled.
- Submit calls `updateProject(token, id, body)` with the expected payload.
- Edit page shows inline errors and preserves form state on failure.
- Project detail page shows an Edit action for central-team users.
- Clicking Edit routes to `/projects/{id}/edit`.

## Verification

- Run the focused project edit tests in `web`.
- Smoke-check the project detail page and the edit page in the browser.

## Pitfalls

- Do not turn the edit screen into a brand-new wizard; keep it aligned with the existing detail view and project API.
- Keep the top nav and project shell intact.
- Make sure edit failure does not lose the already-entered form state.

## Commits

- `feat(001aw): add SamplePolicy model and destination_schema to domain config`
- `feat(001aw): add reusable project edit form and route`
- `feat(001aw): add project detail edit entry point`

### Task 0: Extend backend and frontend domain config types

**Files:**
- Modify: `engine/src/migrations_engine/api/schemas.py`
- Modify: `web/lib/projects-api.ts`

**Interfaces:**
- Produces:
  - `SamplePolicyStrategy = Literal["random", "top_n", "full", "stratified"]`
  - `class SamplePolicy(BaseModel): strategy / max_rows / stratified_column`
  - `MigrationProjectConfig.destination_schema: str | None = None`
  - `MigrationProjectConfig.sample_policy: SamplePolicy | None = None`
  - Frontend `SamplePolicy` interface with camelCase keys
  - Frontend `ProjectDomainConfig.destinationSchema: string | null`

**Why destination_schema matters for codegen:**
The codegen layer (`codegen/service.py`) already injects `staging_schema` into every system prompt and user prompt so the AI knows to prefix staging tables as `{staging_schema}.stg_{table}` and lookup tables as `{staging_schema}.{lookup_table}`. The `destination_schema` name completes this — migration procedures read from `{staging_schema}.stg_{table}` and write to `{destination_schema}.{table}`. Without it, the AI cannot generate fully-qualified destination table references. Both names must be in the prompt.

- [ ] **Step 1: Write the failing test**

In `engine/tests/test_project_crud_api.py`, add a test that round-trips `destination_schema` and a structured `sample_policy`:

```python
def test_create_project_with_domain_config_extensions(client, auth_headers):
    body = {
        "name": "Schema Test",
        "goal": "Verify domain config extensions",
        "domain_config": {
            "target_db_engine": "mssql",
            "staging_schema": "stg",
            "destination_schema": "dbo",
            "sample_policy": {
                "strategy": "stratified",
                "max_rows": 500,
                "stratified_column": "region",
            },
        },
    }
    response = client.post("/projects", json=body, headers=auth_headers)
    assert response.status_code == 201
    data = response.json()
    assert data["domain_config"]["destination_schema"] == "dbo"
    assert data["domain_config"]["sample_policy"]["strategy"] == "stratified"
    assert data["domain_config"]["sample_policy"]["max_rows"] == 500
    assert data["domain_config"]["sample_policy"]["stratified_column"] == "region"
```

- [ ] **Step 2: Run the test and confirm it fails**

Run: `cd engine && python -m pytest tests/test_project_crud_api.py::test_create_project_with_domain_config_extensions -v`
Expected: `destination_schema` key not present in response; `sample_policy` accepts the dict but returns it unvalidated.

- [ ] **Step 3: Update the backend schema**

In `engine/src/migrations_engine/api/schemas.py`, after the `ProjectStatus` line add:

```python
SamplePolicyStrategy = Literal["random", "top_n", "full", "stratified"]


class SamplePolicy(BaseModel):
    strategy: SamplePolicyStrategy = "random"
    max_rows: int | None = None
    stratified_column: str | None = None
```

In `MigrationProjectConfig`, replace `sample_policy` and add `destination_schema`:

```python
class MigrationProjectConfig(BaseModel):
    target_db_engine: TargetDbEngine | None = None
    staging_schema: str | None = None
    destination_schema: str | None = None
    dry_run: bool = False
    sample_policy: SamplePolicy | None = None
    destination_schema_ddl: str | None = None
    environments: list[str] | None = None
```

- [ ] **Step 4: Update the frontend types**

In `web/lib/projects-api.ts`, after `TargetDbEngine` add:

```ts
export type SamplePolicyStrategy = "random" | "top_n" | "full" | "stratified";

export interface SamplePolicy {
  strategy: SamplePolicyStrategy;
  maxRows: number | null;
  stratifiedColumn: string | null;
}
```

In `ProjectDomainConfig`, add `destinationSchema` and change `samplePolicy` type:

```ts
export interface ProjectDomainConfig {
  targetDbEngine: TargetDbEngine | null;
  stagingSchema: string | null;
  destinationSchema: string | null;
  dryRun: boolean;
  samplePolicy: SamplePolicy | null;
  destinationSchemaDdl: string | null;
  environments: string[] | null;
}
```

In `ProjectDomainConfigInput`:

```ts
export interface ProjectDomainConfigInput {
  targetDbEngine?: TargetDbEngine | null;
  stagingSchema?: string | null;
  destinationSchema?: string | null;
  dryRun?: boolean;
  samplePolicy?: SamplePolicy | null;
  destinationSchemaDdl?: string | null;
  environments?: string[] | null;
}
```

In `mapDomainConfig`, add the two new fields:

```ts
return {
  targetDbEngine: config.target_db_engine ?? null,
  stagingSchema: config.staging_schema ?? null,
  destinationSchema: config.destination_schema ?? null,
  dryRun: config.dry_run ?? false,
  samplePolicy: config.sample_policy
    ? {
        strategy: config.sample_policy.strategy as SamplePolicyStrategy,
        maxRows: config.sample_policy.max_rows ?? null,
        stratifiedColumn: config.sample_policy.stratified_column ?? null,
      }
    : null,
  destinationSchemaDdl: config.destination_schema_ddl ?? null,
  environments: config.environments ?? null,
};
```

In `serializeDomainConfig`, add the two new fields:

```ts
return {
  target_db_engine: config.targetDbEngine,
  staging_schema: config.stagingSchema,
  destination_schema: config.destinationSchema,
  dry_run: config.dryRun ?? false,
  sample_policy: config.samplePolicy
    ? {
        strategy: config.samplePolicy.strategy,
        max_rows: config.samplePolicy.maxRows,
        stratified_column: config.samplePolicy.stratifiedColumn,
      }
    : null,
  destination_schema_ddl: config.destinationSchemaDdl,
  environments: config.environments,
};
```

Also update the inline raw type annotation inside `mapDomainConfig` and `mapProjectRecord` to include `destination_schema` and the typed `sample_policy` shape.

- [ ] **Step 5: Re-run the test and confirm it passes**

Run: `cd engine && python -m pytest tests/test_project_crud_api.py::test_create_project_with_domain_config_extensions -v`
Expected: passes; `destination_schema` and `sample_policy` structure round-trip correctly.

- [ ] **Step 6: Inject destination_schema into codegen prompts**

In `engine/src/migrations_engine/codegen/service.py`, update both prompt builders to include `destination_schema`:

```python
def _build_system_prompt(*, project_config: MigrationProjectConfig, destination_object_name: str) -> str:
    return (
        "You generate SQL bundles for migration delivery.\n"
        f"Destination object: {destination_object_name}\n"
        f"Target DB engine: {project_config.target_db_engine or 'unknown'}\n"
        f"Staging schema: {project_config.staging_schema or 'unknown'}\n"
        f"Destination schema: {project_config.destination_schema or 'unknown'}"
    )


def _build_user_prompt(...) -> str:
    lines = [
        ...
        f"Target DB engine: {project_config.target_db_engine or 'unknown'}",
        f"Staging schema: {project_config.staging_schema or 'unknown'}",
        f"Destination schema: {project_config.destination_schema or 'unknown'}",
        "Field bindings:",
    ]
```

Write a focused test in `engine/tests/test_codegen_service.py` (or the existing codegen test file) verifying the prompts include both schema names:

```python
def test_system_prompt_includes_both_schemas():
    config = MigrationProjectConfig(
        target_db_engine="mssql",
        staging_schema="stg",
        destination_schema="dbo",
    )
    prompt = _build_system_prompt(project_config=config, destination_object_name="Customer")
    assert "Staging schema: stg" in prompt
    assert "Destination schema: dbo" in prompt
```

Run: `cd engine && python -m pytest tests/test_codegen_service.py -v`
Expected: new prompt tests pass; existing codegen tests unaffected.

- [ ] **Step 7: Inject both schema names into the fiber feed-analysis prompt**

In `engine/src/migrations_engine/management/fibers.py`, the feed analysis call currently passes only `destination_schema_ddl`. Lookups are always placed on `staging_schema`, so the AI needs both names to generate correct table references.

Read `fibers.py` around line 307 to find the `get("destination_schema_ddl", "")` read, then also extract `staging_schema` and `destination_schema` from `project_definition.domain_config` and pass them in the same payload:

```python
staging_schema = ""
destination_schema = ""
destination_schema_ddl = ""
if project_definition is not None and project_definition.domain_config:
    cfg = project_definition.domain_config
    destination_schema_ddl = str(cfg.get("destination_schema_ddl", ""))
    staging_schema = str(cfg.get("staging_schema", ""))
    destination_schema = str(cfg.get("destination_schema", ""))

# In the feed_analysis_adapter.call payload:
{
    "source_headers": source_headers,
    "destination_schema_ddl": destination_schema_ddl,
    "staging_schema": staging_schema,
    "destination_schema": destination_schema,
}
```

- [ ] **Step 8: Commit**

```bash
git add engine/src/migrations_engine/api/schemas.py \
        engine/src/migrations_engine/codegen/service.py \
        engine/src/migrations_engine/management/fibers.py \
        web/lib/projects-api.ts
git commit -m "feat(001aw): add destination_schema to domain config, codegen and fiber prompts"
```

---

### Task 1: Build the reusable edit form and edit route

**Files:**
- Create `web/components/projects/ProjectEditForm.tsx`
- Create `web/app/projects/[id]/edit/page.tsx`
- Create `web/components/projects/__tests__/ProjectEditForm.test.tsx`
- Create `web/app/projects/[id]/edit/page.test.tsx`

**Interfaces:**
- Consumes: `ProjectRecord`, `updateProject(token, id, body)`, `projectErrorMessage(error)`
- Produces: a prefilled edit form and a submit handler that returns the updated project record

- [ ] **Step 1: Write the failing tests**

```tsx
// web/components/projects/__tests__/ProjectEditForm.test.tsx
it("prefills and submits the project update payload", async () => {
  const onSubmit = vi.fn().mockResolvedValue(undefined);

  render(<ProjectEditForm project={project} onSubmit={onSubmit} />);

  expect(screen.getByDisplayValue("CRM Migration")).toBeInTheDocument();
  fireEvent.change(screen.getByLabelText("Project name"), { target: { value: "CRM Migration v2" } });
  fireEvent.submit(screen.getByRole("button", { name: "Save changes" }).closest("form") as HTMLFormElement);

  await waitFor(() =>
    expect(onSubmit).toHaveBeenCalledWith(
      expect.objectContaining({
        name: "CRM Migration v2",
        goal: "Migrate all CRM data",
        executionEnvironments: ["STG", "UAT", "PROD"],
        domainConfig: expect.objectContaining({
          stagingSchema: "stg",
          destinationSchema: "dbo",
          samplePolicy: expect.objectContaining({ strategy: "random" }),
        }),
      })
    ));
});
```

```tsx
// web/app/projects/[id]/edit/page.test.tsx
it("loads the project and saves updates", async () => {
  render(<ProjectEditPage params={Promise.resolve({ id: "proj-1" })} />);

  expect(await screen.findByDisplayValue("CRM Migration")).toBeInTheDocument();
  fireEvent.submit(screen.getByRole("button", { name: "Save changes" }).closest("form") as HTMLFormElement);

  await waitFor(() => expect(updateProjectMock).toHaveBeenCalledWith("tok-1", "proj-1", expect.any(Object)));
});
```

- [ ] **Step 2: Run the tests and confirm they fail for the expected reasons**

Run:

```bash
cd web && npm test -- components/projects/__tests__/ProjectEditForm.test.tsx app/projects/[id]/edit/page.test.tsx
```

Expected:

- There is no `ProjectEditForm` component yet.
- There is no `/projects/[id]/edit` page yet.

- [ ] **Step 3: Implement the reusable form and route**

```tsx
// web/components/projects/ProjectEditForm.tsx
export interface ProjectEditFormProps {
  project: ProjectRecord;
  loading?: boolean;
  errorMessage?: string;
  onSubmit: (value: ProjectUpdateInput) => Promise<void> | void;
}

export function ProjectEditForm({ project, loading = false, errorMessage, onSubmit }: ProjectEditFormProps) {
  // State: name, goal, executionEnvironments, targetDbEngine,
  //        stagingSchema, destinationSchema, dryRun, destinationSchemaDdl,
  //        sampleStrategy, sampleMaxRows, sampleStratifiedColumn
  // Prefill from project and call onSubmit with the API payload.
  // Sample policy section uses a visual divider heading before its fields.
}
```

The form must include a **"Sample Policy" section divider** before the strategy/max-rows/stratified-column fields:

```tsx
{/* Section divider */}
<div className="col-span-3 border-t border-outline-variant pt-4">
  <h3 className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">
    Sample Policy
  </h3>
  <p className="mt-1 text-xs text-slate-400">
    Controls how many source rows are included in the approved source slice for AI analysis.
  </p>
</div>

{/* Strategy picklist */}
<div className="space-y-2">
  <label className="block text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">
    Strategy
  </label>
  <select aria-label="Sample strategy" value={sampleStrategy} onChange={...}>
    <option value="">None</option>
    <option value="random">Random</option>
    <option value="top_n">Top N</option>
    <option value="full">Full</option>
    <option value="stratified">Stratified</option>
  </select>
</div>

{/* Max rows */}
<div className="space-y-2">
  <label className="block text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">
    Max rows
  </label>
  <input type="number" aria-label="Max rows" min={1} value={sampleMaxRows} onChange={...} />
</div>

{/* Stratified column — only when strategy === "stratified" */}
{sampleStrategy === "stratified" && (
  <div className="space-y-2">
    <label className="block text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">
      Stratified column
    </label>
    <input type="text" aria-label="Stratified column" value={sampleStratifiedColumn} onChange={...} />
  </div>
)}
```

Add a `lexiconScope` textarea after `assumptions` and before the Sample Policy section:

```tsx
<div className="col-span-3 space-y-2">
  <label className="block text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">
    Lexicon
  </label>
  <p className="text-xs text-slate-400">
    Domain vocabulary, business term definitions, and abbreviation expansions used by the AI during mapping.
  </p>
  <textarea
    aria-label="Lexicon"
    className="min-h-24 w-full rounded-md border border-outline-variant bg-white px-3 py-3 text-sm text-slate-900"
    name="lexiconScope"
    onChange={(event) => setLexiconScope(event.target.value)}
    value={lexiconScope}
  />
</div>
```

The submit payload constructs `samplePolicy` from the three fields:

```ts
domainConfig: {
  targetDbEngine: targetDbEngine || null,
  stagingSchema: normalizeOptionalText(stagingSchema),
  destinationSchema: normalizeOptionalText(destinationSchema),
  dryRun,
  samplePolicy: sampleStrategy
    ? {
        strategy: sampleStrategy as SamplePolicyStrategy,
        maxRows: sampleMaxRows ? parseInt(sampleMaxRows, 10) : null,
        stratifiedColumn: sampleStrategy === "stratified"
          ? normalizeOptionalText(sampleStratifiedColumn)
          : null,
      }
    : null,
  destinationSchemaDdl: normalizeOptionalText(destinationSchemaDdl),
  environments: project.domainConfig?.environments ?? null,
},
```

```tsx
// web/app/projects/[id]/edit/page.tsx
const session = useMemo(() => loadUiSession(), []);
const [project, setProject] = useState<ProjectRecord | null>(null);
const [errorMessage, setErrorMessage] = useState<string | null>(null);

useEffect(() => {
  if (!session) return;
  void getProject(session.accessToken, id).then(setProject).catch((error) => {
    setErrorMessage(projectErrorMessage(error));
  });
}, [id, session]);

const handleSubmit = async (value: ProjectUpdateInput) => {
  if (!session) return;
  setErrorMessage(null);
  try {
    const next = await updateProject(session.accessToken, id, value);
    router.push(`/projects/${next.projectId}`);
  } catch (error) {
    setErrorMessage(projectErrorMessage(error));
  }
};
```

Also update `ProjectDetailView` to show `destinationSchema` as a `KeyValue` alongside `stagingSchema`, and replace the `JSON.stringify(samplePolicy)` display with labelled readable values:

```tsx
<KeyValue label="Staging schema" value={domainConfig?.stagingSchema ?? "—"} />
<KeyValue label="Destination schema" value={domainConfig?.destinationSchema ?? "—"} />
...
<KeyValue
  label="Sample policy"
  value={
    domainConfig?.samplePolicy
      ? `${domainConfig.samplePolicy.strategy}${domainConfig.samplePolicy.maxRows ? ` · ${domainConfig.samplePolicy.maxRows} rows` : ""}${domainConfig.samplePolicy.stratifiedColumn ? ` · by ${domainConfig.samplePolicy.stratifiedColumn}` : ""}`
      : "—"
  }
/>
```

- [ ] **Step 4: Re-run the tests and confirm they pass**

Run:

```bash
cd web && npm test -- components/projects/__tests__/ProjectEditForm.test.tsx app/projects/[id]/edit/page.test.tsx
```

Expected:

- The edit form test passes with prefills and payload mapping.
- The edit page test passes with load, submit, and navigation behavior.

- [ ] **Step 5: Commit**

```bash
git add web/components/projects/ProjectEditForm.tsx web/app/projects/[id]/edit/page.tsx web/components/projects/__tests__/ProjectEditForm.test.tsx web/app/projects/[id]/edit/page.test.tsx
git commit -m "feat: add reusable project edit form and route"
```

### Task 2: Expose the edit entry point from project detail

**Files:**
- Modify `web/app/projects/[id]/page.tsx`
- Modify `web/app/projects/[id]/page.test.tsx`

**Interfaces:**
- Consumes: `session.role`, `useRouter`, the new edit route
- Produces: a visible Edit action in the project detail header for central-team users

- [ ] **Step 1: Write the failing tests**

```tsx
// web/app/projects/[id]/page.test.tsx
it("shows an edit button for central team users", async () => {
  await renderPage("proj-1");
  expect(await screen.findByRole("link", { name: "Edit" })).toHaveAttribute("href", "/projects/proj-1/edit");
});

it("hides edit for read-only auditors", async () => {
  loadUiSessionMock.mockReturnValue(AUDITOR_SESSION);
  await renderPage("proj-1");
  expect(screen.queryByRole("link", { name: "Edit" })).not.toBeInTheDocument();
});
```

- [ ] **Step 2: Run the tests and confirm they fail for the expected reasons**

Run:

```bash
cd web && npm test -- app/projects/[id]/page.test.tsx
```

Expected:

- The detail page does not yet render an Edit action.

- [ ] **Step 3: Implement the entry point**

```tsx
// web/app/projects/[id]/page.tsx
<div className="flex items-center justify-between">
  <button ...>Back to projects</button>
  {role === "central_team" ? (
    <Link
      className="rounded-md border border-outline-variant bg-surface-container px-3 py-2 text-sm font-medium text-slate-700 hover:bg-outline-variant"
      href={`/projects/${id}/edit`}
    >
      Edit
    </Link>
  ) : null}
</div>
```

- [ ] **Step 4: Re-run the tests and confirm they pass**

Run:

```bash
cd web && npm test -- app/projects/[id]/page.test.tsx
```

Expected:

- The detail page shows Edit for central team users.
- The link points to the edit route created in Task 1.

- [ ] **Step 5: Commit**

```bash
git add web/app/projects/[id]/page.tsx web/app/projects/[id]/page.test.tsx
git commit -m "feat: add project detail edit entry point"
```
