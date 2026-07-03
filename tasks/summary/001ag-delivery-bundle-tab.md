# Summary: Task 001ag — Delivery Bundle Tab

## What changed

- Added a shared `ProjectNavigationTabs` component for the project detail and codegen pages.
- Added `SQL Bundle` to the project detail tab row and wired it to `/projects/[id]/codegen`.
- Added the same tab row to the codegen page with `SQL Bundle` shown as active.
- Kept the codegen page content unchanged aside from the shared navigation row.
- Added focused tests for the shared tab component, the project detail page, and the codegen page.

## Verification

- `cd web && npm test -- components/projects/__tests__/ProjectNavigationTabs.test.tsx`
- `cd web && npm test -- app/projects/[id]/page.test.tsx`
- `cd web && npm test -- app/projects/[id]/codegen/page.test.tsx`
- `cd web && npm test`

## Commit

- `1149fff` - `feat(001ag): add shared SQL Bundle tabs for project and codegen pages`
