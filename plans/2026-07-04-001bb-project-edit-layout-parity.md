# Project Edit Layout Parity Implementation Plan

Task: [tasks/001bb-project-edit-layout-parity.md](/Users/vjkotra/projects/katana/tasks/001bb-project-edit-layout-parity.md)
Domain: [docs/domain/ui.md](/Users/vjkotra/projects/katana/docs/domain/ui.md)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the project edit and project detail screens share the same
metadata layout, while keeping the AI model policy tucked behind a collapsed
accordion in the edit form.

**Architecture:** Keep the change UI-local. Extract the repeated project
metadata layout into a shared component or small shared render helper so both
screens use the same section order and field labels. The edit form keeps the
same submit payload, but the model policy becomes a small stateful accordion
that is collapsed by default and only renders the grid when expanded. The
detail view renders the same grouping in read-only form instead of the current
ad hoc key-value cards.

**Tech Stack:** Next.js App Router, React, Vitest, Markdown domain docs.

## Global Constraints

- Do not change the project API payload shape
- Do not make the detail screen editable
- Preserve the existing project shell and top navigation
- Keep `project_resources` rendering unchanged

## Current State

- `ProjectEditForm` shows the AI model policy as a full-width always-visible
  section of text inputs.
- `ProjectDetailView` uses a separate key-value card grid for project metadata.
- `docs/domain/ui.md` describes the project detail page at a higher level and
  does not yet mention the accordion or layout parity.
- `ProjectDetailView` still stringifies `lexiconScope`; if `001ax` lands first,
  that field should render as plain text instead of JSON.

## Objective

Collapse the AI model policy section behind a disclosure in the edit form and
align the project detail screen’s metadata presentation with the edit layout
for the non-editable fields.

## Out of Scope

- Backend schema or API changes
- Project resources editor changes
- Project creation or deletion
- Any change to model policy semantics or submit behavior

## Blast Radius

- `web/components/projects/ProjectEditForm.tsx`
- `web/components/projects/ProjectDetailView.tsx`
- `web/components/projects/__tests__/ProjectEditForm.test.tsx`
- `web/components/projects/__tests__/ProjectDetailView.test.tsx`
- `docs/domain/ui.md`

## File Changes

| Action | Path |
|--------|------|
| Modify | `web/components/projects/ProjectEditForm.tsx` |
| Modify | `web/components/projects/ProjectDetailView.tsx` |
| Modify | `web/components/projects/__tests__/ProjectEditForm.test.tsx` |
| Modify | `web/components/projects/__tests__/ProjectDetailView.test.tsx` |
| Modify | `docs/domain/ui.md` |

## Tests

- `cd web && npm test -- components/projects/__tests__/ProjectEditForm.test.tsx components/projects/__tests__/ProjectDetailView.test.tsx`

## Verification

- `rg -n "Model Policy|Project Resources|KeyValue|details|summary" web/components/projects docs/domain/ui.md`

Expected:

- the edit form exposes the model policy section behind a disclosure
- the detail view uses the same field ordering and labels for non-editable
  project metadata

## Pitfalls

- Leave the project update payload unchanged
- Keep the edit disclosure default state collapsed so the screen stays compact
- Do not accidentally make the detail page a form
- Native `<details>`/`<summary>` is not a good fit for the tests here; use a
  React state toggle so the model policy inputs are absent from the DOM until
  expanded
- If `001ax` changes `lexiconScope` to plain text first, remove the temporary
  `JSON.stringify` wrapping here instead of duplicating serialization logic

## Commit

- `feat(001bb): align project edit and detail layouts`

---

### Task 1: Add the collapsed model policy section

**Files:**
- Modify: `web/components/projects/ProjectEditForm.tsx`
- Modify: `web/components/projects/__tests__/ProjectEditForm.test.tsx`

**Interfaces:**
- Consumes: the existing `modelPolicy` draft state and submit payload builder
- Produces: a collapsed disclosure for the model policy fields that still
  submits the same payload when expanded/edited

- [ ] **Step 1: Update the failing test**

Add a test that asserts the model policy section is collapsed by default and
reveals the model policy inputs when opened:

```tsx
render(<ProjectEditForm project={project} onSubmit={vi.fn()} />);

expect(screen.getByRole("button", { name: /Model Policy/i })).toBeInTheDocument();
expect(screen.queryByRole("textbox", { name: "Field mapping model" })).not.toBeInTheDocument();

fireEvent.click(screen.getByRole("button", { name: /Model Policy/i }));

expect(screen.getByRole("textbox", { name: "Field mapping model" })).toBeInTheDocument();
expect(screen.getByRole("textbox", { name: "Script generation model" })).toBeInTheDocument();
```

- [ ] **Step 2: Implement the accordion**

Wrap the existing model policy grid in a small stateful accordion so it is
collapsed by default and only renders the fields when expanded:

```tsx
const [modelPolicyOpen, setModelPolicyOpen] = useState(false);

<button
  className="flex w-full items-center justify-between rounded-xl border border-outline-variant bg-surface px-4 py-4 text-left"
  onClick={() => setModelPolicyOpen((value) => !value)}
  type="button"
>
  <span className="text-sm font-semibold text-slate-900">Model Policy</span>
  <span className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">
    {modelPolicyOpen ? "Collapse" : "Expand"}
  </span>
</button>
{modelPolicyOpen ? (
  <div className="mt-4 grid gap-4 lg:grid-cols-3">
    {MODEL_POLICY_FIELDS.map(...)}
  </div>
) : null}
```

- [ ] **Step 3: Run the targeted test**

Run:

```bash
cd web && npm test -- components/projects/__tests__/ProjectEditForm.test.tsx
```

Expected:

- the disclosure starts collapsed
- the model policy inputs appear after expanding the disclosure

### Task 2: Align the project detail layout with the edit screen

**Files:**
- Modify: `web/components/projects/ProjectDetailView.tsx`
- Modify: `web/components/projects/__tests__/ProjectDetailView.test.tsx`
- Modify: `docs/domain/ui.md`

**Interfaces:**
- Consumes: the same project metadata ordering used by the edit surface
- Produces: a read-only detail layout with the same field groupings and labels

- [ ] **Step 1: Update the failing test**

Add or update the detail-view test so it asserts the read-only layout uses the
same field labels and order as the edit screen:

```tsx
render(<ProjectDetailView project={active} />);

expect(screen.getByText("Target DB engine")).toBeInTheDocument();
expect(screen.getByText("Staging schema")).toBeInTheDocument();
expect(screen.getByText("Destination schema")).toBeInTheDocument();
expect(screen.getByText("Dry run")).toBeInTheDocument();
expect(screen.getByText("Destination schema DDL")).toBeInTheDocument();
expect(screen.getByText("Sample policy")).toBeInTheDocument();
```

- [ ] **Step 2: Refactor the detail view to match the edit layout**

Render the read-only metadata in the same section order as the edit form:

```tsx
<div className="grid gap-4 lg:grid-cols-3">
  {/* same field order as ProjectEditForm, but read-only */}
</div>
```

Use the same label order for:
- target database engine
- staging schema
- destination schema
- dry run
- destination schema DDL
- sample policy
- constraints
- unresolved questions
- assumptions
- lexicon scope

- [ ] **Step 3: Update the UI doc**

Adjust `docs/domain/ui.md` so the project detail Overview tab reflects the
shared project metadata layout and the model policy disclosure in edit.

- [ ] **Step 4: Run the focused tests**

Run:

```bash
cd web && npm test -- components/projects/__tests__/ProjectEditForm.test.tsx components/projects/__tests__/ProjectDetailView.test.tsx
```

Expected:

- the project detail view renders the same metadata labels and ordering as the
  edit layout
- the UI doc stays aligned with the screen behavior

- [ ] **Step 5: Commit**

```bash
git add web/components/projects/ProjectEditForm.tsx \
  web/components/projects/ProjectDetailView.tsx \
  web/components/projects/__tests__/ProjectEditForm.test.tsx \
  web/components/projects/__tests__/ProjectDetailView.test.tsx \
  docs/domain/ui.md
git commit -m "feat(001bb): align project edit and detail layouts"
```
