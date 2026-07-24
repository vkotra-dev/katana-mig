---
id: 001gn
title: Component-Level Stacked Source Upsert & Delete Controls in LookupMappingTable
status: active
created: 2026-07-24
priority: high
domain: frontend / lookup-mapping-table
depends-on: [001fk, 001fm]
---

# Task 001gn — Component-Level Stacked Source Upsert & Delete Controls in LookupMappingTable

## Context

Refactor `LookupMappingTable.tsx` on the Review Page to provide a destination-anchored stacked source upsert interface with exact visual parity (`×` buttons) matching table mapping fibers (Task 001eq).

## Requirements

1. **Individual Item Delete (`×`)**: Render `×` delete button next to each stacked source value input with `text-slate-400 hover:text-red-600 focus:outline-none text-xs font-bold leading-none p-1` styling, invoking `onRemoveSourceValue(destId, srcVal)`.
2. **Row-Level Group Delete (`×`)**: Render a row-level delete button next to the Destination Value header on hover (`title="Delete destination group"`), invoking `onDeleteGroup(destId)`.
3. **Inline Add Input Form**: Replace `window.prompt()` with an inline input form (`addingDestId` state, text input, `Add` button, `Cancel` button, `Enter` key to submit, `Esc` key to cancel), invoking `onAddSourceValue(destId, value)`.

## Files to Change

1. `web/components/projects/LookupMappingTable.tsx` — Add inline form, item delete `×`, and row delete `×`.
2. `web/components/projects/__tests__/LookupMappingTable.test.tsx` — Add component unit tests.

## Verification

```bash
cd web && npm test -- --run components/projects/__tests__/LookupMappingTable.test.tsx
```
