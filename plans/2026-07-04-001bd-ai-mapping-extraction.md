# AI Mapping Extraction Implementation Plan

Task: [tasks/001bd-ai-mapping-extraction.md](/Users/vjkotra/projects/katana/tasks/001bd-ai-mapping-extraction.md)
Domain: [docs/domain/governance.md](/Users/vjkotra/projects/katana/docs/domain/governance.md)

**Goal:** Replace the regex DDL parser (`_parse_ddl`) with native AI-based target table extraction and field mapping.

---

## Current State

- The mapping review backend currently uses a brittle regex DDL parser (`_parse_ddl`) to extract the first table name and its columns from `destination_schema_ddl`.
- It mixes columns of all subsequent tables into a single flat list under that first table's name.
- It forces the AI model to map CSV source fields to this single merged table schema.
- This prevents a single project from supporting multiple source definitions mapping to different destination tables.

---

## Objective

Replace the regex-based DDL parser with native AI-based target table extraction and field mapping. The AI model will receive the full multi-table DDL and source columns, select the correct target table, and return both the target table name and semantic field mappings in a structured JSON.

---

## Out of Scope

- Changing how codegen executes downstream migrations (we only change how the mapping snapshot itself is proposed, stored, and retrieved).
- Changing frontend UI screens other than correcting segment route linkages if any.

---

## Blast Radius

- `engine/src/migrations_engine/db/models.py` (Database schema changes)
- `engine/src/migrations_engine/mapping/review.py` (Mapping proposal, retrieval, and patch logic)
- `engine/migrations/versions/` (New Alembic migration file)
- `engine/tests/` (API unit/integration tests)

---

## File Changes

### 1. Database Schema
- [ ] Add `source_definition_id` to `MappingSnapshot` model in `engine/src/migrations_engine/db/models.py`.
- [ ] Generate Alembic migration file:
  ```python
  # engine/migrations/versions/0023_mapping_snapshot_source_id.py
  def upgrade():
      op.add_column("mapping_snapshots", sa.Column("source_definition_id", sa.String(length=36), nullable=True))
      op.create_foreign_key(
          "fk_mapping_snapshots_source",
          "mapping_snapshots",
          "source_definitions",
          ["source_definition_id"],
          ["source_definition_id"]
      )
  ```

### 2. AI Schema Definition
- [ ] Update `_FieldMappingProposal` Pydantic model in `engine/src/migrations_engine/mapping/review.py`:
  ```python
  class _FieldMappingProposal(BaseModel):
      destination_table_name: str | None = None
      bindings: list[_ProposedBinding] = []
      error_code: str | None = None
      error_message: str | None = None
  ```

### 3. Prompt Refactoring
- [ ] Modify `propose_mapping` in `engine/src/migrations_engine/mapping/review.py`:
  - Pass the complete DDL schema to the LLM.
  - Instruct the model to analyze the full multi-table DDL, identify the primary target table name, map fields, and output errors/exceptions gracefully.
  - Validate response and save `source_definition_id` alongside `destination_object_name`.

### 4. Query & Resolution Logic
- [ ] Update `_latest_snapshot` in `engine/src/migrations_engine/mapping/review.py` to filter by `source_definition_id` instead of parsing DDL.
- [ ] Update `patch_mapping` and `approve_mapping` to resolve mapping snapshots by `source_definition_id`.

---

## Tests

- [ ] Update unit tests in `engine/tests/test_mapping_review_api.py` to mock `_FieldMappingProposal` with the new fields:
  ```python
  mock_proposal = {
      "destination_table_name": "policy_master",
      "bindings": [
          {"source_field": "policy_id", "destination_field": "policy_id"},
          {"source_field": "member_id", "destination_field": "member_id"}
      ],
      "error_code": None,
      "error_message": None
  }
  ```
- [ ] Run Pytest:
  ```bash
  pytest engine/tests/
  ```

---

## Verification

- Run `alembic upgrade head` to verify migration execution.
- Trigger the mapping endpoint `POST /projects/{id}/sources/{sourceId}/mapping/propose` via postman/local web app and verify correct table mapping.

---

## Pitfalls

- Ensure database migrations handle existing mapping snapshot records (by leaving `source_definition_id` nullable).
- Ensure subsequent snapshot retrievals find the correct draft/approved snapshot without parsing DDL.

---

## Commit

- `feat(001bd): implement AI-driven target table and mapping extraction`
