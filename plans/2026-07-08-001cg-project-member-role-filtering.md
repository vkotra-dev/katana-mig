# Plan: 001cg — Project Member Autocomplete: Filter Out Admin and PM Roles

- **Task Link:** [tasks/001cg-project-member-role-filtering.md](../tasks/001cg-project-member-role-filtering.md)
- **Domain:** [docs/domain/management.md](../docs/domain/management.md)

## Current State

In [web/app/projects/[id]/page.tsx](file:///Users/vjkotra/projects/katana/web/app/projects/[id]/page.tsx):
```typescript
availableUsers={allUsers.filter((u) => !members.some((m) => m.userId === u.userId))}
```

In [web/app/admin/projects/[projectId]/members/page.tsx](file:///Users/vjkotra/projects/katana/web/app/admin/projects/[projectId]/members/page.tsx):
```typescript
const availableUsers = allUsers.filter((u) => !memberUserIds.has(u.userId));
```

Both filter lists include `admin` and `pm` role users, which causes 422 errors on selection.

## Objective

Filter out users with roles `admin` and `pm` from the project member autocomplete dropdown lists on both screens.

## Out of Scope

- Modifying the backend endpoints.

## File Changes

### Step 1 — Update `web/app/projects/[id]/page.tsx`

Filter out `admin` and `pm` roles from `availableUsers` passed to `ProjectMembersPanel`:

```typescript
availableUsers={allUsers.filter(
  (u) =>
    u.role !== "admin" &&
    u.role !== "pm" &&
    !members.some((m) => m.userId === u.userId)
)}
```

### Step 2 — Update `web/app/admin/projects/[projectId]/members/page.tsx`

Filter out `admin` and `pm` roles from the computed `availableUsers` list:

```typescript
const availableUsers = allUsers.filter(
  (u) =>
    u.role !== "admin" &&
    u.role !== "pm" &&
    !memberUserIds.has(u.userId)
);
```

## Tests

Run existing unit tests to make sure no existing assertions are broken, and update any unit test mocks if necessary.

## Verification

1. Log in to the application.
2. Go to a project's Members view.
3. Verify that the autocomplete search input does not suggest users with `admin` or `pm` roles.
4. TypeScript compiles with no errors.
5. All frontend and backend tests pass.

## Commit

```
fix: exclude admin and pm roles from project membership autocomplete suggestions
```
