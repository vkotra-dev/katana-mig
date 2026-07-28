---
id: 002b9
title: Add version history dropdown UI for mapping fields
status: completed
created: 2026-07-24
priority: medium
depends-on: [002b8]
domain: web
---

# Task 002b9 — Version History Frontend

## Context

Follow-up to [[002b8]] — once the backend version history API exists, add a "View History" toggle near each editable field (mapping hints, codegen instructions, transformation instructions) that shows a collapsible list of version history entries with old/new diff views.

## Current State

- `web/lib/feeds-api.ts` has `patchFeedMappingHints` and `saveTransformationInstructions` that call PATCH endpoints.
- `web/lib/projects-api.ts` has `saveCodegenInstructions` that calls PATCH endpoint.
- No API client function for reading version history.
- No UI component for browsing version history.
- Mapping hints editor is in `web/app/projects/[id]/feeds/[feedId]/page.tsx` (lines 69-71, 785-792).
- Codegen instructions editor is in `web/app/projects/[id]/codegen/page.tsx` (lines 264, 396, 417).
- No editor exists for transformation_instructions in the UI yet (it's stored but not directly editable from any page).

## Objective

1. Add `listVersionHistory(token, entityType, opts)` to the appropriate API client module.
2. Add a "View History" toggle/button near each editable field (mapping hints, codegen instructions) that fetches and renders a list of version history entries.
3. Each entry shows: `changed_at` (timestamp), `changed_by` (user), and a collapsible old/new diff.
4. Dropdown is per-field, not global — each entity type has its own list.

## Out of Scope

- No version comparison/diff highlighting (just show old/new side by side as text)
- No pagination UI — fetch all versions (limited to 50 by backend) at once

## Domain Updates Required

- `docs/domain/ui.md` — add changelog line noting version history UI feature (View History toggle + diff panel on mapping hints and codegen instructions editors)

## Tests

No new test files needed. Manual verification only:
1. Edit mapping hints, open history toggle — see one entry with correct old/new values
2. Edit codegen instructions, open history toggle — see entry
3. Reload page — history still accessible (proves API works, not just local state)

## Commit

```
feat(versioning): add version history dropdown UI for mapping fields

- listVersionHistory API client function in feeds-api.ts
- VersionHistoryEntry TypeScript interface
- Collapsible version history panel near mapping hints editor
- Collapsible version history panel near codegen instructions editor
```
