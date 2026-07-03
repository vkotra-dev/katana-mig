# Task 001av — Admin User Edit & Delete Controls

**Plan:** `plans/2026-07-03-001av-admin-user-edit-delete-controls.md`

## Domain

- [ui.md](/Users/vjkotra/projects/katana/docs/domain/ui.md)
- [management.md](/Users/vjkotra/projects/katana/docs/domain/management.md)
- [auth.md](/Users/vjkotra/projects/katana/docs/domain/auth.md)
- [security.md](/Users/vjkotra/projects/katana/docs/domain/security.md)
- [api.md](/Users/vjkotra/projects/katana/docs/domain/api.md)

## Current State

- `/admin/users` shows the user list and create-user entry point.
- `/admin/users/new` has a page header and a create form.
- The admin user list does not currently surface an edit entry point.
- The delete action is present in the list UI but remains disabled or unusable.

## Objective

Add user edit access from the admin user management screens and enable the delete
action so central-team operators can update or remove users from the UI.

## Scope

- Add an edit entry point from the admin user list
- Wire the edit flow to the existing user detail/update screen
- Enable the delete button and keep the list state in sync after deletion
- Update the admin user management page tests to cover the new controls

## Out of Scope

- Backend user-management API changes
- Role and permission model changes
- Membership management screens
- Password reset or login flow changes

## Blast Radius

- `web/app/admin/users/page.tsx`
- `web/app/admin/users/[userId]/page.tsx`
- `web/components/UserList.tsx`
- `web/app/admin/users/page.test.tsx`
- `web/app/admin/users/[userId]/page.test.tsx`
- Related management API helpers only if the edit flow needs a missing client call

## File Changes

- Update the user list UI to expose an edit affordance and enable delete
- Confirm the user detail page can be reached from the list
- Adjust tests for the list and detail screens

## Tests

- User list renders an edit control for each user
- Clicking edit routes to the user detail/update page
- Delete invokes the user delete API and removes the user from the list
- User detail page still renders the update form and submits changes

## Verification

- Run the targeted admin user tests in `web`
- Smoke-check the admin users pages in the browser

## Pitfalls

- Keep the control labels consistent with the existing admin UI
- Do not reintroduce duplicate headers inside the shared admin layout
- Ensure delete failure states still surface an error instead of silently
  removing the row

## Commit

- `chore: add admin user edit and delete-controls task`
