# Task: 001ce — Project Member Management: Autocomplete Picker + PM Scoping

## Status
Ready

## Problem

Three gaps after 001cd:

**Gap 1 — Add-member UX:** `ProjectMembersPanel` accepts a raw UUID. PM cannot
discover user IDs without leaving the project context.

**Gap 2 — PM visibility is global:** `user_has_project_access` short-circuits
`True` for all PM-role users, so every PM sees every project. There is no
per-project PM assignment.

**Gap 3 — No PM handover:** If a PM leaves or a project is reassigned, there is
no mechanism to change which PM owns a project.

## Solution

### Part A — Autocomplete member picker (PM-facing)

Replace the User ID text input in `ProjectMembersPanel` with a combobox:
- `availableUsers` prop receives the full user list minus current members
- Searching filters by email or display name (case-insensitive substring)
- Each dropdown row shows `email — display_name (role)`
- Selecting immediately calls `onAdd(userId)` — no extra confirm step
- Keyboard: arrow-up/down, Enter to select, Escape to dismiss

### Part B — `pm_user_id` on ProjectRegistry (new column)

Add `pm_user_id: Mapped[str | None]` (nullable FK → `users.user_id`) to
`ProjectRegistry`. This column is the single source of truth for which PM owns
a project.

**Auto-population on project initiation:**
- `create_project` sets `pm_user_id = actor.user_id` (actor is always PM, gated
  by `get_pm_user`)
- `copy_project` sets `pm_user_id = actor.user_id` on the new project

**Access control change — PM loses global access:**
- Remove `PM_ROLE` from the global-access set in `user_has_project_access`
- Add PM check: `if user.role == PM_ROLE: return registry.pm_user_id == user.user_id`
- `list_projects` for PM filters by `ProjectRegistry.pm_user_id == user.user_id`
- Result: a PM only sees the projects they initiated or were assigned to

**Side effects of this change:**
- PM auto-membership in `ProjectMembership` is no longer needed for access
  (access is driven by `pm_user_id`). Remove PM from the `ProjectMembership`
  auto-add in `create_project` and `copy_project`
- Remove PM from `add_project_member` allowlist (PM access is registry-based,
  not membership-based)
- Remove the `remove_project_member` 422 guard for `PM_ROLE` (no longer needed)

### Part C — Admin PM reassignment

Admin can change which PM owns a project when the need arises (PM leaves team,
project handover, etc.):

**Backend:**
- New endpoint `PATCH /projects/{id}/manager` (admin-only via `get_admin_user`)
- Body: `{ "pm_user_id": "<uuid>" }` — validates user exists and has `pm` role
- Sets `ProjectRegistry.pm_user_id`; returns updated project record

**Frontend — admin members page** (`/admin/projects/[projectId]/members`):
- "Project Manager" section at the top of the page
- Shows current PM: display name + email, or "Unassigned" if null
- Admin-only autocomplete dropdown filtered to PM-role users
- On selection, calls `PATCH /projects/{id}/manager` then refreshes

Note: Admin cannot access project detail pages (`canAccessProject` returns
`false` for admin), so this control lives in the admin panel, not the project
tabs.

## Files Changed

**Backend:**
- `engine/src/migrations_engine/db/models.py` — add `pm_user_id` to `ProjectRegistry`
- `engine/src/migrations_engine/migrations/versions/<new>.py` — Alembic migration (nullable, no backfill)
- `engine/src/migrations_engine/management/access.py` — update `user_has_project_access` to check `pm_user_id` for PM role
- `engine/src/migrations_engine/management/projects.py` — set `pm_user_id` in `create_project` / `copy_project`; remove PM auto-membership; update `list_projects` PM filter
- `engine/src/migrations_engine/management/service.py` — remove PM from `add_project_member` allowlist; remove PM from `remove_project_member` guard
- `engine/src/migrations_engine/routes/projects.py` — new `PATCH /projects/{id}/manager` (admin-only); return `pm_user_id` in project response

**Frontend:**
- `web/components/ProjectMembersPanel.tsx` — replace UUID input with autocomplete combobox; add `availableUsers: UserResponse[]` prop
- `web/app/projects/[id]/page.tsx` — pass `availableUsers` down to `ProjectMembersPanel`
- `web/app/admin/projects/[projectId]/members/page.tsx` — add "Project Manager" section with current PM display and admin reassignment control
- `web/lib/projects-api.ts` — add `pmUserId` to `ProjectRecord`; add `assignProjectManager(token, projectId, pmUserId)` API call

## Out of Scope

- Notifying the new PM on reassignment
- Enforcing that every project must have a PM (nullable is intentional for legacy rows)
- Fuzzy / ranked search in autocomplete

## Verification

1. PM creates a project → `pm_user_id` is set to the creating PM automatically
2. PM logs in → sees only their own projects; other PMs' projects not visible
3. PM opens a project → Members tab → types partial email → non-member users
   appear → select → user added to roster
4. Admin opens `/admin/projects/{id}/members` → "Project Manager" section shows
   current PM → admin picks a new PM from dropdown → PM field updates
5. After admin reassignment, original PM no longer sees the project; new PM does
6. `GET /projects/{id}` returns `pmUserId` in payload
7. `PATCH /projects/{id}/manager` with PM role returns 403
8. `PATCH /projects/{id}/manager` with a non-PM user ID returns 422
9. TypeScript compiles with no new errors
