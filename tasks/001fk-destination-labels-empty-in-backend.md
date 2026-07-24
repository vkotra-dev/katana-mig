---
id: 001fk
title: Populate dest_label in destination_mappings when building groups in backend
status: active
created: 2026-07-24
priority: high
domain: backend / lookup-mapping / fibers / destination-labels
depends-on: [001fj, 001fb]
---

# Task 001fk — Populate dest_label in destination_mappings

## Context

When the frontend displays lookup mappings on the review page, each group's destination value should render as `"Label (ID)"` — for example `"Bronze Standard (1)"`. The feed page correctly shows this because `proposed_mappings` include full `destRow` objects with `name`/`label` fields.

However, the backend **never populates** `dest_label` when building `destination_mappings` groups. Every code path that creates or rebuilds these groups hardcodes `"dest_label": ""`:

| Location | Trigger |
|---|---|
| `fibers.py:256` | Auto-creating LookupValueMap from fiber `proposed_mappings` |
| `lookup_mapping.py:118` | `add_source_value` when no existing `destination_mappings` |
| `lookup_mapping.py:145` | `remove_source_value` when no existing `destination_mappings` |
| `lookup_mapping.py:188` | `move_source_value` when no existing `destination_mappings` |
| `lookup_mapping.py:211` | `move_source_value` creating new group |

The backend already has `_extract_destination_label(row)` at line 538 of `lookup_mapping.py` — a multi-strategy function that extracts a human-readable label from a destination row by checking `label`, `name`, `description`, `desc`, `val`, `value`, `display`, and fallback substring matches. It is **never called** when building `destination_mappings`.

The frontend fallback in `review/page.tsx` (line 463-464) was also fixed to extract `destLabel` from `destRow` as a defensive measure, but the root cause is the backend not populating `dest_label` at group creation time.

## Fix

In every place where a new `destination_mappings` group dict is constructed with `"dest_label": ""`, call `_extract_destination_label()` using the available `dest_row` data. Where `dest_row` is not available (e.g., the `source_value_map` rebuild path), pass the `destination_table` rows to extract labels from.

### Changes in `lookup_mapping.py`

For the `add_source_value` path (line ~116), `remove_source_value` path (line ~143), and `move_source_value` path (lines ~188, ~209): these have access to `lookup_map.destination_table`. When building a new group with empty `dest_label`, look up the matching row from `destination_table` and call `_extract_destination_label(row)`.

For the `source_value_map` rebuild path (line ~188), derive the label from the `dest_id` by looking it up in the destination table.

### Changes in `fibers.py`

For the auto-create path (line ~254), the `dest_row_data` variable already contains the full row from `proposed_mappings`. Pass it to `_extract_destination_label(dest_row_data)`.

### Import

`fibers.py` needs to import `_extract_destination_label` from `lookup_mapping`. Since `fibers.py` is in the same package and both are under `management/`, this is a direct relative import. However, circular import risk must be checked — `lookup_mapping.py` does not import from `fibers.py`, so one-way import is safe.

## Testing

1. Update `test_lookup_mapping_api.py` — verify that `add_source_value`, `remove_source_value`, and `move_source_value` tests assert `dest_label` is populated from `destination_table` when the action creates a new group.
2. Add a new test in `test_fiber_ai_flow.py` or `test_lookup_mapping_api.py` verifying that the auto-creation path (from `fibers.py`) populates `dest_label` from `proposed_mappings[].dest_row`.
3. Run full test suite — all existing tests must pass.

## Files to change

1. `engine/src/migrations_engine/management/lookup_mapping.py` — populate `dest_label` in 4 places
2. `engine/src/migrations_engine/management/fibers.py` — populate `dest_label` in 1 place, add import
3. `engine/tests/test_lookup_mapping_api.py` — update assertions to verify `dest_label`
4. `engine/tests/test_fiber_ai_flow.py` (or new test) — verify auto-creation path
