---
id: 001fl
title: Fix Destination Value column showing raw ID instead of human-readable label in Review page
status: active
created: 2026-07-24
priority: high
domain: frontend / review-page / lookup-mapping-table
depends-on: [001fk, 001fj]
---

# Task 001fl — Fix Destination Value Column Showing Raw ID

## Context

On the Review Page (`/projects/[id]/feeds/[feedId]/review`), the lookup mapping grid displays mapped destination values.
When rendering destination mappings, each row should display a human-readable label along with the raw ID in parentheses (e.g. `Paid (2)` or `Active (ACTIVE)`).

Currently, for legacy lookup maps (or maps built via the frontend fallback in `review/page.tsx`), the "Destination Value (ID)" column displays raw values like `2`, `4`, or UUIDs like `6f24684f-c1af-49e9-9cc3-437358a40783` without any label description.

## Root Cause

1. In `web/app/projects/[id]/feeds/[feedId]/review/page.tsx` (lines 463-464), when building `destinationMappings` from `sourceValueMap` in fallback mode, `destLabel` is extracted using:
   ```typescript
   const destLabel = destRow ? ((destRow as any).name ?? (destRow as any).value ?? "") : "";
   ```
   This extractor only checks `name` and `value`. Most reference table rows store their display label under `"label"` (e.g. `{"id": "2", "label": "Paid"}`). Because `"label"` is omitted from the key check, `destLabel` evaluates to `""`.

2. `LookupMappingTable.tsx` checks `if (group.destLabel && group.destLabel !== group.destId)`. Since `destLabel` is `""`, it falls through to rendering `group.destId || "—"`, outputting the raw ID.

3. Additionally, the table header in `LookupMappingTable.tsx` is named `"Destination Value (ID)"`, which is misleading once human-readable labels are displayed.

## Step-by-Step Execution Plan

### Step 1: Widen label extractor in `web/app/projects/[id]/feeds/[feedId]/review/page.tsx`
Add a robust `extractDestLabel(row)` helper before line 456 that checks keys `["label", "name", "description", "desc", "val", "value", "display"]` followed by substring key searches, matching the backend `_extract_destination_label()` priority. Use it at line 463 to set `destLabel`.

### Step 2: Update table header in `web/components/projects/LookupMappingTable.tsx`
Change line 55 from `<th className="py-2 w-1/3">Destination Value (ID)</th>` to `<th className="py-2 w-1/3">Destination</th>`.

### Step 3: Run Vitest Unit Tests
Execute `npm test -- --run components/projects/__tests__/LookupMappingTable.test.tsx` inside `web/`.

## Files to Change

1. `web/app/projects/[id]/feeds/[feedId]/review/page.tsx` — Widen legacy fallback label extractor.
2. `web/components/projects/LookupMappingTable.tsx` — Update table header from `Destination Value (ID)` to `Destination`.

## Verification

1. Run frontend unit tests (`npm test` in `web/`).
2. Verify visual rendering format `Label (ID)` on the Review Page for reference table mappings.
