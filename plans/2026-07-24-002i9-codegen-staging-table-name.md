Task: tasks/002i9-codegen-staging-table-name.md
Domain: docs/domain/source-model.md

## Current State

- `_build_system_prompt()` (`codegen/service.py:668-679`) has no `staging_table_name` parameter.
- `generate_codegen_artifact()` fetches `source_definition` once at the top (line ~65); it is in
  scope for the entire function, including inside the per-table loop where `_build_system_prompt()`
  is called (line ~134).
- `system_prompt.txt.j2:20` has a placeholder-only example: `<staging_schema>.staging_table` —
  never a real Jinja variable.
- `002i8` creates `_staging_table_name(feed_label: str) -> str` in `feeds.py`, returning
  `f"stg_{sanitized_label}"`. This task imports and reuses it verbatim.
- `002i7` already established the pattern of computing feed-level values once, before the per-table
  loop, and reusing them across iterations (the `comments`/`slice_comments` restoration). This task
  follows the identical placement pattern for `staging_table_name`.

## Objective

Wire a real, deterministic `staging_table_name` into codegen's system prompt, computed once per
feed via the shared helper from `002i8`, so codegen-generated stored procedures reference the same
staging table name that source analysis's DDL establishes for that feed.

## Out of Scope

- Do NOT create a new sanitization function — import `_staging_table_name()` from `feeds.py`.
- Do NOT touch `_build_user_prompt()`, `feed_instructions`, or anything related to task 002i2.
- Do NOT change `destination_object_name` handling — unrelated, that's the destination side.
- Do NOT recompute `staging_table_name` per destination table inside the loop — compute once per
  feed, before the loop.

## Blast Radius

| File | Action | What changes |
|------|--------|-------------|
| `engine/src/migrations_engine/codegen/service.py` | modify | Import shared helper, compute once before the per-table loop, add `_build_system_prompt()` parameter |
| `engine/src/migrations_engine/codegen/templates/system_prompt.txt.j2` | modify | Replace placeholder example with real `{{ staging_table_name }}` |
| `engine/tests/test_codegen_service_api.py` | modify | Add tests verifying the value reaches the rendered prompt |

## File Changes

### `engine/src/migrations_engine/codegen/service.py`

Add import:
```python
from .feeds import _source_label, _staging_table_name
```

Before the per-table loop (`for destination_object_name in destination_references:`), alongside
the existing `comments`/`slice_comments` fetch (restored by 002i7):

```python
staging_table_name = _staging_table_name(_source_label(source_definition.source_details))
```

Update `_build_system_prompt()`:

```python
def _build_system_prompt(
    *,
    project_config: MigrationProjectConfig,
    destination_object_name: str,
    project_definition: ProjectDefinition,
    staging_table_name: str,
) -> str:
    template = jinja_env.get_template("system_prompt.txt.j2")
    return template.render(
        project_config=project_config,
        destination_object_name=destination_object_name,
        project_definition=project_definition,
        staging_table_name=staging_table_name,
    ).strip()
```

Update the call site inside the loop to pass the new argument:

```python
system_prompt = _build_system_prompt(
    project_config=project_config,
    destination_object_name=destination_object_name,
    project_definition=project_definition,
    staging_table_name=staging_table_name,
)
```

### `engine/src/migrations_engine/codegen/templates/system_prompt.txt.j2`

Replace line 20's placeholder:
```diff
-     JOIN <staging_schema>.staging_table stg ON stg.<source_column> = ref.source_val
+     JOIN {{ project_config.staging_schema or '<staging_schema>' }}.{{ staging_table_name }} stg ON stg.<source_column> = ref.source_val
```

## Tests

- `test_system_prompt_includes_staging_table_name` — feed with `source_details={"label": "Orders"}`
  → trigger codegen → assert `stg_orders` appears in the `FakeAdapter`-captured system prompt.
- `test_system_prompt_staging_table_name_fallback` — feed with no label → assert `stg_source`
  appears.

## Verification

```bash
.venv/bin/python -m pytest engine/tests/test_codegen_service_api.py -v
.venv/bin/python -m pytest engine/tests -q
```

Expected: new tests pass, full suite 0 failures.

## Pitfalls

- Compute `staging_table_name` once per feed, before the loop — it doesn't vary by destination
  table, matching how `comments`/`slice_comments` are already handled after 002i7's fix.
- Import the helper, don't duplicate it — `002i8` owns the sanitization logic; this task only
  consumes it.
- This depends on `002i8` being merged first (the helper must exist in `feeds.py`).

## Commit

```
feat(codegen): wire staging table name into system prompt

Reuse 002i8's shared _staging_table_name() helper, computed once per feed
before the per-table loop. Add as a new _build_system_prompt() parameter.
Replace the illustrative placeholder in system_prompt.txt.j2 with the real
value so codegen-generated procedures reference the same stg_{feed_label}
table that source analysis's DDL establishes for the same feed.
```
