# Admin User Edit & Delete Controls Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an explicit edit action to admin user management and make delete keep the list state in sync after removal.

**Architecture:** Keep `web/components/UserList.tsx` dumb and reusable: it should render one row per user and surface explicit Edit/Delete intents through callbacks. `web/app/admin/users/page.tsx` owns navigation and data refresh: it turns Edit into a route change to the existing user detail/update page and re-fetches the user list after a successful delete. The existing `web/app/admin/users/[userId]/page.tsx` already serves as the edit form, so no new backend route is needed.

**Tech Stack:** Next.js App Router, React, Vitest, existing management API client.

## Global Constraints

- `central_team` can create, update, and soft-delete users.
- `project_stakeholder` cannot manage users or memberships.
- `read_only_auditor` cannot manage users or memberships.
- Administrative actions are auditable.
- Keep admin access behind the existing authenticated admin layout.

## Task

- [001av-admin-user-edit-delete-controls](../tasks/001av-admin-user-edit-delete-controls.md)

## Domain

- [ui.md](/Users/vjkotra/projects/katana/docs/domain/ui.md)
- [management.md](/Users/vjkotra/projects/katana/docs/domain/management.md)
- [auth.md](/Users/vjkotra/projects/katana/docs/domain/auth.md)
- [security.md](/Users/vjkotra/projects/katana/docs/domain/security.md)
- [api.md](/Users/vjkotra/projects/katana/docs/domain/api.md)

## Current State

- `/admin/users` lists users and shows a create-user button.
- `web/components/UserList.tsx` renders only the row label and Delete button.
- `web/app/admin/users/[userId]/page.tsx` already loads and submits the edit form, but nothing routes users to it.
- The delete path has no explicit failure handling in the page component.

## Objective

Expose an Edit action beside each user row, route that action to the existing user detail/update page, and make Delete refresh the list so the screen stays current after removal.

## Out of Scope

- Backend user-management API changes.
- Membership screens.
- Password-reset or login flow changes.
- Any new admin route beyond the already existing user detail page.

## Blast Radius

- `web/components/UserList.tsx`
- `web/app/admin/users/page.tsx`
- `web/components/__tests__/UserList.test.tsx`
- `web/app/admin/users/page.test.tsx`
- `web/app/admin/users/[userId]/page.test.tsx` only if the detail page needs a small navigation affordance after review

## File Changes

- Extend the shared list row component with an explicit Edit action and keep Delete actionable.
- Wire the admin users page to route Edit clicks to `/admin/users/{userId}`.
- Re-fetch users after delete and surface a visible error if delete fails.
- Update the list/page tests to cover the new navigation and refresh behavior.

## Tests

- `UserList` renders Edit and Delete buttons for each row.
- Clicking Edit calls the supplied callback with the user ID.
- Admin users page pushes to the existing detail route when Edit is clicked.
- Delete calls the API, re-fetches the list, and removes the deleted row from the UI.
- Delete failure renders an inline alert instead of silently no-oping.

## Verification

- Run the focused admin user tests in `web`.
- Confirm the list page still renders the create-user link and the admin header.

## Pitfalls

- Keep the row component generic; the row should not hardcode routing.
- Do not break the existing user detail/update page, because that route becomes the edit target.
- Keep delete handling explicit so the UI does not look successful when the refresh fails.

## Commit

- `feat: add admin user edit and delete controls`

### Task 1: Add row-level edit/delete wiring

**Files:**
- Modify `web/components/UserList.tsx`
- Modify `web/app/admin/users/page.tsx`

**Interfaces:**
- Consumes: `UserRecord`, `onDelete(userId)`, `onEdit(userId)`
- Produces: user rows with an Edit button and a delete flow that re-fetches the list

- [ ] **Step 1: Write the failing tests**

```tsx
// web/components/__tests__/UserList.test.tsx
it("renders edit and delete actions", () => {
  const onDelete = vi.fn();
  const onEdit = vi.fn();

  render(
    <UserList
      onDelete={onDelete}
      onEdit={onEdit}
      users={[
        {
          userId: "user-1",
          email: "operator@example.com",
          displayName: "Operator",
          role: "central_team",
          status: "active",
        },
      ]}
    />
  );

  fireEvent.click(screen.getByRole("button", { name: "Edit" }));
  expect(onEdit).toHaveBeenCalledWith("user-1");
  expect(screen.getByRole("button", { name: "Delete" })).toBeInTheDocument();
});
```

```tsx
// web/app/admin/users/page.test.tsx
it("routes to the user detail page for edit and refreshes after delete", async () => {
  render(<AdminUsersPage />);

  await screen.findByText("stakeholder@example.com");
  fireEvent.click(screen.getByRole("button", { name: "Edit" }));
  expect(routerPushMock).toHaveBeenCalledWith("/admin/users/user-2");

  fireEvent.click(screen.getByRole("button", { name: "Delete" }));
  await waitFor(() => expect(deleteUserMock).toHaveBeenCalledWith("token-1", "user-2"));
  await waitFor(() => expect(listUsersMock).toHaveBeenCalledTimes(2));
  expect(screen.queryByText("stakeholder@example.com")).not.toBeInTheDocument();
});
```

- [ ] **Step 2: Run the tests and confirm they fail for the expected reasons**

Run:

```bash
cd web && npm test -- components/__tests__/UserList.test.tsx app/admin/users/page.test.tsx
```

Expected:

- `UserList` has no `Edit` action yet.
- `AdminUsersPage` has no edit routing and does not refresh the list after delete.

- [ ] **Step 3: Implement the minimal UI wiring**

```tsx
// web/components/UserList.tsx
export interface UserListProps {
  users: UserRecord[];
  onDelete: (userId: string) => void;
  onEdit: (userId: string) => void;
}

export function UserList({ users, onDelete, onEdit }: UserListProps) {
  return (
    <div className="rounded-2xl border border-outline-variant bg-surface-container shadow-sm">
      <div className="border-b border-outline-variant px-6 py-4">
        <h2 className="text-lg font-semibold text-slate-900">Users</h2>
      </div>
      <ul>
        {users.map((user) => (
          <li key={user.userId} className="flex items-center justify-between border-b border-outline-variant px-6 py-4 last:border-b-0">
            <div>
              <div className="text-sm font-semibold text-slate-900">{user.email}</div>
              <div className="text-xs text-slate-500">
                {user.displayName ?? "No display name"} · {user.role} · {user.status}
              </div>
            </div>
            <div className="flex items-center gap-2">
              <button type="button" className="rounded-md border border-outline-variant px-3 py-2 text-sm text-slate-700" onClick={() => onEdit(user.userId)}>
                Edit
              </button>
              <button type="button" className="rounded-md border border-outline-variant px-3 py-2 text-sm text-slate-700" onClick={() => onDelete(user.userId)}>
                Delete
              </button>
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}
```

```tsx
// web/app/admin/users/page.tsx
const router = useRouter();

const handleEdit = (userId: string) => {
  router.push(`/admin/users/${userId}`);
};

const handleDelete = async (userId: string) => {
  if (!session) {
    return;
  }

  try {
    await deleteUser(session.accessToken, userId);
    setUsers(await listUsers(session.accessToken));
  } catch (error) {
    setErrorMessage(error instanceof Error ? error.message : "Unable to delete user.");
  }
};

<UserList onEdit={handleEdit} onDelete={(userId) => void handleDelete(userId)} users={users.map(toUserRecord)} />
```

- [ ] **Step 4: Re-run the tests and confirm they pass**

Run:

```bash
cd web && npm test -- components/__tests__/UserList.test.tsx app/admin/users/page.test.tsx
```

Expected:

- `UserList` test passes with an `Edit` button.
- `AdminUsersPage` test passes with edit navigation and list refresh after delete.

- [ ] **Step 5: Commit**

```bash
git add web/components/UserList.tsx web/app/admin/users/page.tsx web/components/__tests__/UserList.test.tsx web/app/admin/users/page.test.tsx
git commit -m "feat: add admin user edit and delete controls"
```
