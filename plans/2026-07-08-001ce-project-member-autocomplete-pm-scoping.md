# Plan: 001ce — PM Scoping, Admin Project Management, Member Autocomplete

- **Task Link:** [tasks/001ce-project-member-autocomplete.md](../tasks/001ce-project-member-autocomplete.md)

> **Implementation status (verified 2026-07-08):** Steps 1–8, 11–13, and 6 are fully implemented in the codebase. Steps 9 and 10 are the only remaining work — admin nav still points to `/projects` and `/admin/assign-pm` (stale); admin project list page does not exist.

## Execution Order

Backend (schema → access → service → routes) → Frontend API client → Frontend pages/components.

---

## Step 1 — DB model: `pm_user_id` on `ProjectRegistry` ✅ DONE

**File:** `engine/src/migrations_engine/db/models.py`

Add after `definition_id`:
```python
pm_user_id: Mapped[str | None] = mapped_column(
    String(36), ForeignKey("users.user_id"), nullable=True, index=True
)
```

---

## Step 2 — Alembic migration `0026_project_pm_user.py` ✅ DONE

**File:** `engine/migrations/versions/0026_project_pm_user.py` — already exists.
Note: actual `down_revision = "2149fa46cde2"`, not `"0025"` as shown below (doc error; migration is applied correctly).

---

## Step 3 — Schemas: `pm_user_id` on response; new request schema ✅ DONE

**File:** `engine/src/migrations_engine/api/schemas.py`

In `ProjectResponse` add after `health`:
```python
pm_user_id: str | None = None
```

Add new schema after `ProjectUpdateRequest`:
```python
class AssignProjectManagerRequest(BaseModel):
    pm_user_id: str
```

---

## Step 4 — Access: PM checks `pm_user_id` instead of global short-circuit ✅ DONE

**File:** `engine/src/migrations_engine/management/access.py`

Add `ProjectRegistry` to imports. Update `user_has_project_access`:

```python
def user_has_project_access(db: Session, *, user: User, project_id: str) -> bool:
    if user.role in {ADMIN_ROLE, READ_ONLY_AUDITOR_ROLE}:
        return True
    if user.role == PM_ROLE:
        pm_user_id = db.scalar(
            select(ProjectRegistry.pm_user_id).where(
                ProjectRegistry.project_id == project_id
            )
        )
        return pm_user_id == user.user_id
    if user.role not in {CENTRAL_TEAM_ROLE, PROJECT_STAKEHOLDER_ROLE}:
        return False
    membership = db.scalar(
        select(ProjectMembership.user_id).where(
            ProjectMembership.project_id == project_id,
            ProjectMembership.user_id == user.user_id,
        )
    )
    return membership is not None
```

---

## Step 5 — Projects service (verify 5a–5d; 5e ✅ DONE)

**File:** `engine/src/migrations_engine/management/projects.py`

### 5a — `create_project`: set `pm_user_id`, remove auto-membership

```python
registry = ProjectRegistry(
    project_id=project_id,
    name=body.name,
    definition_id=definition_id,
    lexicon_scope=body.lexicon_scope,
    pm_user_id=actor.user_id,          # new
    status="active",
)
db.add(definition)
db.add(registry)
db.flush()
# Remove: db.add(ProjectMembership(...))
```

Update audit payload key `auto_member_user_id` → `pm_user_id`.

### 5b — `copy_project`: set `pm_user_id`, remove PM from membership logic

```python
new_registry = ProjectRegistry(
    project_id=new_project_id,
    name=body.name,
    definition_id=new_definition_id,
    lexicon_scope=source_registry.lexicon_scope,
    pm_user_id=actor.user_id,          # new
    status="active",
)
```

Replace the `members_to_add` block. PM no longer goes into membership. Valid roles are `{CENTRAL_TEAM_ROLE, PROJECT_STAKEHOLDER_ROLE}` only:

```python
for user_id in body.stakeholder_user_ids:
    user = _get_active_user(db, user_id)
    if user.role not in {CENTRAL_TEAM_ROLE, PROJECT_STAKEHOLDER_ROLE}:
        raise AuthApiError(
            "invalid_role_for_membership",
            "Only central_team and project_stakeholder users can be assigned project membership.",
            422,
        )
    db.add(ProjectMembership(project_id=new_project_id, user_id=user_id))
```

Remove `PM_ROLE` from import if unused elsewhere in this file.

### 5c — `list_projects`: PM filter via `pm_user_id`

```python
if actor.role == PM_ROLE:
    stmt = stmt.where(ProjectRegistry.pm_user_id == actor.user_id)
elif actor.role in {CENTRAL_TEAM_ROLE, PROJECT_STAKEHOLDER_ROLE}:
    stmt = stmt.join(
        ProjectMembership,
        (ProjectMembership.project_id == ProjectRegistry.project_id)
        & (ProjectMembership.user_id == actor.user_id),
    )
```

### 5d — `_project_response`: include `pm_user_id`

```python
return ProjectResponse(
    ...
    pm_user_id=registry.pm_user_id,
)
```

### 5e — new `assign_project_manager`

```python
def assign_project_manager(
    db: Session,
    *,
    actor: User,
    project_id: str,
    pm_user_id: str,
) -> ProjectResponse:
    registry, definition = _get_project_rows(db, project_id)
    user = _get_active_user(db, pm_user_id)
    if user.role != PM_ROLE:
        raise AuthApiError(
            "invalid_role_for_pm",
            "Only users with role 'pm' can be assigned as project manager.",
            422,
        )
    registry.pm_user_id = pm_user_id
    record_management_audit(
        db,
        project_id=project_id,
        actor_user_id=actor.user_id,
        event_type="project.pm_assigned",
        payload={"project_id": project_id, "pm_user_id": pm_user_id},
    )
    db.commit()
    db.refresh(registry)
    db.refresh(definition)
    return _project_response(registry, definition)
```

---

## Step 6 — Membership service cleanup ✅ DONE

**File:** `engine/src/migrations_engine/management/service.py`

### 6a — `add_project_member`: remove `PM_ROLE` from allowlist

```python
if user.role not in {CENTRAL_TEAM_ROLE, PROJECT_STAKEHOLDER_ROLE}:
    raise AuthApiError(
        "invalid_role_for_membership",
        "Only central_team and project_stakeholder users can be assigned project membership.",
        422,
    )
```

### 6b — `remove_project_member`: remove the 422 guard block entirely

Delete:
```python
user = _get_user_record(db, user_id)
if user.role in {ADMIN_ROLE, PM_ROLE, READ_ONLY_AUDITOR_ROLE}:
    raise AuthApiError("cannot_remove_global_role_membership", ..., 422)
```

Clean up unused imports (`ADMIN_ROLE`, `READ_ONLY_AUDITOR_ROLE`, `PM_ROLE`) — check first that nothing else in the file uses them.

---

## Step 7 — Routes: `PATCH /projects/{id}/manager` ✅ DONE

**File:** `engine/src/migrations_engine/routes/projects.py`

```python
from ..api.deps import get_admin_user          # add
from ..api.schemas import AssignProjectManagerRequest   # add
from ..management.projects import assign_project_manager  # add

@router.patch("/{project_id}/manager", response_model=ProjectResponse)
def patch_project_manager(
    project_id: str,
    body: AssignProjectManagerRequest,
    actor: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
) -> ProjectResponse:
    return assign_project_manager(db, actor=actor, project_id=project_id, pm_user_id=body.pm_user_id)
```

---

## Step 8 — Frontend API: `projects-api.ts` ✅ DONE

**File:** `web/lib/projects-api.ts`

Add `pmUserId: string | null` to `ProjectRecord`; map `pm_user_id` from snake_case in `mapProjectResponse`.

Add function:
```typescript
export async function assignProjectManager(
  token: string,
  projectId: string,
  pmUserId: string,
): Promise<ProjectRecord> {
  const data = await jsonRequest(`/projects/${projectId}/manager`, {
    method: "PATCH",
    token,
    body: { pm_user_id: pmUserId },
  });
  return mapProjectResponse(data);
}
```

---

## Step 9 — Topbar nav: admin "Projects" → `/admin/projects` ⚠️ NOT DONE

**File:** `web/lib/ui-model.ts`

For `admin` role the "Projects" nav item must point to `/admin/projects` (not `/projects`, which admin cannot use):

```typescript
export function navItemsForRole(role: SessionRole): NavItem[] {
  const projectsHref = role === "admin" ? "/admin/projects" : "/projects";
  const common: NavItem[] = [
    { label: "Portfolio", href: "/" },
    { label: "Projects", href: projectsHref },
    { label: "Runs", href: "/runs" },
    { label: "Reconciliation", href: "/reconciliation" },
  ];
  if (canAccessAdmin(role)) {
    return [...common, { label: "Admin", href: "/admin" }];
  }
  return common;
}
```

---

## Step 10 — New admin project list page ⚠️ NOT DONE

**File:** `web/app/admin/projects/page.tsx` (new)

Renders inside the existing admin layout (auth gate already handled by `AdminLayout`).

```tsx
"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { listProjects, type ProjectRecord } from "../../../../lib/projects-api";
import { listUsers, type UserResponse } from "../../../../lib/management-api";
import { loadUiSession } from "../../../../lib/session";

export default function AdminProjectsPage() {
  const [projects, setProjects] = useState<ProjectRecord[]>([]);
  const [users, setUsers] = useState<UserResponse[]>([]);
  const [session] = useState(() => loadUiSession());
  const router = useRouter();

  useEffect(() => {
    if (!session) return;
    void Promise.all([
      listProjects(session.accessToken),
      listUsers(session.accessToken),
    ]).then(([projs, usrs]) => {
      setProjects(projs);
      setUsers(usrs);
    });
  }, [session]);

  function pmLabel(pmUserId: string | null): string {
    if (!pmUserId) return "Unassigned";
    const user = users.find((u) => u.userId === pmUserId);
    return user ? `${user.displayName ?? user.email} (${user.email})` : pmUserId;
  }

  return (
    <main className="min-h-screen bg-surface px-6 py-8 text-slate-800">
      <div className="mx-auto max-w-5xl space-y-6">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">Admin</p>
          <h1 className="text-3xl font-semibold text-slate-900">Project management</h1>
        </div>

        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-outline-variant text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
              <th className="py-2 pr-4">Project</th>
              <th className="py-2 pr-4">Status</th>
              <th className="py-2 pr-4">Project Manager</th>
              <th className="py-2" />
            </tr>
          </thead>
          <tbody>
            {projects.map((p) => (
              <tr key={p.projectId} className="border-b border-outline-variant">
                <td className="py-3 pr-4 font-medium text-slate-900">{p.name}</td>
                <td className="py-3 pr-4 text-slate-600">{p.status}</td>
                <td className="py-3 pr-4 text-slate-600">{pmLabel(p.pmUserId)}</td>
                <td className="py-3 text-right">
                  <button
                    className="rounded-md border border-outline-variant px-3 py-1.5 text-xs font-semibold text-slate-700"
                    onClick={() => router.push(`/admin/projects/${p.projectId}/members`)}
                    type="button"
                  >
                    Manage
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </main>
  );
}
```

Note: `listProjects` in `projects-api.ts` must exist and accept a token. Check current signature; add if missing.

---

## Step 11 — Admin members page: add PM assignment section ✅ DONE

**File:** `web/app/admin/projects/[projectId]/members/page.tsx`

Add state and load `getProject` alongside existing calls:
```typescript
const [project, setProject] = useState<ProjectRecord | null>(null);
const [allUsers, setAllUsers] = useState<UserResponse[]>([]);

// In load effect:
void Promise.all([
  getProject(session.accessToken, params.projectId),
  listProjectMembers(session.accessToken, params.projectId),
  listUsers(session.accessToken),
]).then(([proj, projectMembers, users]) => {
  setProject(proj);
  setAllUsers(users);
  setMembers(joinMembers(projectMembers, users));
});
```

Add PM assignment handler:
```typescript
const handleAssignPm = async (pmUserId: string) => {
  if (!session) return;
  const updated = await assignProjectManager(session.accessToken, params.projectId, pmUserId);
  setProject(updated);
};
```

Add "Project Manager" section above `ProjectMembersPanel`:
- Displays: `project?.pmUserId` resolved to name/email via `allUsers`, or "Unassigned"
- Combobox filtered to `allUsers.filter(u => u.role === "pm")`
- On select → `handleAssignPm(user.userId)`

Combobox pattern (inline, same as Step 12):
- State: `pmQuery`, `pmOpen`, `pmHighlighted`
- Filtered list: PM-role users matching `pmQuery`
- Row format: `email — displayName`

---

## Step 12 — `ProjectMembersPanel.tsx`: autocomplete combobox ✅ DONE

**File:** `web/components/ProjectMembersPanel.tsx`

Add `availableUsers: UserResponse[]` to props (import `UserResponse` from `../lib/management-api`).

Replace the UUID `<input>` + `<form>` with a combobox:

```tsx
const [query, setQuery] = useState("");
const [open, setOpen] = useState(false);
const [highlighted, setHighlighted] = useState(0);

const filtered = availableUsers.filter((u) => {
  const q = query.toLowerCase();
  return u.email.toLowerCase().includes(q) || (u.displayName ?? "").toLowerCase().includes(q);
});

// input: onChange sets query + opens dropdown, onFocus opens
// onKeyDown: ArrowDown/Up moves highlighted, Enter picks filtered[highlighted], Escape closes
// dropdown ul: each li onClick fires onAdd(user.userId) + clears query + closes
```

---

## Step 13 — Wire `availableUsers` in project detail page ✅ DONE

**File:** `web/app/projects/[id]/page.tsx`

Already has `allUsers` state and `refreshMembers` that sets it (from earlier work in this session). Add the filter and prop:

```tsx
const memberUserIds = new Set(members.map((m) => m.userId));
const availableUsers = allUsers.filter((u) => !memberUserIds.has(u.userId));

<ProjectMembersPanel
  availableUsers={availableUsers}
  ...
/>
```

---

## Step 14 — conftest.py: remove PM auto-membership bootstrap

**File:** `engine/tests/conftest.py`

The `before_flush` listener adds a `ProjectMembership` row for the bootstrap admin whenever a `ProjectRegistry` is flushed. After this task, PM membership is not used for access — access is via `pm_user_id`. The listener should set `pm_user_id` on new projects instead of (or in addition to) inserting a membership row.

Review whether any existing tests depend on the bootstrap admin's membership row. Replace the membership insert with:
```python
for proj in new_projects:
    if proj.pm_user_id is None:
        proj.pm_user_id = user.user_id
```

---

## Step 15 — Test updates

**Backend tests to update:**
- `create_project` no longer adds `ProjectMembership`; `registry.pm_user_id` is set
- `list_projects` for PM returns only their projects (by `pm_user_id`)
- `copy_project` `stakeholder_user_ids` rejects PM_ROLE with 422
- `PATCH /projects/{id}/manager`: 403 as PM, 422 for non-PM user ID, 200 on success with updated `pm_user_id`
- `add_project_member` rejects PM_ROLE with 422
- `remove_project_member` no longer raises 422 for PM (guard removed)
- PM loses access after admin reassigns `pm_user_id` to a different user

**Frontend tests to update:**
- `ProjectMembersPanel.test.tsx` — replace UUID input test with combobox interactions (`availableUsers` prop)
- `admin/projects/[projectId]/members/page.test.tsx` — add PM section render + assign interaction
- New test file: `admin/projects/page.test.tsx` — renders project list with PM column, Manage button navigates

---

## Commit

`feat(001ce): pm scoping via pm_user_id, admin project list, member autocomplete`
