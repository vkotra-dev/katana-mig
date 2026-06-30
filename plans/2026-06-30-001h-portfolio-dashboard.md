Task: tasks/001h-ui-portfolio-project-screens.md
Domain: docs/domain/ui.md, docs/domain/project.md
Reference template: mockmigration/src/components/Portfolio.tsx

## Current State

`web/app/dashboard/page.tsx` is a placeholder (hardcoded `role = "central_team"`, empty
div). No portfolio components exist. The following are already in place and must NOT
be modified:

- `web/components/projects/ProjectTable.tsx` — used by the `/projects` page
- `web/app/projects/page.tsx` — existing project list page
- `web/lib/projects-api.ts` — `listProjects(token, { includeArchived })` already implemented
- `web/lib/slice-approval-api.ts` — `getPendingApprovalCount(token)` already implemented
- `web/lib/session.ts` — `loadUiSession()` and `UiSession` already implemented

The backend `GET /projects` already filters by membership for `project_stakeholder` role.
No backend changes are needed.

## Objective

Replace the `/dashboard` placeholder with a real portfolio page modelled on the
mockmigration Portfolio template. Show a summary strip of 4 metrics and a sortable,
filterable project table. Keep implementation in `web/components/portfolio/`.

## Blast Radius

| File | Action | What changes |
|---|---|---|
| `web/components/portfolio/SummaryStrip.tsx` | create | 4 metric cards component |
| `web/components/portfolio/PortfolioTable.tsx` | create | filter bar + sortable table |
| `web/components/portfolio/__tests__/SummaryStrip.test.tsx` | create | unit tests |
| `web/components/portfolio/__tests__/PortfolioTable.test.tsx` | create | unit tests |
| `web/app/dashboard/page.tsx` | replace | real portfolio page wiring |
| `web/app/dashboard/page.test.tsx` | create | page-level integration tests |

## Component Specifications

### `web/components/portfolio/SummaryStrip.tsx`

Pure presentational component. No state, no API calls.

```tsx
interface MetricCardProps {
  label: string;
  value: number;
  accent?: string;
}

function MetricCard({ label, value, accent }: MetricCardProps) {
  return (
    <div className="flex flex-col gap-1 rounded-xl border border-outline-variant bg-surface-container p-5 shadow-sm">
      <span className={`text-3xl font-semibold tabular-nums ${accent ?? "text-slate-900"}`}>
        {value}
      </span>
      <span className="text-xs font-medium uppercase tracking-wide text-neutral">{label}</span>
    </div>
  );
}

export interface SummaryStripProps {
  total: number;
  active: number;
  archived: number;
  pendingApprovals: number;
}

export function SummaryStrip({ total, active, archived, pendingApprovals }: SummaryStripProps) {
  return (
    <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
      <MetricCard label="Total Projects" value={total} />
      <MetricCard accent="text-primary" label="Active" value={active} />
      <MetricCard label="Archived" value={archived} />
      <MetricCard
        accent={pendingApprovals > 0 ? "text-warning" : undefined}
        label="Pending Approvals"
        value={pendingApprovals}
      />
    </div>
  );
}
```

### `web/components/portfolio/PortfolioTable.tsx`

Manages its own filter and sort state. Receives the raw (unfiltered) project list from
the page. Renders the filter bar and table together inside a card wrapper.

```tsx
"use client";

import { useMemo, useState } from "react";
import type { SessionRole } from "../../lib/session";
import type { ProjectRecord } from "../../lib/projects-api";

export interface PortfolioTableProps {
  projects: ProjectRecord[];
  role: SessionRole;
  onInitiate?: () => void;
}

type SortKey = "name" | "updatedAt";
type SortDir = "asc" | "desc";
type StatusFilter = "all" | "active" | "archived";

function statusChipClass(status: "active" | "archived"): string {
  return status === "archived"
    ? "bg-surface-dim text-neutral"
    : "bg-primary-container text-on-primary-container";
}

function truncate(text: string | null | undefined, max: number): string {
  if (!text) return "—";
  return text.length > max ? `${text.slice(0, max)}…` : text;
}

export function PortfolioTable({ projects, role, onInitiate }: PortfolioTableProps) {
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("active");
  const [environmentFilter, setEnvironmentFilter] = useState("");
  const [sortKey, setSortKey] = useState<SortKey>("name");
  const [sortDir, setSortDir] = useState<SortDir>("asc");

  const environmentOptions = useMemo(() => {
    const seen = new Set<string>();
    for (const p of projects) {
      for (const env of p.executionEnvironments ?? []) seen.add(env);
    }
    return [...seen].sort();
  }, [projects]);

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    return projects.filter((p) => {
      if (q && !p.name.toLowerCase().includes(q) && !p.projectId.toLowerCase().includes(q)) {
        return false;
      }
      if (statusFilter !== "all" && p.status !== statusFilter) return false;
      if (environmentFilter && !(p.executionEnvironments ?? []).includes(environmentFilter)) {
        return false;
      }
      return true;
    });
  }, [projects, search, statusFilter, environmentFilter]);

  const sorted = useMemo(() => {
    const copy = [...filtered].sort((a, b) => {
      if (sortKey === "updatedAt") return a.updatedAt.localeCompare(b.updatedAt);
      return a.name.localeCompare(b.name);
    });
    return sortDir === "asc" ? copy : copy.reverse();
  }, [filtered, sortKey, sortDir]);

  function toggleSort(key: SortKey) {
    if (sortKey === key) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortKey(key);
      setSortDir(key === "updatedAt" ? "desc" : "asc");
    }
  }

  const canCreate = role !== "read_only_auditor";

  return (
    <section className="space-y-4 rounded-2xl border border-outline-variant bg-surface-container p-6 shadow-sm">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-xl font-semibold text-slate-900">Projects</h2>
          <p className="text-sm text-neutral">Migration projects visible to your role.</p>
        </div>
        {canCreate && onInitiate ? (
          <button
            className="rounded-md bg-primary px-4 py-2 text-sm font-semibold text-white hover:opacity-95"
            onClick={onInitiate}
            type="button"
          >
            Initiate project
          </button>
        ) : null}
      </div>

      <div className="flex flex-wrap items-center gap-3">
        <input
          aria-label="Search projects"
          className="rounded-md border border-outline-variant bg-surface px-3 py-1.5 text-sm placeholder:text-neutral focus:outline-none focus:ring-1 focus:ring-primary"
          onChange={(e) => { setSearch(e.target.value); }}
          placeholder="Search by name or ID…"
          type="search"
          value={search}
        />
        <select
          aria-label="Filter by status"
          className="rounded-md border border-outline-variant bg-surface px-3 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-primary"
          onChange={(e) => { setStatusFilter(e.target.value as StatusFilter); }}
          value={statusFilter}
        >
          <option value="all">All statuses</option>
          <option value="active">Active</option>
          <option value="archived">Archived</option>
        </select>
        {environmentOptions.length > 0 && (
          <select
            aria-label="Filter by environment"
            className="rounded-md border border-outline-variant bg-surface px-3 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-primary"
            onChange={(e) => { setEnvironmentFilter(e.target.value); }}
            value={environmentFilter}
          >
            <option value="">All environments</option>
            {environmentOptions.map((env) => (
              <option key={env} value={env}>{env}</option>
            ))}
          </select>
        )}
      </div>

      {sorted.length === 0 ? (
        <div className="rounded-xl border border-dashed border-outline-variant px-6 py-12 text-center text-sm text-neutral">
          No matching projects.
        </div>
      ) : (
        <div className="overflow-x-auto rounded-xl border border-outline-variant">
          <table className="w-full border-collapse text-sm">
            <thead className="bg-surface">
              <tr className="text-left text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">
                <th className="px-4 py-3">
                  <button
                    className="inline-flex items-center gap-1"
                    onClick={() => { toggleSort("name"); }}
                    type="button"
                  >
                    Project
                  </button>
                </th>
                <th className="px-4 py-3">Goal</th>
                <th className="px-4 py-3">Target DB</th>
                <th className="px-4 py-3">Environments</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3">
                  <button
                    className="inline-flex items-center gap-1"
                    onClick={() => { toggleSort("updatedAt"); }}
                    type="button"
                  >
                    Last Updated
                  </button>
                </th>
                <th className="px-4 py-3 sr-only">Actions</th>
              </tr>
            </thead>
            <tbody>
              {sorted.map((project) => (
                <tr
                  key={project.projectId}
                  className="border-t border-outline-variant hover:bg-surface-container-lowest"
                >
                  <td className="px-4 py-3 align-top">
                    <div className="space-y-0.5">
                      <a
                        className="font-semibold text-slate-900 hover:text-primary hover:underline"
                        href={`/projects/${project.projectId}`}
                      >
                        {project.name}
                      </a>
                      <div className="mono-id text-xs">{project.projectId}</div>
                    </div>
                  </td>
                  <td className="px-4 py-3 align-top text-slate-700">
                    {truncate(project.goal, 60)}
                  </td>
                  <td className="px-4 py-3 align-top text-slate-700">
                    {project.domainConfig?.targetDbEngine ?? "—"}
                  </td>
                  <td className="px-4 py-3 align-top">
                    {project.executionEnvironments?.length ? (
                      <div className="flex flex-wrap gap-1">
                        {project.executionEnvironments.map((env) => (
                          <span
                            key={env}
                            className="rounded border border-outline-variant bg-surface px-1.5 py-0.5 text-xs text-slate-600"
                          >
                            {env}
                          </span>
                        ))}
                      </div>
                    ) : (
                      "—"
                    )}
                  </td>
                  <td className="px-4 py-3 align-top">
                    <span
                      className={`status-chip inline-flex items-center ${statusChipClass(project.status)}`}
                    >
                      {project.status}
                    </span>
                  </td>
                  <td className="px-4 py-3 align-top text-slate-700">
                    {project.updatedAt.slice(0, 10)}
                  </td>
                  <td className="px-4 py-3 align-top">
                    <a
                      className="text-xs font-medium text-primary hover:underline"
                      href={`/projects/${project.projectId}`}
                    >
                      Open
                    </a>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
```

### `web/app/dashboard/page.tsx`

Replaces the existing placeholder. Loads projects (including archived) and pending
approval count in parallel. Computes summary stats from the full project list. The
`PortfolioTable` manages its own filtering so the page only passes unfiltered data.

```tsx
"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { Topbar } from "../../components/Topbar";
import { SummaryStrip } from "../../components/portfolio/SummaryStrip";
import { PortfolioTable } from "../../components/portfolio/PortfolioTable";
import { CreateProjectDialog } from "../../components/projects/CreateProjectDialog";
import { listProjects, projectErrorMessage, type ProjectRecord } from "../../lib/projects-api";
import { getPendingApprovalCount } from "../../lib/slice-approval-api";
import { loadUiSession, type SessionRole, type UiSession } from "../../lib/session";

export default function DashboardPage() {
  const router = useRouter();
  const [session, setSession] = useState<UiSession | null>(null);
  const [projects, setProjects] = useState<ProjectRecord[]>([]);
  const [pendingApprovals, setPendingApprovals] = useState(0);
  const [loading, setLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [dialogOpen, setDialogOpen] = useState(false);

  useEffect(() => {
    setSession(loadUiSession());
  }, []);

  useEffect(() => {
    if (!session) {
      setLoading(false);
      return;
    }
    let active = true;
    setLoading(true);
    setErrorMessage(null);

    void Promise.all([
      listProjects(session.accessToken, { includeArchived: true }),
      getPendingApprovalCount(session.accessToken),
    ])
      .then(([allProjects, count]) => {
        if (active) {
          setProjects(allProjects);
          setPendingApprovals(count);
        }
      })
      .catch((error: unknown) => {
        if (active) setErrorMessage(projectErrorMessage(error));
      })
      .finally(() => {
        if (active) setLoading(false);
      });

    return () => {
      active = false;
    };
  }, [session]);

  const total = projects.length;
  const active = useMemo(
    () => projects.filter((p) => p.status === "active").length,
    [projects],
  );
  const archived = useMemo(
    () => projects.filter((p) => p.status === "archived").length,
    [projects],
  );

  const role: SessionRole = session?.role ?? "read_only_auditor";

  return (
    <main className="flex min-h-screen flex-col bg-surface text-slate-800">
      <Topbar role={role} />
      <section className="mx-auto flex w-full max-w-[1600px] flex-1 flex-col gap-6 px-6 py-6">
        {loading ? (
          <div className="rounded-2xl border border-outline-variant bg-surface-container p-8 text-sm text-slate-600">
            Loading portfolio…
          </div>
        ) : errorMessage ? (
          <div
            role="alert"
            className="rounded-2xl border border-error/30 bg-error/10 px-4 py-3 text-sm text-error"
          >
            {errorMessage}
          </div>
        ) : (
          <>
            <SummaryStrip
              active={active}
              archived={archived}
              pendingApprovals={pendingApprovals}
              total={total}
            />
            <PortfolioTable
              onInitiate={() => { setDialogOpen(true); }}
              projects={projects}
              role={role}
            />
          </>
        )}
      </section>
      <CreateProjectDialog
        onClose={() => { setDialogOpen(false); }}
        onCreated={(project) => {
          setProjects((current) => [project, ...current]);
          setDialogOpen(false);
          router.push(`/projects/${project.projectId}`);
        }}
        open={dialogOpen}
        token={session?.accessToken ?? ""}
      />
    </main>
  );
}
```

## Tests

### `web/components/portfolio/__tests__/SummaryStrip.test.tsx`

```tsx
import { render, screen } from "@testing-library/react";
import { SummaryStrip } from "../SummaryStrip";

describe("SummaryStrip", () => {
  it("renders four metric cards with correct values", () => {
    render(
      <SummaryStrip active={4} archived={1} pendingApprovals={2} total={5} />,
    );
    expect(screen.getByText("5")).toBeInTheDocument();
    expect(screen.getByText("4")).toBeInTheDocument();
    expect(screen.getByText("1")).toBeInTheDocument();
    expect(screen.getByText("2")).toBeInTheDocument();
    expect(screen.getByText("Total Projects")).toBeInTheDocument();
    expect(screen.getByText("Active")).toBeInTheDocument();
    expect(screen.getByText("Archived")).toBeInTheDocument();
    expect(screen.getByText("Pending Approvals")).toBeInTheDocument();
  });
});
```

### `web/components/portfolio/__tests__/PortfolioTable.test.tsx`

```tsx
import { render, screen, fireEvent } from "@testing-library/react";
import { PortfolioTable } from "../PortfolioTable";
import type { ProjectRecord } from "../../../lib/projects-api";

const makeProject = (overrides: Partial<ProjectRecord>): ProjectRecord => ({
  projectId: "proj-001",
  name: "Alpha Migration",
  goal: null,
  repos: null,
  workspace: null,
  environment: null,
  executionEnvironments: null,
  modelPolicy: null,
  canonicalTerms: null,
  constraints: null,
  unresolvedQuestions: null,
  assumptions: null,
  domainConfig: null,
  lexiconScope: null,
  status: "active",
  createdAt: "2026-01-01T00:00:00Z",
  updatedAt: "2026-06-01T00:00:00Z",
  archivedAt: null,
  ...overrides,
});

const PROJECTS: ProjectRecord[] = [
  makeProject({ projectId: "proj-001", name: "Alpha Migration", status: "active", executionEnvironments: ["dev", "prod"] }),
  makeProject({ projectId: "proj-002", name: "Beta Sync", status: "archived", executionEnvironments: ["staging"] }),
  makeProject({ projectId: "proj-003", name: "Gamma Load", status: "active", executionEnvironments: ["dev"] }),
];

describe("PortfolioTable", () => {
  it("shows all projects when no filter is set (default status=active shows 2)", () => {
    render(<PortfolioTable projects={PROJECTS} role="central_team" />);
    expect(screen.getByText("Alpha Migration")).toBeInTheDocument();
    expect(screen.getByText("Gamma Load")).toBeInTheDocument();
    expect(screen.queryByText("Beta Sync")).not.toBeInTheDocument();
  });

  it("shows all projects when status filter is 'all'", () => {
    render(<PortfolioTable projects={PROJECTS} role="central_team" />);
    fireEvent.change(screen.getByRole("combobox", { name: /filter by status/i }), {
      target: { value: "all" },
    });
    expect(screen.getByText("Beta Sync")).toBeInTheDocument();
  });

  it("filters by search term on project name", () => {
    render(<PortfolioTable projects={PROJECTS} role="central_team" />);
    fireEvent.change(screen.getByRole("combobox", { name: /filter by status/i }), {
      target: { value: "all" },
    });
    fireEvent.change(screen.getByRole("searchbox", { name: /search projects/i }), {
      target: { value: "alpha" },
    });
    expect(screen.getByText("Alpha Migration")).toBeInTheDocument();
    expect(screen.queryByText("Beta Sync")).not.toBeInTheDocument();
    expect(screen.queryByText("Gamma Load")).not.toBeInTheDocument();
  });

  it("filters by project ID", () => {
    render(<PortfolioTable projects={PROJECTS} role="central_team" />);
    fireEvent.change(screen.getByRole("combobox", { name: /filter by status/i }), {
      target: { value: "all" },
    });
    fireEvent.change(screen.getByRole("searchbox", { name: /search projects/i }), {
      target: { value: "proj-002" },
    });
    expect(screen.getByText("Beta Sync")).toBeInTheDocument();
    expect(screen.queryByText("Alpha Migration")).not.toBeInTheDocument();
  });

  it("hides Initiate project button for read_only_auditor", () => {
    const onInitiate = vi.fn();
    render(
      <PortfolioTable onInitiate={onInitiate} projects={PROJECTS} role="read_only_auditor" />,
    );
    expect(screen.queryByRole("button", { name: /initiate project/i })).not.toBeInTheDocument();
  });

  it("shows Initiate project button for central_team", () => {
    const onInitiate = vi.fn();
    render(
      <PortfolioTable onInitiate={onInitiate} projects={PROJECTS} role="central_team" />,
    );
    expect(screen.getByRole("button", { name: /initiate project/i })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /initiate project/i }));
    expect(onInitiate).toHaveBeenCalledTimes(1);
  });

  it("shows no-match empty state when search finds nothing", () => {
    render(<PortfolioTable projects={PROJECTS} role="central_team" />);
    fireEvent.change(screen.getByRole("searchbox", { name: /search projects/i }), {
      target: { value: "zzz-no-match" },
    });
    expect(screen.getByText("No matching projects.")).toBeInTheDocument();
  });
});
```

### `web/app/dashboard/page.test.tsx`

```tsx
import { render, screen, waitFor } from "@testing-library/react";
import { vi, beforeEach, describe, it, expect } from "vitest";
import DashboardPage from "./page";

vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn() }) }));
vi.mock("../../lib/session", () => ({
  loadUiSession: vi.fn(),
}));
vi.mock("../../lib/projects-api", () => ({
  listProjects: vi.fn(),
  projectErrorMessage: (e: unknown) => (e instanceof Error ? e.message : "error"),
}));
vi.mock("../../lib/slice-approval-api", () => ({
  getPendingApprovalCount: vi.fn(),
}));

import { loadUiSession } from "../../lib/session";
import { listProjects } from "../../lib/projects-api";
import { getPendingApprovalCount } from "../../lib/slice-approval-api";

const mockSession = {
  accessToken: "tok-abc",
  expiresAt: "2099-01-01T00:00:00Z",
  userId: "user-1",
  role: "central_team" as const,
  sessionVersion: 1,
};

const mockProject = {
  projectId: "proj-001",
  name: "Alpha Migration",
  goal: null,
  repos: null,
  workspace: null,
  environment: null,
  executionEnvironments: null,
  modelPolicy: null,
  canonicalTerms: null,
  constraints: null,
  unresolvedQuestions: null,
  assumptions: null,
  domainConfig: null,
  lexiconScope: null,
  status: "active" as const,
  createdAt: "2026-01-01T00:00:00Z",
  updatedAt: "2026-06-01T00:00:00Z",
  archivedAt: null,
};

beforeEach(() => {
  vi.resetAllMocks();
});

describe("DashboardPage", () => {
  it("shows loading state initially", () => {
    vi.mocked(loadUiSession).mockReturnValue(mockSession);
    vi.mocked(listProjects).mockReturnValue(new Promise(() => {}));
    vi.mocked(getPendingApprovalCount).mockReturnValue(new Promise(() => {}));
    render(<DashboardPage />);
    expect(screen.getByText("Loading portfolio…")).toBeInTheDocument();
  });

  it("renders summary strip and table on success", async () => {
    vi.mocked(loadUiSession).mockReturnValue(mockSession);
    vi.mocked(listProjects).mockResolvedValue([mockProject]);
    vi.mocked(getPendingApprovalCount).mockResolvedValue(3);
    render(<DashboardPage />);
    await waitFor(() => {
      expect(screen.getByText("Total Projects")).toBeInTheDocument();
    });
    expect(screen.getByText("1")).toBeInTheDocument();
    expect(screen.getByText("Alpha Migration")).toBeInTheDocument();
  });

  it("shows error banner on API failure", async () => {
    vi.mocked(loadUiSession).mockReturnValue(mockSession);
    vi.mocked(listProjects).mockRejectedValue(new Error("server error"));
    vi.mocked(getPendingApprovalCount).mockResolvedValue(0);
    render(<DashboardPage />);
    await waitFor(() => {
      expect(screen.getByRole("alert")).toBeInTheDocument();
    });
    expect(screen.getByRole("alert")).toHaveTextContent("server error");
  });

  it("shows no content when session is null", async () => {
    vi.mocked(loadUiSession).mockReturnValue(null);
    render(<DashboardPage />);
    await waitFor(() => {
      expect(screen.queryByText("Loading portfolio…")).not.toBeInTheDocument();
    });
  });
});
```

## Implementation Order

1. Create `web/components/portfolio/SummaryStrip.tsx`
2. Write and pass `SummaryStrip.test.tsx`
3. Create `web/components/portfolio/PortfolioTable.tsx`
4. Write and pass `PortfolioTable.test.tsx`
5. Replace `web/app/dashboard/page.tsx`
6. Write and pass `web/app/dashboard/page.test.tsx`

## Verification

```bash
pnpm --filter web test
pnpm --filter web lint
pnpm --filter web build
```

## Pitfalls

- Do NOT modify `web/components/projects/ProjectTable.tsx` or `web/app/projects/page.tsx`.
- The `PortfolioTable` default `statusFilter` is `"active"` (not `"all"`). Tests that
  expect archived projects to be visible must first change the status filter to `"all"`.
- `listProjects` is called with `{ includeArchived: true }` so summary counts include
  archived projects, even though the table defaults to showing only active.
- Use `vi.fn()` (not `jest.fn()`) in tests — this project uses Vitest.
- The `CreateProjectDialog` is imported in the page; do not remove it even if dialog
  is not the focus of 001h.

## Commit

```bash
feat(ui): add portfolio dashboard with summary strip and filterable project table
```
