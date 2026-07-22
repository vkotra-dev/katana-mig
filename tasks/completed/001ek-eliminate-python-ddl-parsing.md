---
type: Task Plan
title: Eliminate Python-Side DDL Parsing — Let the AI Extract Table/Column Structure
status: ready
---

# Task: 001ek-eliminate-python-ddl-parsing

## Context
There are currently **two independent, regex-based DDL parsers** in the codebase
(`mapping/ddl.py::parse_all_ddl_tables`/`parse_ddl`, and `codegen/service.py`'s private
`_get_required_destination_columns` with its own copy of `_TABLE_RE`/`_COLUMN_RE`), and both have
the same confirmed bug: a multi-line `FOREIGN KEY (...) \n REFERENCES ... \n ON DELETE ...`
constraint only has its first line correctly skipped — continuation lines fall through and get
misparsed as fake columns (`KEY`, `REFERENCES`, `ON` were found polluting a real
`MappingSnapshot.destination_fields` in the live dev DB). `propose_mapping`'s AI call already
reads the full DDL and reliably extracts `destination_data_type`/`nullable` for every column it
*binds* (hardened in `001ea`) — the fragile Python parsing only remains for things the AI isn't
currently asked to also report: the *full* column list per table (mapped or not) and per-table
existence validation.

Direction: stop parsing DDL text in Python at all. Extend the same AI call that already reads the
DDL to also report the full column structure, store that on `MappingSnapshot`, and have every
other consumer read the stored, AI-derived data instead of re-parsing DDL.

## Requirements

1. **Extend the mapping AI schema and prompt**: `TableProposal` (`ai_schemas.py`) gains
   `all_columns: list[DestinationColumn]`, where `DestinationColumn` has `name: str`,
   `destination_data_type: str | None`, `nullable: bool | None` — the *complete* column list for
   that destination table as declared in the DDL, not just the ones this proposal binds. Update
   `mapping.yaml`'s system prompt (item list) to require this for every identified table.
2. **`MappingSnapshot` gains `destination_columns: list[dict] | None]` (new JSON column,
   migration required — governance I18)**, populated directly from `table_mapping.all_columns` at
   creation in `propose_mapping` — no DDL re-parsing. `destination_fields` (the existing
   `list[str]`, still consumed by `patch_mapping`'s membership check and the frontend
   autocomplete — do not change its shape, per the same reasoning as `001dz`) gets populated as
   `[c.name for c in all_columns]` from the same AI response, also without re-parsing.
3. **`propose_mapping` stops calling `parse_all_ddl_tables` for table-existence validation.**
   This is a deliberate trade-off, not an oversight: today, `if table_mapping.destination_table_name
   not in ddl_tables: raise` is an independent, Python-verified cross-check against the AI
   hallucinating a table name. Removing it means trusting the AI's own self-consistency instead
   (the table names it reports existing vs. the table names it proposes bindings for, both from
   the same response) rather than an independent ground truth. State this trade-off explicitly in
   the PR description — it's the direct cost of "AI does the parsing," not a side effect to
   discover later.
4. **`codegen/service.py::generate_codegen_artifact`'s unmapped-required-fields gate**: replace
   `_get_required_destination_columns(ddl, target_table)` (delete this function and its private
   `_TABLE_RE`/`_COLUMN_RE`/`_CONSTRAINT_PREFIXES` entirely) with a read of
   `mapping_snapshot.destination_columns` — `required_dest_fields = {c["name"] for c in
   mapping_snapshot.destination_columns if c.get("nullable") is False}`. Zero DDL text touched by
   codegen.
5. **`routes/mapping_snapshots.py`'s two call sites** (`derive_destination_fields(...) or
   (mapping_snapshot.destination_fields or [])`) simplify to just
   `mapping_snapshot.destination_fields or []` — no more live re-derivation on every read, since
   it's reliably populated at creation time by requirement 2.
6. **`review_repository.py::derive_destination_fields`** becomes unnecessary once requirement 2
   lands (its only remaining caller, `snapshot_to_response`'s fallback, no longer needs to
   fall back once the field is always populated at creation) — remove it and its
   `parse_all_ddl_tables` call.
7. **`review_repository.py::get_project_destination_schema`/`mapping/ddl.py::parse_ddl`**: used
   by `get_mapping` for the single-destination-object project-config path, *before* any
   `propose_mapping` call may have happened — this is the one case that can't simply read
   already-stored AI-derived data, because there may not be a snapshot yet. This needs its own
   small, dedicated AI call (e.g. `Prompt("single_table_schema")`: given a single-table DDL,
   return the table name + full column list) rather than being left as Python regex parsing.
   Scope this explicitly — don't silently leave it behind while claiming "zero DDL parsing."
8. **Delete `mapping/ddl.py` entirely** once nothing calls `parse_all_ddl_tables`/`parse_ddl`
   (requirements 3, 6, 7 all need to land first) — confirm via grep before deleting, not assumed.

## Out of Scope
- `codegen/schema_analysis.py::run_schema_analysis`'s existing AI call (table names + dependency
  graph only) — already AI-driven, not touched; it doesn't do column-level parsing so it's
  outside this task's scope, though it's the same *kind* of DDL-to-AI extraction already proven
  to work in this codebase.
- Any change to `propose_mapping`'s actual binding logic — only the table-existence-validation
  and full-column-list mechanics change.
- Historical `MappingSnapshot` rows created before this migration won't have
  `destination_columns` populated — no backfill; they'll simply have `destination_columns=None`
  until re-proposed. Codegen against an old, un-migrated snapshot needs a decision (see plan).

## Dependencies
None, but touches the same files `001ei` (mypy fix) and `001ee`-`001eg` (module split) already
modified this session — sequence after those to avoid conflicts.
