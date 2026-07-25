---
id: 001gu
title: Wire AI unmatched_source_values Through to UI, Reject Cross-Destination Case-Insensitive Duplicates on Add
status: active
created: 2026-07-25
priority: critical
domain: backend / frontend / lookup-mapping
depends-on: [001gs]
---

# Task 001gu — Wire `unmatched_source_values` Through, Reject Cross-Destination Duplicates

## Context

Live-tested by hand (not simulated): a user clicked "+ Add another source value" on the `insurance_plan` lookup's "Bronze Standard" destination row and typed `"bronze standard"` (lowercase). Instead of stacking into the existing `07da836a-bd8b-4f19-b3bc-71b137033347` group, the system created a **phantom new group** with a fabricated `dest_id` and a garbled label. Root cause of *why* the wrong `dest_id` got sent traces to `review/page.tsx`'s fallback-escalation logic (documented separately, out of scope here). This task addresses two things confirmed to be **structurally wrong regardless of how a bad `dest_id` arrives**, per explicit product clarification:

### 1. The AI already computes an unmapped-values list — it's discarded today

`_LookupMappingResult` (`engine/src/migrations_engine/management/fibers.py:89-91`) already has:
```python
class _LookupMappingResult(BaseModel):
    proposals: list[_LookupProposal]
    unmatched_source_values: list[str] = []
```
Confirmed via a real AI call log for the `claim_status` lookup: the model correctly returns `"unmatched_source_values": []` (empty in that case, but the field is populated correctly by the model per its system prompt instructions). **Nothing after the AI call in `submit_lookup_inputs` ever reads `ai_result.unmatched_source_values`.** It's computed, then dropped on the floor — never stored on the fiber, never stored on the `LookupValueMap`, never surfaced in the UI. This is the literal "lost in cyberspace" gap: the exact mechanism the product owner asked for (unmapped source values, displayed like unmapped fields in table mapping — `ReviewGrid.tsx`'s `unmappedSourceFields`, lines 643-675) was already being computed and just never wired through.

### 2. `add_source_value` must reject cross-destination duplicates, not silently no-op or fabricate

Explicit clarification from product: when a new source value is added on the Review page, validate whether that value (**case-insensitive** — the user can make a casing mistake) is already mapped to *any other* destination. If a match is found under a **different** destination id, **reject the addition/update** — do not silently succeed, do not move it, do not fabricate a new destination for it. (If the case-insensitive match is under the *same* destination already being targeted, that's a harmless idempotent duplicate — allow it, no-op.)

Today `add_source_value` does neither of these things: no case-insensitive check at all, and it will fabricate a brand-new `destination_mappings` group for literally any `dest_id` string with zero validation against real data.

### Also noticed, filed separately (do not do in this task)

The raw AI call log used to confirm point 1 also revealed that `_parse_destination_csv`'s output already has every CSV cell wrapped in stray quote characters *before* the AI ever sees it (e.g. `"id": "'2'"`, `"status_code": "'’UNDER_REVIEW''"`) — the AI is instructed to and does strip these in its own output, but the underlying CSV-parsing/quote-stripping gap is real and affects any `destination_table` shape that doesn't route through the AI's cleanup (as `insurance_plan`'s apparently didn't — still not fully traced). This is a separate, likely-systemic parsing bug, not folded into this task. Consider filing as 001gv if the product owner wants it addressed.

## Requirements

### 1. New column: `unmapped_source_values`

Add `unmapped_source_values: list[str]` (JSON, default `[]`, not null) to `LookupValueMap`. Alembic migration following migration `0040`'s exact pattern (`engine/migrations/versions/0040_add_destination_mappings_column.py`) — MySQL `ADD COLUMN IF NOT EXISTS` / backfill `[]` / `MODIFY COLUMN ... NOT NULL`. New revision `0041`, `down_revision = "0040"` (confirmed current head via `alembic heads`).

### 2. Wire the AI's `unmatched_source_values` through `submit_lookup_inputs`

`_sync_lookup_value_map_from_proposed_mappings` (`fibers.py:346-416`) needs a new parameter, e.g. `unmatched_source_values: list[str] | None = None`, and must set it on `val_map.unmapped_source_values` in **both** branches (existing `val_map` update, and new `LookupValueMap(...)` construction). `submit_lookup_inputs` (`fibers.py:757-880`) must pass `ai_result.unmatched_source_values` through at its call site (`fibers.py:872-877`).

### 3. Rewrite `add_source_value` in `lookup_mapping.py`

New logic, in order:

1. **Case-insensitive lookup first**: fold/strip `src_val` and every existing key in `lookup_map.source_value_map`; find any existing key that matches case-insensitively.
2. **If a case-insensitive match exists**:
   - If it already maps to the **same** `dest_id` being requested: no-op, return success unchanged (harmless idempotent duplicate — e.g. re-adding `"Active"` when `"active"` is already mapped there).
   - If it maps to a **different** `dest_id`: **reject** — raise `AuthApiError` (409, matching the existing `lookup_map_approved` pattern's status code for "can't do this given current state") with a clear message naming the existing destination, e.g. `f"'{src_val}' is already mapped to a different destination ({existing_dest_id})."`. Do not modify `destination_mappings`, `source_value_map`, or `unmapped_source_values`.
3. **If no case-insensitive match exists at all**: validate `dest_id` against known destinations — an existing `destination_mappings` group's `dest_id`, or a row in `destination_table` (`row.get("id") or row.get("destination_id")`). If valid, proceed with the existing stack-or-create logic (unchanged from [[001gs]]/[[001gr]]).
4. **If `dest_id` doesn't match anything real** (and there was no case-insensitive match to reject or no-op against): do NOT create a `destination_mappings` group. Append `src_val` to `lookup_map.unmapped_source_values` (dedup), `flag_modified(lookup_map, "unmapped_source_values")`. Leave `destination_mappings`/`source_value_map` untouched.

The frontend already handles PATCH errors generically (`review/page.tsx`'s `handleAddSourceValue` catches and displays `err.message` via `setError`) — no new frontend error-handling plumbing is needed for the rejection case, just verify the existing catch surfaces the new 409 message intelligibly.

**Hard constraint: all decision-making stays server-side.** The case-insensitive match check, the no-op/reject/unmapped-routing decision, and the `dest_id` validation against `destination_table` must live *only* in this backend handler. Do not add any client-side pre-check, duplicate-prevention, or "is this value already mapped" logic in `LookupMappingTable.tsx`/`ReviewGrid.tsx`/`review/page.tsx` — the frontend's only job is to submit the `add_source_value` request and render whatever the API decides (success, no-op, or the 409 error message via the existing generic catch). The backend is the single source of truth here; do not duplicate or shadow this logic in JS, even as a "nicer UX" optimization — a second, drifting copy of this logic is exactly how the original incident's inconsistency happened in the first place (frontend and backend disagreeing about what `dest_id` a row actually maps to).

### 4. Schema & response plumbing

- `LookupValueMapResponse` (`api/schemas.py`): add `unmapped_source_values: list[str] = Field(default_factory=list)`.
- `_lookup_value_map_response` (`lookup_mapping.py`): include `unmapped_source_values=row.unmapped_source_values or []`.

### 5. Frontend: surface the list

- `web/lib/lookup-api.ts`: add `unmappedSourceValues: string[]` to `LookupValueMapRecord`; map `response.unmapped_source_values` in `mapLookupValueMapResponse`.
- `web/components/projects/LookupMappingTable.tsx`: new optional prop `unmappedSourceValues?: string[]`; render a compact amber warning list below the table when non-empty, visually consistent with (scaled down from, since this lives inside a per-lookup card, not a whole page section) `ReviewGrid.tsx`'s existing `unmappedSourceFields` block (lines 643-675).
- `web/components/projects/ReviewGrid.tsx`: pass `group.unmappedSourceValues` through to `<LookupMappingTable>`.
- `web/app/projects/[id]/feeds/[feedId]/review/page.tsx`: thread `latestMap.unmappedSourceValues` into the `lookupGroups` entries pushed for `ReviewGrid`.

**Explicitly out of scope**: any UI to *resolve* or reassign an unmapped value to a real destination from this list — read-only, matching the existing `unmappedSourceFields`/`unmappedDestinationFields` pattern (also read-only today).

## Files to Change

1. `engine/migrations/versions/0041_add_unmapped_source_values_column.py` — new migration.
2. `engine/src/migrations_engine/db/models.py` — add `unmapped_source_values` column to `LookupValueMap`.
3. `engine/src/migrations_engine/api/schemas.py` — add field to `LookupValueMapResponse`.
4. `engine/src/migrations_engine/management/fibers.py` — wire `ai_result.unmatched_source_values` through `_sync_lookup_value_map_from_proposed_mappings` (both branches) and its call site in `submit_lookup_inputs`.
5. `engine/src/migrations_engine/management/lookup_mapping.py` — rewrite `add_source_value` block (case-insensitive lookup → no-op / reject / validate / route-to-unmapped); update `_lookup_value_map_response`.
6. `web/lib/lookup-api.ts` — add `unmappedSourceValues` to `LookupValueMapRecord` + response mapping.
7. `web/components/projects/LookupMappingTable.tsx` — render unmapped list.
8. `web/components/projects/ReviewGrid.tsx` — pass prop through.
9. `web/app/projects/[id]/feeds/[feedId]/review/page.tsx` — thread data through.
10. `engine/tests/test_lookup_mapping_api.py` — new regression tests (see plan): reject-on-cross-destination-duplicate, no-op-on-same-destination-duplicate, unknown-dest_id-routes-to-unmapped, and AI-wiring test for `submit_lookup_inputs`.

## Verification

```bash
.venv/bin/python -m pytest engine/tests -q
cd web && npm test -- --run
```

Applying migration `0041` to the live dev MySQL DB is a separate, explicit step for whoever owns that environment — do not run it automatically as part of "verification."
