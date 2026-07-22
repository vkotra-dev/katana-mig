# Plan: 001es — Wire "Suggest Standards" Button to the New Backend Endpoint

## Task and Domain links

- Task: `tasks/001es-wire-suggest-standards-button-to-backend-endpoint.md`
- Design: `docs/superpowers/specs/2026-07-22-codegen-coding-standards-prompt-extraction-design.md`
- Depends on: `001er` (must be committed first). Confirm before starting:
  `grep -n "codegen-coding-standards-template" engine/src/migrations_engine/routes/projects.py`
  must return a match. If it doesn't, stop.

## Audience note

Written for an agent with no prior context. Every edit gives exact current text and exact
replacement. Re-read both files in full immediately before starting to confirm they still match
what's quoted below.

## Current State (verbatim)

`web/app/projects/[id]/codegen/page.tsx`, lines 477-491 (`handleSuggestGlobalInstructions`, the
function this task changes):

```tsx
  const handleSuggestGlobalInstructions = () => {
    if (
      globalInstructions.trim() &&
      !window.confirm("This will overwrite your existing global instructions. Are you sure you want to proceed?")
    ) {
      return;
    }

    const engine = project?.domainConfig?.targetDbEngine || "";
    const staging = project?.domainConfig?.stagingSchema || "";
    const dest = project?.domainConfig?.destinationSchema || "";

    const template = generateCodingStandardsTemplate(engine, staging, dest);
    setGlobalInstructions(template.trim());
  };
```

`page.tsx`, lines 1-19 (imports — the `getProject` import line is what changes):

```tsx
"use client";

import { use, useEffect, useMemo, useState, Fragment } from "react";
import { Topbar } from "../../../../components/Topbar";
import { ProjectNavigationTabs } from "../../../../components/projects/ProjectNavigationTabs";
import {
  downloadCodegenDeliveryBundle,
  getSchemaAnalysis,
  listCodegenArtifacts,
  triggerSchemaAnalysis,
  triggerCodegen,
  type CodegenArtifactRecord,
  type SchemaAnalysisRecord,
} from "../../../../lib/codegen-api";
import { listFeedContracts, saveTransformationInstructions, listFeedFibers, listFeedSlices, type FeedContractRecord, type FiberRecord } from "../../../../lib/feeds-api";
import { getProject, saveCodegenInstructions, type ProjectRecord } from "../../../../lib/projects-api";
import { getAllApprovedMappingSnapshots, type MappingSnapshotRecord } from "../../../../lib/mapping-api";
import { loadUiSession, type SessionRole, type UiSession } from "../../../../lib/session";
import { AiLogViewer } from "../../../../components/ai-logs/AiLogViewer";
```

An existing error-handling pattern to match (`handleSuggestFeedInstructions`, elsewhere in this
same file — not being edited, quoted only as the reference `setPageError` catch shape):

```tsx
    } catch (error) {
      setPageError(error instanceof Error ? error.message : "Unable to suggest transformation instructions.");
    } finally {
      setFeedSuggestLoading((prev) => ({ ...prev, [feedId]: false }));
    }
```

`web/lib/projects-api.ts`, lines 437-444 (`getProject`, the reference pattern for the new API
function):

```typescript
export async function getProject(token: string, id: string): Promise<ProjectRecord> {
  const response = await requestJson<Parameters<typeof mapProjectRecord>[0]>(`/projects/${id}`, {
    method: "GET",
    token,
  });

  return mapProjectRecord(response);
}
```

`web/app/projects/[id]/codegen/page.test.tsx`, lines 302-320 (the existing test, which must be
updated since `handleSuggestGlobalInstructions` becomes async):

```tsx
  it("suggests coding standards template when clicking Suggest Standards", async () => {
    const confirmSpy = vi.spyOn(window, "confirm").mockReturnValue(true);

    render(<CodegenPage params={Promise.resolve({ id: "project-1" })} />);

    await screen.findByText("Customer extract");

    const textarea = screen.getByPlaceholderText(/e.g. All date columns must use DATE type/i);
    expect(textarea).toHaveValue("Date rules");

    const suggestBtn = screen.getByRole("button", { name: "Suggest Standards" });
    fireEvent.click(suggestBtn);

    expect(confirmSpy).toHaveBeenCalled();
    expect(textarea.value).toContain("Coding Standards and Guidelines");
    expect(textarea.value).toContain("Schemas and Scoping");

    confirmSpy.mockRestore();
  });
```

Lines 1-47 of the same test file (mock setup — the parts this task's test change touches):

```tsx
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import CodegenPage from "./page";

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
}));

vi.mock("../../../../components/Topbar", () => ({
  Topbar: () => <div>Topbar</div>,
}));

vi.mock("../../../../lib/session", () => ({
  loadUiSession: loadUiSessionMock,
}));

vi.mock("../../../../lib/projects-api", () => ({
  getProject: getProjectMock,
}));
```

## Objective

Replace the local-function call inside `handleSuggestGlobalInstructions` with a call to the new
backend endpoint, delete the now-dead `generateCodingStandardsTemplate` function, and update the
one existing test that exercises this button (it changes from a synchronous to an async
assertion).

## File Changes

### 1. `web/lib/projects-api.ts`

Find this exact block (quoted in full above under Current State):

```typescript
export async function getProject(token: string, id: string): Promise<ProjectRecord> {
  const response = await requestJson<Parameters<typeof mapProjectRecord>[0]>(`/projects/${id}`, {
    method: "GET",
    token,
  });

  return mapProjectRecord(response);
}
```

Immediately after it, insert a new function:

```typescript

export async function getCodegenCodingStandardsTemplate(token: string, id: string): Promise<string> {
  const response = await requestJson<{ template: string }>(
    `/projects/${id}/codegen-coding-standards-template`,
    { method: "GET", token },
  );

  return response.template;
}
```

### 2. `web/app/projects/[id]/codegen/page.tsx`

**2a.** Find this exact import line (quoted in full above under Current State):

```tsx
import { getProject, saveCodegenInstructions, type ProjectRecord } from "../../../../lib/projects-api";
```

Replace with:

```tsx
import { getProject, saveCodegenInstructions, getCodegenCodingStandardsTemplate, type ProjectRecord } from "../../../../lib/projects-api";
```

**2b.** Find this exact function (quoted in full above under Current State):

```tsx
  const handleSuggestGlobalInstructions = () => {
    if (
      globalInstructions.trim() &&
      !window.confirm("This will overwrite your existing global instructions. Are you sure you want to proceed?")
    ) {
      return;
    }

    const engine = project?.domainConfig?.targetDbEngine || "";
    const staging = project?.domainConfig?.stagingSchema || "";
    const dest = project?.domainConfig?.destinationSchema || "";

    const template = generateCodingStandardsTemplate(engine, staging, dest);
    setGlobalInstructions(template.trim());
  };
```

Replace with:

```tsx
  const handleSuggestGlobalInstructions = async (): Promise<void> => {
    if (
      globalInstructions.trim() &&
      !window.confirm("This will overwrite your existing global instructions. Are you sure you want to proceed?")
    ) {
      return;
    }
    if (!session || !routeParams) return;

    try {
      const template = await getCodegenCodingStandardsTemplate(session.accessToken, routeParams.id);
      setGlobalInstructions(template.trim());
    } catch (error) {
      setPageError(error instanceof Error ? error.message : "Unable to suggest coding standards.");
    }
  };
```

**2c.** Find the `generateCodingStandardsTemplate` function — its full current body is quoted in
full in `001er`'s plan under "Current State" (98 lines, from `const generateCodingStandardsTemplate
= (` through its closing `};`). Delete the entire function.

**2d.** Find the call site for this button (search for `onClick={handleSuggestGlobalInstructions}`
— it's a `<button>` element). The click handler is now async — confirm the JSX doesn't need a
`void` wrapper by checking how other async handlers in this same file are wired to `onClick` (e.g.
search for `onClick={() => void handle` in this file — if that pattern is used elsewhere for other
async handlers, apply the same `onClick={() => void handleSuggestGlobalInstructions()}` wrapping
here for consistency; if a bare `onClick={handleAsyncFn}` pattern is used elsewhere instead, match
that pattern instead). Do not guess — grep the file for the exact existing convention before
editing this line.

### 3. `web/app/projects/[id]/codegen/page.test.tsx`

**3a.** Find this exact block inside the `vi.hoisted(...)` destructuring (quoted in full above
under Current State):

```tsx
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
}));
```

Replace with (adds one new mock name to both the destructuring list and the `vi.hoisted` object):

```tsx
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
  getCodegenCodingStandardsTemplateMock,
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
  getCodegenCodingStandardsTemplateMock: vi.fn(),
}));
```

**3b.** Find this exact block (quoted in full above under Current State):

```tsx
vi.mock("../../../../lib/projects-api", () => ({
  getProject: getProjectMock,
}));
```

Replace with:

```tsx
vi.mock("../../../../lib/projects-api", () => ({
  getProject: getProjectMock,
  getCodegenCodingStandardsTemplate: getCodegenCodingStandardsTemplateMock,
}));
```

**3c.** Find this exact test (quoted in full above under Current State):

```tsx
  it("suggests coding standards template when clicking Suggest Standards", async () => {
    const confirmSpy = vi.spyOn(window, "confirm").mockReturnValue(true);

    render(<CodegenPage params={Promise.resolve({ id: "project-1" })} />);

    await screen.findByText("Customer extract");

    const textarea = screen.getByPlaceholderText(/e.g. All date columns must use DATE type/i);
    expect(textarea).toHaveValue("Date rules");

    const suggestBtn = screen.getByRole("button", { name: "Suggest Standards" });
    fireEvent.click(suggestBtn);

    expect(confirmSpy).toHaveBeenCalled();
    expect(textarea.value).toContain("Coding Standards and Guidelines");
    expect(textarea.value).toContain("Schemas and Scoping");

    confirmSpy.mockRestore();
  });
```

Replace with (adds the mock's resolved value and switches the post-click assertions into a
`waitFor`, since the handler is now async):

```tsx
  it("suggests coding standards template when clicking Suggest Standards", async () => {
    const confirmSpy = vi.spyOn(window, "confirm").mockReturnValue(true);
    getCodegenCodingStandardsTemplateMock.mockResolvedValue(
      "### Coding Standards and Guidelines\n\n1. **Schemas and Scoping**:\n   - ...\n"
    );

    render(<CodegenPage params={Promise.resolve({ id: "project-1" })} />);

    await screen.findByText("Customer extract");

    const textarea = screen.getByPlaceholderText(/e.g. All date columns must use DATE type/i);
    expect(textarea).toHaveValue("Date rules");

    const suggestBtn = screen.getByRole("button", { name: "Suggest Standards" });
    fireEvent.click(suggestBtn);

    expect(confirmSpy).toHaveBeenCalled();
    await waitFor(() => {
      expect(textarea.value).toContain("Coding Standards and Guidelines");
      expect(textarea.value).toContain("Schemas and Scoping");
    });

    confirmSpy.mockRestore();
  });
```

Note `waitFor` is already imported in this file (`import { fireEvent, render, screen, waitFor }
from "@testing-library/react";`, quoted above) — no new import needed.

**3d.** Add `getCodegenCodingStandardsTemplateMock.mockResolvedValue(...)` (or at minimum
`.mockResolvedValue("")`) to the shared `beforeEach` block if this test file has one that sets up
default mock return values for all tests (check for a `beforeEach(() => { ... })` near the top of
the `describe` block — if found, add a sensible default there instead of only in the one test
above, so other tests that happen to trigger this code path incidentally don't get an unhandled
promise rejection from an un-mocked `vi.fn()` returning `undefined`).

## Tests

The test change in step 3c above is the only test change required — it updates existing coverage
to match the new async behavior. No new test cases are needed beyond that, since the underlying
rendered content is already covered by `001er`'s backend tests (this task just confirms the
frontend correctly displays whatever the endpoint returns).

## Verification

```bash
cd /Users/vjkotra/projects/katana/web
npx tsc --noEmit
```
Expect: no new type errors versus the pre-existing baseline (compare via `git checkout HEAD~1 --
<file>` + rerun + `git checkout HEAD -- <file>`, as done for every prior task this session).

```bash
npx vitest run "app/projects/[id]/codegen/page.test.tsx"
```
Expect: all tests pass, including every pre-existing test in this file plus the updated one.

```bash
npx vitest run
```
Expect: full suite passes, same count as before this task (no new tests added, one updated).

## Pitfalls

- **Confirm `001er` actually landed before starting** — this task calls an endpoint that doesn't
  exist until `001er` ships. The dependency check at the top of this plan exists specifically to
  prevent starting this out of order.
- **Don't guess the `onClick` wrapping convention (step 2d).** This file mixes both
  `onClick={handler}` and `onClick={() => void handler()}` styles for different handlers elsewhere
  — grep for the actual pattern used by a comparable async handler in this same file (e.g.
  `handleSuggestFeedInstructions`'s button) and match it exactly, rather than assuming either style.
- **Delete `generateCodingStandardsTemplate` completely** — don't leave it as dead code "just in
  case." Its only caller is being replaced in this same task; leaving it behind is exactly the kind
  of stray leftover this session has repeatedly had to clean up in prior tasks.
- **The mock's resolved value in the test doesn't need to match `001er`'s real backend output
  byte-for-byte** — it just needs to contain the two substrings the test asserts on
  (`"Coding Standards and Guidelines"`, `"Schemas and Scoping"`), matching the same
  minimal-mock-content style already used elsewhere in this test file (e.g. the mocked
  `getAllApprovedMappingSnapshotsMock` fixtures don't reproduce full production data either).

## Commit

Own commit, after `001er`. Suggested message: `feat: wire Suggest Standards button to the new
coding-standards-template endpoint (001es)`.
