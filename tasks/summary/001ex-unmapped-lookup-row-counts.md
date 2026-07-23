---
type: Summary
task: 001ex-unmapped-lookup-row-counts
date: 2026-07-23
outcome: completed
---

# Summary: 001ex — Display unmapped lookup row counts

## What was done

Added the `data_profile` JSON column to the `FeedSlice` database model to store source column row frequencies centrally (avoiding proliferation). The backend API `GET /projects/{id}/lookup-maps` now dynamically computes the `unmapped_row_count` by cross-referencing empty mappings in the `source_value_map` with the `data_profile` frequencies. The frontend `LookupMappingTable` and Feed Page lookup cards have been updated to display an amber warning badge when unmapped rows exist.

## File changes

| File | Change |
|------|--------|
| `engine/src/migrations_engine/db/models.py` | Added `data_profile` JSON column to `FeedSlice` model |
| `engine/src/migrations_engine/api/schemas.py` | Added `unmapped_row_count` to `LookupValueMapResponse` |
| `engine/src/migrations_engine/management/lookup_mapping.py` | Updated `list_lookup_value_maps()` to fetch the latest `FeedSlice` and compute `unmapped_row_count` dynamically |
| `engine/tests/test_lookup_mapping_api.py` | Added `test_get_lookup_maps_returns_unmapped_row_count` |
| `web/lib/lookup-api.ts` | Added `unmappedRowCount` to `LookupValueMapRecord` |
| `web/components/projects/ReviewGrid.tsx` | Appended `unmappedRowCount` to `LookupValueGroup` |
| `web/components/projects/LookupMappingTable.tsx` | Display amber warning badge when count > 0 |
| `web/app/projects/[id]/feeds/[feedId]/page.tsx` | Added warning badge to lookup fiber cards in the Feed Page |
| `web/app/projects/[id]/feeds/[feedId]/review/page.tsx` | Passed `unmappedRowCount` prop down to `LookupMappingTable` |

## Verification

Backend tests: All 10 lookup API tests pass.
Frontend tests: All 67 UI tests pass.
Code quality verified.
