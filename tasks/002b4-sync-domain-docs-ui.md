---
id: 002b4
title: Sync docs/domain/ui.md against actual codebase
status: completed
created: 2026-07-24
priority: medium
domain: docs
depends-on: []
---

# Sync docs/domain/ui.md

## Objective

Update `docs/domain/ui.md` to accurately reflect the current UI implementation. Last updated 2026-07-20.

## Scope

- `docs/domain/ui.md` only

## What to verify

1. **Entry points** — Verify the 5 role landing pages match actual routes:
   - Portfolio dashboard → `/projects`
   - Project detail → `/projects/[id]`
   - Feed detail → `/projects/[id]/feeds/[feedId]`
   - Review page → `/projects/[id]/feeds/[feedId]/review`
   - Codegen → `/projects/[id]/codegen`

2. **Screens** — Verify each screen description matches actual components:
   - Portfolio dashboard `ProjectHealthSummary` widget
   - Project detail tabs (Overview, Feeds, Artifacts, SQL Bundle)
   - DDL analysis prompt banner (new)
   - Knowledge freeze panel (new)
   - Project edit form
   - SQL bundle delivery page
   - Feed intake page
   - Fiber management page
   - Fiber detail page
   - Per-feed workspace
   - Review grid

3. **Missing from docs:**
   - Stacked source values UI (task 001gn) — feed page lookup fiber cards now have stacked textareas
   - Unmapped row counts UI (task 001ex) — warning badges in lookup fiber cards
   - Mapping hints textarea (new on feed page, central_team only)
   - Discard feed dialog (new on feed page)
   - Upload replacement slice flow (new on feed page)
   - AI Mapping Hints panel with save button (new on feed page)
   - Re-analyze DDL button on codegen page
   - AI Log Viewer / AI Trace panel

4. **Lookup value mapping grids** — Verify the `destinationMappings` structure matches the actual ReviewGrid rendering:
   - `destId`, `destLabel`, `destRow`, `sourceValues`, `status` fields
   - Fallback logic from `sourceValueMap` → `destinationTable` → `fiber.proposedMappings`

5. **Fiber lifecycle states** — Verify the documented state machine matches actual fiber statuses:
   - The doc lists `created → deferred → inputs_ready → ai_running → mapped → operator_assigned → business_approved → operator_triggered → codegen_complete`
   - Actual fiber statuses in code may be a simplified set

6. **Lookup delta review** — Verify the CR page description matches actual `change-requests/[crId]/page.tsx`

7. **Notification system** — Verify `NotificationBell`, polling, event types match actual implementation

8. **Role table** — Verify role capabilities match actual route guards

## Out of scope

- Any other domain doc files
- Frontend implementation changes

## Acceptance criteria

- [ ] All screen descriptions match actual routes and components
- [ ] All new UI features (stacked source values, unmapped counts, mapping hints) are documented
- [ ] Lookup mapping grid structure matches actual data model
- [ ] Fiber lifecycle states match actual fiber statuses
- [ ] Notification system is accurate
- [ ] Role table matches actual permissions
- [ ] Changelog updated
- [ ] timestamp updated
