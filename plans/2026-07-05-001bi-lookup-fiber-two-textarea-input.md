# Plan: 001bi — Lookup Fiber Two-Textarea Input

- **Task Link:** [001bi-lookup-fiber-two-textarea-input.md](file:///Users/vjkotra/projects/katana/tasks/001bi-lookup-fiber-two-textarea-input.md)
- **Domain Link:** [ui.md](file:///Users/vjkotra/projects/katana/docs/domain/ui.md)

## Current State

- Each lookup fiber card in `/feeds/[feedId]` shows a list of individual value summaries from the feed window and allows the operator to input destination values one by one in text boxes.
- Stands in contrast to the two-textarea flow where source values are entered in bulk, reference rows are pasted in bulk, and the backend resolves them together via AI.
- There is an old, superseded lookup page at `/sources/[sourceId]/lookup` which contains obsolete sampling and rendering logic.

## Objective

1. Replace the per-value inputs in the lookup fiber cards with two bulk textareas (Source Values + Destination reference rows) and an "AI Analyze" button.
2. Add a `submitLookupInputs` API helper that maps to the new POST endpoint.
3. Remove the old standalone lookup page to keep the route map clean.

## Out of Scope

- Modifying mapping grid or review grid structures.
- Modifying backend AI resolver logic.

## Blast Radius

Moderate. Removes the `/sources/[sourceId]/lookup` route and updates the feed detail page interface.

## File Changes

### `web/lib/lookup-api.ts`

- Export `submitLookupInputs` function to POST to `/projects/{projectId}/sources/{sourceDefinitionId}/lookup/submit`.

### `web/app/projects/[id]/feeds/[feedId]/page.tsx`

- Remove imports of `listFeedValueSummaries`.
- Remove `valueSummaries`, `lookupEdits`, `savingLookup` states.
- Remove `handleSaveLookup` and `handleRunAiLookup` handlers.
- Add `lookupDrafts` state keeping textarea strings/states per lookupName.
- Replace per-value card layout with two `<textarea>` blocks (one for source values, one for reference rows) and an "AI Analyze" button.
- Implement `handleAnalyzeLookup` to parse text areas (supporting JSON-per-line and CSV) and call `submitLookupInputs`.

### Delete Files

- `web/app/projects/[id]/sources/[sourceId]/lookup/page.tsx`
- `web/app/projects/[id]/sources/[sourceId]/lookup/page.test.tsx`

## Tests

- Update feed workspace page tests in `web/app/projects/[id]/feeds/[feedId]/page.test.tsx` to align with the new two-textarea layout.
- Run `npm test` to verify all tests pass.

## Verification

- Verify type-safety, clean compilation, and correctness of JSON/CSV parsing logic.

## Pitfalls

- CSV parsing must split lines on `\n` or `\r\n`, strip header columns, and construct clean dictionaries (`Record<string, unknown>[]`).
- JSON-per-line parsing must parse each line as a JSON object, catching errors gracefully.
- Ensure that the old `/sources/[sourceId]/lookup` references are not imported anywhere in other pages.

## Commit

- `feat(001bi): two-textarea lookup fiber input and remove superseded lookup page`
