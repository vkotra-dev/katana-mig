# Project Resources Rich Text Editor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the plain `projectResources` textarea in the project edit form with a Tiptap rich-text editor (Bold / Bullets / Center), restructure the form to a three-column grid, and update the detail view to render the stored HTML.

**Architecture:** A focused `ProjectResourcesEditor` component wraps a Tiptap editor instance with a minimal three-button toolbar. `ProjectEditForm` swaps the textarea for this component and the outer form grid moves to `grid-cols-3`; `projectResources` spans all three columns as the last field. The stored value is Tiptap HTML output (`editor.getHTML()`). `ProjectDetailView` replaces its plain `<textarea readOnly>` with a `<div dangerouslySetInnerHTML>` so the HTML renders correctly.

**Tech Stack:** Next.js App Router, React, Tiptap (`@tiptap/react`, `@tiptap/starter-kit`, `@tiptap/extension-text-align`), Vitest + Testing Library

## Global Constraints

- Store as HTML string — `editor.getHTML()` is passed as `projectResources` in the submit payload
- Toolbar contains exactly three actions: Bold, Bullet List, Center alignment
- `projectResources` is always the last field in the edit form
- `projectResources` spans `col-span-3` in the three-column form grid
- Do not log `projectResources` content in errors (may contain credentials)
- `dangerouslySetInnerHTML` is acceptable in the detail view because only `central_team` operators write this field
- Tiptap browser-API requirements mean editor tests are smoke tests only (render + button presence); do not test editor state mutations in jsdom

---

## File Changes

| Action | Path |
|--------|------|
| Install | `@tiptap/react`, `@tiptap/starter-kit`, `@tiptap/extension-text-align` |
| Create | `web/components/projects/ProjectResourcesEditor.tsx` |
| Create | `web/components/projects/__tests__/ProjectResourcesEditor.test.tsx` |
| Modify | `web/components/projects/ProjectEditForm.tsx` |
| Modify | `web/components/projects/ProjectDetailView.tsx` |
| Modify | `web/components/projects/__tests__/ProjectEditForm.test.tsx` |
| Modify | `web/components/projects/__tests__/ProjectDetailView.test.tsx` |

---

### Task 1: Install Tiptap and build the editor component

**Files:**
- Install packages
- Create: `web/components/projects/ProjectResourcesEditor.tsx`
- Create: `web/components/projects/__tests__/ProjectResourcesEditor.test.tsx`

**Interfaces:**
- Produces:
  ```tsx
  interface ProjectResourcesEditorProps {
    value: string;                        // initial HTML content
    onChange: (html: string) => void;     // called on every editor change
  }
  export function ProjectResourcesEditor({ value, onChange }: ProjectResourcesEditorProps)
  ```

- [ ] **Step 1: Write the failing tests**

Create `web/components/projects/__tests__/ProjectResourcesEditor.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ProjectResourcesEditor } from "../ProjectResourcesEditor";

describe("ProjectResourcesEditor", () => {
  it("renders without crashing with empty initial value", () => {
    render(<ProjectResourcesEditor value="" onChange={vi.fn()} />);
    expect(screen.getByRole("button", { name: "Bold" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Bullet list" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Center" })).toBeInTheDocument();
  });

  it("renders without crashing with initial HTML content", () => {
    render(
      <ProjectResourcesEditor
        value="<p><strong>PROD</strong></p><ul><li>Host: 10.0.0.1</li></ul>"
        onChange={vi.fn()}
      />
    );
    expect(screen.getByRole("button", { name: "Bold" })).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run the tests and confirm they fail**

Run: `cd web && npm test -- components/projects/__tests__/ProjectResourcesEditor.test.tsx`
Expected: `ProjectResourcesEditor` module not found.

- [ ] **Step 3: Install Tiptap packages**

Run: `cd web && npm install @tiptap/react @tiptap/starter-kit @tiptap/extension-text-align`
Expected: packages install without peer-dependency errors.

- [ ] **Step 4: Create the editor component**

Create `web/components/projects/ProjectResourcesEditor.tsx`:

```tsx
"use client";

import { useEditor, EditorContent } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";
import TextAlign from "@tiptap/extension-text-align";

export interface ProjectResourcesEditorProps {
  value: string;
  onChange: (html: string) => void;
}

export function ProjectResourcesEditor({ value, onChange }: ProjectResourcesEditorProps) {
  const editor = useEditor({
    extensions: [
      StarterKit,
      TextAlign.configure({ types: ["heading", "paragraph"] }),
    ],
    content: value,
    onUpdate({ editor }) {
      onChange(editor.getHTML());
    },
  });

  return (
    <div className="rounded-md border border-outline-variant bg-white">
      <div className="flex gap-1 border-b border-outline-variant px-2 py-1">
        <button
          type="button"
          aria-label="Bold"
          onClick={() => editor?.chain().focus().toggleBold().run()}
          className={`rounded px-2 py-1 text-sm font-bold text-slate-700 hover:bg-surface-container ${
            editor?.isActive("bold") ? "bg-surface-container" : ""
          }`}
        >
          B
        </button>
        <button
          type="button"
          aria-label="Bullet list"
          onClick={() => editor?.chain().focus().toggleBulletList().run()}
          className={`rounded px-2 py-1 text-sm text-slate-700 hover:bg-surface-container ${
            editor?.isActive("bulletList") ? "bg-surface-container" : ""
          }`}
        >
          • List
        </button>
        <button
          type="button"
          aria-label="Center"
          onClick={() => editor?.chain().focus().setTextAlign("center").run()}
          className={`rounded px-2 py-1 text-sm text-slate-700 hover:bg-surface-container ${
            editor?.isActive({ textAlign: "center" }) ? "bg-surface-container" : ""
          }`}
        >
          ≡ Center
        </button>
        <button
          type="button"
          aria-label="Align left"
          onClick={() => editor?.chain().focus().setTextAlign("left").run()}
          className="rounded px-2 py-1 text-sm text-slate-700 hover:bg-surface-container"
        >
          ≡ Left
        </button>
      </div>
      <EditorContent
        editor={editor}
        className="prose prose-sm min-h-48 max-w-none px-3 py-2 text-slate-900 focus-within:outline-none"
      />
    </div>
  );
}
```

- [ ] **Step 5: Re-run the tests and confirm they pass**

Run: `cd web && npm test -- components/projects/__tests__/ProjectResourcesEditor.test.tsx`
Expected: both tests pass.

- [ ] **Step 6: Commit**

```bash
git add web/components/projects/ProjectResourcesEditor.tsx \
        web/components/projects/__tests__/ProjectResourcesEditor.test.tsx \
        web/package.json web/package-lock.json
git commit -m "feat(001ay): add ProjectResourcesEditor with bold/bullets/center toolbar"
```

---

### Task 2: Wire editor into the edit form and restructure grid

**Files:**
- Modify: `web/components/projects/ProjectEditForm.tsx`
- Modify: `web/components/projects/__tests__/ProjectEditForm.test.tsx`

**Interfaces:**
- Consumes: `ProjectResourcesEditor({ value, onChange })` from Task 1
- Consumes: `project.projectResources: string | null` from `ProjectRecord` (001ax)
- Produces: form submits `projectResources` as the Tiptap HTML string

**Form grid target layout:**

```
[ Project name                            col-span-3 ]
[ Goal                                    col-span-3 ]
[ Exec envs        ] [ Target DB engine ] [ Staging schema ]   (3 cols)
[ Dry run checkbox ]                                           (1 col)
[ Destination schema DDL                  col-span-3 ]
[ Sample policy                           col-span-3 ]
[ Constraints                             col-span-3 ]
[ Unresolved questions                    col-span-3 ]
[ Assumptions                             col-span-3 ]
[ Project Resources (rich editor)         col-span-3 ]
```

- [ ] **Step 1: Write the failing tests**

In `web/components/projects/__tests__/ProjectEditForm.test.tsx`, add:

```tsx
it("includes projectResources in the submit payload", async () => {
  const onSubmit = vi.fn().mockResolvedValue(undefined);
  render(<ProjectEditForm project={project} onSubmit={onSubmit} />);

  fireEvent.submit(screen.getByRole("button", { name: "Save changes" }).closest("form") as HTMLFormElement);

  await waitFor(() =>
    expect(onSubmit).toHaveBeenCalledWith(
      expect.objectContaining({
        projectResources: expect.any(String),
      })
    )
  );
});

it("renders the Project Resources editor last in the form", () => {
  render(<ProjectEditForm project={project} onSubmit={vi.fn()} />);
  const buttons = screen.getAllByRole("button");
  const saveIndex = buttons.findIndex((b) => b.textContent === "Save changes");
  const boldIndex = buttons.findIndex((b) => b.getAttribute("aria-label") === "Bold");
  // Bold toolbar button appears before Save changes
  expect(boldIndex).toBeLessThan(saveIndex);
});
```

- [ ] **Step 2: Run the tests and confirm they fail**

Run: `cd web && npm test -- components/projects/__tests__/ProjectEditForm.test.tsx`
Expected: form does not include `projectResources` in payload yet; no Bold button present.

- [ ] **Step 3: Update the form**

In `web/components/projects/ProjectEditForm.tsx`:

**Add the import at the top:**
```tsx
import { ProjectResourcesEditor } from "./ProjectResourcesEditor";
```

**Add state for projectResources alongside the other useState calls:**
```tsx
const [projectResources, setProjectResources] = useState(project.projectResources ?? "");
```

**Remove `environment` state and field** (dropped in 001ax):
```tsx
// Remove: const [environment, setEnvironment] = useState(project.environment ?? "");
```

**Update onSubmit payload** — replace `environment` with `projectResources`:
```tsx
void onSubmit({
  name: name.trim(),
  goal: normalizeOptionalText(goal),
  projectResources: projectResources || null,
  executionEnvironments: parseList(executionEnvironments),
  domainConfig: {
    targetDbEngine: targetDbEngine || null,
    stagingSchema: normalizeOptionalText(stagingSchema),
    dryRun,
    samplePolicy: parsedSamplePolicy,
    destinationSchemaDdl: normalizeOptionalText(destinationSchemaDdl),
    environments: project.domainConfig?.environments ?? null,
  },
});
```

**Replace the form body** — change the outer container from `space-y-5` to a three-column grid and add `projectResources` last:

```tsx
<form
  className="rounded-2xl border border-outline-variant bg-surface-container p-8 shadow-sm"
  onSubmit={...}
>
  {/* Header */}
  <div className="col-span-3 mb-5 space-y-2">
    <h1 className="text-2xl font-semibold text-slate-900">Edit project</h1>
    <p className="text-sm text-slate-600">
      Update the project metadata and destination configuration without leaving the project shell.
    </p>
  </div>

  <div className="grid grid-cols-3 gap-x-6 gap-y-5">
    {/* Project name — full width */}
    <div className="col-span-3 space-y-2">
      <label className="block text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">Project name</label>
      <input aria-label="Project name" ... />
    </div>

    {/* Goal — full width */}
    <div className="col-span-3 space-y-2">
      <label className="block text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">Goal</label>
      <textarea aria-label="Goal" ... />
    </div>

    {/* Execution environments — col 1 */}
    <div className="space-y-2">
      <label ...>Execution environments</label>
      <textarea aria-label="Execution environments" ... />
    </div>

    {/* Target database engine — col 2 */}
    <div className="space-y-2">
      <label ...>Target database engine</label>
      <select aria-label="Target database engine" ...>...</select>
    </div>

    {/* Staging schema — col 3 */}
    <div className="space-y-2">
      <label ...>Staging schema</label>
      <input aria-label="Staging schema" ... />
    </div>

    {/* Dry run — col 1 */}
    <div className="space-y-2">
      <label className="flex items-center gap-3 ...">
        <input type="checkbox" ... /> Dry run
      </label>
    </div>

    {/* Destination schema DDL — full width */}
    <div className="col-span-3 space-y-2">
      <label ...>Destination schema DDL</label>
      <textarea aria-label="Destination schema DDL" ... />
    </div>

    {/* Sample policy — full width */}
    <div className="col-span-3 space-y-2">
      <label ...>Sample policy</label>
      <textarea aria-label="Sample policy" ... />
    </div>

    {/* Constraints — full width */}
    <div className="col-span-3 space-y-2">
      <label ...>Constraints</label>
      <textarea aria-label="Constraints" ... />
    </div>

    {/* Unresolved questions — full width */}
    <div className="col-span-3 space-y-2">
      <label ...>Unresolved questions</label>
      <textarea aria-label="Unresolved questions" ... />
    </div>

    {/* Assumptions — full width */}
    <div className="col-span-3 space-y-2">
      <label ...>Assumptions</label>
      <textarea aria-label="Assumptions" ... />
    </div>

    {/* Project Resources — full width, LAST */}
    <div className="col-span-3 space-y-2">
      <label className="block text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">
        Project Resources
      </label>
      <p className="text-xs text-slate-500">
        Infrastructure notes: server addresses, ports, credentials, VPN details. Visible only to central team operators.
      </p>
      <ProjectResourcesEditor
        value={projectResources}
        onChange={setProjectResources}
      />
    </div>

    {/* Submit row — full width */}
    <div className="col-span-3 flex justify-end gap-3 pt-2">
      {errorMessage && (
        <p role="alert" className="text-sm text-red-600">{errorMessage}</p>
      )}
      {formError && (
        <p role="alert" className="text-sm text-red-600">{formError}</p>
      )}
      <button
        type="submit"
        disabled={loading}
        className="rounded-md bg-primary px-4 py-2 text-sm font-semibold text-white disabled:opacity-50"
      >
        {loading ? "Saving…" : "Save changes"}
      </button>
    </div>
  </div>
</form>
```

- [ ] **Step 4: Re-run the tests and confirm they pass**

Run: `cd web && npm test -- components/projects/__tests__/ProjectEditForm.test.tsx`
Expected: all tests pass including the new `projectResources` payload and ordering tests.

- [ ] **Step 5: Commit**

```bash
git add web/components/projects/ProjectEditForm.tsx \
        web/components/projects/__tests__/ProjectEditForm.test.tsx
git commit -m "feat(001ay): wire rich editor into edit form, restructure to 3-col grid"
```

---

### Task 3: Update the detail view to render HTML

**Files:**
- Modify: `web/components/projects/ProjectDetailView.tsx`
- Modify: `web/components/projects/__tests__/ProjectDetailView.test.tsx`

**Interfaces:**
- Consumes: `project.projectResources: string | null` — stored as Tiptap HTML
- Produces: rendered HTML in the detail view using `dangerouslySetInnerHTML`

- [ ] **Step 1: Write the failing tests**

In `web/components/projects/__tests__/ProjectDetailView.test.tsx`, replace the existing `projectResources` test:

```tsx
it("renders projectResources HTML as formatted content", () => {
  render(
    <ProjectDetailView
      project={{
        ...project,
        projectResources: "<p><strong>PROD</strong></p><ul><li>Host: 10.0.0.1</li></ul>",
      }}
    />
  );
  // The rendered HTML should contain the formatted elements, not raw markup
  expect(screen.getByText("PROD")).toBeInTheDocument();
  expect(screen.getByText("Host: 10.0.0.1")).toBeInTheDocument();
});

it("renders nothing for projectResources when null", () => {
  render(<ProjectDetailView project={{ ...project, projectResources: null }} />);
  expect(screen.queryByLabelText("Project Resources")).not.toBeInTheDocument();
});
```

- [ ] **Step 2: Run the tests and confirm they fail**

Run: `cd web && npm test -- components/projects/__tests__/ProjectDetailView.test.tsx`
Expected: the existing read-only textarea does not render the HTML as elements.

- [ ] **Step 3: Update ProjectDetailView**

In `web/components/projects/ProjectDetailView.tsx`, replace the `projectResources` textarea block (added in 001ax):

```tsx
{project.projectResources && (
  <div className="space-y-1">
    <h3 className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">
      Project Resources
    </h3>
    <div
      aria-label="Project Resources"
      className="prose prose-sm max-w-none rounded-md border border-outline-variant bg-surface px-4 py-3 text-slate-800"
      dangerouslySetInnerHTML={{ __html: project.projectResources }}
    />
  </div>
)}
```

- [ ] **Step 4: Re-run the tests and confirm they pass**

Run: `cd web && npm test -- components/projects/__tests__/ProjectDetailView.test.tsx`
Expected: both new tests pass; existing tests pass.

- [ ] **Step 5: Run the full web test suite for regressions**

Run: `cd web && npm test`
Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
git add web/components/projects/ProjectDetailView.tsx \
        web/components/projects/__tests__/ProjectDetailView.test.tsx
git commit -m "feat(001ay): render project resources HTML in detail view"
```

---

## Verification

1. Component smoke tests: `cd web && npm test -- components/projects/__tests__/ProjectResourcesEditor.test.tsx`
2. Form tests: `cd web && npm test -- components/projects/__tests__/ProjectEditForm.test.tsx`
3. Detail view tests: `cd web && npm test -- components/projects/__tests__/ProjectDetailView.test.tsx`
4. Full web suite (no regressions): `cd web && npm test`
5. Browser smoke check: open the project edit page, verify the three-column grid, the rich editor at the bottom, and the Bold/Bullet/Center buttons all work

## Commit Summary

```
feat(001ay): add ProjectResourcesEditor with bold/bullets/center toolbar
feat(001ay): wire rich editor into edit form, restructure to 3-col grid
feat(001ay): render project resources HTML in detail view
```
