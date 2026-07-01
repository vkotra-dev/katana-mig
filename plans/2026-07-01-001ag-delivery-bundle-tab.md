Task: tasks/001ag-delivery-bundle-tab.md
Spec: docs/superpowers/specs/2026-07-01-delivery-bundle-tab-design.md
Domain: docs/domain/ui.md (authoritative), docs/domain/api.md

## Source of truth

`docs/superpowers/specs/2026-07-01-delivery-bundle-tab-design.md` defines what to build.
Mockmigration (if referenced) is for styling patterns only — not content authority.

## Current state

| File | What exists |
|---|---|
| `web/app/projects/[id]/page.tsx` | Three tabs: Overview, Sources, Artifacts. `activeTab` union is `"overview" \| "sources" \| "artifacts"` |
| `web/app/projects/[id]/codegen/page.tsx` | Full SQL bundle delivery page — sources table, latest artifact + SQL preview, download bundle button, artifact history. No inbound link from project detail |

## Blast radius

| File | Action |
|---|---|
| `web/app/projects/[id]/page.tsx` | modify — add SQL Bundle tab button |
| `web/app/projects/[id]/page.test.tsx` | create — test for tab render and navigation |

---

# Delivery Bundle Tab Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a fourth "SQL Bundle" tab to the project detail page that navigates to `/projects/[id]/codegen`.

**Architecture:** Single file change — add a tab button to `web/app/projects/[id]/page.tsx` that calls `router.push` to the existing codegen page. No new panel content, no new API calls, no state change.

**Tech Stack:** Next.js App Router, React, TypeScript, Vitest + Testing Library

## Global Constraints

- Styling follows mockmigration patterns; content/behaviour is determined by the spec
- Tab pill styling must match the existing three tabs exactly: `rounded-full px-4 py-2 text-sm font-semibold` with active/inactive states
- All authenticated roles (`central_team`, `project_stakeholder`, `read_only_auditor`) see the tab
- No `activeTab` value `"sql-bundle"` is needed — the tab navigates away immediately on click

---

### Task 1: Add SQL Bundle tab + test

**Files:**
- Modify: `web/app/projects/[id]/page.tsx`
- Create: `web/app/projects/[id]/page.test.tsx`

**Interfaces:**
- Consumes: `router.push` from `useRouter()` (already in file at line 6)
- Produces: tab button rendered in DOM, navigation to `/projects/${id}/codegen` on click

- [ ] **Step 1: Write the failing test**

Create `web/app/projects/[id]/page.test.tsx`:

```tsx
import { Suspense } from "react";
import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import ProjectDetailPage from "./page";

const {
  loadUiSessionMock,
  getProjectMock,
  routerPushMock,
} = vi.hoisted(() => ({
  loadUiSessionMock: vi.fn(),
  getProjectMock: vi.fn(),
  routerPushMock: vi.fn(),
}));

vi.mock("../../../lib/session", () => ({
  loadUiSession: loadUiSessionMock,
}));

vi.mock("../../../lib/projects-api", () => ({
  getProject: getProjectMock,
  projectErrorMessage: (e: unknown) => (e instanceof Error ? e.message : "Error"),
}));

vi.mock("../../../components/projects/ProjectDetailView", () => ({
  ProjectDetailView: () => <div>Overview content</div>,
}));

vi.mock("../../../components/projects/SourceList", () => ({
  SourceList: () => <div>Sources content</div>,
}));

vi.mock("../../../components/projects/SourceArtifactsPanel", () => ({
  SourceArtifactsPanel: () => <div>Artifacts content</div>,
}));

vi.mock("../../../components/Topbar", () => ({
  Topbar: () => <nav>Topbar</nav>,
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: routerPushMock }),
}));

const SESSION = {
  accessToken: "tok-1",
  expiresAt: "2027-01-01T00:00:00Z",
  role: "central_team" as const,
  sessionVersion: 1,
  userId: "user-1",
};

const PROJECT = {
  projectId: "proj-1",
  name: "Alpha",
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
  createdAt: "2026-07-01T00:00:00Z",
  updatedAt: "2026-07-01T00:00:00Z",
  archivedAt: null,
  latestRunSummary: null,
};

// Wrap in Suspense because the page uses React.use(params) which suspends briefly
// even with an already-resolved promise in concurrent mode.
function renderPage(id: string) {
  return render(
    <Suspense fallback={<div>loading</div>}>
      <ProjectDetailPage params={Promise.resolve({ id })} />
    </Suspense>,
  );
}

describe("ProjectDetailPage — SQL Bundle tab", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    loadUiSessionMock.mockReturnValue(SESSION);
    getProjectMock.mockResolvedValue(PROJECT);
  });

  it("renders the SQL Bundle tab button", async () => {
    renderPage("proj-1");
    expect(await screen.findByRole("button", { name: "SQL Bundle" })).toBeInTheDocument();
  });

  it("navigates to codegen page when SQL Bundle tab is clicked", async () => {
    renderPage("proj-1");
    const tab = await screen.findByRole("button", { name: "SQL Bundle" });
    fireEvent.click(tab);
    expect(routerPushMock).toHaveBeenCalledWith("/projects/proj-1/codegen");
  });
});
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
cd /Users/vjkotra/projects/katana/web
npm test -- app/projects/\\[id\\]/page.test.tsx
```

Expected: FAIL — "SQL Bundle" button not found.

- [ ] **Step 3: Add the SQL Bundle tab button to the page**

Open `web/app/projects/[id]/page.tsx`. Find the tab strip (the `<div className="flex gap-2">` block containing the three tab buttons). Add the SQL Bundle button immediately after the "Artifacts" button:

```tsx
<button
  className="rounded-full px-4 py-2 text-sm font-semibold border border-outline-variant bg-surface-container text-slate-700"
  onClick={() => router.push(`/projects/${id}/codegen`)}
  type="button"
>
  SQL Bundle
</button>
```

The SQL Bundle tab never has an active state (it navigates away), so it always uses the inactive class string.

- [ ] **Step 4: Run the test to verify it passes**

```bash
cd /Users/vjkotra/projects/katana/web
npm test -- app/projects/\\[id\\]/page.test.tsx
```

Expected: PASS — both tests green.

- [ ] **Step 5: Run the full web test suite to check for regressions**

```bash
cd /Users/vjkotra/projects/katana/web
npm test
```

Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
git add web/app/projects/\[id\]/page.tsx web/app/projects/\[id\]/page.test.tsx
git commit -m "feat(001ag): add SQL Bundle tab navigating to codegen page"
```
