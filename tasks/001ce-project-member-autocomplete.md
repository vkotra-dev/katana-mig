# Task: 001ce — PM Scoping, Admin Project Management, Member Autocomplete

## Status
Ready

## Problem

Four gaps after 001cd:

1. **PM sees all projects** — `user_has_project_access` returns `True` for every PM regardless of project. There is no per-project PM ownership.
2. **No PM handover** — no mechanism for admin to reassign a project to a different PM.
3. **Admin has no project view** — `/admin` only shows user management. Admin cannot see projects or navigate to any project management function.
4. **Add-member UX** — `ProjectMembersPanel` takes a raw UUID. PM cannot discover users without leaving the project.

## Solution

### Part A — `pm_user_id` column (backend, new migration)

Add `pm_user_id: Mapped[str | None]` (nullable FK → `users.user_id`) to `ProjectRegistry`.

- `create_project` and `copy_project` auto-set `pm_user_id = actor.user_id`
- PM access changes: `user_has_project_access` checks `registry.pm_user_id == user.user_id` instead of short-circuiting `True`
- `list_projects` for PM filters by `ProjectRegistry.pm_user_id == actor.user_id`
- PM auto-membership in `ProjectMembership` is removed (access is now registry-based)
- `add_project_member` allowlist narrows to `{central_team, project_stakeholder}` only
- `remove_project_member` 422 guard for PM/admin removed (no longer needed)
- New endpoint: `PATCH /projects/{id}/manager` (admin-only) — sets `pm_user_id` after validating target user has `pm` role
- `GET /projects/{id}` returns `pm_user_id` in response

### Part B — Admin project list (new page)

Admin needs a project view to find and assign PMs. Add `/admin/projects`:

- Lists all projects (name, status, current PM name or "Unassigned")
- Each row links to `/admin/projects/[projectId]/members`
- Update Topbar nav: for `admin` role, the "Projects" nav item points to `/admin/projects` instead of `/projects`

### Part C — Admin PM assignment (existing admin members page)

Extend `/admin/projects/[projectId]/members`:

- Fetch project alongside members to get current `pm_user_id`
- "Project Manager" section at the top shows current PM (name + email) or "Unassigned"
- Admin-only autocomplete dropdown filtered to PM-role users → on select calls `PATCH /projects/{id}/manager`

### Part D — Member autocomplete picker (PM-facing)

Replace the raw UUID input in `ProjectMembersPanel` with a combobox:

- New prop `availableUsers: UserResponse[]` (user list minus current members)
- Filters by email or display name (case-insensitive substring)
- Each row: `email — displayName (role)`
- Select fires `onAdd(userId)` immediately; keyboard navigation (arrows, Enter, Escape)

## Files Changed

**Backend:**
- `engine/src/migrations_engine/db/models.py`
- `engine/migrations/versions/0026_project_pm_user.py` (new)
- `engine/src/migrations_engine/api/schemas.py`
- `engine/src/migrations_engine/management/access.py`
- `engine/src/migrations_engine/management/projects.py`
- `engine/src/migrations_engine/management/service.py`
- `engine/src/migrations_engine/routes/projects.py`

**Frontend:**
- `web/lib/ui-model.ts` — admin "Projects" nav → `/admin/projects`
- `web/lib/projects-api.ts` — `pmUserId` on `ProjectRecord`; `assignProjectManager()`
- `web/app/admin/projects/page.tsx` (new) — admin project list
- `web/app/admin/projects/[projectId]/members/page.tsx` — add PM section
- `web/components/ProjectMembersPanel.tsx` — autocomplete combobox
- `web/app/projects/[id]/page.tsx` — pass `availableUsers` to panel

## Out of Scope

- Notifying the new PM on reassignment
- Enforcing every project has a PM (nullable is intentional for legacy rows)
- Fuzzy/ranked search in autocomplete

## Verification

1. PM creates project → `pm_user_id` set automatically; PM sees only that project in their list
2. Second PM logs in → does not see the first PM's project
3. Admin opens `/admin/projects` → sees all projects with PM column
4. Admin clicks a project → `/admin/projects/{id}/members` → changes PM via dropdown → PM field updates
5. After reassignment: original PM loses project from list; new PM gains it
6. PM opens project → Members tab → types partial email → dropdown shows non-member users → select → user added
7. `PATCH /projects/{id}/manager` as PM returns 403; with non-PM user ID returns 422
8. TypeScript compiles clean; all tests pass
