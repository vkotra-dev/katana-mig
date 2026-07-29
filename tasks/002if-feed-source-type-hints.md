---
id: 002if
title: Surface feed source-side inferred type hints in codegen prompt
status: completed
created: 2026-07-27
completed: 2026-07-27
priority: medium
depends-on: []
domain: engine
task: tasks/002if-feed-source-type-hints.md
plan: plans/002if-codegen-source-type-hints.md
---

# Task 002if — Source-side type hints in codegen prompt

## Goal

Pass source column inferred types (from `SourceSchemaArtifact`) into the codegen prompt so the AI generating staging→destination SQL knows source types for correct CASTing.

## Background

The codegen prompt already shows **destination**-side types in field bindings:
```
customer_id -> customer_id [integer] (lookup: none)
```

But it has **no** source-side type information. The source type is captured during source analysis in `SourceSchemaArtifact.columns` — each column has `{name, inferred_type, nullable, max_length}` where `inferred_type` is a literal: `"text" | "integer" | "decimal" | "date" | "boolean" | "uuid"`.

The AI generating SQL for transforms has to guess the source type from column naming alone, which leads to incorrect CASTs when source and destination types differ.

## Implementation Plan

### 1. Add `SourceSchemaArtifact` import to `service.py`

Add `SourceSchemaArtifact` to the imports from `..db.models` (line 24 of `service.py`).

### 2. Fetch `SourceSchemaArtifact` in `generate_codegen_artifact()`

In the loop over destination objects (inside `generate_codegen_artifact()`, after line 85 where `source_slice` is obtained, and **before** the per-destination loop at line 104), fetch the latest `SourceSchemaArtifact` for the source feed:

```python
source_type_map: dict[str, str] | None = None
artifact = db.scalar(
    select(SourceSchemaArtifact)
    .where(SourceSchemaArtifact.source_definition_id == source_definition_id)
    .order_by(SourceSchemaArtifact.created_at.desc())
    .limit(1)
)
if artifact is not None and artifact.columns:
    # CRITICAL: artifact columns[][].name comes from raw CSV headers (e.g. "CUST_ID"),
    # but field_bindings[].source_field is stored lowercase (e.g. "cust_id").
    # Lowercase both sides to match — this is the same pattern used in page.tsx:479.
    source_type_map = {col["name"].lower(): col["inferred_type"] for col in artifact.columns}
```

Then pass `source_type_map` into `_build_user_prompt()`.

### 3. Update `_build_user_prompt()` signature

Add `source_type_map: dict[str, str] | None = None` parameter.
Build a per-binding augmented bindings list:

```python
# Before template.render(), augment each binding with source_type_hint
bindings = mapping_snapshot.field_bindings or []
if source_type_map:
    bindings = [
        {**b, "source_type_hint": source_type_map.get(b.get("source_field", "").lower())}
        for b in bindings
    ]
```

Then pass this augmented `bindings` list to the template instead of the raw `mapping_snapshot.field_bindings`.

### 4. Update `user_prompt.txt.j2` field bindings line

**Current** (line 18):
```jinja2
- {{ binding.get('source_field') }} -> {{ binding.get('destination_field') }}{% if binding.get('destination_data_type') %} [{{ binding.get('destination_data_type') }}]{% endif %} (lookup: {{ binding.get('lookup_name') or 'none' }})
```

**New**:
```jinja2
{% set _src_hint = binding.get('source_type_hint') %}
- {{ binding.get('source_field') }}{% if _src_hint %} [{{ _src_hint }}]{% endif %} -> {{ binding.get('destination_field') }}{% if binding.get('destination_data_type') %} [{{ binding.get('destination_data_type') }}]{% endif %} (lookup: {{ binding.get('lookup_name') or 'none' }})
```

This produces output like:
```
customer_id [integer] -> customer_id [integer] (lookup: none)
full_name [text] -> full_name [text] (lookup: none)
order_status [text] -> status_code [INT] (lookup: status_lookup)
```

### 5. Add test assertion

Add assertion in `test_codegen_service_api.py` to verify source type hints appear in the captured user prompt. The existing test seed at lines 149-157 already creates `SourceSchemaArtifact` with `inferred_type: "integer"` and `inferred_type: "text"` — the `FakeAdapter` capture at line 893 can check for `[integer]` next to `customer_id`.

## Files changed

| File | Change |
|------|--------|
| `engine/src/migrations_engine/codegen/service.py` | Import `SourceSchemaArtifact`; fetch + build `source_type_map`; pass to `_build_user_prompt`; augment bindings |
| `engine/src/migrations_engine/codegen/templates/user_prompt.txt.j2` | Add source type hint rendering in field bindings line |
| `engine/tests/test_codegen_service_api.py` | Assert `[integer]` and `[text]` appear next to source fields in captured prompt |

## What NOT to change

- **System prompt** — source types are user-prompt data, not system rules.
- **`MappingSnapshot` schema** — no DB schema changes. Source types come fresh from `SourceSchemaArtifact` each codegen call.
- **Lookup resolution flow** — lookup resolution already handles type mismatches via CAST.
- **`_build_lookup_tables()`** — not relevant; source types are about field bindings, not lookup references.

## Domain Updates Required

None. No model/API/role/workflow/UI changes — only codegen prompt data flow (source type hints rendered in field bindings). No domain docs need updating.

## Verification

- Existing test seed data already has `SourceSchemaArtifact` with `inferred_type` values → tests will validate format automatically.
- No new DB migrations needed.
- No frontend changes.
- Graceful degradation: if no `SourceSchemaArtifact` exists, `source_type_map` is `None` and the template omits hints (same behavior as current code).

## Summary

Implemented source-side type hints in codegen prompt field bindings.

**Changes:**

- `engine/src/migrations_engine/codegen/service.py` — Import `SourceSchemaArtifact`, fetch latest artifact per source feed, build `{col_name.lower(): inferred_type}` map (case-normalized to match lowercase binding source_field), augment each binding with `source_type_hint`, pass to `_build_user_prompt` → template.
- `engine/src/migrations_engine/codegen/templates/user_prompt.txt.j2` — Added `{% if _src_hint %}[...]{% endif %}` after source field name in field bindings section.
- `engine/tests/test_codegen_service_api.py` — Added assertion that `[integer]` and `[text]` appear next to source fields in captured prompt.

**Verification:** 24/24 codegen tests pass, 4/4 system prompt tests pass. No new test failures introduced.
