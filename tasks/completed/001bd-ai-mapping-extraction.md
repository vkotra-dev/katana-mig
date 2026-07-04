# Task 001bd — AI Mapping Extraction

**Plan:** `plans/2026-07-04-001bd-ai-mapping-extraction.md`

**Depends on:** 001w (Mapping Stage)

## Domain

- [governance.md](/Users/vjkotra/projects/katana/docs/domain/governance.md)
- [source-model.md](/Users/vjkotra/projects/katana/docs/domain/source-model.md)

## Current State

- The mapping review backend currently uses a brittle regex DDL parser (`_parse_ddl`) to extract the first table name and its columns from `destination_schema_ddl`.
- It mixes columns of all subsequent tables into a single flat list under that first table's name.
- It forces the AI model to map CSV source fields to this single merged table schema — one table, one snapshot per AI call.
- This prevents a single feed from mapping to multiple destination tables and blocks FK-type classification.

## Objective

Replace the regex-based DDL parser with AI-based multi-table extraction and field mapping. The AI receives the full DDL and feed source columns, identifies **all** matching destination tables, maps fields per table, and classifies each binding as `direct`, `detail_fk`, or `lookup_fk`. The backend creates one `MappingSnapshot` per identified table and returns `lookup_table_references` so the UI knows which reference tables back each lookup FK.

## Scope

- Refactor `MappingSnapshot` database model to:
  - Add `source_definition_id` column.
  - Add `destination_fields` JSON column to store valid destination fields at the time of proposal.
- Create a database migration to add `source_definition_id` and `destination_fields` columns to `mapping_snapshots` table using `batch_alter_table` with a proper `downgrade()` implementation.
- Update Pydantic AI response models to support **multi-table output**:
  - `_FieldMappingProposal` becomes a wrapper with `tables: list[_TableMapping]`.
  - `_TableMapping` holds `destination_table_name: str` and `bindings: list[_ProposedBinding]`.
  - `_ProposedBinding` adds `binding_type: Literal["direct", "detail_fk", "lookup_fk"]` and `reference_table_name: str | None` (populated only for `lookup_fk`).
- Add table name validation on the backend to verify each AI-returned table name exists in the DDL.
- Refactor prompts to send the full DDL, feed source columns, and instruct the AI to identify all matching destination tables and classify FK bindings.
- Create **one `MappingSnapshot` per identified table** in a single `propose_mapping` call.
- Expose `lookup_table_references` (aggregated from all `lookup_fk` bindings across all tables) in the propose/get API response so 001be can consume it.
- Update `_next_snapshot_version` and `_latest_snapshot` to query by `source_definition_id`.
- Update `_snapshot_to_response` to read columns from `snapshot.destination_fields`.
- Update unit tests and mocks to cover the multi-table, multi-snapshot flow.

## Out of Scope

- Changing how codegen executes downstream migrations (we only change how the mapping snapshot itself is proposed, stored, and retrieved).
- Changing frontend UI screens other than correcting segment route linkages if any.

## Acceptance Criteria

- Proposing mapping passes the full DDL and feed source columns to the LLM.
- The LLM returns a structured JSON with a list of matched destination tables, each with field bindings and binding types.
- `propose_mapping` creates one `MappingSnapshot` record per AI-identified table in a single call.
- Each snapshot is saved with `source_definition_id`, `destination_fields`, and `destination_object_name` (the AI-returned table name).
- Each AI-returned table name is validated against DDL-parsed table names before saving.
- The propose API response includes `lookup_table_references` (list of `{lookup_name, destination_table_name}` for all `lookup_fk` bindings).
- Draft snapshots can be retrieved, patched, and approved without DDL re-parsing.
- Database migration has clean upgrade and downgrade operations.
- All backend unit/integration tests pass.

## Test Expectations

- API routes tests in `test_mapping_review_api.py` compile and pass.
- Standard python tests pass.

## Pitfalls

- Leave `source_definition_id` and `destination_fields` nullable in the migration so existing snapshot rows are not broken.
- Validate every AI-returned table name against DDL-parsed table names before saving; an unvalidated hallucinated name silently breaks codegen.
- Both `_latest_snapshot` and `_next_snapshot_version` must filter by `source_definition_id`; missing this causes cross-source version bleed when two sources share a destination table.
- Multi-snapshot creation in `propose_mapping` is a single DB transaction — if any table name fails validation, roll back all new snapshots for that call.
- `lookup_table_references` must be derived from binding data at response time, not stored as a separate model. Aggregate all `lookup_fk` bindings across all tables in the response.
- FK bindings where `reference_table_name` is also a table in the AI's own output are `detail_fk`; FK bindings pointing to tables NOT in the output are `lookup_fk`.
- Migration must use `batch_alter_table` for MySQL FK compatibility (consistent with migration 0022) and must include a `downgrade()` that drops the FK constraint before dropping the column.

## Commit

- `feat(001bd): implement AI-driven target table and mapping extraction`
