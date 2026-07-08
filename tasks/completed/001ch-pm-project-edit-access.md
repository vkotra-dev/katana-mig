# Task: 001ch — Project Edit Access: Gate to PM Role in Frontend UI

## Status
Ready

## Problem

After the backend PM/Admin role model migration (task 001cd), editing a project
via `PATCH /projects/{project_id}` is gated by `get_pm_user` (restricting access
exclusively to users with the `pm` role).

However, the frontend project details page (`web/app/projects/[id]/page.tsx`)
renders the "Edit" button only for users with the `central_team` role. When a PM
views the page, they don't see the edit link, and if a central team user clicks
the edit link (which they see), the backend rejects their update request with a
403 Forbidden.

## Solution

1. Update the "Edit" button gating condition on `web/app/projects/[id]/page.tsx`
   from `role === "central_team"` to `role === "pm"`.
2. Update the corresponding frontend unit test in
   `web/app/projects/[id]/page.test.tsx` to assert that the "Edit" button is
   rendered for a user with the `pm` role, and not for `central_team`.

## Files Changed

- `web/app/projects/[id]/page.tsx` — change Edit link condition to `role === "pm"`
- `web/app/projects/[id]/page.test.tsx` — update Edit link test to use `pm` role session

## Out of Scope

- Changing backend route permissions (already correct)

## Verification

1. Log in as a PM user.
2. Go to the project details page.
3. Verify that the "Edit" button is visible and clicking it allows editing the project.
4. Log in as a Central Team user.
5. Verify that the "Edit" button is not visible.
6. Verify that TypeScript compiles and all unit tests pass.
