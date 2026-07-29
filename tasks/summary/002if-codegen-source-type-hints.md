# Summary: 002if — Source-side type hints in codegen prompt

## Goal

Pass source column inferred types (from `SourceSchemaArtifact`) into the codegen prompt so the AI generating staging→destination SQL knows source types for correct CASTing.

## What was shipped

- `engine/src/migrations_engine/codegen/service.py` — Import `SourceSchemaArtifact`, fetch latest artifact per source feed (once, before per-destination loop), build case-normalized `{col_name.lower(): inferred_type}` map, augment each binding with `source_type_hint`, pass to `_build_user_prompt`.
- `engine/src/migrations_engine/codegen/templates/user_prompt.txt.j2` — Added source type hint rendering (`[integer]`, `[text]`, etc.) after source field name in field bindings.
- `engine/tests/test_codegen_service_api.py` — Added assertions for source type hints in captured prompt.

## Verification

- 28/28 codegen tests pass (24 from `test_codegen_service_api.py` + 4 from `test_codegen_system_prompt.py`).
- No regressions on existing tests.
- Case normalization (`lower()` on both map keys and lookups) prevents production bug where CSV header casing ("CUST_ID") wouldn't match lowercase binding source_field ("cust_id").

## Domain Updates Required

None. No model/API/role/workflow/UI changes.
