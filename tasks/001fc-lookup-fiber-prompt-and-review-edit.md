---
id: 001fc
title: Lookup fiber — destination-anchored AI output + review page source value editing
status: active
created: 2026-07-23
priority: high
domain: lookup-fiber / ai-prompt / fibers.py / feed-page / review-page
supersedes: 001fb
---

# Task 001fc — Lookup Fiber: Destination-Anchored Mapping + Review Page Editing

## The Mental Model (what this task establishes)

The **destination lookup table is the anchor**. All its rows are always returned — matched or not.
The operator sees:

| Dest ID | Destination Value | Source Value |
|---|---|---|
| 3 | Approved | `APPROVED` ← AI pre-filled |
| 2 | Under Review | `UNDER_REVIEW` ← AI pre-filled |
| 5 | Paid | `PAID` ← AI pre-filled |
| 4 | Rejected | `REJECTED` ← AI pre-filled |
| 1 | Pending | `PENDING` ← AI pre-filled |
| 6 | Cancelled | _(blank — operator types in)_ |

AI does best-effort matching. Operator fills in blanks or corrects AI mistakes on the
**review page** directly in the grid.

---

## Problem 1 — AI prompt is source-anchored (wrong direction)

**Current AI output** (`source_value` → `dest_id` UUID):
```json
{ "source_value": "APPROVED", "dest_id": "<uuid>", "confidence_score": 0.99 }
```

**Required AI output** (destination-anchored, all rows, some with null source):
```json
{
  "proposals": [
    { "dest_id": "3", "dest_value": "Approved",    "source_value": "APPROVED",     "confidence_score": 0.99 },
    { "dest_id": "2", "dest_value": "Under Review","source_value": "UNDER_REVIEW", "confidence_score": 0.98 },
    { "dest_id": "5", "dest_value": "Paid",        "source_value": "PAID",         "confidence_score": 0.99 },
    { "dest_id": "4", "dest_value": "Rejected",    "source_value": "REJECTED",     "confidence_score": 0.99 },
    { "dest_id": "1", "dest_value": "Pending",     "source_value": "PENDING",      "confidence_score": 0.99 },
    { "dest_id": "6", "dest_value": "Cancelled",   "source_value": null,           "confidence_score": 0.0 }
  ],
  "unmatched_source_values": []
}
```

Where:
- `dest_id` — primary key value from the destination row (the ID the proc needs)
- `dest_value` — best human-readable label from the destination row
- `source_value` — matched source value, or `null` if no confident match
- `confidence_score` — 0.0 if no match

---

## Problem 2 — `LookupMapping` is source-anchored (schema constraint)

Current: `source_entry_id` is `NOT NULL` — a `LookupMapping` row always requires a source entry.

For destination rows with no matched source value, no `LookupMapping` row is created today.

**Fix**: Make `source_entry_id` nullable. Create a `LookupMapping` row for **every** destination
row — matched ones have `source_value` + `source_entry_id`; unmatched ones have `source_value=null`,
`source_entry_id=null`, `status="unmatched"`.

This requires a **hand-written Alembic migration** (I18).

---

## Problem 3 — Review page cannot edit source values for lookup mappings

The review page renders lookup groups from `LookupValueMap.source_value_map`. It cannot:
1. Show destination rows that have no source mapping
2. Let operator type a source value for an unmatched destination row
3. Persist that edit back to the fiber `LookupMapping` rows

**Fix**: Review page fetches ALL `LookupMapping` rows for the fiber (including `status="unmatched"`
ones). Renders a grid where source value column is editable. PATCH route updates `LookupMapping`
and optionally creates a `LookupSourceEntry` if the typed source value is new.

---

## Problem 4 — Display (`dest_row`) currently stores UUID not business key

Current `dest_row = {"id": UUID, "label": garbled}`.
Required `dest_row = {"id": "3", "label": "Approved"}` — what AI extracts.

---

## Problem 5 — `_bridge_lookup_fiber_to_value_map`

Currently reads `mapping.dest_row.get("id")` — after the fix this correctly gives `"3"`.
The bridge already uses this pattern — it will work once `dest_row` is fixed.

---

## Out of Scope

- No changes to `LookupValueMap` model — `source_value_map` and `destination_table` remain
- No codegen changes — already reads `dest_row["id"]`
- No `LookupMappingTable` UI component logic change — just data binding fix

---

## Red Flags

1. **Migration required** — `source_entry_id` nullable change requires Alembic migration. Follow I18.
2. **Local LLM prompt** — Ollama adapter appends Pydantic schema. Prompt must be example-driven
   and explicit. `source_value` must be typed as `str | None` in Pydantic.
3. **Deduplication** — destination CSV dump often has many duplicate rows; deduplicate by
   `row_data` content before sending to AI. Only send unique rows.
4. **`dest_id` in prompt is business key** (e.g. `"3"`), not UUID. Backend scans
   `LookupDestEntry.row_data` using `_extract_destination_id()` heuristic to find the UUID FK.
5. **Review page needs fiber context** — to PATCH individual `LookupMapping` rows, the review
   page needs the `fiberId` for the lookup fiber. Currently available in `fibers` state.
6. **PATCH for unmatched rows** — when operator types a source value for an unmatched row,
   if the source value is new, create a `LookupSourceEntry` and update the `LookupMapping`.
7. **Test suite** — `FakeLookupAdapter` needs updating. Assertions on `LookupMapping` rows
   must expect nullable `source_value`. Migration must run in test DB setup.
