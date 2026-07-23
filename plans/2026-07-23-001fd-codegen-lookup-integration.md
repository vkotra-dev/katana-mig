---
task: 001fd-codegen-lookup-integration
domain: docs/domain/governance.md, docs/domain/harness.md
created: 2026-07-23
---

# Plan — 001fd: Codegen Lookup Reference Integration

## Task Link
[tasks/001fd-codegen-lookup-integration.md](../tasks/001fd-codegen-lookup-integration.md)

---

## Current State

### `codegen/service.py` (`_build_user_prompt`)
- Passes `lookup_snapshot_version` to Jinja context.
- Does not query approved `LookupValueMap` entries to pass table names or sample value pairs.

### `templates/user_prompt.txt.j2`
- Field bindings render as:
  ```text
  - raw_status -> status_id [INTEGER] (lookup: status_map)
  ```
- Missing a dedicated lookup section detailing SQL reference table names (`status_map_ref`), schema (`source_val`, `dest_val`), or sample mappings.

### `templates/system_prompt.txt.j2`
- Lookup resolution rule currently states:
  ```text
  SELECT @_<lookup_name>_id = [id] FROM [schema].[lookup_table] WHERE [source_value] = @_source_field
  ```
- Uses placeholder column names (`[id]`, `[source_value]`) instead of matching Python's `lookup_upsert.py` schema (`source_val`, `dest_val`).

---

## Objective

1. **`codegen/service.py`**:
   Fetch latest approved `LookupValueMap` for each unique `lookup_name` in field bindings. Pass a structured `lookup_tables` list to Jinja rendering context:
   ```python
   lookup_tables = []
   for lookup_name in lookup_names:
       snapshot = select_latest_approved_lookup_snapshot(...)
       ref_table_name = f"{lookup_name}_ref" if not lookup_name.endswith("_ref") else lookup_name
       # Cap sample preview to 5 items to keep prompt compact
       sample_items = dict(list((snapshot.value_map or {}).items())[:5])
       lookup_tables.append({
           "lookup_name": lookup_name,
           "ref_table_name": ref_table_name,
           "sample_mappings": sample_items,
           "total_count": len(snapshot.value_map or {}),
       })
   ```

2. **`templates/user_prompt.txt.j2`**:
   Add structured lookup table reference section:
   ```jinja2
   {% if lookup_tables %}
   LOOKUP REFERENCE TABLES (Pre-created in {{ project_config.staging_schema or 'staging' }}):
   {% for ref in lookup_tables %}
   - Lookup Name: {{ ref.lookup_name }}
     SQL Table Name: {{ project_config.staging_schema or 'staging' }}.{{ ref.ref_table_name }}
     Columns: source_val (VARCHAR), dest_val (VARCHAR)
     Sample Mappings (source_val -> dest_val, {{ ref.total_count }} total entries in table):
     {% for src, dest in ref.sample_mappings.items() %}
       '{{ src }}' -> '{{ dest }}'
     {% endfor %}
   {% endfor %}
   {% endif %}
   ```

3. **`templates/system_prompt.txt.j2`**:
   Update instructions:
   ```text
   LOOKUP RESOLUTION RULES (apply when a field uses a lookup table):
      - Reference tables exist in staging schema as <lookup_name>_ref with columns (source_val VARCHAR, dest_val VARCHAR).
      - Perform LEFT JOIN on staging.source_column = ref.source_val.
      - Extract ref.dest_val and explicitly cast to destination column type:
        CAST(ref.dest_val AS <destination_data_type>)
   ```

---

## Out of Scope

- No DB model or Alembic migration changes.
- No `lookup_upsert.py` changes.
- No UI changes.

---

## Blast Radius

| File | Nature |
|---|---|
| `engine/src/migrations_engine/codegen/service.py` | Enrich `_build_user_prompt` with `lookup_tables` |
| `engine/src/migrations_engine/codegen/templates/user_prompt.txt.j2` | Add `LOOKUP REFERENCE TABLES` block |
| `engine/src/migrations_engine/codegen/templates/system_prompt.txt.j2` | Update `LOOKUP RESOLUTION RULES` |
| `engine/tests/test_codegen_api.py` / `test_prompt.py` | Test assertions update |

---

## Verification Plan

1. Run backend unit tests: `cd engine && pytest tests/test_codegen_api.py -v`.
2. Run full backend test suite: `cd engine && pytest -v`.
3. Verify generated user prompt contains `LOOKUP REFERENCE TABLES` with SQL table names and sample mappings.

---

## Commit Message Format

```
docs(tasks): create task 001fd codegen lookup reference integration
```
