# Task 001ay — Project Resources Rich Text Editor

**Plan:** `plans/2026-07-03-001ay-project-resources-rich-editor.md`

**Depends on:** 001ax (project_resources field), 001aw (project edit form)

## Domain

- [ui.md](/Users/vjkotra/projects/katana/docs/domain/ui.md)
- [project.md](/Users/vjkotra/projects/katana/docs/domain/project.md)
- [security.md](/Users/vjkotra/projects/katana/docs/domain/security.md)

## Current State

- `ProjectEditForm` lays out fields in a vertical `space-y-5` stack with
  nested two-column grids for compact pairs.
- `projectResources` (added in 001ax) is a plain textarea.
- The project detail view renders `projectResources` as a read-only plain
  textarea with monospace font.

## Objective

Replace the plain `projectResources` textarea in the project edit form with a
minimal rich-text editor (Tiptap) that supports bold, bullet lists, and center
alignment. Restructure the form layout to a three-column grid so compact fields
sit in columns and `projectResources` spans all three columns at the bottom.
Update the detail view to render the stored HTML output correctly.

## Scope

- Install Tiptap minimal packages: `@tiptap/react`, `@tiptap/starter-kit`,
  `@tiptap/extension-text-align`
- Create `ProjectResourcesEditor` component: toolbar (Bold / Bullets / Center)
  + Tiptap editor area
- Modify `ProjectEditForm`: replace textarea with `ProjectResourcesEditor`,
  restructure outer grid to three columns, move `projectResources` to last
  position spanning all three columns
- Modify `ProjectDetailView`: replace the read-only plain textarea with an HTML
  render of the stored content

## Out of Scope

- Markdown storage format (store as HTML via Tiptap)
- Image upload, tables, or font colour
- Undo/redo toolbar buttons (Tiptap provides keyboard shortcuts natively)
- Any other form field changes

## Acceptance Criteria

- The edit form renders a toolbar with Bold, Bullet List, and Center actions
- Clicking Bold wraps selected text in `<strong>`; Bullet List inserts a `<ul>`;
  Center centers the current paragraph
- `projectResources` is the last field in the form and spans the full form width
- Compact fields (name, execution environments, target DB engine, staging
  schema, dry run) sit in a three-column grid above it
- Saving the form sends the Tiptap HTML output as `projectResources`
- The detail view renders the stored HTML (not raw markup)

## Test Expectations

- `ProjectResourcesEditor` renders without crashing with an initial HTML value
- The three toolbar buttons (Bold, Bullets, Center) are present in the DOM
- Submitting `ProjectEditForm` includes `projectResources` in the payload
- `ProjectDetailView` renders `projectResources` HTML content rather than a
  plain textarea when the field is non-null

## Pitfalls

- Tiptap uses browser APIs not available in jsdom; keep editor tests as smoke
  tests (render + button presence) rather than testing editor state mutations
- `dangerouslySetInnerHTML` in the detail view is acceptable here because
  `projectResources` is only written by authenticated `central_team` operators
- Do not log or emit `projectResources` content in error messages (may contain
  credentials from the infra template)

## Commit

- `feat(001ay): add rich text editor for project resources field`
