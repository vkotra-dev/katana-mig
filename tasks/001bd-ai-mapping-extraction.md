# Task 001bd — AI Mapping Extraction

**Plan:** `plans/2026-07-04-001bd-ai-mapping-extraction.md`

**Depends on:** 001w (Mapping Stage)

## Domain

- [governance.md](/Users/vjkotra/projects/katana/docs/domain/governance.md)
- [source-model.md](/Users/vjkotra/projects/katana/docs/domain/source-model.md)

## Current State

- The mapping review backend currently uses a brittle regex DDL parser (`_parse_ddl`) to extract the first table name and its columns from `destination_schema_ddl`.
- It mixes columns of all subsequent tables into a single flat list under that first table's name.
- It forces the AI model to map CSV source fields to this single merged table schema.
- This prevents a single project from supporting multiple source definitions mapping to different destination tables.

## Objective

Replace the regex-based DDL parser with native AI-based target table extraction and field mapping. The AI model will receive the full multi-table DDL and source columns, select the correct target table, and return both the target table name and semantic field mappings in a structured JSON.

## Scope

- Refactor `MappingSnapshot` database model to include `source_definition_id`.
- Create a database migration to add the `source_definition_id` column to the `mapping_snapshots` table.
- Update Pydantic response models to enforce AI returning `destination_table_name` along with structured success/error outputs.
- Refactor prompts to send the full DDL and guide the LLM to choose the target table.
- Update mapping snapshot proposal, retrieval, patching, and approval endpoints to query by `source_definition_id` instead of parsing the DDL.
- Update unit tests and mocks to verify the new multi-table mapping flow.

## Out of Scope

- Changing how codegen executes downstream migrations (we only change how the mapping snapshot itself is proposed, stored, and retrieved).
- Changing frontend UI screens other than correcting segment route linkages if any.

## Acceptance Criteria

- Proposing mapping correctly passes the entire DDL schema to the LLM.
- The LLM returns a structured JSON containing the chosen destination table name and mappings.
- The snapshot is saved to the database with the AI-extracted table name and bindings linked to the correct source definition.
- Draft snapshots can be successfully retrieved, patched, and approved.
- All backend unit/integration tests pass.

## Test Expectations

- API routes tests in `test_mapping_review_api.py` compile and pass.
- Standard python tests pass.

## Pitfalls

- Ensure `destination_object_name` in the database matches what the AI returned, and is correctly resolved on subsequent retrieval/approval calls without DDL parsing.

## Commit

- `feat(001bd): implement AI-driven target table and mapping extraction`
