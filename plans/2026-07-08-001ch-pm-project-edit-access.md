# Plan: 001ch — Project Edit Access: Gate to PM Role in Frontend UI

- **Task Link:** [tasks/001ch-pm-project-edit-access.md](../tasks/001ch-pm-project-edit-access.md)
- **Domain:** [docs/domain/ui.md](../docs/domain/ui.md)

## Current State

In [web/app/projects/[id]/page.tsx](file:///Users/vjkotra/projects/katana/web/app/projects/[id]/page.tsx):
```tsx
          {role === "central_team" ? (
            <Link
              className="rounded-md bg-primary px-4 py-2 text-sm font-semibold text-white"
              href={`/projects/${id}/edit`}
            >
              Edit
            </Link>
          ) : null}
```

This gates Edit button visibility to `central_team`, but the backend endpoint only permits the `pm` role.

## Objective

Update Edit button visibility to target the `pm` role, and align the unit tests.

## File Changes

### Step 1 — Update `web/app/projects/[id]/page.tsx`

Change the `central_team` role check to `pm`:

```tsx
          {role === "pm" ? (
            <Link
              className="rounded-md bg-primary px-4 py-2 text-sm font-semibold text-white"
              href={`/projects/${id}/edit`}
            >
              Edit
            </Link>
          ) : null}
```

### Step 2 — Update `web/app/projects/[id]/page.test.tsx`

1. Define a `PM_SESSION` mock:
```typescript
const PM_SESSION = {
  accessToken: "tok-4",
  expiresAt: "2027-01-01T00:00:00Z",
  role: "pm" as const,
  sessionVersion: 1,
  userId: "user-4",
};
```
2. Update the test case:
```typescript
  it("shows an edit link for pm users", async () => {
    loadUiSessionMock.mockReturnValue(PM_SESSION);
    await renderPage("proj-1");
    expect(await screen.findByRole("link", { name: "Edit" })).toHaveAttribute("href", "/projects/proj-1/edit");
  });
```

## Verification

1. TypeScript compiles with no errors.
2. All frontend and backend tests pass.

## Commit

```
fix: gate project editing button in frontend UI to PM role
```
