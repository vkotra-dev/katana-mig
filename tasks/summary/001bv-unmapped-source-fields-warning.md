# Task 001bv Summary — Unmapped Source Fields Warning

Surfaced unmapped source columns as informational warnings on both the review page and feed workspace.

## Details
1. **Shared Parser Extraction**: Moved `splitCsvRow` to a dedicated `web/lib/csv-utils.ts` module to eliminate duplicated row-splitting logic.
2. **Review Grid**:
   - Extended `ReviewGridProps` to accept `unmappedSourceFields?: string[]`.
   - Rendered an amber warning banner container under destination table mappings if any unmapped columns exist.
   - Displayed each unmapped column name with up to 3 real-world sample values looked up case-insensitively from the slice's `sampleValues` dictionary.
3. **Review Page**:
   - Set the `allSourceColumns` state when fetching the approved `FeedSlice` headers.
   - Computed `unmappedSourceFields` by filtering out headers present in any destination table mapping snapshot binding, then passed the resulting array to `<ReviewGrid>`.
4. **Feed Workspace**:
   - Derived `unmappedSourceFields` from the latest slice's `headerCsv` and loaded mapping snapshots.
   - Rendered a compact amber chip warning panel below the Field Mappings accordions.
5. **Tests**: Added a unit test `renders unmapped source fields warning panel when columns are unmapped` verifying that missing columns and their sample values are rendered. All 266 frontend tests are passing.
