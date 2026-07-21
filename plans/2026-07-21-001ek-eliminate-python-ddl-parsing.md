# Plan: 001ek — Eliminate Python-Side DDL Parsing

## Task and Domain links

- Task: `tasks/001ek-eliminate-python-ddl-parsing.md`
- Domain: `docs/domain/project.md` or wherever `destination_schema_ddl` handling is documented —
  check before assuming none needs updating (governance I22 if this changes documented behavior)

## Current State

- **Two independent, buggy DDL parsers**, confirmed via direct inspection and live DB data:
  - `mapping/ddl.py::parse_all_ddl_tables`/`parse_ddl` (extracted in `001ee`).
  - `codegen/service.py:51-83::_get_required_destination_columns`, with its own private
    `_TABLE_RE`/`_COLUMN_RE` (`service.py:51-55`) — not imported from `mapping/ddl.py`.
  - Both skip a constraint line only if it *starts with* `CONSTRAINT/PRIMARY/UNIQUE/FOREIGN/CHECK`
    — a multi-line `FOREIGN KEY (...) \n REFERENCES ... \n ON DELETE ...` only has its first line
    skipped; continuation lines get misparsed as columns. Confirmed live: a real
    `MappingSnapshot.destination_fields` in the dev DB contains `'KEY', 'REFERENCES', 'ON'`.
    `_get_required_destination_columns` is only accidentally unaffected today because it
    additionally requires the matched line to contain `NOT NULL`, which `REFERENCES`/`ON DELETE`
    continuation lines don't happen to.
- **Full call-site map**, confirmed via grep:
  - `mapping/proposal.py:52` — `parse_all_ddl_tables`, validates AI-proposed table names against
    the DDL.
  - `mapping/review_repository.py:92` — `parse_all_ddl_tables`, inside `derive_destination_fields`.
  - `mapping/review_repository.py:28` — `parse_ddl`, inside `get_project_destination_schema`.
  - `mapping/review.py:69` — calls `get_project_destination_schema`, inside `get_mapping`'s
    single-destination-object path.
  - `routes/mapping_snapshots.py:65,110` — call `derive_destination_fields` directly, live, on
    every read, falling back to the stored `destination_fields` only if that returns empty.
  - `codegen/service.py:99-126` (`generate_codegen_artifact`) — calls
    `_get_required_destination_columns`, gates code generation on the result.
- `propose_mapping`'s AI call (`mapping.yaml` prompt) already reliably extracts
  `destination_data_type`/`nullable` per *bound* column (hardened in `001ea`) — the missing piece
  is the *full* column list per table (bound or not) and the source of table-existence truth.
- `run_schema_analysis`'s existing AI call (`DDLAnalysisResult: objects: list[ObjectDependency]`)
  only has table names + dependency edges, no columns — confirmed not reusable as-is for this.

## Objective

1. `ai_schemas.py`: add `DestinationColumn` (`name`, `destination_data_type`, `nullable`);
   `TableProposal.all_columns: list[DestinationColumn]`.
2. `mapping.yaml`: prompt requires the full column list per identified table, not just bound ones.
3. `MappingSnapshot`: new `destination_columns` JSON column (migration), populated at creation
   from the AI response; `destination_fields` populated the same way (name-only projection),
   shape unchanged for existing consumers.
4. `propose_mapping`: stop calling `parse_all_ddl_tables`; drop the DDL-based table-existence
   check (trust AI self-consistency instead — documented trade-off, not silent).
5. `codegen/service.py`: replace `_get_required_destination_columns` with a read of
   `mapping_snapshot.destination_columns`; delete the function and its private regexes.
6. `routes/mapping_snapshots.py`: simplify both call sites to read the stored field directly.
7. `review_repository.py::derive_destination_fields`: delete once its only caller
   (`snapshot_to_response`'s fallback) no longer needs it.
8. `get_project_destination_schema`/`parse_ddl`'s single-table path: new small AI call
   (`Prompt("single_table_schema")`) — the one case with no existing snapshot to read from.
9. Delete `mapping/ddl.py` once nothing calls it — verify via grep, not assumed.

## Out of Scope

- `run_schema_analysis`'s existing table/dependency AI call — untouched.
- `propose_mapping`'s binding logic itself.
- Backfilling `destination_columns` on historical `MappingSnapshot` rows — see Pitfalls for the
  decided behavior when it's absent.

## Blast Radius

- `engine/src/migrations_engine/mapping/ai_schemas.py` (edited)
- `engine/src/migrations_engine/ai/prompts/mapping.yaml` (edited)
- `engine/src/migrations_engine/ai/prompts/single_table_schema.yaml` (new)
- `engine/src/migrations_engine/db/models.py` (edited — `MappingSnapshot.destination_columns`)
- `engine/migrations/versions/00XX_mapping_snapshot_destination_columns.py` (new)
- `engine/src/migrations_engine/mapping/proposal.py` (edited)
- `engine/src/migrations_engine/mapping/review_repository.py` (edited — remove
  `derive_destination_fields`, rewrite `get_project_destination_schema`)
- `engine/src/migrations_engine/mapping/review.py` (edited — `get_mapping`'s call site)
- `engine/src/migrations_engine/mapping/ddl.py` (deleted)
- `engine/src/migrations_engine/routes/mapping_snapshots.py` (edited)
- `engine/src/migrations_engine/codegen/service.py` (edited — delete
  `_get_required_destination_columns` + its private regexes)
- `engine/src/migrations_engine/api/schemas.py` (edited — `destination_columns` on relevant
  response schemas, if exposed)
- Test files for all of the above.

## File Changes

**`mapping/ai_schemas.py`**
```python
class DestinationColumn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    destination_data_type: str | None = None
    nullable: bool | None = None
```
`TableProposal.all_columns: list[DestinationColumn]` (new field, required — the prompt must
always populate it now that nothing else derives the column list).

**`ai/prompts/mapping.yaml`**
- Add a numbered rule: "For every identified destination table, in addition to the bindings, list
  every column declared for that table in the DDL (including ones not bound) in `all_columns`,
  each with `name`, `destination_data_type`, and `nullable` populated the same way as for bound
  columns."
- Update the OUTPUT CONTRACT section's table-keys list to include `all_columns`.

**`db/models.py`**
- `MappingSnapshot`: add `destination_columns: Mapped[list[dict[str, Any]] | None] = mapped_column(JSON, nullable=True)`.

**Migration (new)**
- Hand-written, adds the nullable JSON column. No backfill (per Out of Scope) — `downgrade()`
  drops it.

**`mapping/proposal.py`**
- Remove `from .ddl import parse_all_ddl_tables` and the `ddl_tables = parse_all_ddl_tables(ddl)`
  call plus the `if table_mapping.destination_table_name not in ddl_tables: raise
  AuthApiError("destination_table_invalid", ...)` check (deliberately removed — see task
  requirement 3's documented trade-off).
- When constructing each `MappingSnapshot`: add
  `destination_columns=[c.model_dump() for c in table_mapping.all_columns]`, and change
  `destination_fields=destination_fields` (currently derived from `ddl_tables[tbl_name]`) to
  `destination_fields=[c.name for c in table_mapping.all_columns]`.

**`codegen/service.py`**
- Delete `_get_required_destination_columns` (lines 57-83) and the module-level `_TABLE_RE`/
  `_COLUMN_RE`/`import re` at the top, if nothing else in this file uses them (confirm via grep
  before deleting the regexes — `_build_system_prompt`/templates may not need `re` at all once
  this is gone).
- Replace the gate (`service.py:111-126`):
  ```python
  if mapping_snapshot.destination_columns:
      required_dest_fields = {
          c["name"] for c in mapping_snapshot.destination_columns
          if c.get("nullable") is False
      }
      mapped_dest_fields = {
          binding.get("destination_field")
          for binding in mapping_snapshot.field_bindings
          if binding.get("destination_field")
      }
      unmapped_required = required_dest_fields - mapped_dest_fields
      if unmapped_required:
          ...  # unchanged error
  # else: no destination_columns (legacy snapshot predating this task) — skip the gate rather
  # than resurrect Python DDL parsing as a bridge; log a warning so it's visible, not silent.
  ```

**`review_repository.py`**
- Delete `derive_destination_fields` and its `parse_all_ddl_tables` import.
- `snapshot_to_response`'s fallback (`if destination_fields is None: destination_fields =
  derive_destination_fields(...)`) simplifies to just `destination_fields =
  snapshot.destination_fields or []` — always populated now, no fallback derivation needed.
- `get_project_destination_schema`: replace its `parse_ddl(ddl)` call with a call to a new
  `single_table_schema_lookup(db, project_id)` (or similar) that builds `Prompt("single_table_schema")`,
  calls the adapter, and returns `(table_name, [c.name for c in result.columns])`. This is a new
  AI call site — needs its own `log_ai_call`/error-handling wiring matching the other 6 call
  sites' conventions (including `AIResponseValidationError` handling per `001ec`'s pattern from
  day one, not bolted on later).

**`ai/prompts/single_table_schema.yaml` (new)**
- `system`: "You are a SQL DDL analyst. Given a single-table DDL, identify the table name and
  every column declared, each with its exact SQL type and nullability." Output contract:
  `{"table_name": string, "columns": [{"name", "destination_data_type", "nullable"}]}`.
- `user`: `$ddl`.

**`routes/mapping_snapshots.py`**
- Lines 65, 110: `derive_destination_fields(db, ..., ...) or (mapping_snapshot.destination_fields
  or [])` → `mapping_snapshot.destination_fields or []`.

**Delete `mapping/ddl.py`** — confirm via `grep -rn "from .ddl import\|from ..mapping.ddl import"
engine/src` returns nothing before deleting; update `engine/tests/test_ddl.py` (delete or repoint
to the new AI-driven test coverage for `single_table_schema`).

## Tests

- `ai_schemas.py`: new tests for `DestinationColumn`/`TableProposal.all_columns` validation.
- `proposal.py`: assert `MappingSnapshot.destination_columns`/`destination_fields` are populated
  correctly from a mocked AI response's `all_columns`; assert the table-existence check is
  genuinely gone (a proposal with a nonsense `destination_table_name` no longer raises
  `destination_table_invalid` — document this as an intentional behavior change in the test).
- `codegen/service.py`: assert the required-fields gate correctly blocks on a `destination_columns`
  entry with `nullable: false` unmapped; assert it does NOT block (logs a warning instead) when
  `destination_columns` is `None` (legacy snapshot).
- New `single_table_schema` prompt/call-site tests, mirroring the pattern from `001eb`/`001ec`.
- Rerun `test_mapping_review_api.py`, `test_codegen_service_api.py`,
  `test_mapping_snapshots_api.py` (or equivalent) in full — expect real assertion changes here,
  not just target-module updates, since behavior (not just location) is changing.

## Verification

- `mypy --strict` / `ruff` clean across all touched/new files.
- `alembic upgrade head` runs cleanly.
- Manually run "AI Analyze" on a feed with a multi-line `FOREIGN KEY` constraint in its
  destination DDL (reproduce the exact `KEY`/`REFERENCES`/`ON` bug scenario) and confirm the
  resulting `MappingSnapshot.destination_fields`/`destination_columns` contain only real columns.
- Manually generate SQL for a table with an unmapped `NOT NULL` column and confirm the gate still
  blocks correctly, now reading from `destination_columns` instead of re-parsing DDL.
- `grep -rn "mapping.ddl\|from .ddl import" engine/src` returns nothing.

## Pitfalls

- **The table-existence validation trade-off (requirement 3) is real and should be called out in
  the PR, not discovered later** — this task intentionally removes an independent
  Python-verified check against AI hallucination of table names, replacing it with trust in the
  AI's internal self-consistency. If this turns out to matter in practice (AI proposes a binding
  for a table it didn't actually see in the DDL), that's a new failure mode this task
  deliberately accepts as the cost of "no Python DDL parsing."
- **Legacy `MappingSnapshot` rows with `destination_columns=None`**: the codegen gate must skip
  cleanly (with a warning), not crash on a `None` — don't assume every snapshot going through
  `generate_codegen_artifact` was created after this migration.
- **`get_project_destination_schema`'s new AI call fires before any snapshot exists** — it can't
  reuse `AIResponseValidationError`/`db.commit()`-before-raise patterns by copying an existing
  call site verbatim; build it correctly from the start (per `001ec`'s lessons), not as a
  follow-up fix.
- Don't delete `mapping/ddl.py` until requirements 4, 6, and 8 have all actually landed — grep for
  zero remaining importers first, don't assume from the plan alone that it's safe.

## Commit

Larger task — consider whether this warrants splitting into sub-tasks (schema/prompt extension →
consumer migration → parser deletion) the way `001ee`-`001eg` were split, given the number of
call sites and the new AI call site (`single_table_schema`) this introduces. Sequence after
`001ei` (already touches `review.py`) to avoid conflicts.
