---
id: 001fb
title: Fix lookup fiber AI prompt — output id, source_value, dest_value
status: active
created: 2026-07-23
priority: high
domain: lookup-fiber / ai-prompt / fibers.py
---

# Task 001fb — Fix Lookup Fiber AI Prompt Contract

## Context

The lookup fiber currently submits source values (e.g., `APPROVED`, `UNDER_REVIEW`) and destination
lookup table rows (e.g., `id, is_payable, is_terminal, status_code, status_name, display_order`) to
the AI for mapping.

### Current broken flow

1. Backend pre-processes destination rows with `_extract_destination_label()` — a heuristic that
   only checks exact column names (`name`, `label`, etc.) and fails completely for columns like
   `status_name`, `display_name`, `type_description`.
2. AI receives lossy `{id: UUID, value: "Y | N | APPROVED | Approved | 3"}` — garbled concatenated
   fallback — not the real data.
3. AI returns only `dest_id` (a system UUID). No business key. No human label.
4. The stored `dest_row` in `LookupMapping` is `{id: UUID, label: heuristic_garbage}`.
5. UI can't display properly. Codegen can't extract the right FK value.
6. Destination CSV rows are fed to AI with duplicates (same row appears 4–5×), burning tokens.

## Objective

Fix the full pipeline so:

1. AI receives the **raw deduplicated destination rows** — full column data.
2. AI returns: `source_value`, `id` (business key, e.g. `"3"`), `dest_value` (human label, e.g.
   `"Approved"`), `dest_id` (system `_ref` UUID for DB linking), `confidence_score`.
3. Backend stores `dest_row = {"id": "3", "label": "Approved"}` — clean, no heuristics.
4. UI renders: Column 1 = `APPROVED`, Column 2 = `Approved (3)`.
5. Codegen reads `dest_row["id"]` = `"3"` to feed FK into the proc.

## Out of Scope

- No DB model changes (no migration needed — `dest_row` JSON column already exists)
- No UI component changes (LookupMappingTable already renders `label (id)` format)
- No codegen changes (already reads `dest_row["id"]`)
- No changes to the manual patch path (`patch_mapping` in `fibers.py`) — that path already saves
  simplified `dest_row` from `_extract_destination_label`; fix it as a follow-up if needed

## Blast Radius

- `engine/src/migrations_engine/ai/prompts/lookup_mapping.yaml` — prompt contract changes
- `engine/src/migrations_engine/management/fibers.py` — payload construction, Pydantic model,
  dest_row saving logic
- `engine/tests/test_lookup_fiber_api.py` — `FakeLookupAdapter` and assertion updates

## Red Flags

1. **Duplicate rows** — destination CSV rows can repeat many times; must deduplicate on
   `row_data` content before sending to AI.
2. **`dest_entry_by_id` lookup** — currently keyed by `entry_id` UUID. AI will echo the `_ref`
   UUID field back as `dest_id`, so the lookup still works — do not change the key.
3. **AI field `id` vs model field `id`** — `_LookupProposal.id` is the business key extracted by
   the AI. This is a new field. Do not confuse with the DB primary key or `entry_id`.
4. **Test suite** — `FakeLookupAdapter` currently returns `{"source_value", "dest_id",
   "confidence_score"}`. Adding `id` and `dest_value` to `_LookupProposal` will cause validation
   failures. Must update.
5. **`_extract_destination_id` / `_extract_destination_label` imports** — the import line in
   `fibers.py` must be cleaned up; these heuristics are no longer needed in the AI path.
