# Task 001bi — Lookup Fiber Two-Textarea Input

**Plan:** `plans/2026-07-05-001bi-lookup-fiber-two-textarea-input.md`

## Context

The feed AI analyze call (AI Call 1: feed columns + DDL) produces two kinds of output:

- **Mapping objects** (direct / detail_fk bindings) — AI has already mapped source column → destination column. These flow straight to the review grid with no further operator input.
- **Lookup objects** (lookup_fk bindings) — AI identifies *which field* needs a value lookup and *which reference table* backs it, but cannot map production values because it only sees column names. Operator must supply the actual values before a second AI call can map them.

The canonical home for all lookup value input is the feed detail workspace (`/feeds/[feedId]`). The old standalone lookup page (`/sources/[sourceId]/lookup`) served this purpose before the feed workspace existed; it modelled source values as coming from the feed window sample rather than the operator. With the feed workspace now live, the old page is superseded and creates a conflicting entry point.

## Current State

**Feed detail lookup fiber cards** (`/feeds/[feedId]/page.tsx`):
- Source values sourced from the feed window value summary (capped sample, not the production domain)
- One small `<input type="text">` per value for the operator to type a destination ID
- "Run AI" always enabled regardless of whether destination rows have been provided
- No way to supply destination reference rows at all

**Old lookup page** (`/sources/[sourceId]/lookup/page.tsx`):
- Updated by 001be to show AI-detected reference tables and read-only lookup name badges
- Still uses the old source-values-from-feed-window model (`discovery_type="sample"`)
- Still accessible from the old source list action links (now removed) but reachable via direct URL
- Directly contradicts the new two-textarea model in the feed workspace

## Objective

1. Replace the per-value text inputs in each lookup fiber card with two text areas and a conditionally enabled AI Analyze button — the correct operator workflow.
2. Remove the old standalone lookup page to eliminate the conflicting entry point.

## Scope

### A. Feed detail lookup fiber cards — `web/app/projects/[id]/feeds/[feedId]/page.tsx`

Remove:
- Per-value `<input>` loop sourced from `valueSummaries`
- `lookupEdits` state, `savingLookup` state, `handleSaveLookup` handler
- `valueSummaries` state and the `listFeedValueSummaries` fetch
- `handleRunAiLookup` handler (replaced by `handleAnalyzeLookup`)
- `generateLookupSnapshot` import (only used by `handleRunAiLookup`)
- Save Draft and Run AI buttons from lookup fiber card JSX

Add:
- `lookupDrafts` state keyed on `lookupName`, each holding `{ sourceText: string; destText: string; analyzing: boolean; error: string | null }`
- Per lookup fiber card — two text areas:
  - **Textarea 1** — label "Source values (one per line)"; placeholder `VALUE_A\nVALUE_B\n...`
  - **Textarea 2** — label "Rows from {referenceTableName} (CSV or JSON)"; placeholder `id,description\n1,Active\n2,Inactive\n...`
- **"AI Analyze" button** — disabled when either textarea is empty or an AI call is in flight
- On click: parse source text into `string[]`; parse dest text as CSV (header row) or JSON-per-line into `Record<string, unknown>[]`; call `submitLookupInputs`; reload lookup maps on success; show inline error on parse failure

### B. Remove old lookup page

Delete:
- `web/app/projects/[id]/sources/[sourceId]/lookup/page.tsx`
- `web/app/projects/[id]/sources/[sourceId]/lookup/page.test.tsx`

### C. Create `submitLookupInputs` in `web/lib/lookup-api.ts`

`generateLookupSnapshot` is the existing function but it posts to `/lookup-snapshots` with only `{ lookup_name }` — wrong endpoint and shape for the new design. Do not modify or remove it (other callers may use it). Add a new export:

```typescript
export interface SubmitLookupInputsInput {
  lookupName: string;
  sourceValues: string[];
  destinationRows: Record<string, unknown>[];
}

export async function submitLookupInputs(
  token: string,
  projectId: string,
  sourceDefinitionId: string,
  input: SubmitLookupInputsInput,
): Promise<void>
// POSTs to /projects/{projectId}/sources/{sourceDefinitionId}/lookup/submit
```

## Out of Scope

- The mapping grid and review grid — unaffected.
- The old mapping page (`/sources/[sourceId]/mapping`) — kept for now; separate decision.
- Backend changes to `submit_lookup_inputs` — additive behaviour already specified in 001bd.
- The "Upload New Slice" section in the feed detail — separate concern.

## Acceptance Criteria

- Each lookup fiber card shows exactly two text areas (source values + destination rows) and an "AI Analyze" button.
- "AI Analyze" is disabled until both text areas are non-empty.
- Submitting calls the lookup inputs endpoint with parsed source values and destination rows.
- After submission the review grid updates to reflect the new value mappings.
- No per-value individual inputs remain in the lookup fiber cards.
- No `valueSummaries` fetch on feed detail page load.
- Navigating to `/projects/[id]/sources/[sourceId]/lookup` returns 404.
- All remaining tests pass.

## Pitfalls

- The dest textarea must handle Windows line endings (`\r\n`) — strip `\r` before splitting.
- Parse defensively: try JSON-per-line first (`trimStart().startsWith("{")`), fall back to CSV. Show inline textarea error rather than letting malformed input reach the backend.
- `submitLookupInputs` is additive — re-submitting the same textarea content is safe; the backend deduplicates.
- Keep `lookupMaps` state and the `listLookupValueMaps` reload — the review grid still reads from it after the AI call.
- Deleting the old lookup page may leave a dangling import if any other file imports from it — grep before deleting.

## Commit

- `feat(001bi): two-textarea lookup fiber input and remove superseded lookup page`
