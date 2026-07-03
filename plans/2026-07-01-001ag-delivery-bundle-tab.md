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
| `web/app/projects/[id]/codegen/page.tsx` | Full SQL bundle delivery page — sources table, latest artifact + SQL preview, download bundle button, artifact history. Needs the shared tab row with SQL Bundle active |

## Blast radius

| File | Action |
|---|---|
| `web/components/projects/ProjectNavigationTabs.tsx` | create — shared tab row renderer |
| `web/components/projects/__tests__/ProjectNavigationTabs.test.tsx` | create — test shared tab behavior in both modes |
| `web/app/projects/[id]/page.tsx` | modify — use shared tab row and keep local tab state |
| `web/app/projects/[id]/page.test.tsx` | create — test project-page tab render and navigation |
| `web/app/projects/[id]/codegen/page.tsx` | modify — render the shared tab row with SQL Bundle active |
| `web/app/projects/[id]/codegen/page.test.tsx` | modify — assert the codegen page shows the same row |

---

# Delivery Bundle Tab Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a shared fourth "SQL Bundle" tab row to the project detail and codegen pages so both screens expose the same navigation path.

**Architecture:** Extract one shared project tab row component in `web/components/projects/ProjectNavigationTabs.tsx`. The project detail page keeps local state for Overview/Sources/Artifacts and uses the shared component to push to codegen when SQL Bundle is clicked. The codegen page renders the same shared row with SQL Bundle active and the other tabs routing back to project detail. No backend changes, no page-content changes.

**Tech Stack:** Next.js App Router, React, TypeScript, Vitest + Testing Library

## Priority

This is a later-phase delivery item. Keep it behind the feed/fiber/comment/AI
priority stream.

## Global Constraints

- Styling follows mockmigration patterns; content/behaviour is determined by the spec
- Tab pill styling must match the existing three tabs exactly: `rounded-full px-4 py-2 text-sm font-semibold` with active/inactive states
- All authenticated roles (`central_team`, `project_stakeholder`, `read_only_auditor`) see the tab row
- The codegen page must show `SQL Bundle` as active and the other tabs must return to the project detail page
- No backend API changes

## Objective

Add a shared project navigation affordance for SQL bundle delivery and keep the existing codegen page content intact.

## Out of Scope

- No backend API changes
- No new codegen page panels or content
- No role gates or feature flags
- No navigation changes outside the project/project-codegen tab row

## File Changes

- `web/components/projects/ProjectNavigationTabs.tsx` - shared tab row renderer
- `web/components/projects/__tests__/ProjectNavigationTabs.test.tsx` - verify both modes
- `web/app/projects/[id]/page.tsx` - use the shared tab row on the project detail page
- `web/app/projects/[id]/page.test.tsx` - add coverage for render and navigation
- `web/app/projects/[id]/codegen/page.tsx` - render the same tab row with SQL Bundle active
- `web/app/projects/[id]/codegen/page.test.tsx` - assert the active tab state and back-navigation

## Verification

- `npm test -- components/projects/ProjectNavigationTabs.test.tsx`
- `npm test -- app/projects/\\[id\\]/page.test.tsx`
- `npm test -- app/projects/\\[id\\]/codegen/page.test.tsx`
- `npm test`

## Pitfalls

- Do not add a backend or permission change
- Keep the button styling consistent with the other pills
- Cover at least one non-`central_team` role in the project-page test so the "all authenticated roles" requirement is locked in
- Make sure the codegen page keeps its current content; only the shared tab row moves

## Commit

- `feat(001ag): add shared SQL Bundle tabs for project and codegen pages`

---

### Task 1: Shared tab component and project page

**Files:**
- Create: `web/components/projects/ProjectNavigationTabs.tsx`
- Create: `web/components/projects/__tests__/ProjectNavigationTabs.test.tsx`
- Modify: `web/app/projects/[id]/page.tsx`
- Create: `web/app/projects/[id]/page.test.tsx`

**Interfaces:**
- Consumes: `router.push` from `useRouter()`, project id, active tab key, and the project-page `setActiveTab` callback
- Produces: shared tab row rendered in DOM, navigation to `/projects/${id}/codegen` from project detail, and the shared active-state styling used by both pages

- [ ] **Step 1: Write the failing test**

Create `web/components/projects/__tests__/ProjectNavigationTabs.test.tsx`:

```tsx
import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ProjectNavigationTabs } from "../ProjectNavigationTabs";

const { routerPushMock } = vi.hoisted(() => ({
  routerPushMock: vi.fn(),
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: routerPushMock }),
}));

describe("ProjectNavigationTabs", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("pushes to codegen from the project detail tab row", () => {
    render(
      <ProjectNavigationTabs
        activeTab="overview"
        mode="detail"
        projectId="proj-1"
        onTabChange={vi.fn()}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "SQL Bundle" }));
    expect(routerPushMock).toHaveBeenCalledWith("/projects/proj-1/codegen");
  });

  it("marks SQL Bundle active on the codegen tab row", () => {
    render(<ProjectNavigationTabs activeTab="sql-bundle" mode="codegen" projectId="proj-1" />);

    expect(screen.getByRole("button", { name: "SQL Bundle" })).toHaveClass("bg-primary");
  });
});
```

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
  role: "project_stakeholder" as const,
  sessionVersion: 1,
  userId: "user-1",
};

const AUDITOR_SESSION = {
  accessToken: "tok-2",
  expiresAt: "2027-01-01T00:00:00Z",
  role: "read_only_auditor" as const,
  sessionVersion: 1,
  userId: "user-2",
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

  it("renders the SQL Bundle tab for read-only auditors too", async () => {
    loadUiSessionMock.mockReturnValue(AUDITOR_SESSION);
    renderPage("proj-1");
    expect(await screen.findByRole("button", { name: "SQL Bundle" })).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
cd /Users/vjkotra/projects/katana/web
npm test -- app/projects/\\[id\\]/page.test.tsx
```

Expected: FAIL — "SQL Bundle" button not found.

- [ ] **Step 3: Create the shared tab row component and wire the project page**

Create `web/components/projects/ProjectNavigationTabs.tsx` and move the tab row logic there:

```tsx
"use client";

import { useRouter } from "next/navigation";

export type ProjectTabKey = "overview" | "sources" | "artifacts" | "sql-bundle";

interface ProjectNavigationTabsProps {
  activeTab: ProjectTabKey;
  mode: "detail" | "codegen";
  projectId: string;
  onTabChange?: (tab: Exclude<ProjectTabKey, "sql-bundle">) => void;
}

const tabBase = "rounded-full px-4 py-2 text-sm font-semibold";
const tabInactive = "border border-outline-variant bg-surface-container text-slate-700";
const tabActive = "bg-primary text-white";

export function ProjectNavigationTabs({
  activeTab,
  mode,
  onTabChange,
  projectId,
}: ProjectNavigationTabsProps) {
  const router = useRouter();
  const tabs: Array<{ key: ProjectTabKey; label: string }> = [
    { key: "overview", label: "Overview" },
    { key: "sources", label: "Sources" },
    { key: "artifacts", label: "Artifacts" },
    { key: "sql-bundle", label: "SQL Bundle" },
  ];

  return (
    <div className="flex gap-2">
      {tabs.map((tab) => {
        const isActive = tab.key === activeTab;
        const className = `${tabBase} ${isActive ? tabActive : tabInactive}`;
        const onClick = () => {
          if (mode === "detail") {
            if (tab.key === "sql-bundle") {
              router.push(`/projects/${projectId}/codegen`);
              return;
            }
            onTabChange?.(tab.key);
            return;
          }

          if (tab.key === "sql-bundle") {
            return;
          }
          router.push(`/projects/${projectId}`);
        };

        return (
          <button
            key={tab.key}
            className={className}
            disabled={mode === "codegen" && isActive}
            onClick={onClick}
            type="button"
          >
            {tab.label}
          </button>
        );
      })}
    </div>
  );
}
```

Then update `web/app/projects/[id]/page.tsx` to remove the inline tab buttons and render:

```tsx
<ProjectNavigationTabs
  activeTab={activeTab === "overview" || activeTab === "sources" || activeTab === "artifacts" ? activeTab : "overview"}
  mode="detail"
  onTabChange={setActiveTab}
  projectId={id}
/>
```

The project page still owns the active tab state for Overview / Sources / Artifacts. SQL Bundle always routes to codegen.

- [ ] **Step 4: Run the test to verify it passes**

```bash
cd /Users/vjkotra/projects/katana/web
npm test -- app/projects/\\[id\\]/page.test.tsx
```

Expected: PASS — all targeted tests green.

- [ ] **Step 5: Run the full web test suite to check for regressions**

```bash
cd /Users/vjkotra/projects/katana/web
npm test
```

Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
git add web/components/projects/ProjectNavigationTabs.tsx web/components/projects/__tests__/ProjectNavigationTabs.test.tsx web/app/projects/\[id\]/page.tsx web/app/projects/\[id\]/page.test.tsx
git commit -m "feat(001ag): add shared SQL Bundle tabs for project and codegen pages"
```

---

### Task 2: Wire the codegen page to the shared tab row

**Files:**
- Modify: `web/app/projects/[id]/codegen/page.tsx`
- Modify: `web/app/projects/[id]/codegen/page.test.tsx`

**Interfaces:**
- Consumes: `ProjectNavigationTabs` from the shared component, the project id from `params`, and the existing codegen page state
- Produces: the same four-pill tab row at the top of the codegen page with SQL Bundle active and Overview/Sources/Artifacts returning to project detail

- [ ] **Step 1: Write the failing test**

Update `web/app/projects/[id]/codegen/page.test.tsx` with a tab-row assertion:

```tsx
const { routerPushMock } = vi.hoisted(() => ({
  routerPushMock: vi.fn(),
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: routerPushMock }),
}));

it("renders the shared tab row with SQL Bundle active and returns to project detail from Overview", async () => {
  render(<CodegenPage params={Promise.resolve({ id: "project-1" })} />);

  expect(await screen.findByRole("button", { name: "SQL Bundle" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "SQL Bundle" })).toHaveClass("bg-primary");

  fireEvent.click(screen.getByRole("button", { name: "Overview" }));
  expect(routerPushMock).toHaveBeenCalledWith("/projects/project-1");
});
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
cd /Users/vjkotra/projects/katana/web
npm test -- app/projects/\\[id\\]/codegen/page.test.tsx
```

Expected: FAIL because the codegen page does not yet render the shared tab row.

- [ ] **Step 3: Render the shared tab row on the codegen page**

Open `web/app/projects/[id]/codegen/page.tsx`. Add the shared component import and render it above the page sections:

```tsx
import { ProjectNavigationTabs } from "../../../../components/projects/ProjectNavigationTabs";
```

```tsx
<ProjectNavigationTabs activeTab="sql-bundle" mode="codegen" projectId={routeParams.id} />
```

The codegen page keeps its existing content exactly as-is. Only the tab row is added.

- [ ] **Step 4: Run the test to verify it passes**

```bash
cd /Users/vjkotra/projects/katana/web
npm test -- app/projects/\\[id\\]/codegen/page.test.tsx
```

Expected: PASS.

- [ ] **Step 5: Run the full web test suite**

```bash
cd /Users/vjkotra/projects/katana/web
npm test
```

Expected: all web tests pass.

- [ ] **Step 6: Commit**

```bash
git add web/app/projects/\[id\]/codegen/page.tsx web/app/projects/\[id\]/codegen/page.test.tsx
git commit -m "feat(001ag): add SQL Bundle tab to codegen page"
```
