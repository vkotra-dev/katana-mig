---
type: Plan
task: 001ex-unmapped-lookup-row-counts
date: 2026-07-23
---

# Plan: 001ex — Display unmapped lookup row counts

**Task:** [001ex-unmapped-lookup-row-counts](../tasks/001ex-unmapped-lookup-row-counts.md)  
**Domain:** [governance.md](../docs/domain/governance.md)

---

## Current State

- Operators do not know the data volume impact of unmapped lookup values.
- `FeedSlice` currently has `source_schema_artifact` but no dedicated column for distinct value frequencies.
- `LookupValueMapResponse` does not return unmapped frequency counts.

---

## File Changes

### Step 1 — Backend: Add `data_profile` to `FeedSlice`

**Path:** `engine/src/migrations_engine/db/models.py`
- Add `data_profile: Mapped[dict[str, Any] | None] = mapped_column(JSON)` to `FeedSlice`.

### Step 2 — Backend: Compute `unmapped_row_count`

**Path:** `engine/src/migrations_engine/api/schemas.py`
- Add `unmapped_row_count: int | None = None` to `LookupValueMapResponse`.

**Path:** `engine/src/migrations_engine/routes/lookup.py` (or `lookup_mapping.py`)
- In the `listLookupValueMaps` route/service, you must fetch the `FeedSlice` associated with the project.
- **CRITICAL**: Do not hallucinate relationships. A `LookupValueMap` doesn't explicitly store `source_column_name`. Therefore, search all columns in `data_profile` for the keys.
- Use this exact logic to compute the sum:
  ```python
  unmapped_count = 0
  if slice_record and slice_record.data_profile:
      # Find all unmapped keys
      unmapped_keys = {k for k, v in lookup.source_value_map.items() if not v}
      # Search the profile (which is dict[column_name, dict[value, count]])
      for col_profile in slice_record.data_profile.values():
          if isinstance(col_profile, dict):
              for u_key in unmapped_keys:
                  unmapped_count += col_profile.get(u_key, 0)
  
  response_dto.unmapped_row_count = unmapped_count
  ```

### Step 3 — Frontend API: Update Types

**Path:** `web/lib/lookup-api.ts`
- Add `unmappedRowCount?: number;` to `LookupValueMapRecord`.

### Step 4 — Frontend UI: Display Warnings

**Path:** `web/components/projects/LookupMappingTable.tsx`
- If `group.unmappedRowCount > 0`, render an amber warning badge in the header of the table (e.g. `⚠️ {group.unmappedRowCount} rows unmapped`).

**Path:** `web/app/projects/[id]/feeds/[feedId]/page.tsx`
- In the Lookup Fibers card section, read `unmappedRowCount` from the matched `lookupMaps` item.
- Display the same warning badge next to the lookup name or status.

---

## Blast Radius

| Layer | Impact |
|-------|--------|
| `db/models.py` | Schema migration required for `data_profile` |
| `schemas.py` | Add field to DTO |
| `lookup.py` | Service calculation overhead (dict lookup in memory) |
| `LookupMappingTable.tsx` | UI badge added |
| `Feed Page` | UI badge added |

---

## Tests

1. Create a mock `FeedSlice` with a `data_profile` in `test_lookup_mapping_api.py`.
2. Map one value successfully, leave another unmapped (value=null).
3. Assert that the `GET` endpoint correctly calculates and returns `unmapped_row_count`.
