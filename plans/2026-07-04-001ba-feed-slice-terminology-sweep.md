# Feed Slice Terminology Sweep Implementation Plan

Task: [tasks/001ba-feed-slice-terminology-sweep.md](/Users/vjkotra/projects/katana/tasks/001ba-feed-slice-terminology-sweep.md)
Domain: [docs/domain/ui.md](/Users/vjkotra/projects/katana/docs/domain/ui.md)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove the remaining human-facing "source slice" wording from the
web app and docs so the approved artifact is consistently described as a
feed slice.

**Architecture:** This is a copy-and-test cleanup, not a behavior change. The
work should be limited to UI labels, internal TS identifier renames, focused
component tests, helper test descriptions, and any lingering prose that still
refers to the approved artifact as a source slice. Wire contract names such as
`source_slice_id` stay stable to avoid breaking clients.

**Tech Stack:** Next.js App Router, React, Vitest, Markdown domain docs.

## Global Constraints

- Keep `source_slice_*` JSON keys, route paths, and database names unchanged.
- Use `FeedSlice` / "feed slice" in human-facing prose when referring to the
  approved artifact.
- Do not change runtime behavior, approval semantics, or snapshot wiring.

## Current State

- The domain docs already use feed-slice prose.
- `ApprovalsInbox`, `SourceArtifactsPanel`, and `LaunchRunDialog` still carry
  legacy "source slice" user-facing text and `source*` identifiers.
- The feed API helper tests still describe the old wording in their `it(...)`
  names.

## Objective

Finish the human-facing terminology sweep so the web app and test suite use
feed-slice wording consistently while preserving `source_slice_*` wire names.

## Out of Scope

- Renaming JSON payload keys
- Renaming route segments or database tables
- Changing approval behavior, snapshot semantics, or run behavior

## Blast Radius

- `web/components/approvals/ApprovalsInbox.tsx`
- `web/components/projects/SourceArtifactsPanel.tsx`
- `web/components/runs/LaunchRunDialog.tsx`
- `web/lib/feeds-api.test.ts`
- `web/components/approvals/__tests__/ApprovalsInbox.test.tsx`
- `web/components/projects/__tests__/SourceArtifactsPanel.test.tsx`

## File Changes

| Action | Path |
|--------|------|
| Create | `web/components/approvals/__tests__/ApprovalsInbox.test.tsx` |
| Create | `web/components/projects/__tests__/SourceArtifactsPanel.test.tsx` |
| Modify | `web/components/approvals/ApprovalsInbox.tsx` |
| Modify | `web/components/projects/SourceArtifactsPanel.tsx` |
| Modify | `web/components/runs/LaunchRunDialog.tsx` |
| Modify | `web/lib/feeds-api.test.ts` |

## Tests

- `cd web && npm test -- components/approvals/__tests__/ApprovalsInbox.test.tsx components/projects/__tests__/SourceArtifactsPanel.test.tsx components/runs/LaunchRunDialog.test.tsx lib/feeds-api.test.ts`

## Verification

- `rg -n "source slice|SourceSlice" docs/domain web/components web/lib -g '!**/.next/**'`

Expected:

- only stable wire-field names such as `source_slice_id` and
  `source_slice_version` remain
- no plain-English UI copy or internal TS identifier still uses "source slice"

## Pitfalls

- Leave `source_slice_*` wire names alone until a deliberate API-breaking
  migration is planned
- Avoid renaming route paths or database tables as part of a wording cleanup
- Keep the visible copy and local TS variable names aligned with the
  `Feed` / `FeedSlice` vocabulary from 001aj

## Commit

- `feat(001ba): finish feed slice terminology sweep`

---

### Task 1: Update remaining human-facing copy

**Files:**
- Create: `web/components/approvals/__tests__/ApprovalsInbox.test.tsx`
- Create: `web/components/projects/__tests__/SourceArtifactsPanel.test.tsx`
- Modify: `web/components/approvals/ApprovalsInbox.tsx`
- Modify: `web/components/projects/SourceArtifactsPanel.tsx`
- Modify: `web/components/runs/LaunchRunDialog.tsx`
- Modify: `web/lib/feeds-api.test.ts`

**Interfaces:**
- Consumes: the existing `FeedSlice*` API helpers and records
- Produces: UI labels and focused tests that say "feed slice" instead of
  "source slice"

- [ ] **Step 1: Update the failing assertions and visible labels**

Replace the visible copy and local identifiers in the touched files:

```tsx
// ApprovalsInbox.tsx
<p className="text-sm text-slate-600">Pending feed slices that need a decision.</p>

// SourceArtifactsPanel.tsx
<p className="text-sm text-slate-600">Feed slice versions and approval status.</p>
<div className="text-sm font-semibold text-slate-900">Feed slice</div>
<div className="rounded-xl border border-dashed border-outline-variant bg-surface px-4 py-8 text-sm text-slate-500">
  No feed slices yet.
</div>

// LaunchRunDialog.tsx
setErrorMessage(error instanceof Error ? error.message : "Unable to load feed slices.");
label: "Required feed slice approved & present",

// feeds-api.test.ts
it("uploads a feed slice", async () => { ... });
it("lists feed slices", async () => { ... });

// LaunchRunDialog.tsx internal identifiers
const [sourceSlices, setSourceSlices] = useState<FeedSliceRecord[]>([]);
const selectedSourceSlice = useMemo(() => latestApprovedSlice(sourceSlices), [sourceSlices]);
const requiredSourceSlicePresent = Boolean(selectedSourceSlice);

// rename to:
const [feedSlices, setFeedSlices] = useState<FeedSliceRecord[]>([]);
const selectedFeedSlice = useMemo(() => latestApprovedSlice(feedSlices), [feedSlices]);
const requiredFeedSlicePresent = Boolean(selectedFeedSlice);
```

- [ ] **Step 2: Add focused tests for the copy-heavy components**

Create `ApprovalsInbox.test.tsx` with a minimal render of the component and
assert the heading copy:

```tsx
vi.mock("../../../lib/feed-slice-approval-api", () => ({
  listPendingApprovals: vi.fn().mockResolvedValue([]),
  approveFeedSlice: vi.fn(),
  rejectFeedSlice: vi.fn(),
}));
render(<ApprovalsInbox token="token" role="central_team" />);
expect(screen.getByText("Pending feed slices that need a decision.")).toBeInTheDocument();
```

Create `SourceArtifactsPanel.test.tsx` with a minimal render of the component
and assert the list/empty-state copy:

```tsx
vi.mock("../../../lib/feeds-api", () => ({
  listFeedContracts: vi.fn().mockResolvedValue([
    {
      sourceDefinitionId: "source-1",
      projectId: "project-1",
      sourceType: "csv",
      label: "Customer Extract",
      encoding: "utf-8",
      destinationObjectReferences: null,
      layoutInformation: null,
      copybookText: null,
      status: "active",
      createdAt: "2026-06-30T00:00:00Z",
    },
  ]),
  listFeedSlices: vi.fn().mockResolvedValue([]),
}));
render(<SourceArtifactsPanel projectId="project-1" token="token" role="central_team" />);
expect(screen.getByText("Feed slice versions and approval status.")).toBeInTheDocument();
expect(screen.getByText("No feed slices yet.")).toBeInTheDocument();
```

- [ ] **Step 2b: Keep LaunchRunDialog test aligned with the renamed locals**

The existing `LaunchRunDialog.test.tsx` should continue to pass after the
component renames `sourceSlices` → `feedSlices` and
`selectedSourceSlice` → `selectedFeedSlice`. No new assertions are required
unless the copy in the step panel changes.

- [ ] **Step 3: Run the focused UI tests**

Run:

```bash
cd web && npm test -- \
  components/approvals/__tests__/ApprovalsInbox.test.tsx \
  components/projects/__tests__/SourceArtifactsPanel.test.tsx \
  components/runs/LaunchRunDialog.test.tsx \
  lib/feeds-api.test.ts
```

Expected:

- the updated string assertions pass
- no test output still expects the phrase "source slice" in the touched copy

- [ ] **Step 4: Verify the remaining prose sweep**

Run:

```bash
rg -n "source slice|SourceSlice" docs/domain web/components web/lib -g '!**/.next/**'
```

Expected:

- only stable wire-field names such as `source_slice_id` / `source_slice_version`
  remain
- no plain-English UI copy still uses "source slice"

- [ ] **Step 5: Commit**

```bash
git add web/components/approvals/ApprovalsInbox.tsx \
  web/components/approvals/__tests__/ApprovalsInbox.test.tsx \
  web/components/projects/SourceArtifactsPanel.tsx \
  web/components/projects/__tests__/SourceArtifactsPanel.test.tsx \
  web/components/runs/LaunchRunDialog.tsx \
  web/components/runs/LaunchRunDialog.test.tsx \
  web/lib/feeds-api.test.ts
git commit -m "feat(001ba): finish feed slice terminology sweep"
```
