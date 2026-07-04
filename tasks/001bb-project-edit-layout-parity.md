# Task 001bb — Project Edit Layout Parity

**Plan:** `plans/2026-07-04-001bb-project-edit-layout-parity.md`

**Depends on:** 001aw (Project Edit)

## Domain

- [ui.md](/Users/vjkotra/projects/katana/docs/domain/ui.md)
- [project.md](/Users/vjkotra/projects/katana/docs/domain/project.md)

## Current State

- `ProjectEditForm` renders the AI model policy as an always-expanded three-column
  grid, which is visually loud for a section most operators rarely change.
- `ProjectDetailView` renders project metadata with a `KeyValue` card grid that
  does not match the edit screen layout.
- The project edit and project detail surfaces therefore diverge in both
  structure and emphasis.

## Objective

Make the project edit and project detail screens use the same project metadata
layout pattern, with the AI model policy moved behind a collapsed accordion in
the edit form and the detail view rendering non-editable fields in the same
section order and visual rhythm as the edit screen.

## Scope

- Collapse the AI model policy section in the project edit form
- Align the project detail view’s read-only layout with the edit form’s field
  grouping and order
- Update the project detail/edit tests to cover the new disclosure and layout
- Update the UI domain doc so the project-detail contract matches the rendered
  screens

## Out of Scope

- Backend project API changes
- Project resources editor behavior
- Project creation
- Any changes to `project_resources` HTML rendering

## Acceptance Criteria

- The AI model policy section in the edit form is collapsed by default and can
  be expanded when needed
- The project detail view uses the same metadata grouping and field order as the
  edit screen for non-editable fields
- The project detail screen no longer uses a separate one-off card pattern for
  metadata
- Existing submit payloads and API behavior remain unchanged

## Test Expectations

- Project edit tests verify the model policy accordion is collapsed by default
  and expands to show the model inputs
- Project detail tests verify the read-only layout uses the same field labels
  and ordering as the edit screen
- No regression in form submission payloads

## Pitfalls

- Do not change the project update payload shape
- Keep the edit collapse behavior purely presentational; the model policy values
  still submit exactly as before
- Avoid turning the detail view into an editable form

## Commit

- `feat(001bb): collapse model policy and align project detail layout`
