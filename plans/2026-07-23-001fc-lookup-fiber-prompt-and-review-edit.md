---
task: 001fc-lookup-fiber-prompt-and-review-edit
domain: docs/domain/ui.md, docs/domain/governance.md
created: 2026-07-23
supersedes: 001fb
---

# Plan — 001fc: Lookup Fiber Prompt Fix + Review Page Editing

## Task Link
[tasks/001fc-lookup-fiber-prompt-and-review-edit.md](../tasks/001fc-lookup-fiber-prompt-and-review-edit.md)

---

## Current State

### AI Prompt (`lookup_mapping.yaml`)
Output contract: `source_value`, `dest_id` (UUID), `confidence_score`.
No business key. No human label. Local LLMs get garbled pre-processed data.

### Payload (`fibers.py` ~line 850)
```python
"destination_options": [
    {"id": entry.entry_id,                              # UUID
     "value": _extract_destination_label(entry.row_data)} # heuristic, often garbled
    for entry in dest_entries                           # no deduplication
]
```

### `_LookupProposal` Pydantic (~line 93)
```python
class _LookupProposal(BaseModel):
    source_value: str
    dest_id: str        # UUID
    confidence_score: float
    # missing: id (business key), dest_value (human label)
```

### `dest_row` saved in DB (~line 926)
```python
dest_row = {"id": dest_entry.entry_id,   # UUID — wrong
            "label": _extract_destination_label(...)}  # heuristic — often garbled
```

### `patch_mapping` manual edit (~line 1105)
```python
mapping.dest_row = {"id": dest_entry.entry_id,         # UUID — wrong
                    "label": _extract_destination_label(...)}
```

### `_bridge_lookup_fiber_to_value_map`
```python
source_value_map[mapping.source_value] = mapping.dest_entry_id   # UUID — should be business key
```

### Review page pair building (`review/page.tsx` ~line 459)
```ts
const destRow = latestMap.destinationTable.find(
    (row) => String(row.id) === String(destId) || ...
) || { id: destId };   // fallback shows raw UUID
```
Matches UUID → UUID, display shows UUID not `"Approved (3)"`.

### Review page `handleEditLookup` (~line 208)
Calls only `patchLookupValueMap` — does not update individual `LookupMapping` rows.
Feed page stays out of sync after review page edits.

---

## Objective

```
After this task:

Feed page and review page both show:
  Column 1: APPROVED
  Column 2: Approved (3)

dest_row in LookupMapping DB:
  {"id": "3", "label": "Approved"}   ← business key + clean label

source_value_map in LookupValueMap DB:
  {"APPROVED": "3", "UNDER_REVIEW": "2", ...}   ← business key, not UUID

Codegen reads dest_row["id"] = "3" → correct FK value in generated proc.

Review page allows operator to change a mapping inline — persisted to both
LookupValueMap and the individual LookupMapping fiber rows.
```

---

## Out of Scope

- No DB model changes — no migration
- No `LookupMappingTable` UI component changes
- No codegen changes — already reads `dest_row["id"]`
- No retroactive fix to existing approved `LookupValueMap` rows with UUID values

---

## Blast Radius

| File | Nature |
|---|---|
| `engine/src/migrations_engine/ai/prompts/lookup_mapping.yaml` | Full rewrite |
| `engine/src/migrations_engine/management/fibers.py` | Payload, Pydantic, dest_row (AI + manual), bridge |
| `web/app/projects/[id]/feeds/[feedId]/review/page.tsx` | Pair building + handleEditLookup |
| `web/lib/lookup-api.ts` | Add `patchFiberLookupMapping` API call |
| `engine/tests/test_lookup_fiber_api.py` | FakeLookupAdapter + assertions |

---

## File Changes — Detailed

---

### 1. `lookup_mapping.yaml` — full rewrite

The Ollama adapter appends the Pydantic schema automatically. The system prompt must not
duplicate schema — but must explain the data shape and include an example.

```yaml
system: |
  You are a lookup value mapper for a data migration project.

  You will receive:
  - "source_values": distinct values extracted from the source system
  - "destination_rows": rows from the destination reference/lookup table.
    Each row contains multiple columns. One column is the primary key or unique identifier
    (usually named "id", or ending in "_id", or a short code column).
    Another column contains the best human-readable label (usually named "name",
    "status_name", "display_name", "description", or similar).

  Your job:
  For each source value, find the destination row that best represents the same concept.
  Use semantic matching — not just string equality.
  Examples: "UNDER_REVIEW" matches "Under Review", "A" matches "Active", "M" matches "Male".

  For each match return:
  - "source_value": the original source value (copy exactly from input)
  - "id": the value of the primary key / unique identifier column of the matched row
    (prefer short numeric or code columns; avoid flag columns like Y/N)
  - "dest_value": the value of the most human-readable label column of the matched row
    (prefer "name", "status_name", "display_name", "description"; avoid Y/N flags or
    pure numeric columns)
  - "confidence_score": float 0.0–1.0

  If a source value has no confident match (confidence < 0.5), add it to
  "unmatched_source_values" instead.

  EXAMPLE:
  Input source_values: ["APPROVED", "PENDING"]
  Input destination_rows:
    [{"id": "3", "status_code": "APPROVED", "status_name": "Approved", "is_payable": "Y"},
     {"id": "1", "status_code": "PENDING",  "status_name": "Pending",  "is_payable": "N"}]
  Correct output:
    proposals: [
      {"source_value": "APPROVED", "id": "3", "dest_value": "Approved", "confidence_score": 0.99},
      {"source_value": "PENDING",  "id": "1", "dest_value": "Pending",  "confidence_score": 0.99}
    ]
    unmatched_source_values: []

  RULES:
  - Return strictly valid JSON only. No markdown fences. No extra keys.
  - "id" must be the exact string value of the primary key column of the matched row.
  - "dest_value" must be human-readable text — NOT a flag like "Y"/"N".
  - Every source value must appear in exactly one of: proposals or unmatched_source_values.

user: |
  $payload
```

---

### 2. `fibers.py` — `_LookupProposal` Pydantic (~line 93)

```python
class _LookupProposal(BaseModel):
    source_value: str
    id: str            # business key / PK value from the matched destination row
    dest_value: str    # human-readable label from the matched destination row
    confidence_score: float
```

Remove `dest_id` entirely. No UUIDs in the AI contract.

---

### 3. `fibers.py` — payload construction (~lines 846–863)

```python
# Step 1: Deduplicate destination rows by content
seen_sigs: set[str] = set()
deduped_dest_entries: list[LookupDestEntry] = []
for entry in dest_entries:
    sig = json.dumps(entry.row_data, sort_keys=True)
    if sig not in seen_sigs:
        seen_sigs.add(sig)
        deduped_dest_entries.append(entry)

# Step 2: Build payload with raw rows (no pre-processing)
payload = json.dumps({
    "source_values": [e.source_value for e in source_entries],
    "destination_rows": [e.row_data for e in deduped_dest_entries],
})
```

Remove the old import: `from .lookup_mapping import _extract_destination_id, _extract_destination_label`

---

### 4. `fibers.py` — lookup dict for dest_entry after AI call (~line 916)

```python
from .lookup_mapping import _extract_destination_id

# Keyed by the heuristic PK value of the row_data
dest_entry_by_row_pk: dict[str, LookupDestEntry] = {}
for entry in deduped_dest_entries:
    pk_val = _extract_destination_id(entry.row_data)
    if pk_val:
        dest_entry_by_row_pk[pk_val] = entry
```

In proposal loop:
```python
dest_entry = dest_entry_by_row_pk.get(proposal.id)
```

---

### 5. `fibers.py` — `dest_row` save in AI path (~lines 926–932)

```python
dest_row = None
if dest_entry:
    dest_row = {
        "id": proposal.id,           # business key e.g. "3"
        "label": proposal.dest_value, # human label e.g. "Approved"
    }
```

---

### 6. `fibers.py` — `patch_mapping` manual edit path (~lines 1105–1112)

```python
dest_entry = db.get(LookupDestEntry, body.dest_entry_id)
mapping.dest_entry_id = body.dest_entry_id
if dest_entry is not None:
    from .lookup_mapping import _extract_destination_id, _extract_destination_label
    row_data = dest_entry.row_data or {}
    mapping.dest_row = {
        "id": _extract_destination_id(row_data) or dest_entry.entry_id,
        "label": _extract_destination_label(row_data),
    }
else:
    mapping.dest_row = None
```

---

### 7. `fibers.py` — `_bridge_lookup_fiber_to_value_map` source_value_map

Find where `source_value_map` is built (currently `mapping.dest_entry_id` → UUID).
Change to:
```python
dest_id_for_map = (mapping.dest_row or {}).get("id") or mapping.dest_entry_id
source_value_map[mapping.source_value] = dest_id_for_map
```

This writes the business key `"3"` instead of UUID into `LookupValueMap.source_value_map`.

---

### 8. `web/lib/lookup-api.ts` — add `patchFiberLookupMapping`

Add a new function to call the fiber PATCH mapping endpoint:
```ts
export async function patchFiberLookupMapping(
  token: string,
  projectId: string,
  feedId: string,
  fiberId: string,
  mappingId: string,
  body: { dest_entry_id: string; status: "confirmed" | "pending" | "rejected" }
): Promise<void>
```
Calls `PATCH /projects/:projectId/feeds/:feedId/fibers/:fiberId/mappings/:mappingId`.

---

### 9. `web/app/projects/[id]/feeds/[feedId]/review/page.tsx`

#### A. Fix pair building (~line 459)

Current: `latestMap.destinationTable.find(row => String(row.id) === String(destId))`
where `destId` is a UUID from `sourceValueMap`.

After fix, `sourceValueMap` values are business keys and `destinationTable` rows have
`{id: business_key, label: human_label}`. Update pair building:

```ts
for (const [srcVal, destBusinessId] of Object.entries(latestMap.sourceValueMap)) {
    const destRow = latestMap.destinationTable.find(
        (row) => String(row.id) === String(destBusinessId)
    ) || { id: destBusinessId, label: String(destBusinessId) };
    pairs.push({
        sourceValue: srcVal,
        destinationRow: destRow,
        confidenceScore: 0.95,
        status: isConfirmed ? "confirmed" : "pending",
    });
}
```

#### B. Fix `handleEditLookup` (~line 208)

After saving to `patchLookupValueMap`, also iterate each updated pair and call
`patchFiberLookupMapping` for each mapping in the fiber:

```ts
// After patchLookupValueMap succeeds:
if (fiber) {
    const fiberMappings = await listFiberLookupMappings(token, projectId, feedId, fiber.fiberId);
    for (const pair of updatedPairs) {
        const mapping = fiberMappings.find(m => m.sourceValue === pair.sourceValue);
        if (mapping && pair.destinationId) {
            await patchFiberLookupMapping(token, projectId, feedId, fiber.fiberId,
                mapping.mappingId, { dest_entry_id: pair.destinationId, status: pair.status });
        }
    }
}
```

---

## Tests

```bash
cd engine && source ../.venv/bin/activate
pytest tests/test_lookup_fiber_api.py -v   # all 8 must pass
```

```bash
cd web && npm run test   # all 317 must pass
```

Update `FakeLookupAdapter` in `test_lookup_fiber_api.py`:
- Read `destination_rows` (raw rows) not `destination_options`
- Return proposals with `id` (from `row_data`) and `dest_value`
- Assertions on `dest_row` must expect `{id: business_key, label: human_label}`
- Assertions on `source_value_map` must expect business key values not UUIDs

---

## Verification

1. Submit a lookup fiber with `APPROVED/UNDER_REVIEW/PAID/PENDING/REJECTED` source values
   and the multi-column status CSV. Confirm:
   - Feed page fiber detail shows `APPROVED → Approved (3)`.
   - Review page shows `APPROVED → Approved (3)`.
   - DB `LookupMapping.dest_row` = `{"id": "3", "label": "Approved"}`.
   - DB `LookupValueMap.source_value_map` = `{"APPROVED": "3", ...}`.
2. Manually edit a mapping from the review page. Confirm:
   - Review page updates.
   - Feed page fiber also reflects the edit.
3. All 8 backend tests pass.
4. All 317 frontend tests pass.

---

## Pitfalls

- `_extract_destination_id` must match what the AI returns as `id`. Test with a table
  where the PK column is NOT named `id` (e.g. `status_id`) to verify alignment.
- Review page `handleEditLookup` needs the fiber's `fiberId` — ensure it's available
  in the `lookupGroups` data or look it up from `fibers` state.
- `listFiberLookupMappings` API call may not exist in `web/lib/` yet — add if missing.
- Forward-only: existing `LookupValueMap` rows with UUID `source_value_map` values are
  not retroactively fixed.

---

## Commit

```
fix(lookup-fiber): AI extracts business id/label from raw dest rows; review page editing synced (#001fc)
```
