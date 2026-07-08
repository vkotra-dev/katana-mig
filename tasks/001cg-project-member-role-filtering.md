# Task: 001cg — Project Member Autocomplete: Filter Out Admin and PM Roles

## Status
Ready

## Problem

Currently, the project members autocomplete dropdown (available on both the
operators' project members tab and the admin's project membership management
screen) displays all users in the system who are not yet members. This includes
users with `admin` and `pm` roles.

However, the backend validation in `add_project_member` strictly rejects
membership additions for users with roles other than `central_team` and
`project_stakeholder` (raising a `invalid_role_for_membership` 422 error).
Listing `admin` and `pm` users in the selection picker leads to a broken UX when
selection is attempted.

## Solution

Modify the client-side filtering logic for the available members autocomplete
ratios on both views:
1. **Operator Project Members Tab** (`web/app/projects/[id]/page.tsx`)
2. **Admin Project Members Management Page** (`web/app/admin/projects/[projectId]/members/page.tsx`)

Only users whose roles are `central_team` or `project_stakeholder` should be
available for project membership assignment. Filter out users with `admin` or
`pm` roles.

## Files Changed

- `web/app/projects/[id]/page.tsx` — update `availableUsers` filtering
- `web/app/admin/projects/[projectId]/members/page.tsx` — update `availableUsers` filtering

## Out of Scope

- Modifying the backend endpoints (the validation is already correct)
- Changing role schemas

## Verification

1. Log in as a PM or Admin.
2. Navigate to a project's members page.
3. Open the "Search users" autocomplete picker.
4. Verify that users with the role `admin` or `pm` are not listed in the options.
5. Verify that only eligible users with `central_team` or `project_stakeholder` roles can be found and assigned.
6. Run unit/integration tests to ensure no regressions.
