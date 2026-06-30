Task: tasks/001m-ui-management-user-admin.md
Domain: docs/domain/management.md

## Current State

The backend already exposes `/users` and project-membership endpoints, and the
engine tests cover create/update/delete and membership behavior. The web app,
however, only renders the public login card and a placeholder shell; there are
no admin pages, no user creation form, and no membership management UI.

## Objective

Build the central-team management surface for users and project memberships so
operators can create users, update roles and status, soft-delete accounts, and
manage project membership from the UI against the existing API endpoints.

## Out of Scope

- Auth API wiring
- Menu access control and route gating
- Project detail and run monitoring screens
- Backend management endpoint changes

## Blast Radius

| File | Action | What changes |
|------|--------|--------------|
| `web/app/admin/users/page.tsx` | create | User list and create entry point |
| `web/app/admin/users/new/page.tsx` | create | User creation form |
| `web/app/admin/users/[userId]/page.tsx` | create | User detail and update form |
| `web/app/admin/projects/[projectId]/members/page.tsx` | create | Project membership management |
| `web/lib/management-api.ts` | create | API helpers for users and memberships |
| `web/components/UserForm.tsx` | create | Shared create/update form |
| `web/components/UserList.tsx` | create | Central-team user table/list |
| `web/components/ProjectMembersPanel.tsx` | create | Membership add/remove surface |
| `web/lib/management-api.test.ts` | create | Cover user and membership endpoint payloads |
| `web/components/__tests__/UserForm.test.tsx` | create | Cover create and edit form submission |
| `web/components/__tests__/UserList.test.tsx` | create | Cover user list rendering and delete actions |
| `web/components/__tests__/ProjectMembersPanel.test.tsx` | create | Cover membership add/remove and warnings |

## File Changes

### `web/lib/management-api.ts`

```ts
export interface UserCreateInput {
  email: string;
  password: string;
  displayName: string | null;
  role: "central_team" | "project_stakeholder" | "read_only_auditor";
}

export function listUsers(token: string): Promise<UserResponse[]>;
export function createUser(token: string, input: UserCreateInput): Promise<UserResponse>;
export function updateUser(token: string, userId: string, input: UserUpdateInput): Promise<UserResponse>;
export function deleteUser(token: string, userId: string): Promise<void>;
export function listProjectMembers(token: string, projectId: string): Promise<ProjectMemberResponse[]>;
export function addProjectMember(token: string, projectId: string, userId: string): Promise<MembershipResponse>;
export function removeProjectMember(token: string, projectId: string, userId: string): Promise<void>;
```

### `web/components/UserForm.tsx`

```tsx
export interface UserFormProps {
  mode: "create" | "edit";
  initialValue?: {
    email: string;
    displayName: string | null;
    role: "central_team" | "project_stakeholder" | "read_only_auditor";
    status: "active" | "disabled";
  };
  onSubmit: (value: UserFormValue) => Promise<void>;
}
```

### `web/app/admin/users/new/page.tsx`

```tsx
export default function NewUserPage() {
  // Render the central-team create-user form and submit to POST /users.
}
```

### `web/app/admin/projects/[projectId]/members/page.tsx`

```tsx
export default function ProjectMembersPage({
  params,
}: {
  params: { projectId: string };
}) {
  // List members and wire add/remove actions to the membership endpoints.
}
```

## Tests

### `web/lib/management-api.test.ts`

```ts
import { createUser, addProjectMember } from "../lib/management-api";

describe("management-api", () => {
  it("posts new users to /users", async () => {
    // Mock fetch and assert request body includes email, password, displayName, and role.
  });
});
```

### `web/components/__tests__/UserForm.test.tsx`

```tsx
it("collects the create-user fields", async () => {
  // Render the form, fill the fields, submit, and assert the payload.
});
```

### `web/components/__tests__/ProjectMembersPanel.test.tsx`

```tsx
it("renders the duplicate-membership warning from the API", () => {
  // Ensure the warning message is visible when the backend returns it.
});
```

## Verification

- `npm test` in `web` passes the new management API and component tests
- `npm run build` in `web` still succeeds with the new admin routes
- Manual check: central-team user can create a user, edit role/status, and add
  or remove project membership

## Pitfalls

- Do not let request-body role data drive access control
- Do not merge user creation and membership management into one form
- Keep duplicate membership as a warning path, not an error path
- Preserve the backend role enum values exactly

## Commit

- `feat(ui): add user management and membership admin screens`
