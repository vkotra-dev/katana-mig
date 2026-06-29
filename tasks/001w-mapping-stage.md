# Task 001w — Mapping Stage (API + AI + Approval)

**Plan:** `plans/2026-06-29-001w-mapping-stage.md` _(to be written)_

## Domain

- `docs/domain/source-model.md` — MappingSnapshot, destination_object_references
- `docs/domain/runs.md` — baton_2 (mapping stage); baton handoff on approval
- `docs/domain/governance.md` — approval chain, I18

## Depends on

- 001v (SourceSchemaArtifact must exist — drives field binding proposal)
- 001s (AI adapter)

## Scope

AI-suggested field binding + operator approval flow for the mapping stage.

**Backend:**

1. Propose field bindings using AI: read `SourceSchemaArtifact` columns and destination
   object schema (provided in the request as a list of destination field names); call AI
   adapter to generate `MappingSnapshot.field_bindings`.

2. Operator reviews and approves the mapping. On approval:
   - `MappingSnapshot.status` → `"approved"`
   - Write `destination_object_references` back to `SourceDefinition`
   - Emit `AuditEvent(event_type="mapping_approved")`

3. Operator can reject (status → `"rejected"`) and trigger a new proposal.

**UI (mapping review screen — stitch `06-mapping-review.md` if it exists):**

- Table of source field → proposed destination field, with lookup flag per row
- Per-row override: operator can change destination field via dropdown
- "Approve" button (central_team only); "Reject and re-propose" button

## MappingSnapshot fields (already exist in models.py)

```python
field_bindings: list[dict]  # [{source_field, destination_field, lookup_name}]
status: str  # "draft" | "approved" | "rejected"
mapping_snapshot_version: str
```

No new model needed. Confirm `status` and `field_bindings` are present before
starting (read `engine/src/migrations_engine/db/models.py`).

## API routes (`routes/mapping.py`)

```
POST /projects/{project_id}/sources/{source_definition_id}/mapping/propose
  — no body required
  — reads destination_fields from ProjectDefinition.domain_config.destination_schema_ddl
    (parsed to extract column names); returns 409 destination_schema_missing if not set
  — AI proposes field_bindings → creates MappingSnapshot(status="draft")
  — returns snapshot with field_bindings
  — central_team only

GET  /projects/{project_id}/sources/{source_definition_id}/mapping
  — latest MappingSnapshot

PATCH /projects/{project_id}/sources/{source_definition_id}/mapping
  — update field_bindings before approval (operator overrides)
  — body: {field_bindings: list[dict]}

POST /projects/{project_id}/sources/{source_definition_id}/mapping/approve
  — status → "approved"; writes destination_object_references to SourceDefinition
  — central_team only

POST /projects/{project_id}/sources/{source_definition_id}/mapping/reject
  — status → "rejected"
  — central_team only
```

## UI page (`web/app/projects/[id]/sources/[sourceId]/mapping/page.tsx`)

- Loads `SourceSchemaArtifact` (for source column list) and `MappingSnapshot`
- Renders field binding table: source field | destination field (editable) | lookup?
- Displays destination fields dropdown from the `destination_fields` the user entered
- Approve/Reject buttons (role-gated)
- Toasts on success/error

## Acceptance criteria

- [ ] `POST .../propose` creates a `MappingSnapshot` in `"draft"` status
- [ ] AI-suggested bindings match source columns to destination fields
- [ ] `PATCH .../mapping` allows operator to override bindings
- [ ] `POST .../approve` marks snapshot approved and writes `destination_object_references`
- [ ] `AuditEvent` is created on approval
- [ ] UI renders field binding table with editable destination column
- [ ] Tests mock AI adapter; no live API calls

## Notes

- One `MappingSnapshot` per `(source_definition_id, snapshot_version)`; previous drafts
  can remain in the database (they are not superseded unless a new proposal is triggered)
- `lookup_name` in `field_bindings` is null unless the destination field uses a lookup table;
  operator sets this manually in the UI
- `destination_object_references` written on approval is a `list[str]` of destination object
  names derived from the approved bindings (e.g. `["Customer", "Address"]`)
