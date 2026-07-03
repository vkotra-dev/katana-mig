# Task 001aw — Project Edit

**Plan:** `plans/2026-07-03-001aw-project-edit.md`

## Domain

- [ui.md](/Users/vjkotra/projects/katana/docs/domain/ui.md)
- [project.md](/Users/vjkotra/projects/katana/docs/domain/project.md)
- [api.md](/Users/vjkotra/projects/katana/docs/domain/api.md)

## Current State

- The project list and project detail pages already exist.
- The detail screen shows project overview data and tabs, but it has no edit
  entry point.
- The project update API exists, but the UI does not surface a project edit
  flow.

## Objective

Add a project edit flow so central-team users can update project metadata from
the project detail area.

## Scope

- Add an edit entry point on the project detail screen
- Build the project edit UI using the existing project update API
- Keep the edit flow aligned with the current project detail layout and top nav
- Add or update tests for the edit entry point and update submission

## Out of Scope

- Project creation
- Project archive/delete behavior
- Source, run, or approval workflows
- Backend project API changes unless the UI needs a missing client helper

## Acceptance Criteria

- Project detail shows a clear edit action for authorized users
- The edit UI loads the current project values
- Saving sends the update payload to the project update endpoint
- Successful save returns the user to the updated project detail view
- Errors are shown inline instead of silently failing

## Test Expectations

- Edit action is visible on the project detail page for central-team users
- Edit form pre-fills existing project values
- Submit calls the update API with the expected payload
- Update failure renders an error message and preserves the form state

