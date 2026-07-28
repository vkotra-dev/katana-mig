---
id: 001fb
title: Fix lookup fiber AI prompt — output id, source_value, dest_value
status: active
created: 2026-07-23
priority: high
domain: lookup-fiber / ai-prompt / fibers.py / feed-page / review-page
---

# Task 001fb — Fix Lookup Fiber AI Prompt Contract

## Context

The lookup fiber has two inputs:

**Input A — Source values** (unique values extracted from the source CSV by the operator):
```
APPROVED
UNDER_REVIEW
PAID
PENDING
REJECTED
```

**Input B — Destination lookup CSV** (pasted by the operator, full table dump, may contain duplicates):
```
id,is_payable,is_terminal,status_code,status_name,display_order
3,Y,N,APPROVED,Approved,3
2,N,N,UNDER_REVIEW,Under Review,2
5,Y,Y,PAID,Paid,5
...
```

The AI does the mapping work: for each source value it finds the best matching row in the
destination CSV and extracts the business key (`id`) and the human-readable label (`dest_value`).

## Current Broken State

1. **Backend pre-processes destination rows** using a heuristic `_extract_destination_label()` that
   only matches exact column names (`name`, `label`, etc.) — fails for `status_name`,
   `display_name`, `type_description`.
2. **AI receives lossy, garbled data** like `{id: UUID, value: "Y | N | APPROVED | Approved | 3"}`.
3. **AI output has no business key or label** — only `dest_id` (a system UUID), `source_value`,
   `confidence_score`.
4. **`dest_row` saved in DB is wrong** — `{id: UUID, label: "Y | N | APPROVED | Approved | 3"}`.
5. **Duplicate rows sent to AI** — same dest CSV row repeated 4–5× burns tokens and confuses
   local LLMs.
6. **`patch_mapping` (manual edit path)** also uses the same broken heuristic — so manually
   patching a mapping from the feed page also saves a wrong `dest_row`.
7. **Both feed page and review page** display from `dest_row.label` and `dest_row.id`, so both
   pages show garbled values.

## Correct Output Contract

**AI must return:**
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
- `source_value` — the original source value
- `id` — the value in the `id` column of the best-matching destination row (business key, used by codegen for FK)
- `dest_value` — the best human-readable label column value from the matching row (used by UI display)
- `confidence_score` — 0.0–1.0

## Local LLM Considerations

The Ollama adapter appends the Pydantic JSON schema to the system prompt automatically. The prompt
must therefore be:
- **Extremely explicit** — local LLMs do not infer intent well; every field must be named and described
- **Example-driven** — include a concrete input/output example in the system prompt
- **No ambiguity** — do not rely on the LLM to "figure out" which column is the ID vs the label

## Objective

Fix the full pipeline:

1. Prompt receives raw deduplicated destination rows and is explicit enough for local LLMs.
2. AI returns `source_value`, `id`, `dest_value`, `confidence_score`.
3. Backend looks up `LookupDestEntry` by scanning `row_data["id"] == proposal.id`.
4. `dest_row` saved as `{"id": proposal.id, "label": proposal.dest_value}` — clean, no heuristic.
5. `patch_mapping` (manual edit) also saves the same clean format.
6. Feed page and review page both display correctly via `LookupMappingTable`.

## Out of Scope

- No DB model changes — `LookupMapping.dest_row` JSON column is sufficient
- No migration needed
- No UI component changes — `LookupMappingTable` already renders `label (id)` format
- No codegen changes — already reads `dest_row["id"]`

## Red Flags

1. **Duplicate dest rows** — destination CSV dump often has repeated rows; must deduplicate by
   `row_data` content before sending to AI.
2. **Local LLM JSON compliance** — Ollama models sometimes wrap JSON in markdown fences or add
   extra keys. The OllamaAdapter already strips fences and retries 3×. The prompt must still be as
   tight as possible.
3. **`dest_entry_id` FK lookup** — AI returns business `id` value (e.g. `"3"`). Backend must scan
   `dest_entries` for `row_data["id"] == proposal.id` to find the UUID FK. No UUIDs in the prompt.
4. **`id` field name conflict** — `_LookupProposal.id` is the business key string. Pydantic allows
   it. Be careful it does not shadow Python's built-in `id()` in surrounding code.
5. **`patch_mapping` path** — must also be fixed to save business key + label, not UUID + heuristic.
   This is the manual operator edit path on the feed page.
6. **Test `FakeLookupAdapter`** — currently returns `{"source_value", "dest_id",
   "confidence_score"}`. Must add `id` and `dest_value`. Assertion on `dest_row` shape must match
   new format.
