# AI Mapping Extraction Implementation Plan

Task: [tasks/001bd-ai-mapping-extraction.md](/Users/vjkotra/projects/katana/tasks/001bd-ai-mapping-extraction.md)
Domain: [docs/domain/governance.md](/Users/vjkotra/projects/katana/docs/domain/governance.md)

**Goal:** Replace the regex DDL parser (`_parse_ddl`) with native AI-based target table extraction and field mapping.

---

## Current State

- The mapping review backend currently uses a brittle regex DDL parser (`_parse_ddl`) to extract the first table name and its columns from `destination_schema_ddl`.
- It mixes columns of all subsequent tables into a single flat list under that first table's name.
- It forces the AI model to map CSV source fields to this single merged table schema — one table, one snapshot per AI call.
- FK bindings are not classified; there is no `binding_type` or `reference_table_name` in any snapshot record.
- The UI has no `lookup_table_references` to guide the lookup page.

---

## Objective

Replace the regex-based DDL parser with AI-based multi-table extraction and field mapping. The AI receives the full DDL and feed source columns, identifies all matching destination tables, maps fields per table, and classifies each binding as `direct`, `detail_fk`, or `lookup_fk`. The backend creates one `MappingSnapshot` per identified table and returns `lookup_table_references` for the UI.

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
- [ ] Add `source_definition_id` and `destination_fields` to `MappingSnapshot` model in `engine/src/migrations_engine/db/models.py`:
  ```python
  source_definition_id: Mapped[str | None] = mapped_column(
      String(36), ForeignKey("source_definitions.source_definition_id"), nullable=True
  )
  destination_fields: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
  ```
- [ ] Generate Alembic migration file using `batch_alter_table` for MySQL FK compatibility:
  ```python
  # engine/migrations/versions/0023_mapping_snapshot_source_id.py
  def upgrade():
      with op.batch_alter_table("mapping_snapshots") as batch_op:
          batch_op.add_column(sa.Column("source_definition_id", sa.String(36), nullable=True))
          batch_op.add_column(sa.Column("destination_fields", sa.JSON(), nullable=True))
          batch_op.create_foreign_key(
              "fk_mapping_snapshots_source_def",
              "source_definitions",
              ["source_definition_id"],
              ["source_definition_id"],
          )

  def downgrade():
      with op.batch_alter_table("mapping_snapshots") as batch_op:
          batch_op.drop_constraint("fk_mapping_snapshots_source_def", type_="foreignkey")
          batch_op.drop_column("destination_fields")
          batch_op.drop_column("source_definition_id")
  ```

### 2. AI Schema Definition
- [ ] Replace `_FieldMappingProposal` and `_ProposedBinding` in `engine/src/migrations_engine/mapping/review.py`
  with a multi-table, binding-typed structure:
  ```python
  from typing import Literal

  class _ProposedBinding(BaseModel):
      source_field: str
      destination_field: str
      binding_type: Literal["direct", "detail_fk", "lookup_fk"] = "direct"
      reference_table_name: str | None = None  # populated only for lookup_fk

  class _TableMapping(BaseModel):
      destination_table_name: str
      bindings: list[_ProposedBinding] = []

  class _FieldMappingProposal(BaseModel):
      tables: list[_TableMapping] = []
      error_code: str | None = None
      error_message: str | None = None
  ```
  A binding is `detail_fk` when its `reference_table_name` is also present in
  `proposal.tables[*].destination_table_name` (the AI mapped it too). It is `lookup_fk` when
  `reference_table_name` points to a table that is NOT in the AI's output (needs lookup snapshot).

### 3. Prompt Refactoring and Multi-Snapshot Creation
- [ ] Modify `propose_mapping` in `engine/src/migrations_engine/mapping/review.py`:
  - Pass the complete DDL and feed source column list to the LLM.
  - Instruct the model to: (a) identify all destination tables that receive fields from this feed, (b) map source fields to each table, (c) classify each binding as `direct`, `detail_fk`, or `lookup_fk`, and (d) set `reference_table_name` for any FK binding.
  - After receiving the AI response, use `_TABLE_RE` to extract all table names from the DDL. Validate each `_TableMapping.destination_table_name` in the response against this set. Raise `AuthApiError("destination_table_invalid", ..., 422)` on any mismatch.
  - Create one `MappingSnapshot` per `_TableMapping` in a single DB transaction. Each snapshot gets: `source_definition_id`, `destination_object_name` (the table name), `destination_fields` (columns for that table extracted from DDL), and `field_bindings` (the bindings for that table, serialised with `binding_type` and `reference_table_name`).
  - Derive `lookup_table_references` by collecting all `lookup_fk` bindings across all tables: `[{"lookup_name": binding.source_field, "destination_table_name": binding.reference_table_name}]`.
  - Return all created snapshots and `lookup_table_references` in the API response.

### 4. Query & Resolution Logic
- [ ] Update `_latest_snapshot` to accept and filter by `source_definition_id`:
  ```python
  def _latest_snapshot(db, *, project_id: str, source_definition_id: str) -> MappingSnapshot | None:
      return db.scalar(
          select(MappingSnapshot)
          .where(
              MappingSnapshot.project_id == project_id,
              MappingSnapshot.source_definition_id == source_definition_id,
          )
          .order_by(MappingSnapshot.created_at.desc(), MappingSnapshot.mapping_snapshot_id.desc())
      )
  ```
- [ ] Update `_next_snapshot_version` to filter by `source_definition_id` for the same reason — sources
  that share a destination table must not share version counters.
- [ ] Update `patch_mapping`, `approve_mapping`, and the get function to pass `source_definition_id` to
  `_latest_snapshot` and `_next_snapshot_version` instead of deriving `destination_object_name` from DDL.
- [ ] Update `_snapshot_to_response` callers to read `destination_fields` from the stored snapshot
  (`snapshot.destination_fields`) instead of calling `_get_project_destination_schema`. Remove the
  `_get_project_destination_schema` call from all non-propose paths once `destination_fields` is reliably
  stored.

---

## Tests

- [ ] Update unit tests in `engine/tests/test_mapping_review_api.py` to mock `_FieldMappingProposal` with the new multi-table structure:
  ```python
  mock_proposal = {
      "tables": [
          {
              "destination_table_name": "policy_master",
              "bindings": [
                  {"source_field": "policy_id", "destination_field": "policy_id", "binding_type": "direct"},
                  {"source_field": "status_code", "destination_field": "status_id", "binding_type": "lookup_fk", "reference_table_name": "status_ref"},
              ],
          },
          {
              "destination_table_name": "member_detail",
              "bindings": [
                  {"source_field": "member_id", "destination_field": "member_id", "binding_type": "direct"},
                  {"source_field": "policy_id", "destination_field": "policy_fk", "binding_type": "detail_fk", "reference_table_name": "policy_master"},
              ],
          },
      ],
      "error_code": None,
      "error_message": None,
  }
  ```
- [ ] Assert that two `MappingSnapshot` records are created (one per table) and `lookup_table_references` contains `[{"lookup_name": "status_code", "destination_table_name": "status_ref"}]`.
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

- Leave `source_definition_id` and `destination_fields` nullable in the migration so existing snapshot rows are not broken.
- Validate every AI-returned table name against DDL-parsed table names. An unvalidated hallucinated name silently breaks downstream codegen.
- Multi-snapshot creation must be a single DB transaction — if any table fails validation, no snapshots for that call are committed.
- Both `_latest_snapshot` and `_next_snapshot_version` must filter by `source_definition_id`. Missing this causes cross-source version bleed when two sources share a destination table.
- `lookup_table_references` is derived at response time from binding data — do not store it as a separate DB column.
- `detail_fk` vs `lookup_fk` classification rule: if `reference_table_name` is among the tables the AI also mapped in this call → `detail_fk`; if not → `lookup_fk`.
- Use `batch_alter_table` for the FK in the migration (MySQL requirement, consistent with migration 0022). Always include a working `downgrade()`.
- After storing `destination_fields` in the snapshot, remove `_get_project_destination_schema` calls from the get/patch/approve paths.

---

## Commit

- `feat(001bd): implement AI-driven target table and mapping extraction`
