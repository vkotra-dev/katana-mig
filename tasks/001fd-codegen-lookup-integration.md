---
id: 001fd
title: Codegen lookup reference integration — prompt embedding & procedure resolution rules
status: active
created: 2026-07-23
priority: high
domain: codegen / prompts / templates / service.py
---

# Task 001fd — Codegen Lookup Reference Integration

## Context

Task `001fc` updated the lookup mapping structure so that `LookupValueMap.source_value_map` stores clean business keys (e.g. `{"APPROVED": "3", "UNDER_REVIEW": "2"}`).

While Python's `generate_lookup_upsert_sql()` in `codegen/lookup_upsert.py` generates pure DDL/DML reference tables (`status_map_ref`), the Codegen prompt templates (`user_prompt.txt.j2` and `system_prompt.txt.j2`) currently have gaps when instructing the LLM to generate the stored procedure:

1. **`user_prompt.txt.j2`**: Only outputs raw `(lookup: status_map)`. It does not explicitly state the SQL table name (`status_map_ref`), table column schema (`source_val`, `dest_val`), or provide sample mapping pairs.
2. **`system_prompt.txt.j2`**: Uses placeholder names (`SELECT [id] FROM [lookup_table] WHERE [source_value] = ...`) instead of instructing the LLM to join `staging.<lookup_name>_ref` on `source_val` and cast `dest_val` to the target destination column data type (e.g. `CAST(ref.dest_val AS INT)`).

## Objective

Update the Codegen service and Jinja templates to explicitly embed approved lookup reference table metadata into the AI user prompt and enforce strict lookup resolution rules in the system prompt.

1. **`service.py` (`_build_user_prompt`)**:
   Fetch approved `LookupValueMap` entries for all lookups referenced in field bindings. Build a structured `lookup_tables` list containing:
   - `lookup_name` (e.g. `status_map`)
   - `ref_table_name` (e.g. `status_map_ref`)
   - `columns` (`source_val VARCHAR`, `dest_val VARCHAR`)
   - `sample_mappings` (capped preview of up to 5 `source_val -> dest_val` pairs for prompt context)

2. **`user_prompt.txt.j2`**:
   Render a dedicated `LOOKUP REFERENCE TABLES` block showing the staging table name, column schema, and sample mappings.

3. **`system_prompt.txt.j2`**:
   Update `LOOKUP RESOLUTION RULES` to explicitly instruct the LLM:
   - Reference tables exist in staging schema as `<lookup_name>_ref`.
   - Join on `staging.source_column = ref.source_val`.
   - Select `ref.dest_val` and cast to destination column type (e.g. `CAST(ref.dest_val AS INT)`).
   - Maintain transaction atomicity (`TRY...CATCH` / `XACT_ABORT` / `BEGIN...EXCEPTION`) and logging to `mig_upsert_log`.

## Out of Scope

- No DB model or migration changes (table models are unchanged).
- No changes to `lookup_upsert.py` (Python DDL generator is already working).
- No changes to execution engine or verifier.

## Blast Radius

- `engine/src/migrations_engine/codegen/service.py`
- `engine/src/migrations_engine/codegen/templates/user_prompt.txt.j2`
- `engine/src/migrations_engine/codegen/templates/system_prompt.txt.j2`
- `engine/tests/test_codegen_api.py` / `test_prompt.py`
