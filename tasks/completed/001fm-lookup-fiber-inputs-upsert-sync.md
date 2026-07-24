---
id: 001fm
title: Fix lookup fiber source and destination values upsert and pre-fill on feed page
status: completed
created: 2026-07-24
priority: high
domain: fullstack / fibers / lookup-value-map / feed-page
depends-on: [001fk, 001fi]
---

# Task 001fm — Fix Lookup Fiber Source & Destination Values Upsert and Pre-fill

## Context

On the Feed Page (`/projects/[id]/feeds/[feedId]`), when an operator enters source values and destination CSV for a lookup fiber and triggers "AI Analyze":
1. `POST /projects/{project_id}/feeds/{feed_id}/fibers/{fiber_id}/lookup-inputs` (`submit_lookup_inputs`) is invoked.
2. The backend updates `fiber.proposed_mappings` and `fiber.status = "mapped"`, but **fails to upsert/sync `LookupValueMap`**.
3. On the frontend, `lookupDrafts` state is not pre-filled from existing `LookupValueMap` / `fiber.proposed_mappings` data on initial page load or after refresh. As a result, the source values and destination CSV textareas revert to empty strings `""` when the page reloads.

## Root Causes

### Backend:
1. **`submit_lookup_inputs` ignores `LookupValueMap`**: It writes `proposed_mappings` to `ProjectFiber` in the database, but does not create or update `LookupValueMap` for `(project_id, lookup_name)`.
2. **Existing draft `LookupValueMap` stays stale**: If a draft `LookupValueMap` already exists, `list_fibers()` skips re-creating it (`if not val_map:`), leaving `source_value_map`, `destination_table`, and `destination_mappings` out of sync.
3. **`_bridge_lookup_fiber_to_value_map` omits `destination_mappings`**: When a lookup fiber is approved by a stakeholder, `_bridge_lookup_fiber_to_value_map()` populates `source_value_map` and `destination_table`, but omits `destination_mappings`.

### Frontend:
1. **`lookupDrafts` state not pre-filled**: In `web/app/projects/[id]/feeds/[feedId]/page.tsx`, `draft = lookupDrafts[lName] || { sourceText: "", destText: "", ... }` defaults `sourceText` and `destText` to empty strings instead of deriving initial values from existing `lookupMap` / `fiber` data.

## Step-by-Step Execution Plan

### Step 1: Add `_sync_lookup_value_map_from_proposed_mappings()` helper in `fibers.py`
Insert `_sync_lookup_value_map_from_proposed_mappings()` around line 345 of `fibers.py` to synchronize `LookupValueMap` (`source_value_map`, `destination_table`, and `destination_mappings`).

### Step 2: Refactor `_bridge_lookup_fiber_to_value_map()`
Replace the manual dictionary building in `_bridge_lookup_fiber_to_value_map()` (lines 346-407 of `fibers.py`) with a call to `_sync_lookup_value_map_from_proposed_mappings()`.

### Step 3: Wire helper into `submit_lookup_inputs()`
In `submit_lookup_inputs()` (around line 850 of `fibers.py`), call `_sync_lookup_value_map_from_proposed_mappings()` before `db.commit()`.

### Step 4: Pre-fill frontend `lookupDrafts` in `page.tsx`
In `web/app/projects/[id]/feeds/[feedId]/page.tsx` (around line 887), derive default values for `sourceText` and `destText` from `lookupMap` when `lookupDrafts[lName]` is unedited.

### Step 5: Add Backend API Test in `test_lookup_fiber_api.py`
Add `test_submit_lookup_inputs_upserts_lookup_value_map` to `engine/tests/test_lookup_fiber_api.py`.

## Files to Change

1. `engine/src/migrations_engine/management/fibers.py` — Add helper and wire into `submit_lookup_inputs()` and `_bridge_lookup_fiber_to_value_map()`.
2. `web/app/projects/[id]/feeds/[feedId]/page.tsx` — Derive default text for unedited lookup fiber textareas.
3. `engine/tests/test_lookup_fiber_api.py` — Add test verifying `LookupValueMap` upsert.

## Verification

1. Run backend tests: `pytest tests/test_lookup_fiber_api.py -v`
2. Run full backend suite: `pytest -v`
3. Run frontend tests: `cd web && npm test -- --run`
