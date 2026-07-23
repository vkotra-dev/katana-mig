---
id: 001fc
title: Lookup fiber — destination-anchored AI output + review page source value editing
status: completed
created: 2026-07-23
completed: 2026-07-23
domain: lookup-fiber / ai-prompt / fibers.py / feed-page / review-page
---

# Task 001fc Summary — Lookup Fiber Prompt & Review Page Interop

## Key Accomplishments

1. **Alembic Migration 0038**: Made `source_entry_id` and `source_value` nullable on `lookup_mappings` table (`0038_lookup_mapping_nullable_source.py`).
2. **`db/models.py`**: Updated `LookupMapping` model fields to `Mapped[str | None]` with `nullable=True`.
3. **Destination-Anchored AI Prompt Contract (`lookup_mapping.yaml`)**:
   - Rewrote prompt to be destination-anchored (1 proposal per destination row).
   - Prompt receives raw CSV `destination_rows` with original column headers.
   - Instructs LLM to return `dest_id` (business key like `"3"`), `dest_value` (human label like `"Approved"`), and `source_value` (or `null` if unmapped).
   - Added explicit worked examples and RULES for local LLMs (Ollama).
4. **Backend Resolution (`fibers.py`)**:
   - Deduplicates `destination_rows` by content hash before sending to AI.
   - Uses `_extract_destination_id(entry.row_data)` heuristic to resolve business keys (`dest_entry_by_pk`), supporting `id`, `status_id`, `code`, etc.
   - Creates a `LookupMapping` for **every** destination row (matched rows get `status="proposed"`, unmatched ones get `source_value=None`, `status="unmatched"`).
   - Saves `dest_row` as `{"id": proposal.dest_id, "label": proposal.dest_value}` across AI resolution, manual `patch_mapping` edits, and `list_fibers` auto-heal.
   - Updated `_bridge_lookup_fiber_to_value_map` to skip null `source_value`s and populate `LookupValueMap.source_value_map` with business keys.
5. **API & Test Harness Update**:
   - Updated `LookupMappingPatchRequest` and `LookupMappingResponse` Pydantic schemas.
   - Updated `FakeLookupAdapter` in `test_lookup_fiber_api.py`.
   - Verified **369 backend tests** and **317 frontend tests** pass cleanly.

## Files Changed

- `engine/migrations/versions/0038_lookup_mapping_nullable_source.py` (New)
- `engine/src/migrations_engine/db/models.py`
- `engine/src/migrations_engine/ai/prompts/lookup_mapping.yaml`
- `engine/src/migrations_engine/management/fibers.py`
- `engine/src/migrations_engine/api/schemas.py`
- `engine/tests/test_lookup_fiber_api.py`
