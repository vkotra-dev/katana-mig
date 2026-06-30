# 001e-ui-shell

> **SUPERSEDED** — Covered by:
> - `001i` (ui-template-foundation) — shell layout, tokens, Topbar/Sidebar/LoginView
> - `001l` (ui-auth-api-wiring, **completed**) — auth and session routing
> - `001n` (ui-role-based-navigation, **completed**) — role-based nav
>
> Do not implement. Archive this task.

## Domain

- [ui.md](/Users/vjkotra/projects/katana/docs/domain/ui.md)
- [auth.md](/Users/vjkotra/projects/katana/docs/domain/auth.md)
- [security.md](/Users/vjkotra/projects/katana/docs/domain/security.md)

## Objective

Build the Katana UI shell to strictly follow the supplied Stitch screen
`web application/stitch/projects/2270475859168384623/screens/163360a01fe241b1969cfe14f8caa0b1`
and the provided CSS token set, while preserving the role-based operator model
described in `docs/domain/ui.md`.

## Scope

- App shell layout and navigation based on the supplied HTML scaffold
- Core CSS variables and typography tokens from the provided design system
- Role-aware navigation and content regions for `central_team`,
  `project_stakeholder`, and `read_only_auditor`
- Dashboard/portfolio-style landing structure and project-scoped views
- Login and auth-aware shell states needed to route the user correctly

## Out of Scope

- New visual direction that departs from the supplied screen
- Backend business logic beyond the minimum UI state needed to render routes
- Migration workflow changes unrelated to the UI shell
- Reworking the domain contract pages

## Acceptance Criteria

- The UI uses the supplied token set as the source of truth for colors,
  typography, spacing, and radius
- The overall layout matches the supplied shell: sticky top nav, left-aligned
  brand, main nav, search/action cluster, and content canvas
- Role-based views remain aligned to `docs/domain/ui.md`
- The UI does not introduce a competing design language

## Test Expectations

- The rendered shell uses the supplied CSS custom properties
- The top navigation and content canvas reflect the supplied layout structure
- Role-based nav items render according to the authenticated session role
- Project-scoped views hide or show content according to membership and role

