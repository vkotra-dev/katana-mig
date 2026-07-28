---
id: 002h0
title: Add expand/collapse for Source DDL, move it to bottom of Slice, and lock lookup mappings when approved
status: completed
created: 2026-07-24
priority: medium
depends-on: []
domain: web
task: tasks/002h0-ui-slice-ddl-collapse-and-lookup-lock.md
plan: plans/2026-07-24-002h0-ui-slice-ddl-collapse-and-lookup-lock.md
---

# Task 002h0 — UI improvements: Source DDL collapse/move + lookup mapping lock

## Context

Three UI/UX improvements were identified during the brainstorming session:

1. **Source DDL expand/collapse** in the Slice section of the feed page — currently always visible as a static block after analysis.
2. **Move Source DDL to bottom** of the Slice section — currently sits between the "Analyze with AI" button and the "Upload new slice" section.
3. **Lock lookup mapping source values** on the review page when the lookup is signed off — currently users can edit lookup source values even after sign-off because `LookupMappingTable` doesn't check sign-off status. Uses OR logic (consistent with table binding lock): lock as soon as either `centralTeam` OR `projectStakeholder` signs.

## Domain Updates Required

- `docs/domain/ui.md` — add section covering the review page's lookup lock behavior and the feed page's collapsible Source DDL section.

## Out of Scope

- No backend API changes — all changes are frontend-only.
- No changes to the table mapping expand/collapse — already exists.
- No changes to the sign-off workflow itself.

## Pitfalls

1. The `signOffStatus.lookups` object is keyed by `lookupValueMapId` — need to match this to the lookup group's `lookupValueMapId` when determining if a lookup is locked. Guard against `undefined` via optional chaining.
2. Source DDL's collapsed state should persist during the session (use `useState` with default `false`).
3. The `editingEnabled` flag in `ReviewGrid` is a global ball-holder check — per-lookup locks are a separate, additive check (`editingEnabled && !locked`).
4. Lock uses OR logic (either party signs → locked), matching the existing table binding lock at ReviewGrid.tsx line 589.

## Tests

- Unit: `ReviewGrid` with `signOffStatus.lookups[mapId].centralTeam.signed === true` (projectStakeholder false) — verify lookup edit controls are hidden (OR logic).
- Unit: `ReviewGrid` with both `centralTeam` and `projectStakeholder` unsigned — verify edit controls visible when editingEnabled.
- Unit: Feed page Source DDL starts collapsed — verify toggle button exists and toggles visibility.
- Manual: Sign off one side of a lookup on the review page — verify lookup values become non-editable (remove buttons and "add" button disappear).
- Manual: Verify Source DDL collapses/hides correctly in feed page Slice section.

## Commit

```
fix(ui): add Source DDL expand/collapse, move to bottom, and lock lookup mappings when approved

- Add collapsible Source DDL in Slice section of feed page (collapsed by default)
- Move Source DDL below upload section in Slice panel
- Add locked prop to LookupMappingTable; gate edit controls when lookup is signed off (OR logic)
- Derive isLocked from signOffStatus.lookups in ReviewGrid, matching table binding lock pattern
```
