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
(`/projects/[id]/codegen`) via `router.push`.

The same tab row must also appear on the codegen page
(`web/app/projects/[id]/codegen/page.tsx`) with `SQL Bundle` shown as the
active tab.

This is a later-phase delivery ticket. Feed/fiber/comment/AI work is now the
priority stream; keep this ticket queued behind that stream.

## Success criteria

- "SQL Bundle" button renders alongside Overview / Sources / Artifacts tabs
- Clicking calls `router.push("/projects/{id}/codegen")`
- All roles see the tab (no role gate)
- The codegen page shows the same tab row with SQL Bundle active
- Test passes in `npm test`
