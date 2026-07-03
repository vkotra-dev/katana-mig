# Project Edit — Implementation Plan (001aw)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Task:** [`tasks/001aw-project-edit.md`](../tasks/001aw-project-edit.md)

**Goal:** Add an inline project edit form to the project detail overview tab, gated to `central_team`, covering all editable fields.

**Architecture:** Inline toggle on the overview tab — `page.tsx` gains `isEditing` + `saveError` state. When `isEditing` is true, `ProjectDetailView` is replaced by a new `ProjectEditForm` component. On save, `updateProject` patches the project and the component re-enters view mode with the refreshed data. All string arrays are edited as newline-separated textareas; JSON blobs as raw JSON textareas. No new route is added.

**Tech Stack:** Next.js App Router, React, TypeScript, Vitest + Testing Library

## Global Constraints

- Edit button is visible only when `role === "central_team"` — same inline pattern used everywhere in the codebase (`role === "central_team" ? ... : null`)
- Error display uses the `role="alert"` paragraph pattern already in `page.tsx` and `CreateProjectDialog`
- Form field styling matches `CreateProjectDialog`: `rounded-md border border-outline-variant bg-white px-3 py-3 text-sm` inputs; `text-xs font-semibold uppercase tracking-[0.16em] text-slate-500` labels
- `name` is the only required field (consistent with `CreateProjectDialog`)
- JSON blob fields (`repos`, `workspace`, `modelPolicy`, `lexiconScope`, `samplePolicy`) are edited as raw JSON text and silently parsed to `null` on invalid JSON
- Array fields (`executionEnvironments`, `constraints`, `unresolvedQuestions`, `assumptions`, `canonicalTerms`, `domainConfig.environments`) are edited as one-item-per-line textareas
- `KnowledgeFreezePanel` stays visible below the form/view in both modes

---

## File Changes

| Action | Path |
|--------|------|
| Create | `web/components/projects/ProjectEditForm.tsx` |
| Create | `web/components/projects/__tests__/ProjectEditForm.test.tsx` |
| Modify | `web/app/projects/[id]/page.tsx` |
| Modify | `web/app/projects/[id]/page.test.tsx` |

---

## Task 1: `ProjectEditForm` component

**Files:**
- Create: `web/components/projects/ProjectEditForm.tsx`
- Create: `web/components/projects/__tests__/ProjectEditForm.test.tsx`

**Interfaces:**
- Produces:
  ```ts
  export interface ProjectEditFormProps {
    project: ProjectRecord;
    onSubmit: (body: ProjectUpdateInput) => Promise<void>;
    onCancel: () => void;
    errorMessage?: string;
  }
  export function ProjectEditForm(props: ProjectEditFormProps): JSX.Element
  ```

- [ ] **Step 1: Write the failing tests**

Create `web/components/projects/__tests__/ProjectEditForm.test.tsx`:

```tsx
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ProjectEditForm } from "../ProjectEditForm";
import type { ProjectRecord, ProjectUpdateInput } from "../../../lib/projects-api";

const PROJECT: ProjectRecord = {
  projectId: "proj-1",
  name: "CRM Migration",
  goal: "Migrate CRM data",
  repos: null,
  workspace: null,
  environment: "PROD",
  executionEnvironments: ["STG", "UAT"],
  modelPolicy: null,
  canonicalTerms: null,
  constraints: ["GDPR", "Art 6"],
  unresolvedQuestions: ["PHI present?"],
  assumptions: ["Source is stable"],
  domainConfig: {
    targetDbEngine: "mssql",
    stagingSchema: "stg",
    dryRun: false,
    samplePolicy: null,
    destinationSchemaDdl: "create table t(id int);",
    environments: ["dev", "prod"],
  },
  lexiconScope: null,
  status: "active",
  createdAt: "2026-07-01T00:00:00Z",
  updatedAt: "2026-07-01T00:00:00Z",
  archivedAt: null,
  latestRunSummary: null,
};

describe("ProjectEditForm", () => {
  let onSubmit: ReturnType<typeof vi.fn>;
  let onCancel: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    onSubmit = vi.fn().mockResolvedValue(undefined);
    onCancel = vi.fn();
  });

  it("pre-fills the name and goal fields", () => {
    render(<ProjectEditForm errorMessage={undefined} onCancel={onCancel} onSubmit={onSubmit} project={PROJECT} />);
    expect(screen.getByDisplayValue("CRM Migration")).toBeInTheDocument();
    expect(screen.getByDisplayValue("Migrate CRM data")).toBeInTheDocument();
  });

  it("pre-fills array fields as newline-separated lines", () => {
    render(<ProjectEditForm errorMessage={undefined} onCancel={onCancel} onSubmit={onSubmit} project={PROJECT} />);
    expect(screen.getByDisplayValue("GDPR\nArt 6")).toBeInTheDocument();
    expect(screen.getByDisplayValue("STG\nUAT")).toBeInTheDocument();
  });

  it("pre-fills the target DB engine select", () => {
    render(<ProjectEditForm errorMessage={undefined} onCancel={onCancel} onSubmit={onSubmit} project={PROJECT} />);
    expect(screen.getByDisplayValue("mssql")).toBeInTheDocument();
  });

  it("calls onSubmit with the updated name when saved", async () => {
    render(<ProjectEditForm errorMessage={undefined} onCancel={onCancel} onSubmit={onSubmit} project={PROJECT} />);
    const nameInput = screen.getByDisplayValue("CRM Migration");
    fireEvent.change(nameInput, { target: { value: "New Name" } });
    fireEvent.submit(screen.getByRole("button", { name: /save/i }).closest("form") as HTMLFormElement);
    await waitFor(() => expect(onSubmit).toHaveBeenCalledOnce());
    const payload = onSubmit.mock.calls[0][0] as ProjectUpdateInput;
    expect(payload.name).toBe("New Name");
  });

  it("calls onSubmit with constraints as an array", async () => {
    render(<ProjectEditForm errorMessage={undefined} onCancel={onCancel} onSubmit={onSubmit} project={PROJECT} />);
    fireEvent.submit(screen.getByRole("button", { name: /save/i }).closest("form") as HTMLFormElement);
    await waitFor(() => expect(onSubmit).toHaveBeenCalledOnce());
    const payload = onSubmit.mock.calls[0][0] as ProjectUpdateInput;
    expect(payload.constraints).toEqual(["GDPR", "Art 6"]);
  });

  it("calls onCancel when cancel is clicked", () => {
    render(<ProjectEditForm errorMessage={undefined} onCancel={onCancel} onSubmit={onSubmit} project={PROJECT} />);
    fireEvent.click(screen.getByRole("button", { name: /cancel/i }));
    expect(onCancel).toHaveBeenCalledOnce();
  });

  it("renders error message when provided", () => {
    render(<ProjectEditForm errorMessage="Save failed" onCancel={onCancel} onSubmit={onSubmit} project={PROJECT} />);
    expect(screen.getByRole("alert")).toHaveTextContent("Save failed");
  });
});
```

- [ ] **Step 2: Run to verify tests fail**

```bash
cd /Users/vjkotra/projects/katana/web
npm test -- components/projects/__tests__/ProjectEditForm.test.tsx
```

Expected: FAIL — `ProjectEditForm` module not found.

- [ ] **Step 3: Create `ProjectEditForm.tsx`**

Create `web/components/projects/ProjectEditForm.tsx`:

```tsx
"use client";

import { useState } from "react";
import type { ProjectRecord, ProjectUpdateInput, TargetDbEngine } from "../../lib/projects-api";

export interface ProjectEditFormProps {
  project: ProjectRecord;
  onSubmit: (body: ProjectUpdateInput) => Promise<void>;
  onCancel: () => void;
  errorMessage?: string;
}

interface FormState {
  name: string;
  goal: string;
  environment: string;
  executionEnvironments: string;
  constraints: string;
  unresolvedQuestions: string;
  assumptions: string;
  canonicalTerms: string;
  targetDbEngine: TargetDbEngine | "";
  stagingSchema: string;
  dryRun: boolean;
  destinationSchemaDdl: string;
  samplePolicyJson: string;
  domainEnvironments: string;
  reposJson: string;
  workspaceJson: string;
  modelPolicyJson: string;
  lexiconScopeJson: string;
}

function toFormState(p: ProjectRecord): FormState {
  const dc = p.domainConfig;
  return {
    name: p.name,
    goal: p.goal ?? "",
    environment: p.environment ?? "",
    executionEnvironments: (p.executionEnvironments ?? []).join("\n"),
    constraints: (p.constraints ?? []).join("\n"),
    unresolvedQuestions: (p.unresolvedQuestions ?? []).join("\n"),
    assumptions: (p.assumptions ?? []).join("\n"),
    canonicalTerms: (p.canonicalTerms ?? []).join("\n"),
    targetDbEngine: dc?.targetDbEngine ?? "",
    stagingSchema: dc?.stagingSchema ?? "",
    dryRun: dc?.dryRun ?? false,
    destinationSchemaDdl: dc?.destinationSchemaDdl ?? "",
    samplePolicyJson: dc?.samplePolicy ? JSON.stringify(dc.samplePolicy, null, 2) : "",
    domainEnvironments: (dc?.environments ?? []).join("\n"),
    reposJson: p.repos ? JSON.stringify(p.repos, null, 2) : "",
    workspaceJson: p.workspace ? JSON.stringify(p.workspace, null, 2) : "",
    modelPolicyJson: p.modelPolicy ? JSON.stringify(p.modelPolicy, null, 2) : "",
    lexiconScopeJson: p.lexiconScope ? JSON.stringify(p.lexiconScope, null, 2) : "",
  };
}

function parseLines(s: string): string[] | null {
  const lines = s.split("\n").map((l) => l.trim()).filter(Boolean);
  return lines.length ? lines : null;
}

function parseJson(s: string): Record<string, unknown> | null {
  if (!s.trim()) return null;
  try { return JSON.parse(s) as Record<string, unknown>; } catch { return null; }
}

function toUpdateInput(f: FormState): ProjectUpdateInput {
  return {
    name: f.name.trim(),
    goal: f.goal.trim() || null,
    environment: f.environment.trim() || null,
    executionEnvironments: parseLines(f.executionEnvironments),
    constraints: parseLines(f.constraints),
    unresolvedQuestions: parseLines(f.unresolvedQuestions),
    assumptions: parseLines(f.assumptions),
    canonicalTerms: parseLines(f.canonicalTerms),
    repos: parseJson(f.reposJson) as Record<string, unknown>[] | null,
    workspace: parseJson(f.workspaceJson),
    modelPolicy: parseJson(f.modelPolicyJson),
    lexiconScope: parseJson(f.lexiconScopeJson),
    domainConfig: {
      targetDbEngine: f.targetDbEngine || null,
      stagingSchema: f.stagingSchema.trim() || null,
      dryRun: f.dryRun,
      destinationSchemaDdl: f.destinationSchemaDdl.trim() || null,
      samplePolicy: parseJson(f.samplePolicyJson),
      environments: parseLines(f.domainEnvironments),
    },
  };
}

const INPUT = "w-full rounded-md border border-outline-variant bg-white px-3 py-2 text-sm text-slate-900 outline-none placeholder:text-slate-400 focus:border-primary focus:ring-2 focus:ring-primary/20";
const LABEL = "text-xs font-semibold uppercase tracking-[0.16em] text-slate-500";

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="block space-y-1">
      <span className={LABEL}>{label}</span>
      {children}
    </label>
  );
}

export function ProjectEditForm({ project, onSubmit, onCancel, errorMessage }: ProjectEditFormProps) {
  const [form, setForm] = useState<FormState>(() => toFormState(project));
  const [submitting, setSubmitting] = useState(false);

  const set = (key: keyof FormState) => (
    e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>
  ) => setForm((prev) => ({ ...prev, [key]: e.target.value }));

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (submitting || !form.name.trim()) return;
    setSubmitting(true);
    try {
      await onSubmit(toUpdateInput(form));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <section className="space-y-6 rounded-2xl border border-outline-variant bg-surface-container p-6 shadow-sm">
      <h2 className="text-xl font-semibold text-slate-900">Edit project</h2>

      <form className="space-y-4" onSubmit={handleSubmit}>
        {/* Identity */}
        <Field label="Project name">
          <input aria-label="Project name" className={INPUT} onChange={set("name")} required value={form.name} />
        </Field>
        <Field label="Goal">
          <textarea aria-label="Goal" className={`${INPUT} min-h-20`} onChange={set("goal")} value={form.goal} />
        </Field>
        <Field label="Environment">
          <input aria-label="Environment" className={INPUT} onChange={set("environment")} value={form.environment} />
        </Field>
        <Field label="Execution environments (one per line)">
          <textarea aria-label="Execution environments" className={`${INPUT} min-h-20`} onChange={set("executionEnvironments")} value={form.executionEnvironments} />
        </Field>

        {/* Domain config */}
        <Field label="Target database engine">
          <select aria-label="Target database engine" className={INPUT} onChange={set("targetDbEngine")} value={form.targetDbEngine}>
            <option value="">— none —</option>
            <option value="mssql">mssql</option>
            <option value="oracle">oracle</option>
            <option value="postgresql">postgresql</option>
            <option value="mysql">mysql</option>
          </select>
        </Field>
        <Field label="Staging schema">
          <input aria-label="Staging schema" className={INPUT} onChange={set("stagingSchema")} value={form.stagingSchema} />
        </Field>
        <label className="flex items-center gap-2 text-sm text-slate-700">
          <input
            checked={form.dryRun}
            onChange={(e) => setForm((prev) => ({ ...prev, dryRun: e.target.checked }))}
            type="checkbox"
          />
          Dry run
        </label>
        <Field label="Destination schema DDL">
          <textarea aria-label="Destination schema DDL" className={`${INPUT} min-h-24 font-mono`} onChange={set("destinationSchemaDdl")} value={form.destinationSchemaDdl} />
        </Field>
        <Field label="Domain environments (one per line)">
          <textarea aria-label="Domain environments" className={`${INPUT} min-h-20`} onChange={set("domainEnvironments")} value={form.domainEnvironments} />
        </Field>
        <Field label="Sample policy (JSON)">
          <textarea aria-label="Sample policy" className={`${INPUT} min-h-20 font-mono`} onChange={set("samplePolicyJson")} value={form.samplePolicyJson} />
        </Field>

        {/* Arrays */}
        <Field label="Constraints (one per line)">
          <textarea aria-label="Constraints" className={`${INPUT} min-h-20`} onChange={set("constraints")} value={form.constraints} />
        </Field>
        <Field label="Unresolved questions (one per line)">
          <textarea aria-label="Unresolved questions" className={`${INPUT} min-h-20`} onChange={set("unresolvedQuestions")} value={form.unresolvedQuestions} />
        </Field>
        <Field label="Assumptions (one per line)">
          <textarea aria-label="Assumptions" className={`${INPUT} min-h-20`} onChange={set("assumptions")} value={form.assumptions} />
        </Field>
        <Field label="Canonical terms (one per line)">
          <textarea aria-label="Canonical terms" className={`${INPUT} min-h-20`} onChange={set("canonicalTerms")} value={form.canonicalTerms} />
        </Field>

        {/* JSON blobs */}
        <Field label="Repos (JSON array)">
          <textarea aria-label="Repos" className={`${INPUT} min-h-20 font-mono`} onChange={set("reposJson")} value={form.reposJson} />
        </Field>
        <Field label="Workspace (JSON)">
          <textarea aria-label="Workspace" className={`${INPUT} min-h-20 font-mono`} onChange={set("workspaceJson")} value={form.workspaceJson} />
        </Field>
        <Field label="Model policy (JSON)">
          <textarea aria-label="Model policy" className={`${INPUT} min-h-20 font-mono`} onChange={set("modelPolicyJson")} value={form.modelPolicyJson} />
        </Field>
        <Field label="Lexicon scope (JSON)">
          <textarea aria-label="Lexicon scope" className={`${INPUT} min-h-20 font-mono`} onChange={set("lexiconScopeJson")} value={form.lexiconScopeJson} />
        </Field>

        {errorMessage ? (
          <p className="rounded-md border border-error/30 bg-error/10 px-3 py-2 text-sm text-error" role="alert">
            {errorMessage}
          </p>
        ) : null}

        <div className="flex items-center justify-end gap-3 pt-2">
          <button
            className="rounded-md border border-outline-variant px-4 py-2 text-sm font-semibold text-slate-700 hover:bg-outline-variant"
            onClick={onCancel}
            type="button"
          >
            Cancel
          </button>
          <button
            className="rounded-md bg-primary px-4 py-2 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:opacity-60"
            disabled={!form.name.trim() || submitting}
            type="submit"
          >
            {submitting ? "Saving…" : "Save changes"}
          </button>
        </div>
      </form>
    </section>
  );
}
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd /Users/vjkotra/projects/katana/web
npm test -- components/projects/__tests__/ProjectEditForm.test.tsx
```

Expected: all 7 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add web/components/projects/ProjectEditForm.tsx web/components/projects/__tests__/ProjectEditForm.test.tsx
git commit -m "feat(001aw): add ProjectEditForm component"
```

---

## Task 2: Wire inline edit into the project detail page

**Files:**
- Modify: `web/app/projects/[id]/page.tsx`
- Modify: `web/app/projects/[id]/page.test.tsx`

**Interfaces:**
- Consumes: `ProjectEditForm` (Task 1), `updateProject` from `projects-api` (already exists)
- Produces: "Edit project" button visible when `role === "central_team"`; toggles to `ProjectEditForm`; save calls `updateProject` and returns to view mode

- [ ] **Step 1: Write the failing tests**

Add to `web/app/projects/[id]/page.test.tsx`:

Add `updateUserMock` → `updateProjectMock` to the `vi.hoisted` block and extend the `projects-api` mock:

```ts
const { loadUiSessionMock, getProjectMock, routerPushMock, updateProjectMock } = vi.hoisted(() => ({
  loadUiSessionMock: vi.fn(),
  getProjectMock: vi.fn(),
  routerPushMock: vi.fn(),
  updateProjectMock: vi.fn(),
}));
```

Update the `projects-api` mock to include `updateProject`:

```ts
vi.mock("../../../lib/projects-api", () => ({
  getProject: getProjectMock,
  updateProject: updateProjectMock,
  projectErrorMessage: (e: unknown) => (e instanceof Error ? e.message : "Error"),
}));
```

Add a mock for `ProjectEditForm` so page tests stay isolated from form internals:

```ts
const onSubmitCapture = vi.hoisted(() => ({ fn: null as null | ((body: unknown) => Promise<void>) }));

vi.mock("../../../components/projects/ProjectEditForm", () => ({
  ProjectEditForm: ({
    onSubmit,
    onCancel,
    errorMessage,
  }: {
    onSubmit: (body: unknown) => Promise<void>;
    onCancel: () => void;
    errorMessage?: string;
  }) => {
    onSubmitCapture.fn = onSubmit;
    return (
      <div>
        <span>Edit form</span>
        {errorMessage ? <span role="alert">{errorMessage}</span> : null}
        <button onClick={onCancel} type="button">Cancel edit</button>
        <button onClick={() => void onSubmit({ name: "Updated" })} type="button">Save edit</button>
      </div>
    );
  },
}));
```

Add a `CENTRAL_TEAM_SESSION` constant and a new `describe` block:

```ts
const CENTRAL_TEAM_SESSION = {
  accessToken: "tok-ct",
  expiresAt: "2027-01-01T00:00:00Z",
  role: "central_team" as const,
  sessionVersion: 1,
  userId: "user-ct",
};
```

```ts
describe("ProjectDetailPage — project edit", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    getProjectMock.mockResolvedValue(PROJECT);
    updateProjectMock.mockResolvedValue({ ...PROJECT, name: "Updated" });
  });

  it("shows Edit project button for central_team", async () => {
    loadUiSessionMock.mockReturnValue(CENTRAL_TEAM_SESSION);
    await renderPage("proj-1");
    expect(await screen.findByRole("button", { name: "Edit project" })).toBeInTheDocument();
  });

  it("does not show Edit project button for project_stakeholder", async () => {
    loadUiSessionMock.mockReturnValue(SESSION);
    await renderPage("proj-1");
    await screen.findByText("Overview content");
    expect(screen.queryByRole("button", { name: "Edit project" })).not.toBeInTheDocument();
  });

  it("shows the edit form when Edit project is clicked", async () => {
    loadUiSessionMock.mockReturnValue(CENTRAL_TEAM_SESSION);
    await renderPage("proj-1");
    fireEvent.click(await screen.findByRole("button", { name: "Edit project" }));
    expect(screen.getByText("Edit form")).toBeInTheDocument();
  });

  it("exits edit mode and refreshes project on successful save", async () => {
    loadUiSessionMock.mockReturnValue(CENTRAL_TEAM_SESSION);
    await renderPage("proj-1");
    fireEvent.click(await screen.findByRole("button", { name: "Edit project" }));
    fireEvent.click(screen.getByRole("button", { name: "Save edit" }));
    await waitFor(() => expect(updateProjectMock).toHaveBeenCalledWith("tok-ct", "proj-1", { name: "Updated" }));
    await waitFor(() => expect(screen.queryByText("Edit form")).not.toBeInTheDocument());
  });

  it("shows save error in edit form on API failure", async () => {
    loadUiSessionMock.mockReturnValue(CENTRAL_TEAM_SESSION);
    updateProjectMock.mockRejectedValue(new Error("server error"));
    await renderPage("proj-1");
    fireEvent.click(await screen.findByRole("button", { name: "Edit project" }));
    fireEvent.click(screen.getByRole("button", { name: "Save edit" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("server error");
    // form must stay open after failure
    expect(screen.getByText("Edit form")).toBeInTheDocument();
  });

  it("exits edit mode when Cancel is clicked", async () => {
    loadUiSessionMock.mockReturnValue(CENTRAL_TEAM_SESSION);
    await renderPage("proj-1");
    fireEvent.click(await screen.findByRole("button", { name: "Edit project" }));
    fireEvent.click(screen.getByRole("button", { name: "Cancel edit" }));
    await waitFor(() => expect(screen.queryByText("Edit form")).not.toBeInTheDocument());
  });
});
```

- [ ] **Step 2: Run to verify tests fail**

```bash
cd /Users/vjkotra/projects/katana/web
npm test -- app/projects/\\[id\\]/page.test.tsx
```

Expected: FAIL — "Edit project" button not found.

- [ ] **Step 3: Update `page.tsx`**

Add imports at the top of `web/app/projects/[id]/page.tsx`:

```ts
import { ProjectEditForm } from "../../../components/projects/ProjectEditForm";
import { getProject, projectErrorMessage, updateProject, type ProjectRecord, type ProjectUpdateInput } from "../../../lib/projects-api";
```

(Replace the existing `projects-api` import line.)

Add two new state variables alongside the existing state declarations:

```ts
  const [isEditing, setIsEditing] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
```

Add `handleProjectUpdate` before the `return`:

```ts
  const handleProjectUpdate = async (body: ProjectUpdateInput) => {
    if (!session) return;
    setSaveError(null);
    try {
      const updated = await updateProject(session.accessToken, id, body);
      setProject(updated);
      setIsEditing(false);
    } catch (error) {
      setSaveError(projectErrorMessage(error));
    }
  };
```

Replace the overview tab content (the `activeTab === "overview"` branch):

```tsx
          activeTab === "overview" ? (
            <div className="space-y-4">
              {isEditing ? (
                <ProjectEditForm
                  errorMessage={saveError ?? undefined}
                  onCancel={() => { setIsEditing(false); setSaveError(null); }}
                  onSubmit={handleProjectUpdate}
                  project={project}
                />
              ) : (
                <>
                  {role === "central_team" ? (
                    <div className="flex justify-end">
                      <button
                        className="rounded-md border border-outline-variant bg-surface-container px-3 py-2 text-sm font-medium text-slate-700 hover:bg-outline-variant"
                        onClick={() => setIsEditing(true)}
                        type="button"
                      >
                        Edit project
                      </button>
                    </div>
                  ) : null}
                  <ProjectDetailView project={project} />
                </>
              )}
              <KnowledgeFreezePanel projectId={id} token={session.accessToken} />
            </div>
          )
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd /Users/vjkotra/projects/katana/web
npm test -- app/projects/\\[id\\]/page.test.tsx
```

Expected: all tests PASS including the existing SQL Bundle tests and the new edit tests.

- [ ] **Step 5: Run the full web suite**

```bash
cd /Users/vjkotra/projects/katana/web
npm test
```

Expected: all tests PASS with no regressions.

- [ ] **Step 6: Commit**

```bash
git add web/app/projects/\[id\]/page.tsx web/app/projects/\[id\]/page.test.tsx
git commit -m "feat(001aw): wire inline project edit into detail overview tab"
```

---

## Verification

1. **Form unit tests:** `cd web && npm test -- components/projects/__tests__/ProjectEditForm.test.tsx`
   Expected: 7 tests pass

2. **Page integration tests:** `cd web && npm test -- app/projects/\\[id\\]/page.test.tsx`
   Expected: all pass (existing SQL Bundle tests unaffected)

3. **Full suite:** `cd web && npm test`
   Expected: no regressions

4. **Browser smoke-check:**
   - Log in as `central_team` → open any project → Overview tab → "Edit project" button visible
   - Click "Edit project" → form appears with all fields pre-filled
   - Edit name → Save → form closes, header reflects new name
   - Log in as `project_stakeholder` → no "Edit project" button visible

## Commit summary

```
feat(001aw): add ProjectEditForm component
feat(001aw): wire inline project edit into detail overview tab
```
