# Plan: 001cf — Admin PM Assignment: Top-Nav Dropdown + Standalone Assignment Page

- **Task Link:** [tasks/001cf-admin-pm-assignment-nav.md](../tasks/001cf-admin-pm-assignment-nav.md)
- **Domain:** [docs/domain/ui.md](../docs/domain/ui.md)

## Current State

- `web/lib/ui-model.ts` — `NavItem` has `{ label, href, active?, badge? }`. Admin returns a single flat link to `/admin`.
- `web/components/Topbar.tsx` — renders all nav items as plain `<a>` tags; no dropdown support.
- `web/app/admin/assign-pm/page.tsx` — does not exist.
- `web/app/projects/[id]/page.tsx` — contains a `Manage Members & PM` button for admin role pointing to `/admin/projects/${id}/members`.
- `web/app/admin/projects/[projectId]/members/page.tsx` — exists; handles both PM assignment and stakeholder membership; kept intact.
- Backend endpoint `PATCH /projects/{id}/manager` — already implemented in 001ce; no backend changes needed.

## Objective

1. Extend `NavItem` to support nested children for dropdown menus.
2. Render a dropdown in `Topbar` when a nav item has children.
3. Create `/admin/assign-pm` — a standalone page with dual autocomplete (active projects × active PMs) and submit.
4. Remove the per-project `Manage Members & PM` button from the project detail page.

## Out of Scope

- Backend changes (endpoint already exists)
- Membership management inside the per-project admin page
- Role-specific items beyond the Admin → Assign PM sub-item

## Blast Radius

- `Topbar` (rendered on every page) — dropdown logic is additive; plain links still work the same
- `ui-model.ts` — additive change; `children` is optional, backward-compatible
- `projects/[id]/page.tsx` — one button removed; rest of page unchanged
- New page at `/admin/assign-pm` — isolated, no shared state

## File Changes

### Step 1 — `web/lib/ui-model.ts`

Add optional `children` array to `NavItem`:

```ts
export interface NavItem {
  label: string;
  href: string;
  active?: boolean;
  badge?: string;
  children?: NavItem[];
}
```

Return Admin as a dropdown with sub-items for admin role.
For PM role, keep Admin as a plain link (no sub-items — PM cannot reassign managers):

```ts
if (canAccessAdmin(role)) {
  if (role === "admin") {
    return [
      ...common,
      {
        label: "Admin",
        href: "/admin",
        children: [
          { label: "Manage Users", href: "/admin/users" },
          { label: "Assign PM to Project", href: "/admin/assign-pm" },
        ],
      },
    ];
  }
  return [...common, { label: "Admin", href: "/admin" }];
}
```

### Step 2 — `web/components/Topbar.tsx`

Add dropdown state for the admin menu item. When a `NavItem` has `children`:
- Render a `<button>` instead of `<a>` with a ▾ chevron
- Toggle `open` state on click
- Render a positioned dropdown `<div>` with child links
- Close on outside click via `useEffect` + `mousedown` listener

```tsx
// Pseudocode — keep styling consistent with existing nav-link classes
{items.map((item) =>
  item.children ? (
    <div key={item.label} className="relative">
      <button onClick={toggle} className="nav-link inline-flex items-center gap-1">
        {item.label} <span className="text-[10px]">▾</span>
      </button>
      {open && (
        <div className="absolute top-full left-0 mt-1 z-50 min-w-[180px] rounded-lg border border-outline-variant bg-white shadow-lg py-1">
          {item.children.map(child => (
            <a key={child.label} href={child.href} className="block px-4 py-2 text-sm text-slate-700 hover:bg-slate-50">
              {child.label}
            </a>
          ))}
        </div>
      )}
    </div>
  ) : (
    <a key={item.label} href={item.href} className={...}>{item.label}</a>
  )
)}
```

### Step 3 — `web/app/admin/assign-pm/page.tsx` (new file)

State:
- `allProjects: ProjectRecord[]` — loaded from `listProjects(token)` on mount; filtered to `status === "active"`
- `allPms: UserResponse[]` — loaded from `listUsers(token)` on mount; filtered to `role === "pm" && status === "active"`
- `projectQuery: string`, `projectOpen: boolean`, `selectedProject: ProjectRecord | null`
- `pmQuery: string`, `pmOpen: boolean`, `selectedPm: UserResponse | null`
- `submitting: boolean`, `successMessage: string | null`, `errorMessage: string | null`

Project autocomplete:
- Filters `allProjects` by `name.toLowerCase().includes(projectQuery.toLowerCase())`
- On select: sets `selectedProject`, sets `projectQuery` to project name, closes dropdown

PM autocomplete:
- Filters `allPms` by email or displayName substring
- On select: sets `selectedPm`, sets `pmQuery` to email, closes dropdown

Submit button:
- Disabled when `!selectedProject || !selectedPm || submitting`
- On click: calls `assignProjectManager(token, selectedProject.projectId, selectedPm.userId)`
- On success: sets `successMessage`, clears both selections and queries
- On error: sets `errorMessage` with message

Layout (reuse admin surface styling):
```
<main class="min-h-screen bg-surface px-6 py-8">
  <div class="mx-auto max-w-xl space-y-6">
    <h1>Assign Project Manager</h1>
    <p>Select an active project and an active PM to assign ownership.</p>

    <!-- Project Autocomplete -->
    <!-- PM Autocomplete -->
    <!-- Submit Button -->
    <!-- Success / Error banners -->
  </div>
</main>
```

### Step 4 — `web/app/projects/[id]/page.tsx`

Remove the `role === "admin"` block that renders the `Manage Members & PM` Link.

## Tests

- `web/components/__tests__/Topbar.test.tsx` — update existing test that asserts Admin renders as an `<a>`; admin role should now render a `<button>` with dropdown children visible on click.
- `web/app/admin/assign-pm/page.test.tsx` — new test file:
  - Renders project and PM autocomplete inputs
  - Typing in project input filters projects; clicking an option selects it
  - Typing in PM input filters PMs; clicking an option selects it
  - Submit button is disabled until both selected
  - On submit: `assignProjectManager` is called with correct args
  - On success: success banner shown, inputs reset
  - On error: error banner shown

## Verification

1. `npx tsc --noEmit` → no errors
2. `npx vitest run` → all tests pass (including updated Topbar test and new assign-pm test)
3. Manual: admin top nav shows dropdown with two items
4. Manual: `/admin/assign-pm` — only active projects appear; only active PMs appear
5. Manual: project detail page no longer shows `Manage Members & PM` button

## Pitfalls

- `Topbar` is rendered on every page — keep dropdown state local; do not lift it
- Outside-click handler must clean up on unmount
- The admin dropdown button must not navigate — it only toggles; only the child `<a>` tags navigate
- `listProjects` for admin returns all projects; filter `status === "active"` in the frontend
- `listUsers` returns all roles; filter to `role === "pm" && status === "active"` in the frontend

## Commit

```
feat: add admin top-nav dropdown and standalone assign-pm page
```
