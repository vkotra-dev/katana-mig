# Task: 001cd — PM and Admin Role Model

## Status
Ready

## Problem

`central_team` currently conflates three unrelated concerns: project lifecycle
(create/copy), user management (create/edit/delete users), and in-project
operations (feeds, AI, mapping, lookups). It is impossible to give an operator
in-project access without also giving them admin rights over users and project
creation.

## Solution

Introduce two new roles and narrow `central_team` to pure in-project operators.

| Role | Capabilities |
|---|---|
| `admin` _(new)_ | Create users, list users, view user, update user, delete user |
| `pm` _(new)_ | Create project, copy project, assign `central_team` operators and `project_stakeholder` members to a project |
| `central_team` _(narrowed)_ | All in-project operations (upload feeds, trigger AI, mapping hints, AI trace, lookup management, generate snapshots, codegen) — requires project membership |
| `project_stakeholder` _(unchanged)_ | Approve feed slices, mapping snapshots, lookup fibers — requires project membership |
| `read_only_auditor` _(unchanged)_ | View-only across all projects |

## Key Behaviour Changes

**`central_team` loses global project access** — Currently `user_has_project_access`
returns `True` for any `central_team` user with no membership check. After this
change, `central_team` uses the same membership join as `project_stakeholder`.

**`add_project_member` accepts `central_team` members** — Currently the guard
at `management/service.py:166` rejects any role other than `project_stakeholder`.
Remove that restriction; valid roles for membership are `central_team` and
`project_stakeholder`.

**User management gates move from `central_team` to `admin`** — All routes in
`routes/users.py` currently depend on `get_central_team_user`. Switch to
`get_admin_user`.

**Project creation and membership assignment move to `pm`** — Routes in
`routes/projects.py` for create, copy, and member management switch to
`get_pm_user`.

## Files Changed

**Backend:**
- `engine/src/migrations_engine/roles.py`
- `engine/src/migrations_engine/api/deps.py`
- `engine/src/migrations_engine/management/access.py`
- `engine/src/migrations_engine/management/service.py`
- `engine/src/migrations_engine/management/projects.py`
- `engine/src/migrations_engine/routes/users.py`
- `engine/src/migrations_engine/routes/projects.py`

**Frontend:**
- `web/lib/session.ts`
- `web/lib/ui-model.ts`
- `web/components/projects/ProjectTable.tsx`

## Out of Scope

- Database schema migration (role is stored as a plain string on `User.role` — no schema change needed)
- Data migration: existing `central_team` users need role reassignment to `pm`, `admin`, or `central_team` (operational, not code)
- Seeding / fixture updates

## Verification

1. Log in as `admin` user → can create/edit/delete users; cannot create projects
2. Log in as `pm` user → can create and copy projects; can assign members; cannot create users
3. Log in as `central_team` user with no membership → project list is empty
4. PM assigns `central_team` user to project → that user now sees the project
5. `central_team` user can upload feeds, trigger AI, manage mappings inside their assigned project
6. `project_stakeholder` approval flow unchanged
7. `read_only_auditor` view-only unchanged
8. TypeScript compiles with no errors
