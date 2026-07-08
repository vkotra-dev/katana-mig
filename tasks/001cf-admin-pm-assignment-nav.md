# Task: 001cf — Admin PM Assignment: Top-Nav Dropdown + Standalone Assignment Page

## Status
Ready

## Problem

The current "Assign PM to Project" flow lives inside the admin project-members
page (`/admin/projects/[projectId]/members`), which requires the admin to first
know the project ID and navigate to a per-project URL. This is unintuitive and
inaccessible from the top navigation.

Additionally, the `Admin` link in the top nav goes directly to `/admin/users`,
giving no discovery for the PM assignment feature. There is no way for an admin
to land on a single page and pick both a project and a PM together.

## Solution

### Part A — Admin top-nav becomes a dropdown

Replace the single `Admin` nav-link in the `Topbar` with a dropdown button
that exposes:

- **Manage Users** → `/admin/users`
- **Assign PM to Project** → `/admin/assign-pm`

The dropdown must:
- Toggle open/closed on click
- Close when the user clicks outside
- Be visible only to roles for which `canAccessAdmin` returns `true`

### Part B — New `/admin/assign-pm` page

A standalone page with two autocomplete pickers and a submit button:

**Project picker:**
- Calls `GET /projects?include_archived=false` (active projects only)
- Autocomplete filters by project name (case-insensitive substring)
- Displays `project name` in the dropdown row
- Selecting a project sets the chosen project state

**PM picker:**
- Calls `GET /users` then filters to `role === "pm"` and `status === "active"`
- Autocomplete filters by email or display name
- Displays `email — display_name` in the dropdown row
- Selecting a PM sets the chosen PM state

**Submit:**
- Active only when both project and PM are selected
- Calls `PATCH /projects/{projectId}/manager` with `{ pm_user_id }`
- On success: shows an inline success banner and resets both pickers
- On error: shows the API error message inline

### Part C — Remove the per-project admin entry point

Remove the `Manage Members & PM` button from the project detail page
(`/projects/[id]/page.tsx`) since the assignment is now accessible from the
top nav. Keep the `/admin/projects/[projectId]/members` page itself intact for
admin-initiated stakeholder/operator membership management.

## Files Changed

**Frontend only — no backend changes:**
- `web/lib/ui-model.ts` — add `children?: NavItem[]` to `NavItem`; return sub-items for Admin
- `web/components/Topbar.tsx` — render dropdown for nav items that have `children`
- `web/app/admin/assign-pm/page.tsx` — new page (project + PM dual-autocomplete + submit)
- `web/app/projects/[id]/page.tsx` — remove `Manage Members & PM` button

## Out of Scope

- Changing the backend assign-manager endpoint (already implemented in 001ce)
- Membership management within the per-project admin members page
- Role-specific nav items beyond the Admin dropdown

## Verification

1. Log in as `admin` → top nav shows "Admin ▾" dropdown
2. Dropdown contains "Manage Users" and "Assign PM to Project"
3. Click "Manage Users" → navigates to `/admin/users`
4. Click "Assign PM to Project" → navigates to `/admin/assign-pm`
5. `/admin/assign-pm` page: project autocomplete shows only active projects
6. PM autocomplete shows only active users with role `pm`
7. Selecting both and submitting calls `PATCH /projects/{id}/manager` → success banner
8. Submitting with non-PM user is blocked by the backend (422 bubbles to error banner)
9. Log in as `pm` → top nav Admin dropdown shows (canAccessAdmin is true for pm); Assign PM option is NOT present (pm cannot reassign managers)
10. Project detail page no longer shows `Manage Members & PM` button
11. TypeScript compiles with no errors; all Vitest tests pass
