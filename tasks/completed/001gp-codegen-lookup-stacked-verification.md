---
id: 001gp
title: Codegen Invalidation & Multi-Dialect DML Tests for Stacked Lookup Mappings
status: completed
created: 2026-07-24
priority: high
domain: backend / codegen / lookup-upsert
depends-on: []
---

# Task 001gp — Codegen Invalidation & Multi-Dialect DML Tests for Stacked Lookup Mappings

## Context

Verify and test that stacked source value modifications (add/remove alias) correctly trigger snapshot invalidation and generate valid DML SQL statements across all supported SQL engines. Source values only — no destination-group delete action exists (see [[001gn]] scope note).

## Requirements

1. **Snapshot Invalidation Tests**: Verify in `test_lookup_mapping_api.py` that editing a lookup map via PATCH (`add_source_value`, `remove_source_value`) resets `LookupSnapshot.status` from `approved` to `draft`.
2. **Multi-Dialect DML Tests**: Verify in `test_bundle_sequencing.py` or `test_codegen_lookup_integration.py` that `generate_lookup_upsert_sql()` outputs valid DML statements for `postgresql`, `mysql`, `mssql`, and `oracle` when 1-to-many stacked source values are present.

## Files to Change

1. `engine/tests/test_lookup_mapping_api.py` — Add snapshot invalidation assertions.
2. `engine/tests/test_bundle_sequencing.py` — Add multi-dialect DML assertions for 1-to-many source values.

## Verification

```bash
cd engine && source ../.venv/bin/activate
pytest tests/test_lookup_mapping_api.py tests/test_bundle_sequencing.py -v
pytest -v
```

---
Plan: plans/2026-07-24-001gp-codegen-lookup-stacked-verification.md
Summary: tasks/summary/001gp-codegen-lookup-stacked-verification.md
