---
id: 001fc
title: Lookup fiber — fix AI prompt contract + review page editing
status: active
created: 2026-07-23
priority: high
domain: lookup-fiber / ai-prompt / fibers.py / feed-page / review-page
supersedes: 001fb
---

# Task 001fc — Lookup Fiber: Fix AI Prompt Contract + Review Page Editing

## Context

The lookup fiber maps source values (e.g. `APPROVED`) to rows from a destination lookup table
(e.g. `id, is_payable, status_code, status_name, display_order`). There are two problems to fix:

### Problem 1 — AI prompt contract is broken

**Input A — source values** (unique values operator extracts from source CSV):
```
APPROVED, UNDER_REVIEW, PAID, PENDING, REJECTED
```

**Input B — destination lookup CSV** (full table dump, may contain duplicate rows):
```
id,is_payable,is_terminal,status_code,status_name,display_order
3,Y,N,APPROVED,Approved,3
2,N,N,UNDER_REVIEW,Under Review,2
...  (same rows repeated many times)
```

**Expected AI output:**
```json
{
  "proposals": [
    { "source_value": "APPROVED",     "id": "3", "dest_value": "Approved",     "confidence_score": 0.99 },
    { "source_value": "UNDER_REVIEW", "id": "2", "dest_value": "Under Review", "confidence_score": 0.99 },
    { "source_value": "PAID",         "id": "5", "dest_value": "Paid",         "confidence_score": 0.99 },
    { "source_value": "PENDING",      "id": "1", "dest_value": "Pending",      "confidence_score": 0.99 },
    { "source_value": "REJECTED",     "id": "4", "dest_value": "Rejected",     "confidence_score": 0.99 }
  ],
  "unmatched_source_values": []
}
```

Where:
- `source_value` — original source value
- `id` — primary key / unique identifier value from the matched destination row
- `dest_value` — best human-readable label from the matched destination row
- `confidence_score` — 0.0–1.0

**Current broken state:**
- AI receives lossy `{id: UUID, value: "Y | N | APPROVED | Approved | 3"}` — not raw rows
- AI only returns `dest_id` (UUID), `source_value`, `confidence_score` — no business key, no label
- Duplicate rows sent to AI — burns tokens, confuses local LLMs
- `dest_row` saved as `{id: UUID, label: garbled_heuristic_output}`

### Problem 2 — Review page lookup editing is broken

The review page builds `pairs` for `LookupMappingTable` from `lookupMaps`. The current pair
building logic:
```ts
const destRow = latestMap.destinationTable.find(
  (row) => String(row.id) === String(destId) || String(row.destination_id) === String(destId)
) || { id: destId };  // fallback: show raw UUID if row not found
```

Since `source_value_map` maps `source_value → dest_entry_id` (UUID), and `destination_table`
rows currently have `id = UUID`, the match works — but the **displayed value** is a UUID.

After the prompt fix, `dest_row.id` will be the business key (`"3"`) and `dest_row.label` will
be the human label (`"Approved"`). The review page pair building must be updated to use this.

Additionally, the review page `handleEditLookup` function saves edits to `LookupValueMap.sourceValueMap`.
Editing a lookup mapping from the review page currently calls `patchLookupValueMap`, but the
fiber-level `LookupMapping` records (the per-row confirmed/proposed state) are not updated.
The review page needs to also PATCH individual `LookupMapping` rows via the fiber PATCH endpoint
so the feed page stays in sync.

### Problem 3 — `source_value_map` stores UUID instead of business key

After the prompt fix, `LookupMapping.dest_row` will have `{id: "3", label: "Approved"}`.
But `_bridge_lookup_fiber_to_value_map` builds `source_value_map = {source_value: dest_entry_id}`
where `dest_entry_id` is still the UUID. Codegen or downstream consumers that read
`source_value_map` get a UUID not `"3"`.

**The bridge must be updated** to write `source_value_map = {source_value: dest_row["id"]}` —
the business key — not the UUID.

## Local LLM Considerations

The Ollama adapter appends the Pydantic JSON schema automatically to every prompt. The system
prompt must be:
- **Explicit**: every output field named and described
- **Example-driven**: concrete input → output example (local LLMs need this)
- **No ambiguity on which column is the PK**: say "the unique identifier column — typically named
  `id`, `code`, or a column ending in `_id`"
- **No ambiguity on which column is the label**: say "the most human-readable text column —
  prefer columns named `name`, `status_name`, `display_name`, `description`; avoid flag columns
  like `Y`/`N` or pure numeric columns"

## Out of Scope

- No DB model changes — `LookupMapping.dest_row` and `LookupValueMap.source_value_map` JSON
  columns are sufficient
- No Alembic migration needed
- No `LookupMappingTable` UI component changes — already renders `label (id)` format

## Red Flags

1. **`dest_entry_by_row_id` lookup** — after removing UUIDs from AI output, backend must scan
   `dest_entries` to find the `LookupDestEntry` whose `row_data` PK value matches `proposal.id`.
   Use `_extract_destination_id(row_data)` heuristic for the scan key — it already handles
   `id`, `code`, `key`, `_id` suffix columns.
2. **`_LookupProposal.id` field name** — `id` is a Python built-in. Pydantic allows it but
   be careful in surrounding code. If it causes issues use `dest_key` as the Pydantic field name
   with `alias="id"` in JSON.
3. **`source_value_map` UUID → business key migration** — the bridge function currently writes
   UUIDs. After the fix it will write business keys. Any existing approved `LookupValueMap` rows
   in prod still have UUID values — no retroactive fix, forward-only.
4. **Review page `handleEditLookup`** — currently only calls `patchLookupValueMap`. Must also
   call the fiber PATCH endpoint (`/fibers/:fiberId/mappings/:mappingId`) so individual
   `LookupMapping` rows reflect the operator's edit.
5. **Test `FakeLookupAdapter`** — must return `id` and `dest_value` in proposals.
   Assertions on `dest_row` shape must match `{id: business_key, label: human_label}`.
