Task: tasks/002i8-source-analysis-staging-table-name.md
Domain: docs/domain/source-model.md

## Current State

- `source_analysis.py`'s `analyze_source_slice()` currently passes `source_type_section`,
  `sample_text`, `target_db_engine`, `staging_schema` to the prompt — no feed label, no table name.
- `source_analysis.yaml` has 6 sequential rules (1-6); rule 6 is "SQL DDL Generation" (added by
  task 002c0). Verified directly against the current file — no free rule slot at "6".
- `feeds.py:598` has `_source_label(source_details)`. Verified zero callers anywhere in the
  codebase via grep — this task is its first real usage.
- `feeds.py` does not currently import `re` at module level.
- No table-naming helper exists anywhere in the codebase. `stg_{name}` is documented in
  `project.md`/`source-model.md` but never implemented — verified via grep, zero matches for
  `f"stg_{{...}}"` construction anywhere.

## Objective

Add a shared `_staging_table_name()` helper (fixed `"stg_"` prefix convention) and wire it into
the source-analysis prompt so the AI uses a deterministic table name instead of inventing one.
This helper is designed to be reused by task 002i9 for codegen's system prompt, so both the
Slice-section source DDL and codegen's generated stored procedures reference the same table name
for the same feed.

**Truncation decision:** Sanitize to 59 chars, then prefix `"stg_"` for a total of ≤63 chars
(PostgreSQL `NAMEDATALEN`, SQL Server limit).

## Out of Scope

- Per-feed staging schema (002c0's scope, already done)
- Changing `_source_label()`'s own extraction logic
- Wiring `staging_table_name` into `codegen/service.py` / `system_prompt.txt.j2` — that is 002i9
- Any frontend changes

## Blast Radius

| File | Action | What changes |
|------|--------|-------------|
| `engine/src/migrations_engine/management/feeds.py` | modify | Add `_staging_table_name()` helper; add `import re` if not present |
| `engine/src/migrations_engine/management/source_analysis.py` | modify | Compute and pass `staging_table_name` to the prompt |
| `engine/src/migrations_engine/ai/prompts/source_analysis.yaml` | modify | Fold table-name guidance into existing rules 5/6 — no new rule number |
| `engine/tests/test_source_analysis_service.py` | modify | Add direct unit tests for `_staging_table_name()` + integration test |
| `docs/domain/source-model.md` | modify | Document `stg_{feed_label}` convention |

## File Changes

### `engine/src/migrations_engine/management/feeds.py`

Add `import re` near the top if not already present. Add next to `_source_label()`:

```python
def _staging_table_name(feed_label: str) -> str:
    sanitized = re.sub(r'[^a-z0-9_]', '_', feed_label.lower())[:59]
    return f"stg_{sanitized if sanitized else 'source'}"
```

Truncation: 59 sanitized chars + `"stg_"` prefix = 63 total (PostgreSQL `NAMEDATALEN` limit).

### `engine/src/migrations_engine/management/source_analysis.py`

```python
from .feeds import _source_label, _staging_table_name
```

In `analyze_source_slice()`, after `staging_schema = ...`:

```python
feed_label = _source_label(source_definition.source_details)
staging_table_name = _staging_table_name(feed_label)
```

```python
prompt.set(
    source_type_section=source_type_section,
    sample_text=sample_text,
    target_db_engine=target_db,
    staging_schema=staging_schema or "",
    staging_table_name=staging_table_name,
)
```

### `engine/src/migrations_engine/ai/prompts/source_analysis.yaml`

Replace rule 5:
```
5. Schema Qualification: If a staging schema name is provided ('$staging_schema'), qualify the table name with this schema (e.g. CREATE TABLE $staging_schema.$staging_table_name (...)). If no schema is provided ('$staging_schema' is empty), use the bare table name.
```

Replace rule 6 (do not add a new rule — this number is taken):
```
6. SQL DDL Generation: Using the inferred columns, the target database engine '$target_db_engine', the schema name '$staging_schema', and the EXACT table name '$staging_table_name' (do NOT invent or randomize the table name), generate a valid CREATE TABLE SQL statement. Use appropriate SQL data types for the target engine (e.g. VARCHAR for text, INT for integer, DECIMAL(p,s) for decimal, DATE for date, BOOLEAN for boolean, CHAR(36) for uuid). Include NOT NULL constraints for non-nullable columns. Return the DDL as a single string with no extra whitespace or markdown formatting.
```

## Tests

Direct unit tests for `_staging_table_name()` (test the helper in isolation, not via `analyze_source_slice`):

- `test_staging_table_name_with_label` — `_staging_table_name("Orders") == "stg_orders"`
- `test_staging_table_name_special_chars` — `_staging_table_name("My-Orders.csv") == "stg_my_orders_csv"`
- `test_staging_table_name_fallback` — `_staging_table_name("Source") == "stg_source"` (matches
  `_source_label()`'s own fallback, so the end-to-end fallback is `stg_source` deterministically)
- `test_staging_table_name_empty` — `_staging_table_name("") == "stg_source"`
- `test_staging_table_name_truncation` — `_staging_table_name("a" * 100) == "stg_" + "a" * 59`

Integration: `analyze_source_slice()` with a labeled feed → assert `staging_table_name` appears
correctly in the rendered prompt and stored DDL.

## Verification

```bash
.venv/bin/python -m pytest engine/tests/test_source_analysis_service.py -v
.venv/bin/python -m pytest engine/tests -q
```

Expected: new tests pass, full suite shows baseline + new tests, 0 failures.

## Pitfalls

1. Rule numbering: the current `source_analysis.yaml` already has 6 sequential rules. Do NOT add
   a 7th top-level rule — fold the guidance into existing rules 5 and 6 as shown above.
2. `_staging_table_name()` must be usable by task 002i9 without modification — keep its signature
   as `(feed_label: str) -> str`, no source-analysis-specific parameters.
3. `source_details` can be `None` — `_source_label()` already returns `"Source"` in that case, so
   `_staging_table_name()` never receives `None`.
4. The test file `test_source_analysis_service.py` uses `SourceDefinition` as the ORM model name
   (imported from `migrations_engine.db.models`) — this matches the actual model. When seeding
   test data with `source_details={"label": "Customer Extract"}`, the label will flow through
   `_source_label()` → `_staging_table_name()` correctly.

## Commit

```
feat(source-analysis): specify staging table name in prompt using feed label

Add shared _staging_table_name() helper (stg_{label} convention, reused by
002i9 for codegen). Wire it into source_analysis.py and fold guidance into
the existing rules 5/6 of source_analysis.yaml — no new rule number, since
6 was already taken by task 002c0's SQL DDL Generation rule.
```
