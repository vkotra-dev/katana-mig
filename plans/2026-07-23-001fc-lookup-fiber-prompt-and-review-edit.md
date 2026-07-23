---
task: 001fc-lookup-fiber-prompt-and-review-edit
domain: docs/domain/ui.md, docs/domain/governance.md
created: 2026-07-23
supersedes: 001fb
---

# Plan — 001fc: Destination-Anchored Lookup Fiber + Review Page Editing

## Task Link
[tasks/001fc-lookup-fiber-prompt-and-review-edit.md](../tasks/001fc-lookup-fiber-prompt-and-review-edit.md)

---

## Current State

| Layer | Current behaviour |
|---|---|
| AI prompt | Source-anchored: AI iterates source values, returns `{source_value, dest_id(UUID), confidence}` |
| Payload | Sends lossy `{id: UUID, value: heuristic_garbage}` per dest row — no deduplication |
| `_LookupProposal` | `source_value + dest_id(UUID) + confidence` |
| `LookupMapping.source_entry_id` | `NOT NULL` — can only create row if source entry exists |
| `dest_row` | `{id: UUID, label: garbled}` |
| `source_value_map` | Built from `dest_row.id` (UUID) |
| Review page | Reads from `LookupValueMap.source_value_map` — cannot show unmatched dest rows or let operator type source values |

---

## Objective

```
AI receives:
  source_values: ["APPROVED", "UNDER_REVIEW", "PAID", "PENDING", "REJECTED"]
  destination_rows: [
    {"id": "3", "status_code": "APPROVED",     "status_name": "Approved"},
    {"id": "2", "status_code": "UNDER_REVIEW", "status_name": "Under Review"},
    {"id": "6", "status_code": "CANCELLED",    "status_name": "Cancelled"},   ← no source match
    ...  (deduplicated)
  ]

AI returns (destination-anchored — one proposal per dest row):
  proposals: [
    { "dest_id": "3", "dest_value": "Approved",    "source_value": "APPROVED",     "confidence_score": 0.99 },
    { "dest_id": "2", "dest_value": "Under Review","source_value": "UNDER_REVIEW", "confidence_score": 0.98 },
    { "dest_id": "6", "dest_value": "Cancelled",   "source_value": null,           "confidence_score": 0.0  }
  ]

LookupMapping rows created (one per dest row):
  { source_value: "APPROVED",     dest_row: {id:"3", label:"Approved"},    status:"proposed" }
  { source_value: "UNDER_REVIEW", dest_row: {id:"2", label:"Under Review"},status:"proposed" }
  { source_value: null,           dest_row: {id:"6", label:"Cancelled"},   status:"unmatched" }

Review page grid:
  Dest ID | Destination Value | Source Value (editable)
  --------|-------------------|------------------------
  3       | Approved          | APPROVED     ← pre-filled
  2       | Under Review      | UNDER_REVIEW ← pre-filled
  6       | Cancelled         | [_______]    ← operator types here

Codegen: reads dest_row["id"] = "3" → FK value into the proc
```

---

## Out of Scope

- No `LookupValueMap` model changes
- No codegen changes (already reads `dest_row["id"]`)
- No `LookupMappingTable` component logic change

---

## Blast Radius

| File | Nature |
|---|---|
| `engine/migrations/versions/0038_lookup_mapping_nullable_source.py` | NEW — Alembic migration |
| `engine/src/migrations_engine/db/models.py` | `source_entry_id` + `source_value` → nullable |
| `engine/src/migrations_engine/ai/prompts/lookup_mapping.yaml` | Full rewrite — dest-anchored |
| `engine/src/migrations_engine/management/fibers.py` | Payload, Pydantic, mapping creation, bridge |
| `engine/src/migrations_engine/api/schemas.py` | `LookupMappingResponse.source_value` → nullable |
| `web/app/projects/[id]/feeds/[feedId]/review/page.tsx` | Grid rebuilt from fiber mappings endpoint |
| `web/lib/lookup-api.ts` | Add `listFiberMappings`, `patchFiberLookupMapping` |
| `engine/tests/test_lookup_fiber_api.py` | FakeLookupAdapter + all assertions |

---

## File Changes — Detailed

---

### 1. Alembic Migration `0038_lookup_mapping_nullable_source.py`

```python
revision = "0038"
down_revision = "0037"

def upgrade():
    with op.batch_alter_table("lookup_mappings") as batch_op:
        batch_op.alter_column("source_entry_id", nullable=True)
        batch_op.alter_column("source_value", nullable=True)

def downgrade():
    # Set nulls to empty string before making NOT NULL again
    op.execute("UPDATE lookup_mappings SET source_value = '' WHERE source_value IS NULL")
    op.execute("UPDATE lookup_mappings SET source_entry_id = '' WHERE source_entry_id IS NULL")
    with op.batch_alter_table("lookup_mappings") as batch_op:
        batch_op.alter_column("source_entry_id", nullable=False)
        batch_op.alter_column("source_value", nullable=False)
```

---

### 2. `db/models.py` — make fields nullable

```python
source_entry_id: Mapped[str | None] = mapped_column(
    String(36), ForeignKey("lookup_source_entries.entry_id"), nullable=True
)
source_value: Mapped[str | None] = mapped_column(String(512), nullable=True)
```

---

### 3. `lookup_mapping.yaml` — destination-anchored rewrite

```yaml
system: |
  You are a lookup value mapper for a data migration project.

  You will receive:
  - "source_values": distinct values extracted from the source system
  - "destination_rows": deduplicated rows from the destination reference/lookup table.
    Each row contains a primary key column (usually "id" or ending in "_id") and a
    human-readable label column (usually "name", "status_name", "display_name", etc.)

  Your job:
  For EVERY destination row, try to find the best matching source value.
  Use semantic matching — not just string equality.
  Examples: "UNDER_REVIEW" matches "Under Review", "A" matches "Active".

  For each destination row return:
  - "dest_id": the value of the primary key / unique identifier column of that row
  - "dest_value": the most human-readable label value from that row
    (prefer "name", "status_name", "display_name"; avoid Y/N flags or pure numeric columns)
  - "source_value": the best matching source value, or null if no confident match
  - "confidence_score": 1.0 for confident match, 0.0 if no match (source_value must be null)

  You must return one proposal for EVERY destination row — even those with no source match
  (set source_value to null and confidence_score to 0.0 for those).

  EXAMPLE:
  Input source_values: ["APPROVED", "PENDING"]
  Input destination_rows:
    [{"id":"3","status_code":"APPROVED","status_name":"Approved"},
     {"id":"1","status_code":"PENDING","status_name":"Pending"},
     {"id":"6","status_code":"CANCELLED","status_name":"Cancelled"}]
  Correct output:
    proposals: [
      {"dest_id":"3","dest_value":"Approved",  "source_value":"APPROVED","confidence_score":0.99},
      {"dest_id":"1","dest_value":"Pending",   "source_value":"PENDING", "confidence_score":0.99},
      {"dest_id":"6","dest_value":"Cancelled", "source_value":null,      "confidence_score":0.0}
    ]
    unmatched_source_values: []

  RULES:
  - Return strictly valid JSON. No markdown fences. No extra keys.
  - "dest_id" must be the exact string of the primary key column value.
  - "dest_value" must be human-readable text — NOT a Y/N flag.
  - Every destination row must appear exactly once in proposals.
  - source_value must be null (not empty string) when there is no match.

user: |
  $payload
```

---

### 4. `fibers.py` — `_LookupProposal` Pydantic

```python
class _LookupProposal(BaseModel):
    dest_id: str               # business key from destination row (e.g. "3")
    dest_value: str            # human-readable label (e.g. "Approved")
    source_value: str | None   # matched source value, or None
    confidence_score: float
```

---

### 5. `fibers.py` — payload construction

```python
# Deduplicate destination rows by content
seen_sigs: set[str] = set()
deduped: list[LookupDestEntry] = []
for entry in dest_entries:
    sig = json.dumps(entry.row_data, sort_keys=True)
    if sig not in seen_sigs:
        seen_sigs.add(sig)
        deduped.append(entry)

payload = json.dumps({
    "source_values": [e.source_value for e in source_entries],
    "destination_rows": [e.row_data for e in deduped],
})
```

---

### 6. `fibers.py` — lookup dict and proposal loop

Build lookup keyed by business PK extracted from row_data:
```python
from .lookup_mapping import _extract_destination_id

dest_entry_by_pk: dict[str, LookupDestEntry] = {}
for entry in deduped:
    pk = _extract_destination_id(entry.row_data)
    if pk:
        dest_entry_by_pk[pk] = entry
```

In proposal loop (now iterates dest rows, not source values):
```python
source_entry_by_value = {e.source_value: e for e in source_entries}

for proposal in ai_result.proposals:
    dest_entry = dest_entry_by_pk.get(proposal.dest_id)
    source_entry = source_entry_by_value.get(proposal.source_value) if proposal.source_value else None

    dest_row = {
        "id": proposal.dest_id,        # business key e.g. "3"
        "label": proposal.dest_value,  # human label e.g. "Approved"
    }

    mapping = LookupMapping(
        fiber_id=fiber.fiber_id,
        lookup_name=fiber.fiber_key,
        source_entry_id=source_entry.entry_id if source_entry else None,
        source_value=proposal.source_value,   # may be None
        dest_entry_id=dest_entry.entry_id if dest_entry else None,
        dest_row=dest_row,
        confidence_score=proposal.confidence_score,
        status="proposed" if proposal.source_value else "unmatched",
        mapped_by="ai",
    )
    db.add(mapping)
```

---

### 7. `fibers.py` — `patch_mapping` manual edit

When operator assigns/changes a source value for a previously unmatched row:
```python
# If source_value provided and no source_entry exists, create one
if body.source_value and mapping.source_entry_id is None:
    src_entry = LookupSourceEntry(
        fiber_id=fiber.fiber_id,
        lookup_name=fiber.fiber_key,
        source_value=body.source_value,
        discovery_type="manual",
    )
    db.add(src_entry)
    db.flush()
    mapping.source_entry_id = src_entry.entry_id

mapping.source_value = body.source_value
mapping.dest_entry_id = body.dest_entry_id
# dest_row stays as set by AI (id + label) — only update if dest changed
if body.dest_entry_id and body.dest_entry_id != mapping.dest_entry_id:
    dest_entry = db.get(LookupDestEntry, body.dest_entry_id)
    if dest_entry:
        from .lookup_mapping import _extract_destination_id, _extract_destination_label
        row_data = dest_entry.row_data or {}
        mapping.dest_row = {
            "id": _extract_destination_id(row_data) or dest_entry.entry_id,
            "label": _extract_destination_label(row_data),
        }
mapping.status = "confirmed" if body.source_value else "unmatched"
mapping.mapped_by = "operator"
```

Update `LookupMappingPatchRequest` schema to accept `source_value: str | None`.

---

### 8. `fibers.py` — `_bridge_lookup_fiber_to_value_map`

No changes needed — already reads `mapping.dest_row.get("id")` which will now correctly
be the business key `"3"` after the prompt fix.

---

### 9. `web/lib/lookup-api.ts` — new functions

```ts
// List all LookupMapping rows for a fiber (including unmatched)
export async function listFiberLookupMappings(
  token: string, projectId: string, feedId: string, fiberId: string
): Promise<LookupMappingRecord[]>

// Patch a single LookupMapping row (assign source value, change status)
export async function patchFiberLookupMapping(
  token: string, projectId: string, feedId: string, fiberId: string, mappingId: string,
  body: { source_value: string | null; dest_entry_id: string; status: string }
): Promise<LookupMappingRecord>
```

Calls:
- `GET /projects/:p/feeds/:f/fibers/:fi/mappings`
- `PATCH /projects/:p/feeds/:f/fibers/:fi/mappings/:m`

---

### 10. `web/app/projects/[id]/feeds/[feedId]/review/page.tsx`

**Replace the `lookupGroups` pair building** (~line 443):

Instead of reading from `LookupValueMap.source_value_map`, fetch all `LookupMapping` rows
directly from the fiber:

```ts
// For each lookup fiber:
const fiberMappings = await listFiberLookupMappings(token, projectId, feedId, fiber.fiberId);
const pairs = fiberMappings.map(m => ({
    mappingId: m.mappingId,
    sourceValue: m.sourceValue,          // may be null
    destinationRow: m.destRow,           // {id, label}
    confidenceScore: m.confidenceScore ?? 0,
    status: m.status,
}));
```

Grid columns:
- **Dest ID**: `destRow.id` (e.g. `"3"`) — read-only
- **Destination Value**: `destRow.label` (e.g. `"Approved"`) — read-only
- **Source Value**: `sourceValue` — **editable text input**

**`handleEditLookup`**: when operator changes source value for a row:
```ts
await patchFiberLookupMapping(token, projectId, feedId, fiber.fiberId, mapping.mappingId, {
    source_value: newSourceValue || null,
    dest_entry_id: mapping.destEntryId,
    status: newSourceValue ? "confirmed" : "unmatched",
});
```

---

## Tests

```bash
# Backend — must all pass
cd engine && source ../.venv/bin/activate
alembic upgrade head
pytest tests/test_lookup_fiber_api.py -v

# Frontend
cd web && npm run test
```

Update `FakeLookupAdapter` to:
- Read `destination_rows` not `destination_options`
- Return `dest_id`, `dest_value`, `source_value`, `confidence_score` per proposal
- Return one proposal per destination row (not per source value)
- Include unmatched rows with `source_value: null`

Update assertions to:
- Expect `LookupMapping` rows with `source_value = null` for unmatched dest rows
- Expect `dest_row = {"id": "..business_key..", "label": "..human_label.."}`

---

## Verification

1. Submit lookup fiber. Confirm:
   - All dest rows create a `LookupMapping` — matched with `source_value`, unmatched with `null`.
   - DB `dest_row` = `{"id": "3", "label": "Approved"}`.
2. Review page lookup grid shows all destination rows.
   - Matched rows show pre-filled source value.
   - Unmatched rows show empty editable field.
3. Operator types a source value for an unmatched row. Confirm:
   - `LookupMapping` updated with `source_value`, `source_entry_id`, `status=confirmed`.
   - Feed page fiber also reflects the change.
4. All 8+ backend tests pass.
5. All 317+ frontend tests pass.

---

## Pitfalls

- `_extract_destination_id()` must agree with what AI returns as `dest_id`. Test with a table
  where PK column is `status_id` not `id` to verify the heuristic aligns.
- Migration `0038` must run before any tests that create `LookupMapping` rows with null source.
- `LookupMappingPatchRequest` schema must accept `source_value: str | None`.
- `_bridge_lookup_fiber_to_value_map` skips mappings with `source_value = null` when building
  `source_value_map` — that is correct behaviour.
- Local LLMs may return `source_value: ""` instead of `null`. Add a post-processing step:
  `proposal.source_value = proposal.source_value or None`.

---

## Commit

```
feat(lookup-fiber): dest-anchored AI output; nullable source; review page editing (#001fc)
```
