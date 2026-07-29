---
id: 002ih
title: Persist mapping_ownership_warnings and unblock codegen
status: abandoned
created: 2026-07-27
completed: null
priority: high
depends-on: [002ig]
domain: engine, web
---

# Task 002ih — Persist `mapping_ownership_warnings` and unblock codegen

## Goal

- Persist `mapping_ownership_warnings` to the `Feed` model so they are visible everywhere (feed page, codegen page)
- Remove the 409 block from codegen when `destination_object_references` is empty

## Implementation

| File | Change |
|------|--------|
| `engine/src/migrations_engine/db/models.py` | Added `mapping_ownership_warnings` JSON column to `Feed` |
| `engine/src/migrations_engine/management/feeds.py` | Persist warnings after computing in `_source_contract_response` and `list_source_contracts` |
| `engine/src/migrations_engine/codegen/service.py` | Removed 409 block; returns empty list when `destination_object_references` is empty |
| `engine/tests/test_mapping_ownership_warnings.py` | 2 new persistence tests |
| `engine/tests/test_codegen_service_api.py` | 1 new test for codegen without destination refs |

## Verification

- 465/465 tests pass
- Frontend wiring (display of warnings on codegen page) is a follow-up frontend task

## Summary

Implemented persistence of `mapping_ownership_warnings` to the `Feed` model. The ownership warnings are now written to the database on every feed list/response call, and the codegen endpoint no longer blocks with a 409 when `destination_object_references` is empty — instead it returns an empty result so the frontend can display the warning context.
