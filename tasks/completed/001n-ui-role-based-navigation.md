# 001n-ui-role-based-navigation

## Domain

- [ui.md](/Users/vjkotra/projects/katana/docs/domain/ui.md)
- [auth.md](/Users/vjkotra/projects/katana/docs/domain/auth.md)
- [management.md](/Users/vjkotra/projects/katana/docs/domain/management.md)
- [security.md](/Users/vjkotra/projects/katana/docs/domain/security.md)

## Objective

Make the top navigation, sidebar, and route entry points respect the
authenticated role so `central_team`, `project_stakeholder`, and
`read_only_auditor` users only see the menus and screens they are allowed to
use.

## Scope

- Role-aware navigation model for topbar and sidebar
- Hidden or disabled admin actions for non-admin roles
- Project-stakeholder menu filtering by membership-scoped views
- Read-only auditor menu restrictions
- Route-level access checks for admin and project-scoped entry points

## Out of Scope

- Auth API wiring
- Management screen implementation details
- Project detail and run-progress content
- Backend authorization policy changes

## Acceptance Criteria

- Central-team users see the admin menu and management entry points
- Project-stakeholder users do not see central-team-only admin actions
- Read-only auditors only see read-only destinations
- Route entry points reject or redirect users whose role does not allow the
  screen
- Menu items are derived from session state, not from request-body role fields

## Test Expectations

- Navigation helpers return role-specific menu sets
- Topbar and sidebar render different items for each role
- Admin links are hidden for non-central-team users
- Route guard tests reject unauthorized access to admin screens
- Membership-scoped project links are not exposed to non-members

