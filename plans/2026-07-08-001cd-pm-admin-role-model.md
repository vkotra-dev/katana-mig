# Plan: 001cd — PM and Admin Role Model

- **Task Link:** [tasks/001cd-pm-admin-role-model.md](../tasks/001cd-pm-admin-role-model.md)

## Current State

Currently, the `central_team` role is a monolith that:
1. Manages users (create, edit, delete)
2. Manages projects globally (create, copy, archive, update, manage memberships)
3. Performs in-project operations (triggers AI, uploads feeds, designs mappings, lookups, generates snapshots, codegen)

Any user with the `central_team` role has global access to all projects without project membership checking. This violates the principle of least privilege and prevents delegating operational tasks to team members without giving them administrative control.

## Objective

Refactor the role model by introducing two new global roles (`admin` and `pm`) and narrowing the existing `central_team` role to scoped project operations:

| Role | Scope | Key Capabilities |
|---|---|---|
| `admin` *(new)* | Global | Full CRUD over users |
| `pm` *(new)* | Global | CRUD over projects, manages project memberships |
| `central_team` *(narrowed)* | Project-specific | Manages feeds, mappings, lookups, codegen. **Requires project membership.** |
| `project_stakeholder` | Project-specific | Approves slices, mapping snapshots, lookup fibers. **Requires project membership.** |
| `read_only_auditor` | Global | View-only across all projects |

## Blast Radius

### Backend Files
- `engine/src/migrations_engine/roles.py`: Define `admin` and `pm` roles.
- `engine/src/migrations_engine/api/deps.py`: Add `get_admin_user` and `get_pm_user` dependencies.
- `engine/src/migrations_engine/management/access.py`: Add `require_admin`, `require_pm`, `require_project_stakeholder` rules, and restrict `central_team` global access in `user_has_project_access`.
- `engine/src/migrations_engine/management/service.py`: Allow `central_team` as a valid membership role in `add_project_member`.
- `engine/src/migrations_engine/routes/users.py`: Gate all user CRUD routes under `get_admin_user`.
- `engine/src/migrations_engine/routes/projects.py`: Gate project create/copy/membership under `get_pm_user`.
- Other `routes/*.py` files: Update endpoints using `get_central_team_user` to call `require_project_access`.
- `routes/feed_slice_approval.py` & `routes/mapping.py`: Change slice & mapping approval endpoints to allow `project_stakeholder` instead of `central_team`.

### Frontend Files
- `web/lib/session.ts` & `web/lib/ui-model.ts`: Map `admin` and `pm` roles.
- `web/components/projects/ProjectTable.tsx` & dashboard components: Hide/show UI elements based on the new roles.

---

## Detailed Backend Modifications

### 1. `roles.py`
Add constants:
```python
ADMIN_ROLE: Final = "admin"
PM_ROLE: Final = "pm"
```
Update `PLATFORM_ROLES`:
```python
PLATFORM_ROLES: Final[tuple[tuple[str, str], ...]] = (
    (ADMIN_ROLE, "Platform administrator; manages system users"),
    (PM_ROLE, "Project manager; creates projects and manages memberships"),
    (CENTRAL_TEAM_ROLE, "In-project operator; manages feeds, maps, lookups"),
    (PROJECT_STAKEHOLDER_ROLE, "Project stakeholder; approves feed slices, mapping snapshots, lookup fibers"),
    (READ_ONLY_AUDITOR_ROLE, "View-only access across projects"),
)
```

### 2. `management/access.py`
Define access assertions:
```python
def require_admin(user: User) -> None:
    if user.role != ADMIN_ROLE:
        raise AuthApiError("forbidden", "Administrator access is required.", 403)

def require_pm(user: User) -> None:
    if user.role != PM_ROLE:
        raise AuthApiError("forbidden", "Project manager access is required.", 403)

def require_project_stakeholder(user: User) -> None:
    if user.role != PROJECT_STAKEHOLDER_ROLE:
        raise AuthApiError("forbidden", "Business approval requires project_stakeholder role.", 403)

def require_admin_or_self(actor: User, target_user_id: str) -> None:
    if actor.user_id != target_user_id:
        require_admin(actor)
```
Update `user_has_project_access` to strip global access from `central_team`:
```python
def user_has_project_access(db: Session, *, user: User, project_id: str) -> bool:
    if user.role in {PM_ROLE, READ_ONLY_AUDITOR_ROLE}:
        return True
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

### 3. `api/deps.py`
Add dependencies:
```python
def get_admin_user(user: User = Depends(get_current_user)) -> User:
    from ..management.access import require_admin
    require_admin(user)
    return user

def get_pm_user(user: User = Depends(get_current_user)) -> User:
    from ..management.access import require_pm
    require_pm(user)
    return user
```

### 4. `management/service.py`
Adjust `add_project_member` validation at line 166:
```python
    if user.role not in {CENTRAL_TEAM_ROLE, PROJECT_STAKEHOLDER_ROLE}:
        raise AuthApiError(
            "invalid_role_for_membership",
            "Only central_team and project_stakeholder users can be assigned project membership.",
            422,
        )
```

### 5. `management/projects.py`
In `list_projects`, restrict `central_team` and `project_stakeholder` to their memberships:
```python
    if actor.role in {CENTRAL_TEAM_ROLE, PROJECT_STAKEHOLDER_ROLE}:
        stmt = stmt.join(
            ProjectMembership,
            (ProjectMembership.project_id == ProjectRegistry.project_id)
            & (ProjectMembership.user_id == actor.user_id),
        )
```

### 6. `routes/users.py`
Update dependencies and access check:
- `get_users`: Depends on `get_admin_user`
- `post_user`: Depends on `get_admin_user`
- `get_user_by_id`: Depends on `get_current_user`, calls `require_admin_or_self`
- `patch_user`: Depends on `get_admin_user`
- `delete_user`: Depends on `get_admin_user`

### 7. `routes/projects.py`
Update dependencies:
- `post_project`: Depends on `get_pm_user`
- `post_project_copy`: Depends on `get_pm_user`
- `get_project_members`: Depends on `get_pm_user`
- `post_project_member`: Depends on `get_pm_user`
- `delete_project_member`: Depends on `get_pm_user`
- `patch_project` & `post_project_archive`: Depends on `get_pm_user` (projects CRUD operations belong to the Project Manager)

### 8. Access checks in operational routes
For every route using `Depends(get_central_team_user)` (except users/projects management), add:
`require_project_access(db, user=actor, project_id=project_id)`
These include:
- `routes/analysis.py`: `post_source_analysis`
- `routes/feeds.py`: `post_source_contract`, `post_source_copybook`, `post_source_slice`
- `routes/lookup.py`: `post_lookup_value_map`, `post_lookup_snapshot`

### 9. Slice and Mapping approvals
Change approvals to require the `project_stakeholder` role:
- `routes/feed_slice_approval.py`:
  - `post_source_slice_approve` & `post_source_slice_reject`: Depend on `get_current_user`, check `require_project_access` and `require_project_holder`.
- `routes/mapping.py`:
  - `post_mapping_approve` & `post_mapping_reject`: Depend on `get_current_user`, check `require_project_access` and `require_project_holder`.

---

## Detailed Frontend Modifications

### 1. `web/lib/session.ts`
Map roles:
```typescript
export type SessionRole = "admin" | "pm" | "central_team" | "project_stakeholder" | "read_only_auditor";
```
Adjust routing logic based on roles:
- `admin` navigates to `/admin/users` on load.
- `pm` navigates to `/dashboard`.
- `central_team` navigates to `/dashboard`.

### 2. `web/lib/ui-model.ts`
Define visibility helpers for UI actions:
```typescript
export function canManageUsers(role: SessionRole): boolean {
  return role === "admin";
}

export function canManageProjects(role: SessionRole): boolean {
  return role === "pm";
}

export function canPerformOperations(role: SessionRole): boolean {
  return role === "pm" || role === "central_team";
}

export function canApprove(role: SessionRole): boolean {
  return role === "project_stakeholder";
}
```

### 3. UI conditional rendering
- Hide "Create Project" button on Dashboard if `role !== "pm"`.
- Hide "Users Admin" option in sidebar/topbar if `role !== "admin"`.
- Disable project membership assignment controls if `role !== "pm"`.

---

## Verification Plan

### Backend Unit Tests
Update tests in:
- `tests/test_auth_api.py`
- `tests/test_project_crud_api.py`
- `tests/test_source_slice_approval_api.py`
- `tests/test_fiber_approval_api.py`
- `tests/test_mapping_review_api.py`

Verify new tests succeed:
1. `admin` user successfully accesses user list, create, edit, delete. Denied project CRUD.
2. `pm` user successfully accesses project create, copy, delete/archive, and project memberships. Denied user management.
3. `central_team` user with no membership gets 403 on accessing project operations.
4. `central_team` user with membership successfully triggers AI, uploads copybook/slice, manages lookup mappings, and triggers codegen. Denied user CRUD and project creation.
5. `project_stakeholder` approves slice, mapping, and lookup fiber mappings inside their project.
6. `read_only_auditor` views projects globally but cannot perform writes.
