---
id: 002if
title: Codegen source-side type hints in field bindings
task: tasks/002if-feed-source-type-hints.md
domain: engine
status: plan-drafted
created: 2026-07-27
---

# Plan — 002if: Source-side type hints in codegen prompt

## Task / Domain Links

- Task: `tasks/002if-feed-source-type-hints.md`
- Domain: engine (codegen service + template)

## Current State

`_build_user_prompt()` renders field bindings in `user_prompt.txt.j2` showing **destination**-side types:

```
customer_id -> customer_id [integer] (lookup: none)
```

Source-side types from `SourceSchemaArtifact` (`columns[].name`, `columns[].inferred_type`) are never fetched or passed into the prompt. The AI has no explicit signal about source column types when generating CASTs for staging→destination transforms.

## Objective

Pass source column inferred types into the codegen prompt so each field binding line shows the source type in brackets:

```
customer_id [integer] -> customer_id [integer] (lookup: none)
full_name [text] -> full_name [text] (lookup: none)
```

## Out of Scope

- **System prompt changes** — source types are user-prompt data, not system rules.
- **Lookup resolution changes** — lookup resolution already handles type mismatches via CAST.
- **MappingSnapshot schema changes** — source types come fresh from `SourceSchemaArtifact` each codegen call; no need to persist them in the mapping.
- **Frontend changes** — purely backend + template.
- **DB migrations** — no schema changes.

## Blast Radius

Narrow. Three files touched:

| File | Type | Risk |
|------|------|------|
| `engine/src/migrations_engine/codegen/service.py` | Backend logic | Low — adds one DB query per codegen run, builds a dict map |
| `engine/src/migrations_engine/codegen/templates/user_prompt.txt.j2` | Template | Low — adds `{% if _src_hint %}` conditional; no structural change |
| `engine/tests/test_codegen_service_api.py` | Test | None — only adds assertions |

No changes to system prompt, lookup flow, or existing API contracts.

## File Changes

### `engine/src/migrations_engine/codegen/service.py`

1. Import `SourceSchemaArtifact` from `..db.models`.
2. After `source_slice` is obtained (line ~85), fetch `SourceSchemaArtifact`:

```python
source_type_map: dict[str, str] | None = None
artifact = db.scalar(
    select(SourceSchemaArtifact)
    .where(SourceSchemaArtifact.source_definition_id == source_definition_id)
    .order_by(SourceSchemaArtifact.created_at.desc())
    .limit(1)
)
if artifact is not None and artifact.columns:
    # CRITICAL: artifact columns[].name comes from raw CSV headers (e.g. "CUST_ID"),
    # but field_bindings[].source_field is stored lowercase (e.g. "cust_id").
    # Lowercase both sides — same pattern as page.tsx:479.
    source_type_map = {col["name"].lower(): col["inferred_type"] for col in artifact.columns}
```

3. Pass `source_type_map` to `_build_user_prompt()`.
4. In `_build_user_prompt()`, add `source_type_map` param, augment each binding:

```python
if source_type_map:
    bindings = [
        {**b, "source_type_hint": source_type_map.get(b.get("source_field", "").lower())}
        for b in (mapping_snapshot.field_bindings or [])
    ]
else:
    bindings = mapping_snapshot.field_bindings or []
```

Pass `bindings` to template as `mapping_snapshot.field_bindings` replacement.

### `engine/src/migrations_engine/codegen/templates/user_prompt.txt.j2`

Line 18 — change:

```jinja2
- {{ binding.get('source_field') }} -> {{ binding.get('destination_field') }}{% if binding.get('destination_data_type') %} [{{ binding.get('destination_data_type') }}]{% endif %} (lookup: {{ binding.get('lookup_name') or 'none' }})
```

To:

```jinja2
{% set _src_hint = binding.get('source_type_hint') %}
- {{ binding.get('source_field') }}{% if _src_hint %} [{{ _src_hint }}]{% endif %} -> {{ binding.get('destination_field') }}{% if binding.get('destination_data_type') %} [{{ binding.get('destination_data_type') }}]{% endif %} (lookup: {{ binding.get('lookup_name') or 'none' }})
```

### `engine/tests/test_codegen_service_api.py`

Add assertion in `test_codegen_includes_discussion_comments` (or `test_post_codegen_creates_active_artifact_and_preview`) that the `FakeAdapter` captured user prompt contains source type hints. The existing test seed at lines 149-157 already creates `SourceSchemaArtifact` with `inferred_type: "integer"` and `inferred_type: "text"` — check for `[integer]` next to `customer_id` in `fake.calls[-1].user`.

## Tests

- **Existing test seed data already has `SourceSchemaArtifact`** with `inferred_type` values — the `FakeAdapter` capture already has access to the rendered prompt. Just add the assertion.
- **Case-sensitivity test** (optional but recommended): seed fixture with a mixed-case column name (e.g. `"CUST_ID"`) and a lowercase binding source_field (e.g. `"cust_id"`) to verify the map still matches.

## Verification

- `source_type_map` is `None` when no artifact exists → template omits hints → same behavior as current code (graceful degradation).
- `source_type_map` is empty dict when artifact exists but has no columns → same graceful degradation.
- Case normalization applied on both map build and lookup (lowercase both sides).
- No change to any existing API contract, model, or prompt structure.

## Pitfalls

1. **Case-sensitivity mismatch** (CRITICAL): `SourceSchemaArtifact.columns[].name` comes from raw CSV headers which preserve original casing (e.g. `"CUST_ID"`), but `field_bindings[].source_field` is stored lowercase (e.g. `"cust_id"`). The dict lookup must lowercase both sides. Test fixture uses matching lowercase names so it won't catch this bug — must be verified manually or with an explicit test.
2. **`artifact.columns` can be `None`**: `artifact.columns` is `Mapped[list[dict]]`, not nullable at the DB level, but the `if artifact is not None and artifact.columns` guard handles the edge case of a malformed artifact.
3. **`field_bindings` can be empty**: The augmentation loop handles `None` and empty lists gracefully with `mapping_snapshot.field_bindings or []`.

## Commit

One commit: "feat(codegen): add source-side type hints to field bindings in codegen prompt". Message focuses on the case-sensitivity fix and the prompt enhancement.
