# Admin User Edit & Delete Controls — Implementation Plan (001av)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Task:** [`tasks/001av-admin-user-edit-delete-controls.md`](../tasks/001av-admin-user-edit-delete-controls.md)

**Goal:** Add a per-row "Edit" link to the admin user list and fix delete error handling so central-team operators can navigate to edit and recover from delete failures.

**Architecture:** Two small changes, no new files. `UserList.tsx` gains a `<Link>` per row that navigates to `/admin/users/[userId]` — no new prop needed. `AdminUsersPage` wraps `handleDelete` in try/catch and surfaces the error through the existing `errorMessage` / `role="alert"` pattern. `[userId]/page.tsx` gains a back link. All existing API calls and the edit form are already wired; this task connects the missing navigation and hardens the delete path.

**Tech Stack:** Next.js App Router, React, TypeScript, Vitest + Testing Library

## Global Constraints

- No backend changes
- Keep existing `errorMessage` / `role="alert"` display pattern in `AdminUsersPage` — do not introduce a second error display mechanism
- Edit link styling must match the Delete button: `rounded-md border border-outline-variant px-3 py-2 text-sm text-slate-700`
- All authenticated roles see the Edit link (no role gate — same as Delete)
- Do not remove `onSelect` from `UserListProps` — leave it optional as-is

---

## File Changes

| Action | Path |
|--------|------|
| Modify | `web/components/UserList.tsx` |
| Modify | `web/app/admin/users/page.tsx` |
| Modify | `web/app/admin/users/[userId]/page.tsx` |
| Modify | `web/app/admin/users/page.test.tsx` |
| Modify | `web/app/admin/users/[userId]/page.test.tsx` |

---

## Task 1: Edit link in user list

**Files:**
- Modify: `web/components/UserList.tsx`
- Modify: `web/app/admin/users/page.test.tsx`

**Interfaces:**
- Produces: each row in `UserList` renders an `<a role="link" name="Edit">` pointing to `/admin/users/${userId}`

- [ ] **Step 1: Write the failing test**

Add to `web/app/admin/users/page.test.tsx` inside the existing `describe("AdminUsersPage")` block:

```ts
it("renders an edit link for each user", async () => {
  render(<AdminUsersPage />);
  const editLink = await screen.findByRole("link", { name: "Edit" });
  expect(editLink).toHaveAttribute("href", "/admin/users/user-2");
});
```

- [ ] **Step 2: Run to verify the test fails**

```bash
cd /Users/vjkotra/projects/katana/web
npm test -- app/admin/users/page.test.tsx
```

Expected: FAIL — "Edit" link not found.

- [ ] **Step 3: Add the Edit link to `UserList.tsx`**

Add `import Link from "next/link";` at the top of `web/components/UserList.tsx` (after the existing `"use client"` directive).

In the `<li>` row, wrap the Delete button in a `<div className="flex items-center gap-2">` and add the Edit `<Link>` before it:

Replace:
```tsx
            <button
              className="rounded-md border border-outline-variant px-3 py-2 text-sm text-slate-700"
              onClick={() => onDelete(user.userId)}
              type="button"
            >
              Delete
            </button>
```

With:
```tsx
            <div className="flex items-center gap-2">
              <Link
                href={`/admin/users/${user.userId}`}
                className="rounded-md border border-outline-variant px-3 py-2 text-sm text-slate-700"
              >
                Edit
              </Link>
              <button
                className="rounded-md border border-outline-variant px-3 py-2 text-sm text-slate-700"
                onClick={() => onDelete(user.userId)}
                type="button"
              >
                Delete
              </button>
            </div>
```

- [ ] **Step 4: Run the test to verify it passes**

```bash
cd /Users/vjkotra/projects/katana/web
npm test -- app/admin/users/page.test.tsx
```

Expected: all tests PASS including the new "Edit" link test.

- [ ] **Step 5: Commit**

```bash
git add web/components/UserList.tsx web/app/admin/users/page.test.tsx
git commit -m "feat(001av): add per-row edit link to admin user list"
```

---

## Task 2: Delete error handling + back link on detail page

**Files:**
- Modify: `web/app/admin/users/page.tsx`
- Modify: `web/app/admin/users/[userId]/page.tsx`
- Modify: `web/app/admin/users/page.test.tsx`
- Modify: `web/app/admin/users/[userId]/page.test.tsx`

**Interfaces:**
- Consumes: existing `errorMessage` state + `role="alert"` paragraph in `AdminUsersPage`
- Produces: failed delete surfaces `errorMessage`; detail page has a back link to `/admin/users`

- [ ] **Step 1: Write failing tests**

Add to `web/app/admin/users/page.test.tsx` inside `describe("AdminUsersPage")`:

```ts
it("shows an error alert when delete fails", async () => {
  deleteUserMock.mockRejectedValue(new Error("server error"));
  render(<AdminUsersPage />);
  await screen.findByText("stakeholder@example.com");
  screen.getByRole("button", { name: "Delete" }).click();
  expect(await screen.findByRole("alert")).toBeInTheDocument();
});
```

Add to `web/app/admin/users/[userId]/page.test.tsx` inside `describe("UserDetailPage")`:

```ts
it("renders a back link to the users list", async () => {
  render(<UserDetailPage params={{ userId: "user-2" }} />);
  const backLink = await screen.findByRole("link", { name: /back to users/i });
  expect(backLink).toHaveAttribute("href", "/admin/users");
});
```

The `[userId]/page.test.tsx` mock block does not include `next/link` — add it:

```ts
vi.mock("next/link", () => ({
  default: ({ href, children }: { href: string; children: React.ReactNode }) => (
    <a href={href}>{children}</a>
  ),
}));
```

- [ ] **Step 2: Run to verify both tests fail**

```bash
cd /Users/vjkotra/projects/katana/web
npm test -- app/admin/users/page.test.tsx app/admin/users/\\[userId\\]/page.test.tsx
```

Expected: FAIL — alert not found; back link not found.

- [ ] **Step 3: Wrap `handleDelete` in try/catch in `AdminUsersPage`**

In `web/app/admin/users/page.tsx`, replace `handleDelete`:

```ts
  const handleDelete = async (userId: string) => {
    if (!session) {
      return;
    }
    setErrorMessage(undefined);
    try {
      await deleteUser(session.accessToken, userId);
      const nextUsers = await listUsers(session.accessToken);
      setUsers(nextUsers);
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Failed to delete user.");
    }
  };
```

- [ ] **Step 4: Add back link to `[userId]/page.tsx`**

Add `import Link from "next/link";` to the existing imports in `web/app/admin/users/[userId]/page.tsx`.

In the JSX, add the back link as the first child of the `<div className="mx-auto max-w-3xl space-y-6">`:

```tsx
      <div className="mx-auto max-w-3xl space-y-6">
        <Link href="/admin/users" className="text-sm text-slate-600 hover:underline">
          ← Back to users
        </Link>
        {user ? (
```

- [ ] **Step 5: Run the tests to verify they pass**

```bash
cd /Users/vjkotra/projects/katana/web
npm test -- app/admin/users/page.test.tsx app/admin/users/\\[userId\\]/page.test.tsx
```

Expected: all tests PASS.

- [ ] **Step 6: Run the full web suite to verify no regressions**

```bash
cd /Users/vjkotra/projects/katana/web
npm test
```

Expected: all tests PASS.

- [ ] **Step 7: Commit**

```bash
git add \
  web/app/admin/users/page.tsx \
  web/app/admin/users/[userId]/page.tsx \
  web/app/admin/users/page.test.tsx \
  web/app/admin/users/[userId]/page.test.tsx
git commit -m "feat(001av): fix delete error handling and add back link on user detail"
```

---

## Verification

1. **Targeted tests:** `cd web && npm test -- app/admin/users`  
   Expected: all pass

2. **Full suite:** `cd web && npm test`  
   Expected: no regressions

3. **Browser smoke-check** (optional but recommended):
   - `/admin/users` — each row shows Edit link beside Delete
   - Click Edit → lands on `/admin/users/[userId]` with form pre-filled
   - Save → success message below form
   - Back link → returns to `/admin/users`
   - Click Delete on a user → user disappears from list
   - Simulate delete failure (network off) → error alert visible, list unchanged

## Commit summary

```
feat(001av): add per-row edit link to admin user list
feat(001av): fix delete error handling and add back link on user detail
```
