# Plan: Rewrite lookup fiber mapping to use strict ID/Value pairs

**Task:** [001fa-lookup-fiber-rewrite](../tasks/001fa-lookup-fiber-rewrite.md)
**Domain:** [Lookup Value Mapping](../docs/domain/lookup-value-mapping.md) *(or relevant section in governance/runs)*

## Current State
The backend and frontend both deal with entire reference rows encoded as JSON (`row_data`). The UI renders these as complex, dynamic grid boxes. AI is burdened with parsing these complex JSON schemas for every lookup map.

## Objective
Tighten the lookup fiber mapping logic to use explicit ID and Label (Value) pairs across the entire pipeline. The UI grid should be simple and mimic the field mapping style: `{label} ({id})`.

## Out of Scope
- Rewriting core run engine or overall fiber approval mechanisms.
- Changing how sources are analyzed or structured.

## Blast Radius
- `migrations_engine.management.fibers` (payload gen, result mapping)
- `migrations_engine.management.lookup_mapping` (ID/label extraction)
- `migrations_engine.ai.prompts.lookup_mapping.yaml`
- `LookupMappingTable.tsx` and related frontend components (simplifying props).
- Tests (`test_lookup_fiber_api.py`, frontend tests).

## File Changes
1. **`engine/src/migrations_engine/management/lookup_mapping.py`**:
   - Write `extract_lookup_label(row: dict) -> str` heuristic.
2. **`engine/src/migrations_engine/management/fibers.py`**:
   - Update `payload` creation for AI to send `[{"id": "...", "value": "..."}]` instead of raw `row_data`.
   - Update `_bridge_lookup_fiber_to_value_map` to map `row_data` to `{"id": "...", "value": "..."}`.
3. **`engine/src/migrations_engine/ai/prompts/lookup_mapping.yaml`**:
   - Refine the prompt schema.
4. **`web/components/projects/LookupMappingTable.tsx`**:
   - Radically simplify `destLabel` to output `{label} ({id})`.
   - Adjust `AutocompleteDropdown` ingestion.

## Tests
- `tests/test_lookup_fiber_api.py`: Fix to match simpler payload array.
- Frontend tests for `LookupMappingTable` will need to mock simplified `destinationTable`.

## Verification
- Start a run with lookup analysis.
- Verify `tasks` endpoint works and displays cleanly in the UI.
- Verify AI outputs map correctly to the given reference rows.

## Pitfalls
- Handling rows with no clear "label" key.
- Ensuring `LookupValueMap` format changes don't break existing historical maps (if applicable, although usually we rebuild).

## Commit
`feat(lookup): rewrite reference rows into strict ID and value pairs to simplify UI`
