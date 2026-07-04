# Task 001bc - Project Model Policy Default Hints

**Plan:** `plans/2026-07-04-001bc-project-model-policy-default-hints.md`

**Depends on:** 001bb (Project Edit Layout Parity)

## Domain

- [ui.md](/Users/vjkotra/projects/katana/docs/domain/ui.md)
- [project.md](/Users/vjkotra/projects/katana/docs/domain/project.md)
- [api.md](/Users/vjkotra/projects/katana/docs/domain/api.md)

## Current State

- The project edit form shows the model policy override inputs, but the helper
  text only says "Global default" and does not tell the operator which model is
  actually being used globally.
- The project detail view does not show the model policy section at all, so
  there is no read-only view of the effective model and its source.
- The UI has no dedicated API surface for the resolved `engine.yaml` model
  defaults, so the frontend cannot truthfully render the live global values.

## Objective

Expose the resolved AI model defaults from `engine/config/engine.yaml` through
an authenticated API and render those defaults in the project edit and project
detail screens so operators can see both the effective model name and where it
comes from.

## Scope

- Add a read-only API for the resolved AI model defaults
- Fetch the defaults on the project edit and project detail routes
- Show the global default model name beneath each model override input in edit
- Show model label and source text in the project detail view
- Update the UI and API domain docs so the new language is explicit

## Out of Scope

- Changing how model overrides are stored on projects
- Changing the project update payload shape
- Exposing provider API keys or environment variable names in the UI
- Changing how the backend resolves models for AI tasks

## Acceptance Criteria

- Each model override input in project edit shows the current global default
  model name from `engine.yaml` directly below the input
- The project detail view shows a read-only model policy section with the model
  label, the effective model name, and a source line that distinguishes project
  override from global default
- The UI does not hardcode model IDs; it reads them from the backend defaults
  response
- The existing project save payload still only sends override values

## Test Expectations

- API tests verify the defaults endpoint returns the current resolved model
  names and does not leak provider config
- Edit-screen tests verify the helper text shows the global default name under
  each override field
- Detail-screen tests verify the model policy section shows label/source
  information for each task slot

## Pitfalls

- Do not add the defaults to the project record itself; they belong in the
  runtime AI config
- Keep the edit screen informational only; blank inputs still mean "use global
  default"
- Keep the detail screen read-only
- The new defaults endpoint should remain auth-protected like the rest of the UI
  API surface

## Commit

- `feat(001bc): show global model defaults in project UI`
