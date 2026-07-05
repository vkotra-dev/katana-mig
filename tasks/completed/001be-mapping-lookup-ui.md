# Task 001be — Mapping and Lookup UI: AI-Driven Field and Table Display

**Plan:** `plans/2026-07-04-001be-mapping-lookup-ui.md`

**Depends on:** 001bd (AI mapping extraction — adds `lookup_table_references` and AI-populated `lookup_name` to the mapping snapshot API response)

## Domain

- [source-model.md](/Users/vjkotra/projects/katana/docs/domain/source-model.md)
- [ui.md](/Users/vjkotra/projects/katana/docs/domain/ui.md)

## Current State

- The mapping page (`/sources/[sourceId]/mapping/page.tsx`) renders a "Lookup" column as a free-text
  `<input>` per binding row. The user must manually type a lookup name for fields that need value mapping.
  The AI proposal does not pre-populate this column; it is always empty on first load.
- The lookup page (`/sources/[sourceId]/lookup/page.tsx`) derives its lookup tabs from bindings where
  `lookupName != null`, but has no knowledge of which destination reference table backs each lookup.
  The user must manually paste destination rows (JSON or CSV) into a textarea with no guidance on
  where those rows should come from.
- Neither page uses the `lookup_table_references` that 001bd will add to the mapping snapshot API
  response.

## Problem

The current UI treats lookup field detection as a manual step. After 001bd, the AI identifies which
bindings need lookups and which destination reference table each lookup maps to. The UI must consume
this information rather than asking the user to re-derive it by hand.

Strictly no regex. All lookup field and table name knowledge comes from the AI-driven API response.

## Objective

Update the mapping and lookup pages to consume AI-detected lookup metadata:

1. **Mapping page** — show AI-proposed `lookup_name` as a read-only badge per binding (not a
   free-text input). Show the associated destination reference table name from
   `lookup_table_references` next to each lookup badge so the reviewer can verify the AI's choice.

2. **Lookup page** — surface the destination reference table name in each lookup tab header and in
   the destination table section label, so the user knows exactly which table's rows they are
   providing. Remove the editable `lookupName` text input (the name is now AI-determined).

## Scope

- Update `web/lib/mapping-api.ts` to expose `lookupTableReferences` from the API response
  (new field added by 001bd).
- Update `web/app/projects/[id]/sources/[sourceId]/mapping/page.tsx`:
  - Replace the free-text `<input>` for `lookupName` with a read-only badge showing the
    AI-proposed lookup name.
  - Add a secondary label showing the destination reference table name from
    `lookupTableReferences` for each binding that has a lookup.
  - Keep the `<select>` for destination field assignment unchanged.
- Update `web/app/projects/[id]/sources/[sourceId]/lookup/page.tsx`:
  - Pass `lookupTableReferences` from the approved mapping snapshot into `LookupFieldState`.
  - Show the reference table name in each tab header and in the destination table section label.
  - Remove the editable `lookupName` override input; the name comes from the approved snapshot.
- Update relevant tests in `mapping/page.test.tsx` and `lookup/page.test.tsx`.

## Out of Scope

- Pre-populating destination table rows by querying the destination database (no backend API for
  that exists yet).
- Any changes to the backend mapping or lookup API beyond what 001bd already delivers.
- Regex-based DDL parsing in the UI at any point.

## Acceptance Criteria

- Mapping page shows AI-proposed `lookup_name` as a non-editable badge; no free-text input.
- Mapping page shows the destination reference table name alongside each lookup badge.
- Lookup page tab headers include the reference table name from `lookup_table_references`.
- Lookup page destination table section label names the reference table the user should pull rows from.
- Lookup page has no editable `lookupName` override input.
- No regex in any changed UI file.
- Existing tests pass; new tests cover the lookup table reference display.

## Pitfalls

- `lookup_table_references` will be absent from snapshots created before 001bd — handle gracefully
  (fall back to showing only the lookup name, no reference table label).
- The mapping page currently marks `isDirty` when `lookupName` changes. Removing the input removes
  that dirty source — verify `isDirty` still tracks destination field edits correctly.
- Lookup page `LookupFieldState` keys on `lookupName`; if the name is now immutable, ensure the
  key is stable across re-renders.

## Commit

- `feat(001be): show AI-detected lookup fields and reference tables in mapping and lookup UI`
