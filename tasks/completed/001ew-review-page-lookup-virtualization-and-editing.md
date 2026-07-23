---
type: Task
id: 001ew
slug: 001ew-review-page-lookup-virtualization-and-editing
title: Enable lookup mapping editing and virtualized scrolling on Review Page
status: ready
domain: docs/domain/governance.md
plan: plans/2026-07-23-001ew-review-page-lookup-virtualization-and-editing.md
---

## Context
Currently, the lookup section on the Review Page (`ReviewGrid.tsx`) only allows sign-off on AI-proposed lookup mappings. It lacks manual editing capability. The migration requires an N-to-1 mapping where multiple source values can map to a single destination row, but a single source value cannot map to multiple destination rows. The existing data model (`sourceValueMap` in `LookupValueMapRecord`) inherently enforces this, but the UI must expose a way to edit these values safely. 

Additionally, rendering massive lookup tables (thousands of rows) currently freezes the browser due to the lack of virtualization or progressive loading.

## Objective
1. Refactor `ReviewGrid.tsx` to support manual editing of the `destinationRow` for each `sourceValue` in the lookup section via dropdowns populated from the predefined `destinationTable`.
2. Implement progressive loading (using `IntersectionObserver` or a virtualization library) for the lookup table rows to handle massive datasets efficiently.
3. Wire the manual edit actions to update the backend data model.

## Out of Scope
- Adding new migration logic for 1-to-N mappings (strictly prohibited).
- Refactoring the entire `ReviewGrid.tsx` component; restrict changes to the lookup section (extract `LookupMappingTable` component).
- Altering the `LookupValueMapRecord` data structure fundamentally (use the existing `sourceValueMap` dictionary).

## Acceptance
- Operators can manually select a destination row for any given source value in the lookup table.
- The dropdown options are strictly populated from the AI/DB-provided `destinationTable`.
- The UI handles large lookup lists seamlessly without browser lag using progressive loading or virtual scrolling.
- A new or updated API endpoint handles saving these manual lookup modifications to the backend via `PATCH`.
- Changing a mapping clears or invalidates existing sign-offs for that specific lookup map.
