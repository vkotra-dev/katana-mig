---
id: 001go
title: End-to-End Prop Wiring for Lookup Mapping Actions in ReviewGrid and Review Page
status: active
created: 2026-07-24
priority: high
domain: frontend / review-page / review-grid
depends-on: [001gn]
---

# Task 001go — End-to-End Prop Wiring for Lookup Mapping Actions in ReviewGrid and Review Page

## Context

Wire lookup mapping action handlers (`onAddSourceValue`, `onRemoveSourceValue`, `onDeleteDestinationGroup`) from the Review Page through `ReviewGrid.tsx` into `LookupMappingTable.tsx`.

## Requirements

1. **ReviewGridProps**: Add `onAddSourceValue`, `onRemoveSourceValue`, and `onDeleteDestinationGroup` to `ReviewGridProps` and forward them to `<LookupMappingTable>`.
2. **Review Page Handlers**:
   - Implement `handleDeleteDestinationGroup` and `handleDeleteDestinationGroupByLookup` in `web/app/projects/[id]/feeds/[feedId]/review/page.tsx` using `patchLookupValueMap({ destinationMappings: updatedMappings })`.
   - Pass `handleAddSourceByLookup`, `handleRemoveSourceByLookup`, and `handleDeleteDestinationGroupByLookup` to `<ReviewGrid>`.

## Files to Change

1. `web/components/projects/ReviewGrid.tsx` — Update `ReviewGridProps` and forward callbacks to `LookupMappingTable`.
2. `web/app/projects/[id]/feeds/[feedId]/review/page.tsx` — Implement group delete handler and pass props into `ReviewGrid`.

## Verification

```bash
cd web && npm test -- --run
```
