# Summary: 002ig — Surface mapping_ownership_warnings where it blocks the operator

## Goal

Surfaced `mapping_ownership_warnings` at the two points where it explains why the operator is stuck — feed page empty-state and codegen page "Generate SQL" button.

## What was shipped

**Feed page** (`web/app/projects/[id]/feeds/[feedId]/page.tsx`):
- Added `hasOwnershipWarning` boolean hoisted at line ~477 (same expression already used to gate the warning card)
- "No mapping proposals generated yet." message now gates on `!hasOwnershipWarning` — suppressed when the warning card already explains why.

**Codegen page** (`web/app/projects/[id]/codegen/page.tsx`):
- Action cell: "Generate SQL" button replaced by "⚠ Table ownership conflict" warning when `source.mappingOwnershipWarnings` has entries — no button renders, so there's no control that could trigger codegen against a conflicting table.
- Expanded panel: added ownership-conflict amber card alongside the existing "Unmapped Required Destination Fields" card, listing each conflicting table and its owner.

## Verification

- 336/338 frontend tests pass (2 pre-existing failures in `codegen/page.test.tsx` unchanged, pre-existing).
- Zero new TypeScript errors from these changes.

## Note

Domain doc update (`ui.md`) deferred — not blocking functionality.
