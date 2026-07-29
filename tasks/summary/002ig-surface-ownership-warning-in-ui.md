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

- 340/342 frontend tests pass (2 pre-existing failures in `codegen/page.test.tsx` unchanged); 4 new tests added:
  - Feed page (2): warning present + empty message suppressed when `mappingOwnershipWarnings` has entries; empty message still shows when no conflict
  - Codegen page (2): button hidden + warning shown when ownership conflict exists; button visible when no conflict
- Zero new TypeScript errors from these changes.

## Domain Updates

`docs/domain/ui.md` updated — Feeds screen note documents button replacement on ownership conflict.
