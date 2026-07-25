Task: tasks/completed/001gn-lookup-stacked-source-ui.md
Plan: plans/2026-07-24-001gn-lookup-stacked-source-ui.md
Commits: a7ce1db

## Changes Made

### `web/components/projects/LookupMappingTable.tsx`
- Replaced `window.prompt()` for adding a new source value alias with an inline form: local `addingDestId`/`newSourceValue` state, a text input (autofocus, Enter to confirm, Escape to cancel) plus Add/Cancel buttons, shown per destination group when `handleStartAdd` is triggered.
- Restyled the existing `×` remove-source-value button for visual consistency with other action buttons in the app (`hover:text-red-600`, `transition-colors`, explicit `focus:outline-none`).
- Added `font-mono` to the source-value display input's className.

### `web/components/projects/ReviewGrid.tsx`
- Added `onAddLookupSourceValue`/`onRemoveLookupSourceValue` props, wired through to `<LookupMappingTable>`.

### `web/app/projects/[id]/feeds/[feedId]/review/page.tsx`
- Passed `handleAddSourceByLookup`/`handleRemoveSourceByLookup` (already-defined handlers) into `<ReviewGrid>` via the new props.

### `web/components/projects/__tests__/LookupMappingTable.test.tsx`, `web/components/projects/__tests__/ReviewGrid.test.tsx`
- Added tests for the inline add-form interaction (open, type, confirm, cancel, Enter/Escape) and for the new prop wiring through `ReviewGrid`.

## Deviations from Plan

None known.

## Tests

`cd web && npm test -- --run` — passing at time of commit (re-verified as part of the full suite in later session work; no regressions attributable to this change).
