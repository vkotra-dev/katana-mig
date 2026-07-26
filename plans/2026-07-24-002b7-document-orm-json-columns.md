---
id: 002b7
title: Fix 3 MappingBindingSignOff/LookupSignOff/source-model.md contradictions
status: completed
created: 2026-07-24
domain: docs/domain/
task: 002b7
---

# Plan: Fix 3 schema contradictions in source-model.md

## Task Link

- **Task:** [002b7](../tasks/002b7-document-orm-json-columns.md)

## Objective

Apply 3 corrections to `docs/domain/source-model.md` discovered by 002b6 verification.

## Changes

### 1. MappingBindingSignOff (line ~495-504)

Replace `binding_index`+`status` (enum) with `source_field`+`destination_field` (existence-based via unique constraint).

### 2. LookupSignOff (line ~506-515)

Replace `fiber_id`+`lookup_name`+`status` with `lookup_value_map_id`+`user_id`+`signed_at`.

### 3. Delete stale fiber entities (lines 314-338)

Remove `LookupSourceEntry`/`LookupDestFeed`/`LookupDestEntry`/`LookupMapping` descriptions.

## Files changed

- `docs/domain/source-model.md` — 3 corrections

## Tests

N/A

## Commit

```
fix(docs): correct MappingBindingSignOff, LookupSignOff, and remove stale fiber entities in source-model.md

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
```
