# Task: 001cq — Fix GeneratedSQL Schema Split

## Status
Ready

## Problem

`GeneratedSQL.staging_table_ddl` is a single string catch-all. The system prompt tells the AI to put lookup DDL, seed data, and stored procedures all inside this one field — but the field name says "staging_table_ddl", so the AI follows the name literally and only returns a `CREATE TABLE`. Procs and lookup data are never generated.

## Fix

Split `GeneratedSQL` into four typed fields. The field names guide the AI without needing an explicit instruction.

Update `_assemble_sql_bundle()` to assemble in the correct order.

Update the system prompt template to remove the contradictory instruction 3 and replace it with field-level guidance.

## Files

- `engine/src/migrations_engine/codegen/service.py`
- `engine/src/migrations_engine/codegen/templates/system_prompt.txt.j2`

## Plan

[2026-07-10-generated-sql-schema-split.md](../docs/superpowers/plans/2026-07-10-generated-sql-schema-split.md)
