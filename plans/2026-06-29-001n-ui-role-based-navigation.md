Task: tasks/001n-ui-role-based-navigation.md
Domain: docs/domain/ui.md

## Current State

The current `Topbar` and `Sidebar` components already call `navItemsForRole`,
but the helper is very shallow and does not enforce a complete role policy. The
app also has no route guard helper, so the menu can show or hide items without a
corresponding access decision.

## Objective

Turn the navigation layer into a role-aware access surface so the menu items,
route entry points, and admin links match the authenticated role and project
membership state.

## Out of Scope

- Auth API implementation
- Management screen rendering
- Backend authorization rules
- Portfolio and run content beyond navigation entry points

## Blast Radius

| File | Action | What changes |
|------|--------|--------------|
| `web/lib/ui-model.ts` | modify | Expand the role-to-navigation mapping |
| `web/lib/navigation-access.ts` | create | Decide what each role may see or open |
| `web/components/Topbar.tsx` | modify | Render role-specific items and admin visibility |
| `web/components/Sidebar.tsx` | modify | Mirror the same role-based policy |
| `web/app/admin/layout.tsx` | create | Enforce admin-only route access |
| `web/app/projects/layout.tsx` | create | Enforce membership-aware project access |
| `web/lib/navigation-access.test.ts` | create | Cover the role-to-access policy |
| `web/components/__tests__/Topbar.test.tsx` | modify | Cover role-specific top navigation |
| `web/components/__tests__/Sidebar.test.tsx` | create | Cover role-specific sidebar output |
| `web/app/admin/layout.test.tsx` | create | Cover admin-only route gating |
| `web/app/projects/layout.test.tsx` | create | Cover membership-aware project access |

## File Changes

### `web/lib/ui-model.ts`

```ts
export type SessionRole = "central_team" | "project_stakeholder" | "read_only_auditor";

export function navItemsForRole(role: SessionRole): NavItem[] {
  // Return the exact menu set allowed for the role.
}
```

### `web/lib/navigation-access.ts`

```ts
export function canAccessAdmin(role: SessionRole): boolean;
export function canAccessProject(role: SessionRole, projectId: string, projectIds: string[]): boolean;
export function visibleActionsForRole(role: SessionRole): string[];
```

### `web/app/admin/layout.tsx`

```tsx
export default function AdminLayout({ children }: { children: React.ReactNode }) {
  // Read the stored session and redirect to login or a safe page when the role
  // is not central_team.
}
```

## Tests

### `web/lib/navigation-access.test.ts`

```ts
import { canAccessAdmin } from "../lib/navigation-access";

describe("navigation-access", () => {
  it("allows admin access only for central_team", () => {
    expect(canAccessAdmin("central_team")).toBe(true);
    expect(canAccessAdmin("project_stakeholder")).toBe(false);
  });
});
```

### `web/components/__tests__/Topbar.test.tsx`

```tsx
it("hides the admin menu for non-central roles", () => {
  // Render the topbar for each role and assert menu differences.
});
```

### `web/components/__tests__/Sidebar.test.tsx`

```tsx
it("renders a role-specific sidebar", () => {
  // Verify the navigation items differ by role.
});
```

## Verification

- `npm test` in `web` passes the new navigation-policy tests
- Route guard checks block direct access to admin pages for non-admin roles
- Central-team, stakeholder, and auditor menu sets match `docs/domain/ui.md`

## Pitfalls

- Do not rely on CSS-only hiding for access control
- Do not expose admin routes just because the links are hidden
- Keep project-stakeholder access membership-scoped instead of role-only

## Commit

- `feat(ui): add role-aware navigation and route access control`
