# Plan: 001ce — Project Member Autocomplete + PM Scoping

- **Task Link:** [tasks/001ce-project-member-autocomplete.md](../tasks/001ce-project-member-autocomplete.md)

## Current State

- `ProjectRegistry` has no `pm_user_id` column
- `user_has_project_access` short-circuits `True` for all PM-role users — every PM sees every project
- `ProjectMembersPanel` accepts a raw UUID text input
- `add_project_member` allows `{CENTRAL_TEAM_ROLE, PROJECT_STAKEHOLDER_ROLE, PM_ROLE}`
- `remove_project_member` blocks deletion for `{ADMIN_ROLE, PM_ROLE, READ_ONLY_AUDITOR_ROLE}` (PM guard now redundant after this task)
- `create_project` and `copy_project` auto-add the actor to `ProjectMembership` (no longer needed after pm_user_id)

---

## Execution Order

Backend first (schema → access → routes), then frontend (API client → components → pages).

---

## Step 1 — DB model: add `pm_user_id` to `ProjectRegistry`

**File:** `engine/src/migrations_engine/db/models.py`

Add after `definition_id`:
```python
pm_user_id: Mapped[str | None] = mapped_column(
    String(36), ForeignKey("users.user_id"), nullable=True, index=True
)
```

---

## Step 2 — Alembic migration `0026_project_pm_user.py`

**File:** `engine/migrations/versions/0026_project_pm_user.py`

```python
"""add pm_user_id to project_registry

Revision ID: 0026
Revises: 0025
Create Date: 2026-07-08
"""

from alembic import op
import sqlalchemy as sa

revision = "0026"
down_revision = "0025"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "project_registry",
        sa.Column("pm_user_id", sa.String(36), sa.ForeignKey("users.user_id"), nullable=True, index=True),
    )


def downgrade() -> None:
    op.drop_column("project_registry", "pm_user_id")
```

---

## Step 3 — Schema: add `pm_user_id` to `ProjectResponse`; add `AssignProjectManagerRequest`

**File:** `engine/src/migrations_engine/api/schemas.py`

In `ProjectResponse`, add after `health`:
```python
pm_user_id: str | None = None
```

Add new request schema after `ProjectUpdateRequest`:
```python
class AssignProjectManagerRequest(BaseModel):
    pm_user_id: str
```

---

## Step 4 — Access: update `user_has_project_access` for PM scoping

**File:** `engine/src/migrations_engine/management/access.py`

Remove `PM_ROLE` from the global-access set; add registry lookup for PM:

```python
def user_has_project_access(db: Session, *, user: User, project_id: str) -> bool:
    if user.role in {ADMIN_ROLE, READ_ONLY_AUDITOR_ROLE}:
        return True
    if user.role == PM_ROLE:
        pm_user_id = db.scalar(
            select(ProjectRegistry.pm_user_id).where(ProjectRegistry.project_id == project_id)
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

Add `ProjectRegistry` to the imports in this file.

---

## Step 5 — Projects service: `create_project`, `copy_project`, `list_projects`, `_project_response`, new `assign_project_manager`

**File:** `engine/src/migrations_engine/management/projects.py`

### 5a — `create_project`

Replace PM auto-membership with `pm_user_id` on registry:

```python
registry = ProjectRegistry(
    project_id=project_id,
    name=body.name,
    definition_id=definition_id,
    lexicon_scope=body.lexicon_scope,
    pm_user_id=actor.user_id,   # ← new
    status="active",
)
db.add(definition)
db.add(registry)
db.flush()
# Remove: db.add(ProjectMembership(project_id=project_id, user_id=actor.user_id))
```

Update audit payload: replace `auto_member_user_id` with `pm_user_id`:
```python
payload={
    "project_id": project_id,
    "name": body.name,
    "pm_user_id": actor.user_id,
},
```

### 5b — `copy_project`

Set `pm_user_id` on new registry; remove PM from membership logic:

```python
new_registry = ProjectRegistry(
    project_id=new_project_id,
    name=body.name,
    definition_id=new_definition_id,
    lexicon_scope=source_registry.lexicon_scope,
    pm_user_id=actor.user_id,   # ← new
    status="active",
)
```

Replace the current `members_to_add` block — PM no longer goes into membership.
Valid membership roles are now only `{CENTRAL_TEAM_ROLE, PROJECT_STAKEHOLDER_ROLE}`:

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

Remove `PM_ROLE` import if no longer needed here (check other usages first).

### 5c — `list_projects`

Replace the membership join for PM with a `pm_user_id` filter:

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

### 5d — `_project_response`

Add `pm_user_id` to the returned schema:
```python
return ProjectResponse(
    ...
    pm_user_id=registry.pm_user_id,
)
```

### 5e — new `assign_project_manager` function

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

## Step 6 — Membership service cleanup

**File:** `engine/src/migrations_engine/management/service.py`

### 6a — `add_project_member` allowlist

Remove `PM_ROLE`:
```python
if user.role not in {CENTRAL_TEAM_ROLE, PROJECT_STAKEHOLDER_ROLE}:
    raise AuthApiError(
        "invalid_role_for_membership",
        "Only central_team and project_stakeholder users can be assigned project membership.",
        422,
    )
```

### 6b — `remove_project_member` guard

Remove the PM/admin guard entirely — `add_project_member` now prevents non-membership roles from being added:
```python
# Delete these lines:
user = _get_user_record(db, user_id)
if user.role in {ADMIN_ROLE, PM_ROLE, READ_ONLY_AUDITOR_ROLE}:
    raise AuthApiError("cannot_remove_global_role_membership", ..., 422)
```

Clean up unused imports: `ADMIN_ROLE`, `READ_ONLY_AUDITOR_ROLE` (check if referenced elsewhere first).

---

## Step 7 — Route: new `PATCH /projects/{id}/manager`

**File:** `engine/src/migrations_engine/routes/projects.py`

Add import:
```python
from ..api.deps import get_admin_user
from ..api.schemas import AssignProjectManagerRequest
from ..management.projects import assign_project_manager
```

Add route:
```python
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

## Step 8 — Frontend API: `projects-api.ts`

**File:** `web/lib/projects-api.ts`

Add `pmUserId: string | null` to `ProjectRecord` (snake_case `pm_user_id` → camelCase in mapper).

Add new function:
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

## Step 9 — Frontend component: `ProjectMembersPanel.tsx` autocomplete

**File:** `web/components/ProjectMembersPanel.tsx`

Replace the UUID text input form with a combobox. Add `availableUsers: UserResponse[]` to `ProjectMembersPanelProps`. The combobox:

- State: `query: string`, `open: boolean`, `highlighted: number`
- Filters `availableUsers` by `email.includes(query)` or `displayName?.includes(query)` (case-insensitive)
- Dropdown shows when `open && filtered.length > 0`
- Each row: `email — displayName (role)`, click fires `onAdd(user.userId)` and clears input
- Keyboard: `ArrowDown`/`ArrowUp` moves highlight, `Enter` selects highlighted, `Escape` closes

```tsx
export interface ProjectMembersPanelProps {
  projectId: string;
  members: ProjectMember[];
  availableUsers: UserResponse[];   // ← new
  warning?: string;
  loading?: boolean;
  onAdd: (userId: string) => Promise<void> | void;
  onRemove: (userId: string) => Promise<void> | void;
}
```

The import for `UserResponse` comes from `../lib/management-api`.

---

## Step 10 — Frontend: wire `availableUsers` into Members tab

**File:** `web/app/projects/[id]/page.tsx`

Add `allUsers` state (loaded alongside members):
```typescript
const [allUsers, setAllUsers] = useState<UserResponse[]>([]);
```

Update `refreshMembers` to also set `allUsers`:
```typescript
async function refreshMembers(token: string) {
  const [memberRows, users] = await Promise.all([
    listProjectMembers(token, id),
    listUsers(token),
  ]);
  setAllUsers(users);
  setMembers(joinMembers(memberRows, users));
}
```

Compute `availableUsers` (exclude current members) and pass down:
```typescript
const memberUserIds = new Set(members.map((m) => m.userId));
const availableUsers = allUsers.filter((u) => !memberUserIds.has(u.userId));
```

Pass to panel:
```tsx
<ProjectMembersPanel
  availableUsers={availableUsers}
  members={members}
  onAdd={handleMemberAdd}
  onRemove={handleMemberRemove}
  projectId={id}
  warning={memberWarning}
/>
```

---

## Step 11 — Frontend: admin PM assignment in members page

**File:** `web/app/admin/projects/[projectId]/members/page.tsx`

Add state:
```typescript
const [project, setProject] = useState<ProjectRecord | null>(null);
const [allUsers, setAllUsers] = useState<UserResponse[]>([]);
```

Fetch project on load (admin can call `GET /projects/{id}` — backend allows it):
```typescript
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

Add `handleAssignPm`:
```typescript
const handleAssignPm = async (pmUserId: string) => {
  if (!session) return;
  const updated = await assignProjectManager(session.accessToken, params.projectId, pmUserId);
  setProject(updated);
};
```

Add "Project Manager" section above `ProjectMembersPanel`:
- Shows `project.pmUserId` resolved to email/name from `allUsers`, or "Unassigned"
- Autocomplete dropdown filtered to `allUsers.filter(u => u.role === "pm")`
- On select, calls `handleAssignPm(user.userId)`

The PM autocomplete can reuse the same combobox logic from `ProjectMembersPanel` — either extract a shared `UserCombobox` component or inline the same pattern.

---

## Step 12 — Test updates

**`engine/tests/`** — update or add tests:
- `create_project` no longer adds `ProjectMembership`; PM sees only their project via `pm_user_id`
- `copy_project` sets `pm_user_id`; `stakeholder_user_ids` validation rejects PM_ROLE
- `PATCH /projects/{id}/manager` returns 403 for PM, 422 for non-PM user, 200 on success
- `add_project_member` rejects PM_ROLE with 422
- `remove_project_member` no longer raises 422 for PM (guard removed)

**`web/`** — update:
- `ProjectMembersPanel.test.tsx` — replace UUID input test with autocomplete behavior
- `admin/projects/[projectId]/members/page.test.tsx` — add PM section render and assign tests
- `ProjectNavigationTabs.test.tsx` — no change needed

**conftest.py** — the `before_flush` listener adds a `ProjectMembership` for the bootstrap admin. Since admin is never a member now (blocked by `add_project_member`), review whether this listener should instead set `pm_user_id` on new projects. The conftest bootstrap admin is used for seeding — check if any tests rely on admin membership rows.

---

## Commit

`feat(001ce): pm scoping via pm_user_id, member autocomplete picker, admin pm reassignment`
