# Task 001ag — Delivery Bundle Tab

**Plan:** `plans/2026-07-01-001ag-delivery-bundle-tab.md`
**Spec:** `docs/superpowers/specs/2026-07-01-delivery-bundle-tab-design.md`

## Domain

- `docs/domain/ui.md` — authoritative screen contract
- `docs/domain/api.md` — endpoint reference
- Mockmigration is styling reference only; spec is content authority

## Scope

Add a fourth "SQL Bundle" tab pill to the project detail page
(`web/app/projects/[id]/page.tsx`) that navigates to the existing codegen page
(`/projects/[id]/codegen`) via `router.push`. Single file change + test.

## Success criteria

- "SQL Bundle" button renders alongside Overview / Sources / Artifacts tabs
- Clicking calls `router.push("/projects/{id}/codegen")`
- All roles see the tab (no role gate)
- Test passes in `npm test`
