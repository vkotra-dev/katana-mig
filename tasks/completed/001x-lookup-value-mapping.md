# Task 001x — Lookup Value Mapping (API + UI)

**Plan:** `plans/2026-06-29-001x-lookup-value-mapping.md` _(to be written)_

## Domain

- `docs/domain/source-model.md` — LookupSnapshot, value_map
- `docs/domain/runs.md` — baton_3 (lookup stage); UnmappedValueError / LookupDeltaCR
- `docs/domain/governance.md` — approval chain

## Depends on

- 001v (SourceValueSummary — provides source values that need mapping)
- 001w (MappingSnapshot approved — lookup_name on each binding determines which fields need lookup entry)

## Scope

Operator enters the destination lookup table for each lookup field, and the system
creates an approved `LookupSnapshot`. Each lookup field maps source values → destination IDs.

**Backend:**

1. Endpoint to receive a raw destination lookup table (CSV or JSON array) for a named lookup.
   System parses it and stores it as a `LookupValueMap` record (new model).

2. From a set of `LookupValueMap` records, generate a `LookupSnapshot` per
   `(source_definition_id, lookup_name)` by joining `SourceValueSummary` source values
   against the operator-provided destination table.

3. Approval: `LookupSnapshot.status` → `"approved"`; emit `AuditEvent`.

**UI (lookup entry screen):**

- One tab per lookup field (lookup fields from approved `MappingSnapshot`)
- Left column: source values from `SourceValueSummary` (distinct observed values)
- Right column: destination ID dropdown (from operator-uploaded lookup table)
- "Upload lookup table" file/paste input per tab
- "Approve" button when all source values are mapped

## New model: `LookupValueMap`

```python
class LookupValueMap(Base):
    __tablename__ = "lookup_value_maps"

    lookup_value_map_id: str  # UUID pk
    source_definition_id: str  # FK → source_definitions
    lookup_name: str           # matches lookup_name in field_bindings
    destination_table: list[dict]  # [{id, label, ...}] raw destination table rows
    status: str  # "draft" | "approved"
    created_at: datetime
```

Migration 0012 (after 001v's migration 0011).

`LookupSnapshot` already exists in `models.py`; it has `value_map: dict[str, str]`
(source value → destination ID) and `status`.

## API routes (`routes/lookup.py`)

```
POST /projects/{project_id}/sources/{source_definition_id}/lookup-maps
  — body: {lookup_name: str, destination_table: list[dict]}
  — stores LookupValueMap(status="draft")
  — central_team only

GET  /projects/{project_id}/sources/{source_definition_id}/lookup-maps
  — list LookupValueMap records for this source

POST /projects/{project_id}/sources/{source_definition_id}/lookup-snapshots
  — generates LookupSnapshot from approved LookupValueMap + SourceValueSummary
  — maps each distinct source value to a destination ID; flags unmapped values
  — body: {lookup_name: str}
  — central_team only

POST /projects/{project_id}/sources/{source_definition_id}/lookup-snapshots/{id}/approve
  — status → "approved"; emits AuditEvent
  — central_team only
```

## UI page (`web/app/projects/[id]/sources/[sourceId]/lookup/page.tsx`)

- Tabs for each lookup field (from approved MappingSnapshot bindings where `lookup_name != null`)
- Per-tab: source value list (from SourceValueSummary) + destination ID mapping
- File paste area: operator pastes CSV or JSON of destination lookup table
- Unmapped values highlighted in red until resolved
- "Generate Snapshot" → "Approve" two-step flow
- Role-gated: approve button for `central_team` only

## Acceptance criteria

- [ ] `POST .../lookup-maps` stores destination table for the named lookup
- [ ] `POST .../lookup-snapshots` generates a `LookupSnapshot` with `value_map` populated
- [ ] Unmapped source values produce a validation error listing the unmapped values
- [ ] Approval marks `LookupSnapshot.status = "approved"` and emits `AuditEvent`
- [ ] UI shows per-tab mapping with source values and destination dropdown
- [ ] Migration 0012 runs cleanly after 0011

## Notes

- `LookupDeltaCR` (from runs 001t) handles _runtime_ unmapped values; this task handles
  the _pre-run_ mapping entry step. They are separate flows.
- On resume after a `LookupDeltaCR`, the run reloads the latest `approved` `LookupSnapshot`
  for the project; the operator must add the missing mapping here before resuming.
- Multiple `LookupSnapshot` versions can exist for the same lookup_name; the run always
  pins the latest approved at launch time.
