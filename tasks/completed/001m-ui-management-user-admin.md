# 001m-ui-management-user-admin

## Domain

- [ui.md](/Users/vjkotra/projects/katana/docs/domain/ui.md)
- [management.md](/Users/vjkotra/projects/katana/docs/domain/management.md)
- [auth.md](/Users/vjkotra/projects/katana/docs/domain/auth.md)
- [security.md](/Users/vjkotra/projects/katana/docs/domain/security.md)
- [api.md](/Users/vjkotra/projects/katana/docs/domain/api.md)

## Objective

Build the central-team administrative user management surface, including user
creation, profile updates, soft-delete, and project membership management, and
wire it to the `/users` and project-membership API endpoints.

## Scope

- Central-team user list and detail screens
- User creation form for `central_team`
- User update form for `display_name`, `role`, and `status`
- Soft-delete action for users
- Project membership list/add/remove screens
- Shared management client helpers for users and memberships

## Out of Scope

- Login and password-reset flows
- Role-based menu hiding and route guards
- Project detail or run progress views
- Backend user-management changes

## Acceptance Criteria

- Central-team operators can create a new user from the UI
- User creation sends the API payload required by `POST /users`
- User detail pages can update role and status through `PATCH /users/{user_id}`
- Soft-delete calls `DELETE /users/{user_id}`
- Membership screens list, add, and remove project stakeholders through the
  membership endpoints

## Test Expectations

- User creation submits email, password, display name, and role to `/users`
- User update submits only editable fields to `PATCH /users/{user_id}`
- Soft-delete calls the delete endpoint and hides the removed user from the list
- Membership add/remove actions call the correct project membership endpoints
- Duplicate membership warning is rendered when the API returns the warning

