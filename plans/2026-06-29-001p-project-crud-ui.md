# Project CRUD — UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the project list page, create dialog, and project detail page in the Katana web app, wired to the project CRUD API endpoints from plan `001o`.

**Architecture:**
- Next.js 15 App Router (`web/app/`), React 19, Tailwind CSS v4 tokens
- API client functions in `web/lib/projects-api.ts` — thin fetch wrappers, no UI logic
- Presentational components under `web/components/projects/` — accept props, no direct fetch
- Page components in `web/app/projects/` assemble API calls + components
- Tests via Vitest + @testing-library/react with jsdom; fetch is mocked per test file

**Source references (mockmigration → Katana mapping):**
- `Portfolio.tsx` → `web/app/projects/page.tsx` + `ProjectTable.tsx`
- `ProjectWizard.tsx` (step 1 identity only: name + goal) → `CreateProjectDialog.tsx`
- `ProjectDetail.tsx` (Overview tab only) → `web/app/projects/[id]/page.tsx` + `ProjectDetailView.tsx`

**Role gating (replicated from API contract):**
- List and detail: any authenticated role; stakeholders see member projects only (API enforces)
- Create: `central_team` or `project_stakeholder` — hide the CTA for `read_only_auditor`
- Archive button: `central_team` only — hidden for other roles

**Explicitly out of scope for this plan:**
- Source intake, source contract declaration, source file upload — handled in plan `001q`
- Sources tab on project detail — handled in plan `001q`
- The project create dialog has **no source type field** — sources are attached to a project after it exists

**Tech Stack:** Next.js 15, React 19, TypeScript, Tailwind CSS v4, Vitest 3, @testing-library/react 16, jsdom.

## Global Constraints

- All files: `"use client"` directive where component uses state or event handlers
- All tokens from `globals.css` — no raw hex colours; use `var(--color-*)` or the CSS utility classes already defined
- Tailwind CSS v4 — use `@apply` in globals for shared patterns; prefer utility classes in JSX
- `fetch` base URL: `process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000"`
- Auth token: passed as a prop or from a session context; never stored in module scope
- No external component libraries (no shadcn, no radix direct install) — build from primitives
- Tests: mock `global.fetch` per test file; never rely on real network
- Test runner: `cd web && npm test` (runs `vitest run`)

---

## File Structure

| File | Action | Role |
|------|--------|------|
| `web/lib/projects-api.ts` | Create | API client: fetch wrappers + TypeScript types |
| `web/lib/projects-api.test.ts` | Create | Vitest unit tests for each API function |
| `web/components/projects/ProjectTable.tsx` | Create | Sortable project list table |
| `web/components/projects/CreateProjectDialog.tsx` | Create | Create project modal form |
| `web/components/projects/__tests__/ProjectTable.test.tsx` | Create | Rendering + CTA visibility tests |
| `web/components/projects/__tests__/CreateProjectDialog.test.tsx` | Create | Form validation + submit tests |
| `web/app/projects/page.tsx` | Create | List page — fetches projects, composes table + dialog |
| `web/app/projects/[id]/page.tsx` | Create | Detail page — fetches one project |
| `web/components/projects/ProjectDetailView.tsx` | Create | Key-value overview + status chips |
| `web/components/projects/__tests__/ProjectDetailView.test.tsx` | Create | Field rendering + archive chip tests |

---

### Task 1 — API client

**Files:**
- `web/lib/projects-api.ts` (create)
- `web/lib/projects-api.test.ts` (create)

**Produces:**
- `ProjectRecord` interface (mirrors `ProjectResponse` from `001o`)
- `listProjects(token, opts?)` → `Promise<ProjectRecord[]>`
- `getProject(token, id)` → `Promise<ProjectRecord>`
- `createProject(token, body)` → `Promise<ProjectRecord>`
- `archiveProject(token, id)` → `Promise<ProjectRecord>`

- [ ] **Step 1: Write failing tests**

Create `web/lib/projects-api.test.ts`:

```ts
import { describe, it, expect, vi, afterEach } from "vitest";
import {
  listProjects,
  getProject,
  createProject,
  archiveProject,
  type ProjectRecord,
} from "./projects-api";

const BASE = "http://127.0.0.1:8000";
const TOKEN = "test-token";

const stub: ProjectRecord = {
  project_id: "proj-1",
  name: "Alpha",
  goal: "Migrate CRM",
  repos: null,
  workspace: null,
  environment: null,
  execution_environments: ["STG", "PROD"],
  model_policy: null,
  canonical_terms: null,
  constraints: ["GDPR"],
  unresolved_questions: null,
  assumptions: null,
  domain_config: { target_db_engine: "mssql", staging_schema: "stg", dry_run: false, sample_policy: null },
  lexicon_scope: null,
  status: "active",
  created_at: "2026-06-29T00:00:00Z",
  updated_at: "2026-06-29T00:00:00Z",
  archived_at: null,
};

afterEach(() => vi.restoreAllMocks());

describe("listProjects", () => {
  it("calls GET /projects with auth header", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      ok: true, json: async () => [stub],
    }));
    const result = await listProjects(TOKEN);
    expect(fetch).toHaveBeenCalledWith(`${BASE}/projects`, expect.objectContaining({
      headers: expect.objectContaining({ Authorization: `Bearer ${TOKEN}` }),
    }));
    expect(result).toHaveLength(1);
    expect(result[0].name).toBe("Alpha");
  });

  it("passes include_archived query param when true", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      ok: true, json: async () => [],
    }));
    await listProjects(TOKEN, { includeArchived: true });
    expect(fetch).toHaveBeenCalledWith(
      `${BASE}/projects?include_archived=true`,
      expect.anything(),
    );
  });
});

describe("getProject", () => {
  it("calls GET /projects/{id}", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      ok: true, json: async () => stub,
    }));
    const result = await getProject(TOKEN, "proj-1");
    expect(fetch).toHaveBeenCalledWith(`${BASE}/projects/proj-1`, expect.anything());
    expect(result.project_id).toBe("proj-1");
  });

  it("throws on 404", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      ok: false, status: 404,
      json: async () => ({ error: { code: "project_not_found", message: "Not found" } }),
    }));
    await expect(getProject(TOKEN, "missing")).rejects.toThrow("project_not_found");
  });
});

describe("createProject", () => {
  it("posts to /projects and returns created record", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      ok: true, status: 201, json: async () => stub,
    }));
    const result = await createProject(TOKEN, { name: "Alpha" });
    expect(fetch).toHaveBeenCalledWith(`${BASE}/projects`, expect.objectContaining({
      method: "POST",
      body: JSON.stringify({ name: "Alpha" }),
    }));
    expect(result.name).toBe("Alpha");
  });
});

describe("archiveProject", () => {
  it("posts to /projects/{id}/archive", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      ok: true, json: async () => ({ ...stub, status: "archived", archived_at: "2026-06-29T01:00:00Z" }),
    }));
    const result = await archiveProject(TOKEN, "proj-1");
    expect(fetch).toHaveBeenCalledWith(
      `${BASE}/projects/proj-1/archive`,
      expect.objectContaining({ method: "POST" }),
    );
    expect(result.status).toBe("archived");
  });
});
```

- [ ] **Step 2: Run tests — confirm they fail**

```bash
cd web && npm test -- lib/projects-api.test.ts 2>&1 | tail -15
```

Expected: module not found.

- [ ] **Step 3: Create `web/lib/projects-api.ts`**

```ts
const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

export type TargetDbEngine = "mssql" | "oracle" | "postgresql" | "mysql";

export interface MigrationProjectConfig {
  target_db_engine: TargetDbEngine;
  staging_schema: string | null;
  dry_run: boolean;
  sample_policy: Record<string, unknown> | null;
}

export interface ProjectRecord {
  project_id: string;
  name: string;
  goal: string | null;
  repos: Record<string, unknown>[] | null;
  workspace: Record<string, unknown> | null;
  environment: string | null;
  execution_environments: string[] | null;
  model_policy: Record<string, unknown> | null;
  canonical_terms: string[] | null;
  constraints: string[] | null;
  unresolved_questions: string[] | null;
  assumptions: string[] | null;
  domain_config: MigrationProjectConfig | null;
  lexicon_scope: Record<string, unknown> | null;
  status: "active" | "archived";
  created_at: string;
  updated_at: string;
  archived_at: string | null;
}

export interface ProjectCreateInput {
  name: string;
  goal?: string | null;
  domain_config?: MigrationProjectConfig | null;
  execution_environments?: string[] | null;
  constraints?: string[] | null;
  lexicon_scope?: Record<string, unknown> | null;
}

function authHeaders(token: string): Record<string, string> {
  return {
    Authorization: `Bearer ${token}`,
    "Content-Type": "application/json",
  };
}

async function handleResponse<T>(res: Response): Promise<T> {
  if (res.ok) return res.json() as Promise<T>;
  let code = "api_error";
  try {
    const body = await res.json();
    code = body?.error?.code ?? code;
  } catch { /* ignore parse failure */ }
  throw new Error(code);
}

export async function listProjects(
  token: string,
  opts?: { includeArchived?: boolean },
): Promise<ProjectRecord[]> {
  const params = opts?.includeArchived ? "?include_archived=true" : "";
  const res = await fetch(`${BASE}/projects${params}`, { headers: authHeaders(token) });
  return handleResponse<ProjectRecord[]>(res);
}

export async function getProject(token: string, id: string): Promise<ProjectRecord> {
  const res = await fetch(`${BASE}/projects/${id}`, { headers: authHeaders(token) });
  return handleResponse<ProjectRecord>(res);
}

export async function createProject(
  token: string,
  body: ProjectCreateInput,
): Promise<ProjectRecord> {
  const res = await fetch(`${BASE}/projects`, {
    method: "POST",
    headers: authHeaders(token),
    body: JSON.stringify(body),
  });
  return handleResponse<ProjectRecord>(res);
}

export async function archiveProject(token: string, id: string): Promise<ProjectRecord> {
  const res = await fetch(`${BASE}/projects/${id}/archive`, {
    method: "POST",
    headers: authHeaders(token),
  });
  return handleResponse<ProjectRecord>(res);
}
```

- [ ] **Step 4: Run tests — confirm they pass**

```bash
cd web && npm test -- lib/projects-api.test.ts
```

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add web/lib/projects-api.ts web/lib/projects-api.test.ts
git commit -m "feat: add projects API client with tests"
```

---

### Task 2 — ProjectTable component

**Files:**
- `web/components/projects/ProjectTable.tsx` (create)
- `web/components/projects/__tests__/ProjectTable.test.tsx` (create)

**Produces:** `<ProjectTable projects role onInitiate? />` — renders project rows; shows "Initiate Project" button only when `role !== "read_only_auditor"`.

- [ ] **Step 1: Create `web/components/projects/` directory**

```bash
mkdir -p web/components/projects/__tests__
```

- [ ] **Step 2: Write failing tests**

Create `web/components/projects/__tests__/ProjectTable.test.tsx`:

```tsx
import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { ProjectTable } from "../ProjectTable";
import type { ProjectRecord } from "../../../lib/projects-api";

const activeProject: ProjectRecord = {
  project_id: "p1",
  name: "Alpha Migration",
  goal: "Migrate CRM",
  repos: null, workspace: null, environment: null,
  execution_environments: ["STG", "PROD"],
  model_policy: null, canonical_terms: null,
  constraints: ["GDPR"], unresolved_questions: null, assumptions: null,
  domain_config: { target_db_engine: "mssql", staging_schema: "stg", dry_run: false, sample_policy: null },
  lexicon_scope: null,
  status: "active",
  created_at: "2026-06-29T00:00:00Z",
  updated_at: "2026-06-29T00:00:00Z",
  archived_at: null,
};

const archivedProject: ProjectRecord = {
  ...activeProject,
  project_id: "p2",
  name: "Beta Migration",
  status: "archived",
  archived_at: "2026-06-29T12:00:00Z",
};

describe("ProjectTable", () => {
  it("renders project name and ID", () => {
    render(<ProjectTable projects={[activeProject]} role="central_team" />);
    expect(screen.getByText("Alpha Migration")).toBeInTheDocument();
    expect(screen.getByText(/p1/)).toBeInTheDocument();
  });

  it("shows archived chip for archived projects", () => {
    render(<ProjectTable projects={[archivedProject]} role="central_team" />);
    expect(screen.getByText(/archived/i)).toBeInTheDocument();
  });

  it("shows Initiate Project button for central_team", () => {
    render(<ProjectTable projects={[]} role="central_team" onInitiate={vi.fn()} />);
    expect(screen.getByRole("button", { name: /initiate project/i })).toBeInTheDocument();
  });

  it("shows Initiate Project button for project_stakeholder", () => {
    render(<ProjectTable projects={[]} role="project_stakeholder" onInitiate={vi.fn()} />);
    expect(screen.getByRole("button", { name: /initiate project/i })).toBeInTheDocument();
  });

  it("hides Initiate Project button for read_only_auditor", () => {
    render(<ProjectTable projects={[]} role="read_only_auditor" onInitiate={vi.fn()} />);
    expect(screen.queryByRole("button", { name: /initiate project/i })).not.toBeInTheDocument();
  });

  it("calls onInitiate when button clicked", () => {
    const onInitiate = vi.fn();
    render(<ProjectTable projects={[]} role="central_team" onInitiate={onInitiate} />);
    fireEvent.click(screen.getByRole("button", { name: /initiate project/i }));
    expect(onInitiate).toHaveBeenCalledOnce();
  });

  it("renders constraint and env_pipeline details", () => {
    render(<ProjectTable projects={[activeProject]} role="central_team" />);
    expect(screen.getByText(/GDPR/)).toBeInTheDocument();
    expect(screen.getByText(/PROD/)).toBeInTheDocument();
  });

  it("renders empty state when no projects", () => {
    render(<ProjectTable projects={[]} role="central_team" />);
    expect(screen.getByText(/no projects/i)).toBeInTheDocument();
  });
});
```

- [ ] **Step 3: Run tests — confirm they fail**

```bash
cd web && npm test -- components/projects/__tests__/ProjectTable.test.tsx 2>&1 | tail -15
```

Expected: module not found.

- [ ] **Step 4: Create `web/components/projects/ProjectTable.tsx`**

```tsx
"use client";

import type { ProjectRecord } from "../../lib/projects-api";
import type { SessionRole } from "../../lib/session";

export interface ProjectTableProps {
  projects: ProjectRecord[];
  role: SessionRole;
  onInitiate?: () => void;
}

export function ProjectTable({ projects, role, onInitiate }: ProjectTableProps) {
  const canCreate = role !== "read_only_auditor";

  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center justify-between">
        <h2 className="text-title-md font-semibold text-slate-800">Projects</h2>
        {canCreate && onInitiate && (
          <button
            type="button"
            onClick={onInitiate}
            className="btn-primary"
          >
            Initiate Project
          </button>
        )}
      </div>

      {projects.length === 0 ? (
        <p className="py-8 text-center text-sm text-neutral">No projects found.</p>
      ) : (
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-outline-variant text-left text-xs font-medium text-neutral">
              <th className="pb-2 pr-4">Name</th>
              <th className="pb-2 pr-4">ID</th>
              <th className="pb-2 pr-4">Environments</th>
              <th className="pb-2 pr-4">Constraints</th>
              <th className="pb-2">Status</th>
            </tr>
          </thead>
          <tbody>
            {projects.map((p) => (
              <tr
                key={p.project_id}
                className="border-b border-outline-variant last:border-0"
              >
                <td className="py-3 pr-4 font-medium text-slate-800">
                  <a href={`/projects/${p.project_id}`} className="hover:underline">
                    {p.name}
                  </a>
                </td>
                <td className="py-3 pr-4">
                  <span className="mono-id text-xs">{p.project_id.slice(0, 8)}</span>
                </td>
                <td className="py-3 pr-4 text-neutral">
                  {p.execution_environments?.join(", ") ?? "—"}
                </td>
                <td className="py-3 pr-4 text-neutral">
                  {p.constraints?.join(", ") ?? "—"}
                </td>
                <td className="py-3">
                  {p.status === "archived" ? (
                    <span className="rounded bg-surface-dim px-2 py-0.5 text-xs font-medium text-neutral">
                      archived
                    </span>
                  ) : (
                    <span className="rounded bg-primary-container px-2 py-0.5 text-xs font-medium text-on-primary-container">
                      active
                    </span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
```

- [ ] **Step 5: Run tests — confirm they pass**

```bash
cd web && npm test -- components/projects/__tests__/ProjectTable.test.tsx
```

Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add web/components/projects/ProjectTable.tsx \
        web/components/projects/__tests__/ProjectTable.test.tsx
git commit -m "feat: add ProjectTable component with role-gated CTA"
```

---

### Task 3 — CreateProjectDialog component

**Files:**
- `web/components/projects/CreateProjectDialog.tsx` (create)
- `web/components/projects/__tests__/CreateProjectDialog.test.tsx` (create)

**Produces:** `<CreateProjectDialog open token onCreated onClose />` — modal with name (required) + goal + target database engine (required); submits via `createProject` with `domain_config`; closes and calls `onCreated` on success.

- [ ] **Step 1: Write failing tests**

Create `web/components/projects/__tests__/CreateProjectDialog.test.tsx`:

```tsx
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, afterEach } from "vitest";
import { CreateProjectDialog } from "../CreateProjectDialog";
import type { ProjectRecord } from "../../../lib/projects-api";

const stub: ProjectRecord = {
  project_id: "new-proj",
  name: "New Project",
  goal: "Migrate orders",
  repos: null, workspace: null, environment: null,
  execution_environments: null, model_policy: null, canonical_terms: null,
  constraints: null, unresolved_questions: null, assumptions: null,
  domain_config: null,
  lexicon_scope: null,
  status: "active",
  created_at: "2026-06-29T00:00:00Z",
  updated_at: "2026-06-29T00:00:00Z",
  archived_at: null,
};

afterEach(() => vi.restoreAllMocks());

describe("CreateProjectDialog", () => {
  it("does not render when open=false", () => {
    render(<CreateProjectDialog open={false} token="t" onCreated={vi.fn()} onClose={vi.fn()} />);
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("renders name, goal, and target database engine fields", () => {
    render(<CreateProjectDialog open token="t" onCreated={vi.fn()} onClose={vi.fn()} />);
    expect(screen.getByRole("dialog")).toBeInTheDocument();
    expect(screen.getByLabelText(/project name/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/goal/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/target database engine/i)).toBeInTheDocument();
    expect(screen.queryByLabelText(/source type/i)).not.toBeInTheDocument();
  });

  it("disables submit when name is empty", () => {
    render(<CreateProjectDialog open token="t" onCreated={vi.fn()} onClose={vi.fn()} />);
    expect(screen.getByRole("button", { name: /create/i })).toBeDisabled();
  });

  it("disables submit when name is filled but engine not selected", () => {
    render(<CreateProjectDialog open token="t" onCreated={vi.fn()} onClose={vi.fn()} />);
    fireEvent.change(screen.getByLabelText(/project name/i), { target: { value: "My Project" } });
    expect(screen.getByRole("button", { name: /create/i })).toBeDisabled();
  });

  it("enables submit when name and engine are both filled", () => {
    render(<CreateProjectDialog open token="t" onCreated={vi.fn()} onClose={vi.fn()} />);
    fireEvent.change(screen.getByLabelText(/project name/i), { target: { value: "My Project" } });
    fireEvent.change(screen.getByLabelText(/target database engine/i), { target: { value: "mssql" } });
    expect(screen.getByRole("button", { name: /create/i })).not.toBeDisabled();
  });

  it("submits name, goal, and domain_config with engine; no source fields in payload", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      ok: true, status: 201, json: async () => stub,
    }));
    const onCreated = vi.fn();
    render(<CreateProjectDialog open token="test-token" onCreated={onCreated} onClose={vi.fn()} />);

    fireEvent.change(screen.getByLabelText(/project name/i), { target: { value: "New Project" } });
    fireEvent.change(screen.getByLabelText(/goal/i), { target: { value: "Migrate orders" } });
    fireEvent.change(screen.getByLabelText(/target database engine/i), { target: { value: "mssql" } });
    fireEvent.click(screen.getByRole("button", { name: /create/i }));

    await waitFor(() => expect(onCreated).toHaveBeenCalledWith(stub));
    const body = JSON.parse((fetch as ReturnType<typeof vi.fn>).mock.calls[0][1].body);
    expect(body.name).toBe("New Project");
    expect(body.goal).toBe("Migrate orders");
    expect(body.domain_config.target_db_engine).toBe("mssql");
    expect(body).not.toHaveProperty("source_type");
  });

  it("shows error message on API failure", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      ok: false, status: 403,
      json: async () => ({ error: { code: "forbidden", message: "Forbidden" } }),
    }));
    render(<CreateProjectDialog open token="t" onCreated={vi.fn()} onClose={vi.fn()} />);
    fireEvent.change(screen.getByLabelText(/project name/i), { target: { value: "X" } });
    fireEvent.click(screen.getByRole("button", { name: /create/i }));
    await waitFor(() => expect(screen.getByRole("alert")).toBeInTheDocument());
  });

  it("calls onClose when Cancel is clicked", () => {
    const onClose = vi.fn();
    render(<CreateProjectDialog open token="t" onCreated={vi.fn()} onClose={onClose} />);
    fireEvent.click(screen.getByRole("button", { name: /cancel/i }));
    expect(onClose).toHaveBeenCalledOnce();
  });
});
```

- [ ] **Step 2: Run tests — confirm they fail**

```bash
cd web && npm test -- components/projects/__tests__/CreateProjectDialog.test.tsx 2>&1 | tail -15
```

Expected: module not found.

- [ ] **Step 3: Create `web/components/projects/CreateProjectDialog.tsx`**

Sources are NOT part of project creation. This dialog captures identity only: name and goal.
Source contracts are added separately via the Sources tab after the project exists (plan `001q`).

```tsx
"use client";

import { useState } from "react";
import { createProject, type ProjectRecord } from "../../lib/projects-api";

export interface CreateProjectDialogProps {
  open?: boolean;
  token: string;
  onCreated: (project: ProjectRecord) => void;
  onClose: () => void;
}

export function CreateProjectDialog({
  open,
  token,
  onCreated,
  onClose,
}: CreateProjectDialogProps) {
  const [name, setName] = useState("");
  const [goal, setGoal] = useState("");
  const [targetDbEngine, setTargetDbEngine] = useState<TargetDbEngine | "">("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!open) return null;

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!targetDbEngine) return;
    setSubmitting(true);
    setError(null);
    try {
      const project = await createProject(token, {
        name,
        goal: goal || null,
        domain_config: { target_db_engine: targetDbEngine, staging_schema: null, dry_run: false, sample_policy: null },
      });
      setName("");
      setGoal("");
      onCreated(project);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unexpected error");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label="Create Project"
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/30"
    >
      <div className="w-full max-w-md rounded-xl border border-outline-variant bg-surface-container p-6 shadow-lg">
        <h2 className="mb-4 text-title-md font-semibold text-slate-800">Create Project</h2>

        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          <div className="flex flex-col gap-1">
            <label htmlFor="project-name" className="text-sm font-medium text-slate-700">
              Project Name <span aria-hidden>*</span>
            </label>
            <input
              id="project-name"
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. CRM Migration Q3"
              className="input-field"
              aria-label="Project Name"
              required
            />
          </div>

          <div className="flex flex-col gap-1">
            <label htmlFor="project-goal" className="text-sm font-medium text-slate-700">
              Goal
            </label>
            <textarea
              id="project-goal"
              value={goal}
              onChange={(e) => setGoal(e.target.value)}
              placeholder="Describe the migration objective"
              rows={3}
              className="input-field resize-none"
              aria-label="Goal"
            />
          </div>

          <div className="flex flex-col gap-1">
            <label htmlFor="target-db-engine" className="text-sm font-medium text-slate-700">
              Target Database <span aria-hidden>*</span>
            </label>
            <select
              id="target-db-engine"
              value={targetDbEngine}
              onChange={(e) => setTargetDbEngine(e.target.value as TargetDbEngine | "")}
              className="input-field"
              aria-label="Target Database Engine"
              required
            >
              <option value="">— Select engine —</option>
              <option value="mssql">SQL Server (T-SQL)</option>
              <option value="oracle">Oracle (PL/SQL)</option>
              <option value="postgresql">PostgreSQL</option>
              <option value="mysql">MySQL</option>
            </select>
          </div>

          {error && (
            <p role="alert" className="rounded bg-error/10 px-3 py-2 text-sm text-error">
              {error}
            </p>
          )}

          <div className="flex justify-end gap-3 pt-2">
            <button type="button" onClick={onClose} className="btn-ghost">
              Cancel
            </button>
            <button
              type="submit"
              disabled={!name.trim() || !targetDbEngine || submitting}
              className="btn-primary disabled:opacity-40"
            >
              {submitting ? "Creating…" : "Create Project"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Run tests — confirm they pass**

```bash
cd web && npm test -- components/projects/__tests__/CreateProjectDialog.test.tsx
```

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add web/components/projects/CreateProjectDialog.tsx \
        web/components/projects/__tests__/CreateProjectDialog.test.tsx
git commit -m "feat: add CreateProjectDialog component with form validation and submit"
```

---

### Task 4 — Project list page

**Files:**
- `web/app/projects/page.tsx` (create)

**Produces:** `ProjectsPage` — client component that fetches the project list, renders `ProjectTable`, and shows/hides `CreateProjectDialog`.

No additional component tests here — the page assembles already-tested components. Its own test would be an integration test (full page render with mocked fetch), which lives in a future E2E task.

- [ ] **Step 1: Create `web/app/projects/` directory**

```bash
mkdir -p web/app/projects
```

- [ ] **Step 2: Create `web/app/projects/page.tsx`**

```tsx
"use client";

import { useEffect, useState } from "react";
import { ProjectTable } from "../../components/projects/ProjectTable";
import { CreateProjectDialog } from "../../components/projects/CreateProjectDialog";
import { Topbar } from "../../components/Topbar";
import { listProjects, type ProjectRecord } from "../../lib/projects-api";
import { getUiSession } from "../../lib/session";
import type { SessionRole } from "../../lib/session";

export default function ProjectsPage() {
  const session = getUiSession();
  const role: SessionRole = session?.role ?? "read_only_auditor";
  const token = "";

  const [projects, setProjects] = useState<ProjectRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [dialogOpen, setDialogOpen] = useState(false);

  useEffect(() => {
    listProjects(token)
      .then(setProjects)
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load"))
      .finally(() => setLoading(false));
  }, [token]);

  function handleCreated(project: ProjectRecord) {
    setProjects((prev) => [project, ...prev]);
    setDialogOpen(false);
  }

  return (
    <main className="flex min-h-screen flex-col bg-surface text-slate-800">
      <Topbar role={role} />
      <section className="mx-auto flex w-full max-w-[1600px] flex-1 flex-col gap-4 px-6 py-4">
        {loading && (
          <p className="py-8 text-center text-sm text-neutral">Loading projects…</p>
        )}
        {error && (
          <p role="alert" className="rounded bg-error/10 px-4 py-2 text-sm text-error">
            {error}
          </p>
        )}
        {!loading && !error && (
          <ProjectTable
            projects={projects}
            role={role}
            onInitiate={() => setDialogOpen(true)}
          />
        )}
      </section>

      <CreateProjectDialog
        open={dialogOpen}
        token={token}
        onCreated={handleCreated}
        onClose={() => setDialogOpen(false)}
      />
    </main>
  );
}
```

- [ ] **Step 3: Verify Next.js build accepts the file**

```bash
cd web && npx next build 2>&1 | tail -20
```

Expected: build succeeds (or type errors only — no module-not-found errors).

- [ ] **Step 4: Commit**

```bash
git add web/app/projects/page.tsx
git commit -m "feat: add project list page"
```

---

### Task 5 — Project detail page

**Files:**
- `web/components/projects/ProjectDetailView.tsx` (create)
- `web/components/projects/__tests__/ProjectDetailView.test.tsx` (create)
- `web/app/projects/[id]/page.tsx` (create)

**Produces:** `<ProjectDetailView project />` — renders name, status chip, key-value grid (goal, environments, constraints, source type from `domain_config`); `ProjectDetailPage` — fetches project by ID and renders the view.

- [ ] **Step 1: Write failing tests**

Create `web/components/projects/__tests__/ProjectDetailView.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { ProjectDetailView } from "../ProjectDetailView";
import type { ProjectRecord } from "../../../lib/projects-api";

const active: ProjectRecord = {
  project_id: "proj-abc",
  name: "CRM Migration",
  goal: "Migrate all CRM data to new schema",
  repos: null, workspace: null, environment: "PROD",
  execution_environments: ["STG", "UAT", "PROD"],
  model_policy: null, canonical_terms: null,
  constraints: ["GDPR", "Art 6(1)(c)"],
  unresolved_questions: ["PHI present?"],
  assumptions: ["Source replica is stable"],
  domain_config: { target_db_engine: "mssql", staging_schema: "stg", dry_run: false, sample_policy: null },
  lexicon_scope: null,
  status: "active",
  created_at: "2026-06-29T00:00:00Z",
  updated_at: "2026-06-29T01:00:00Z",
  archived_at: null,
};

const archived: ProjectRecord = {
  ...active,
  status: "archived",
  archived_at: "2026-06-29T12:00:00Z",
};

describe("ProjectDetailView", () => {
  it("renders project name", () => {
    render(<ProjectDetailView project={active} />);
    expect(screen.getByRole("heading", { name: /CRM Migration/i })).toBeInTheDocument();
  });

  it("shows active status chip for active project", () => {
    render(<ProjectDetailView project={active} />);
    expect(screen.getByText(/active/i)).toBeInTheDocument();
  });

  it("shows archived status chip for archived project", () => {
    render(<ProjectDetailView project={archived} />);
    expect(screen.getByText(/archived/i)).toBeInTheDocument();
  });

  it("renders goal", () => {
    render(<ProjectDetailView project={active} />);
    expect(screen.getByText("Migrate all CRM data to new schema")).toBeInTheDocument();
  });

  it("renders execution environments", () => {
    render(<ProjectDetailView project={active} />);
    expect(screen.getByText(/STG.*UAT.*PROD/i)).toBeInTheDocument();
  });

  it("renders constraints", () => {
    render(<ProjectDetailView project={active} />);
    expect(screen.getByText(/GDPR/i)).toBeInTheDocument();
  });

  it("renders target_db_engine from domain_config", () => {
    render(<ProjectDetailView project={active} />);
    expect(screen.getByText(/database/i)).toBeInTheDocument();
  });

  it("renders project ID chip", () => {
    render(<ProjectDetailView project={active} />);
    expect(screen.getByText(/proj-abc/i)).toBeInTheDocument();
  });

  it("shows archived date when archived", () => {
    render(<ProjectDetailView project={archived} />);
    expect(screen.getByText(/2026-06-29/)).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run tests — confirm they fail**

```bash
cd web && npm test -- components/projects/__tests__/ProjectDetailView.test.tsx 2>&1 | tail -15
```

Expected: module not found.

- [ ] **Step 3: Create `web/components/projects/ProjectDetailView.tsx`**

```tsx
"use client";

import type { ProjectRecord } from "../../lib/projects-api";

export interface ProjectDetailViewProps {
  project: ProjectRecord;
}

function KV({ label, value }: { label: string; value: string | null | undefined }) {
  return (
    <div className="flex flex-col gap-0.5">
      <dt className="text-xs font-medium uppercase tracking-wide text-neutral">{label}</dt>
      <dd className="text-sm text-slate-800">{value ?? "—"}</dd>
    </div>
  );
}

export function ProjectDetailView({ project }: ProjectDetailViewProps) {
  const sourceType =
    project.domain_config?.target_db_engine ?? null;

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-2">
        <div className="flex flex-wrap items-center gap-3">
          <h1 className="text-headline-sm font-bold text-slate-800">{project.name}</h1>
          <span className="mono-id text-xs">{project.project_id}</span>
          {project.status === "archived" ? (
            <span className="rounded bg-surface-dim px-2 py-0.5 text-xs font-medium text-neutral">
              archived
            </span>
          ) : (
            <span className="rounded bg-primary-container px-2 py-0.5 text-xs font-medium text-on-primary-container">
              active
            </span>
          )}
        </div>
        {project.archived_at && (
          <p className="text-xs text-neutral">
            Archived {new Date(project.archived_at).toLocaleDateString()}
          </p>
        )}
      </div>

      <dl className="grid grid-cols-2 gap-x-8 gap-y-4 sm:grid-cols-3">
        <KV label="Goal" value={project.goal} />
        <KV
          label="Environments"
          value={project.execution_environments?.join(" → ") ?? null}
        />
        <KV label="Source Type" value={sourceType} />
        <KV
          label="Constraints"
          value={project.constraints?.join(", ") ?? null}
        />
        <KV
          label="Unresolved Questions"
          value={project.unresolved_questions?.join("; ") ?? null}
        />
        <KV
          label="Assumptions"
          value={project.assumptions?.join("; ") ?? null}
        />
        <KV label="Created" value={new Date(project.created_at).toLocaleDateString()} />
        <KV label="Updated" value={new Date(project.updated_at).toLocaleDateString()} />
      </dl>
    </div>
  );
}
```

- [ ] **Step 4: Run tests — confirm they pass**

```bash
cd web && npm test -- components/projects/__tests__/ProjectDetailView.test.tsx
```

Expected: all pass.

- [ ] **Step 5: Create `web/app/projects/[id]/page.tsx`**

```bash
mkdir -p web/app/projects/[id]
```

```tsx
"use client";

import { useEffect, useState } from "react";
import { use } from "react";
import { ProjectDetailView } from "../../../components/projects/ProjectDetailView";
import { Topbar } from "../../../components/Topbar";
import { getProject, type ProjectRecord } from "../../../lib/projects-api";
import { getUiSession } from "../../../lib/session";
import type { SessionRole } from "../../../lib/session";

export default function ProjectDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const session = getUiSession();
  const role: SessionRole = session?.role ?? "read_only_auditor";
  const token = "";

  const [project, setProject] = useState<ProjectRecord | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getProject(token, id)
      .then(setProject)
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load"))
      .finally(() => setLoading(false));
  }, [token, id]);

  return (
    <main className="flex min-h-screen flex-col bg-surface text-slate-800">
      <Topbar role={role} />
      <section className="mx-auto flex w-full max-w-[1600px] flex-1 flex-col gap-4 px-6 py-4">
        {loading && (
          <p className="py-8 text-center text-sm text-neutral">Loading…</p>
        )}
        {error && (
          <p role="alert" className="rounded bg-error/10 px-4 py-2 text-sm text-error">
            {error === "project_not_found" ? "Project not found." : error}
          </p>
        )}
        {project && <ProjectDetailView project={project} />}
      </section>
    </main>
  );
}
```

- [ ] **Step 6: Run full web test suite**

```bash
cd web && npm test
```

Expected: all pass.

- [ ] **Step 7: Commit**

```bash
git add web/components/projects/ProjectDetailView.tsx \
        web/components/projects/__tests__/ProjectDetailView.test.tsx \
        web/app/projects/[id]/page.tsx
git commit -m "feat: add ProjectDetailView component and detail page"
```

---

## Self-Review

**Task granularity:**
- Task 1 (API client): red → green → commit on fetch wrappers ✓
- Task 2 (ProjectTable): red → green → commit on table + CTA gating ✓
- Task 3 (CreateProjectDialog): red → green → commit on form + submit ✓
- Task 4 (list page): build verification only — composes tested pieces ✓
- Task 5 (detail view + page): red → green → commit on detail view; page verified by build ✓

**Coverage:**
- `listProjects`, `getProject`, `createProject`, `archiveProject` tested with mocked fetch ✓
- Role-gated CTA: hidden for `read_only_auditor`, visible for other roles ✓
- Create form: name required, submit disabled when empty, error on 403, calls onCreated on success ✓
- Detail view: name, status chip, goal, environments, constraints, source type, dates ✓
- Archived chip shown for archived projects in both table and detail ✓

**Placeholder scan:** None — all steps have complete code.

**Type consistency:**
- `ProjectRecord` from `projects-api.ts` used in all component props ✓
- `SessionRole` from `session.ts` used for role gating ✓
- `createProject` called with `ProjectCreateInput` shape ✓

**Out of scope (noted):**
- Inline archive action from the detail page — requires admin session wiring (separate task)
- Full E2E page integration tests — separate task when session auth is wired
- Pagination and filter bar on list page — noted in `001i` as future iteration
