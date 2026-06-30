# 001i-ui-template-foundation

**Plan:** `plans/2026-06-29-001i-ui-template-foundation.md`

## Domain

- [ui.md](/Users/vjkotra/projects/katana/docs/domain/ui.md)
- [auth.md](/Users/vjkotra/projects/katana/docs/domain/auth.md)
- [security.md](/Users/vjkotra/projects/katana/docs/domain/security.md)

## Objective

Repurpose the reusable UI templates from `vkotra-dev/mockmigration` into the
Katana codebase as the first executable UI slice: a tokenized shell, role-aware
navigation primitives, and a login template that no longer depends on demo data
or fake local state.

## Scope

- Port the presentational shell patterns from `Topbar`, `Sidebar`, and
  `LoginView`
- Replace the mockmigration dark demo styling with the Katana token set
- Introduce reusable nav/session view-model helpers for role-based rendering
- Keep the result framework-agnostic enough for the later UI tasks to consume

## Out of Scope

- Portfolio and project-detail business data
- Password reset flows
- API implementation or backend auth wiring
- Demo `localStorage` state, seeded data, or fake login shortcuts

## Acceptance Criteria

- The shell layout follows the supplied Katana visual token set
- The template components are reusable and do not depend on mock app context
- Login, sidebar, and topbar templates are driven by session/role inputs only
- No demo data or hardcoded developer credentials remain in the UI templates

## Test Expectations

- The shell renders with the Katana surface, primary, and mono token classes
- The login template accepts credentials without prefilled demo accounts
- The topbar and sidebar render role-aware navigation without app-context mocks
- The template layer can be reused by the later UI tasks without refactoring

