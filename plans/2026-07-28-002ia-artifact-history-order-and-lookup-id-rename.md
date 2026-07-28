Task: tasks/002ia-artifact-history-order-and-lookup-id-rename.md
Domain: docs/domain/ui.md

## Current State

- `list_codegen_artifacts()` (`codegen/service.py:264-276`) orders by
  `CodeGenerationArtifact.destination_object_name.asc(), CodeGenerationArtifact.created_at.desc()`.
  This backs the "Artifact history" table on the codegen page — grouped by table, not truly
  chronological.
- `_build_lookup_tables()` (`codegen/service.py:494-537`) reads `LookupSnapshot.value_map`
  (`{source_value: business_id}` — already correct) and renders it as
  `{"source_val": src, "dest_val": dst}` with hardcoded columns
  `["source_val VARCHAR(255) PRIMARY KEY", "dest_val VARCHAR(255) NOT NULL"]`.
- `user_prompt.txt.j2:27` renders `{{ m.source_val }} -> {{ m.dest_val }}`.
- `system_prompt.txt.j2:15,18` describes the reference table columns as
  `source_val (VARCHAR(255) PRIMARY KEY), dest_val (VARCHAR(255) NOT NULL)` and instructs
  `SELECT @_<lookup_name>_id = CAST(ref.dest_val AS <destination_type>)`.
- `lookup_upsert.py` (`generate_lookup_upsert_sql`, called from `management/fibers.py:491`) emits
  CREATE TABLE / INSERT / upsert SQL for postgresql, mysql, mssql, oracle — all hardcode `dest_val`
  as the column name (lines ~33, 41, 54, 56, 69, 71, 85, 87-89, 103, 105-107).

## Objective

Fix 1: chronological artifact history. Fix 2: rename `dest_val` → `id` everywhere it represents the
resolved lookup business key, so the reference table schema, the AI-generated seed script, and the
deterministic fiber-triggered upsert script all consistently expose an `id` column.

## Out of Scope

- No `LookupValueMap`/`LookupSnapshot` shape change — value is already the id.
- No change to `source_val`'s role as PK/join key.
- No change to `build_delivery_bundle_text`'s `destination_object_name.asc()` grouping
  (`service.py` ~line 304) — intentional there.
- No change to task 001fb's fiber-proposal layer (`dest_row`, `_extract_destination_label`).

## Blast Radius

| File | Action | What changes |
|------|--------|---------------|
| `engine/src/migrations_engine/codegen/service.py` | modify | `ORDER BY` fix in `list_codegen_artifacts()`; `dest_val` → `id` in `_build_lookup_tables()` |
| `engine/src/migrations_engine/codegen/templates/user_prompt.txt.j2` | modify | `m.dest_val` → `m.id` |
| `engine/src/migrations_engine/codegen/templates/system_prompt.txt.j2` | modify | `dest_val` → `id` in column description + FK-resolution rule |
| `engine/src/migrations_engine/codegen/lookup_upsert.py` | modify | `dest_val` → `id` in all 4 engines' generated SQL |
| `engine/tests/test_codegen_service_api.py` | modify | Update assertion; add ordering test |
| `engine/tests/test_codegen_system_prompt.py` | modify | Update assertions |
| `engine/tests/test_bundle_sequencing.py` | modify | Update ~10 SQL-text assertions |
| `docs/domain/ui.md` | modify | Clarify Artifact history ordering claim; bump `timestamp` |

## File Changes

### `engine/src/migrations_engine/codegen/service.py`

```diff
     rows = db.scalars(
-        stmt.order_by(CodeGenerationArtifact.destination_object_name.asc(), CodeGenerationArtifact.created_at.desc())
+        stmt.order_by(CodeGenerationArtifact.created_at.desc())
     ).all()
```

```diff
         value_map = snapshot.value_map or {}
         ref_table = f"{lookup_name}_ref" if not lookup_name.endswith("_ref") else lookup_name
         sample_mappings = [
-            {"source_val": src, "dest_val": dst}
+            {"source_val": src, "id": dst}
             for src, dst in value_map.items()
         ]

         results.append({
             "lookup_name": lookup_name,
             "ref_table_name": ref_table,
-            "columns": ["source_val VARCHAR(255) PRIMARY KEY", "dest_val VARCHAR(255) NOT NULL"],
+            "columns": ["source_val VARCHAR(255) PRIMARY KEY", "id VARCHAR(255) NOT NULL"],
             "sample_mappings": sample_mappings,
             "snapshot_version": snapshot.lookup_snapshot_version,
         })
```

### `engine/src/migrations_engine/codegen/templates/user_prompt.txt.j2`

```diff
   {% for m in lt.sample_mappings %}
-  - {{ m.source_val }} -> {{ m.dest_val }}
+  - {{ m.source_val }} -> {{ m.id }}
   {% endfor %}
```

### `engine/src/migrations_engine/codegen/templates/system_prompt.txt.j2`

```diff
-   - Reference tables are created in the staging schema as <lookup_name>_ref with columns: source_val (VARCHAR(255) PRIMARY KEY), dest_val (VARCHAR(255) NOT NULL)
+   - Reference tables are created in the staging schema as <lookup_name>_ref with columns: source_val (VARCHAR(255) PRIMARY KEY), id (VARCHAR(255) NOT NULL)
    - Declare a local variable of the target type before the loop: DECLARE @_<lookup_name>_id <destination_type> = NULL
    - Inside the loop, resolve before INSERT/UPDATE by joining the staging row to the reference table:
-     SELECT @_<lookup_name>_id = CAST(ref.dest_val AS <destination_type>)
+     SELECT @_<lookup_name>_id = CAST(ref.id AS <destination_type>)
        FROM <staging_schema>.<lookup_name>_ref ref
        JOIN {{ project_config.staging_schema or 'stg' }}.{{ staging_table_name }} stg ON stg.<source_column> = ref.source_val
```

### `engine/src/migrations_engine/codegen/lookup_upsert.py`

Rename every occurrence of the `dest_val` column name to `id` in the generated SQL strings for all
four engine branches (CREATE TABLE column list, INSERT column list, `ON CONFLICT ... DO UPDATE SET`,
`ON DUPLICATE KEY UPDATE`, `MERGE ... WHEN MATCHED/NOT MATCHED`). Do not rename the Python parameter
names or `VALUE_MAP` variable — only the SQL text the function emits. Read the whole file first
(`engine/src/migrations_engine/codegen/lookup_upsert.py`) since the exact line numbers above are
approximate and every engine branch needs the same treatment.

### `docs/domain/ui.md`

```diff
 - **Artifact history** — all artifacts (active and superseded) with timestamps
+  , ordered chronologically (`created_at desc`) across all destination tables — not
+  grouped by table
```

Bump the page's `timestamp` frontmatter field to the actual date this edit lands (never
copy-paste the task's `created:` date — I22/OKF requirement).

## Tests

- New: `test_list_codegen_artifacts_is_chronological` — create `CodeGenerationArtifact` rows for 2+
  distinct `destination_object_name` values with interleaved `created_at` timestamps (e.g. Table A
  at t=1 and t=3, Table B at t=2), call `list_codegen_artifacts`, assert the returned order is
  `[t=3, t=2, t=1]` — i.e. proves it's NOT grouped by table first.
- Update `test_codegen_service_api.py:630` — `m["dest_val"]` → `m["id"]`.
- Update `test_codegen_system_prompt.py:54-55` — `{"source_val": "APPROVED", "dest_val": "3"}` →
  `{"source_val": "APPROVED", "id": "3"}`; columns list `dest_val` → `id`.
- Update `test_bundle_sequencing.py` — every `dest_val` substring in expected SQL text (~10
  assertions across postgresql/mysql/mssql/oracle branches, plus the stacked-mapping test) → `id`.

## Verification

```bash
.venv/bin/python -m pytest engine/tests/test_codegen_service_api.py engine/tests/test_codegen_system_prompt.py engine/tests/test_bundle_sequencing.py -v
.venv/bin/python -m pytest engine/tests -q
.venv/bin/python scripts/validate_okf.py
```

Expected: new/updated tests pass, full suite has no new failures (pre-existing
`test_mapping_review_api.py` Ollama-connection failures are unrelated and environment-dependent);
`validate_okf.py` reports zero warnings for `docs/domain/ui.md`.

## Pitfalls

- `lookup_upsert.py` is a **separate** code path from the AI prompt template — both must be fixed or
  the fiber-triggered seed script and the AI-generated seed script will disagree again on column
  naming.
- Don't rename `source_val` — confirmed with the user it stays the primary/join key.
- Don't touch `build_delivery_bundle_text`'s ordering (`service.py` ~line 304) — different, intentional
  grouping-by-table use case.
- `value_map` dict values are already ids — do not add new extraction/validation logic, this is a
  pure rename at the rendering/SQL-text layer.

## Commit

```
fix(codegen): chronological artifact history; rename lookup dest_val to id

- list_codegen_artifacts() now orders by created_at only, so the codegen
  page's Artifact history shows one true chronological feed instead of
  blocks grouped by destination table.
- Renamed dest_val -> id throughout the lookup reference-table pipeline
  (prompt template, hardcoded schema/rules, lookup_upsert.py seed
  generator). The value was already the business id (via
  _extract_destination_id()); it was just mislabeled downstream, so
  neither the AI-generated seed script nor the fiber-triggered upsert
  script ever emitted an explicit id column.
```
