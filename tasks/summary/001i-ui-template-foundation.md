# Summary: Task 001i — UI Template Foundation

## What changed

- Introduced the reusable Katana UI shell tokens and shared primitives.
- Added role-aware `Topbar` and `Sidebar` components driven by `ui-model.ts`.
- Added `LoginView` as a reusable login template without demo credentials or fake auth state.
- Added `session.ts` to represent the UI session shape used by the shell components.
- Kept the UI template layer reusable for later portfolio, project, and run work.

## Verification

- `cd web && npm test -- --run 'components/__tests__/Topbar.test.tsx' 'components/__tests__/Sidebar.test.tsx' 'components/__tests__/LoginView.test.tsx'`
- `git diff --check`

## Notes

- The task is complete at the component/template layer; backend auth wiring is intentionally out of scope.
- Later UI tasks can compose these primitives without needing mockmigration context.
