# 001g-ui-auth-and-login

> **SUPERSEDED** — Login screen and session-aware routing were shipped in
> `001l` (ui-auth-api-wiring, **completed**).
> Do not implement. Archive this task.

## Domain

- [ui.md](/Users/vjkotra/projects/katana/docs/domain/ui.md)
- [auth.md](/Users/vjkotra/projects/katana/docs/domain/auth.md)
- [security.md](/Users/vjkotra/projects/katana/docs/domain/security.md)

## Objective

Add the login and session-aware routing slice for the UI so authenticated
users land on the correct shell and unauthenticated users are routed to login.

## Scope

- Login screen
- Session-aware route selection
- Role-aware landing behavior for `central_team`, `project_stakeholder`, and
  `read_only_auditor`
- Minimal authentication-state helper for UI rendering

## Out of Scope

- Password reset
- Role assignment and membership management
- Portfolio/project data rendering
- Backend authentication protocol changes beyond the UI contract

## Acceptance Criteria

- Unauthenticated users see the login surface
- Authenticated users land on a role-appropriate view
- The UI reads role from session state, not from request bodies
- Project-stakeholder views remain membership-scoped

## Test Expectations

- Unauthenticated state renders login
- Central-team state renders the correct landing route
- Project-stakeholder state uses membership-aware routing
- Read-only auditor state renders a read-only landing surface

