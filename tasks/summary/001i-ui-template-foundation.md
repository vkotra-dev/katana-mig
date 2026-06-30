# Summary: Task 001i — UI Template Foundation

## What changed

- Established the reusable Katana UI shell and template layer.
- Added the role-aware `Topbar` and `Sidebar` primitives driven by `ui-model.ts`.
- Added `LoginView` as the reusable login template without demo credentials or fake app state.
- Added `session.ts` to represent the UI session shape used by the shell.
- Kept the template layer reusable for later UI work without coupling it to mock data.

## Verification

- `cd web && npm test -- --run 'components/__tests__/Topbar.test.tsx' 'components/__tests__/Sidebar.test.tsx' 'components/__tests__/LoginView.test.tsx'`

## Notes

- Backend auth wiring was intentionally out of scope for this task.
- The component layer is now ready for the later portfolio, project, and run screens.
