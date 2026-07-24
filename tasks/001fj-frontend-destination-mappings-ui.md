# Task 001fj: Ultra-Lightweight React UI Update for Destination 1-to-Many Grid

- **Plan**: [2026-07-24-001fj-frontend-destination-mappings-ui.md](../plans/2026-07-24-001fj-frontend-destination-mappings-ui.md)
- **Domain**: [governance.md](../docs/domain/governance.md)

## Objective
Refactor React frontend components (`LookupMappingTable.tsx`, `review/page.tsx`, `page.tsx`) to directly render `destination_mappings` from the backend API, removing client-side data inversions and key mapping math. Wire inline `+ Add source` and `×` delete buttons to backend PATCH API actions.

## Requirements
1. Update `LookupMappingTable.tsx` to consume `destination_mappings` directly.
2. Render vertically stacked source inputs with inline `+ Add source` and `×` delete buttons per destination group.
3. Wire add/remove actions to `patchLookupValueMap()` API calls.
4. Clean up `review/page.tsx` and `page.tsx` data loading logic.
5. Verify 100% vitest frontend test suite health (`npm run test` passes 100%).
