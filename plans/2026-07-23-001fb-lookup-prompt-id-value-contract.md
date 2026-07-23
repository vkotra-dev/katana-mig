---
task: 001fb-lookup-prompt-id-value-contract
domain: docs/domain/ui.md, docs/domain/governance.md
created: 2026-07-23
---

# Plan — 001fb: Fix Lookup Fiber AI Prompt Contract

## Task Link
[tasks/001fb-lookup-prompt-id-value-contract.md](../tasks/001fb-lookup-prompt-id-value-contract.md)

---

## Current State

### `lookup_mapping.yaml` (prompt)
- System prompt tells AI to propose the best match for each source value.
- Output contract: `source_value`, `dest_id`, `confidence_score` only.
- No instruction to extract business key or human label from the destination row.

### `fibers.py` payload construction
```python
payload = {
    "source_values": [...],
    "destination_options": [
        {"id": entry.entry_id,   # <-- UUID, not business key
         "value": _extract_destination_label(entry.row_data)}  # <-- heuristic, often wrong
        for entry in dest_entries   # <-- includes duplicates
    ]
}
```
- `_extract_destination_label` only checks exact column names (`name`, `label`, etc.) — fails for
  `status_name`, `display_name`, `type_description` etc.
- Fallback concatenates every string value: `"Y | N | APPROVED | Approved | 3"`.
- No deduplication — repeated CSV rows all sent to AI.

### `_LookupProposal` Pydantic
```python
class _LookupProposal(BaseModel):
    source_value: str
    dest_id: str          # UUID
    confidence_score: float
```

### `dest_row` saved to DB
```python
dest_row = {
    "id": dest_entry.entry_id,          # UUID
    "label": _extract_destination_label(dest_entry.row_data)  # often garbled
}
```

---

## Objective

End state after this task:

```
AI receives:
  source_values: ["APPROVED", "UNDER_REVIEW", ...]
  destination_rows: [
    {"_ref": "uuid-abc", "id": "3", "status_code": "APPROVED", "status_name": "Approved", ...},
    {"_ref": "uuid-def", "id": "2", "status_code": "UNDER_REVIEW", "status_name": "Under Review", ...},
    ...  (deduplicated)
  ]

AI returns per proposal:
  source_value: "APPROVED"
  id: "3"               <-- business key from the matching row
  dest_value: "Approved" <-- human label from the matching row
  dest_id: "uuid-abc"   <-- _ref echoed back for DB lookup

Stored dest_row:
  {"id": "3", "label": "Approved"}

UI display:
  Column 1: APPROVED
  Column 2: Approved (3)

Codegen:
  Uses dest_row["id"] = "3" as the FK value into the proc.
```

---

## Out of Scope

- No DB model changes (no migration)
- No UI changes (`LookupMappingTable` already renders `label (id)`)
- No codegen changes (already reads `dest_row["id"]`)
- Manual `patch_mapping` path — keep as-is for now

---

## Blast Radius

| File | Nature of change |
|---|---|
| `engine/src/migrations_engine/ai/prompts/lookup_mapping.yaml` | Full rewrite of system prompt and output contract |
| `engine/src/migrations_engine/management/fibers.py` | Payload, Pydantic model, dest_row save |
| `engine/tests/test_lookup_fiber_api.py` | FakeLookupAdapter + assertions |

No migration. No schema change. No frontend change.

---

## File Changes — Detailed

### 1. `lookup_mapping.yaml`

**System prompt changes:**
- Explain that each destination row has a `_ref` system tracking field.
- Instruct AI to: identify the business key column (look for `id`, `code`, `key`, short numeric);
  identify the human label column (look for `name`, `label`, `description`, `display`); echo `_ref`
  exactly as `dest_id`.
- Update output contract to require: `source_value`, `id`, `dest_value`, `dest_id`,
  `confidence_score`.

### 2. `fibers.py` — payload construction (lines ~846–863)

**Step A — Deduplicate:**
```python
seen: set[str] = set()
deduped = []
for entry in dest_entries:
    sig = json.dumps(entry.row_data, sort_keys=True)
    if sig not in seen:
        seen.add(sig)
        deduped.append(entry)
```

**Step B — Build payload with raw rows + `_ref`:**
```python
payload = json.dumps({
    "source_values": [e.source_value for e in source_entries],
    "destination_rows": [
        {"_ref": e.entry_id, **e.row_data}
        for e in deduped
    ],
})
```

**Remove** the old `from .lookup_mapping import _extract_destination_id, _extract_destination_label`
import from this function (no longer needed in the AI path).

### 3. `fibers.py` — `_LookupProposal` Pydantic (lines 93–96)

```python
class _LookupProposal(BaseModel):
    source_value: str
    dest_id: str       # echoed _ref UUID — used for DB lookup via dest_entry_by_id
    id: str            # business key extracted by AI (e.g. "3")
    dest_value: str    # human label extracted by AI (e.g. "Approved")
    confidence_score: float
```

### 4. `fibers.py` — `dest_row` saving (lines ~926–932)

```python
dest_row = None
if dest_entry:
    dest_row = {
        "id": proposal.id,          # business key, e.g. "3"
        "label": proposal.dest_value,  # human label, e.g. "Approved"
    }
```

No heuristic. AI did the extraction.

### 5. `test_lookup_fiber_api.py` — `FakeLookupAdapter`

Update the mock to:
- Read `destination_rows` (not `destination_options`) from payload.
- Match source values to rows.
- Return proposals with `id`, `dest_value`, `dest_id` fields populated.
- Update any assertions that check `dest_row` shape.

---

## Tests

Run after implementation:
```bash
cd engine && source ../.venv/bin/activate
pytest tests/test_lookup_fiber_api.py -v
```

All 8 tests must pass.

---

## Verification

1. All 8 `test_lookup_fiber_api.py` tests pass.
2. Frontend tests (`cd web && npm run test`) pass (no UI change but confirm no regression).
3. Manually verify: submit a lookup fiber with the `APPROVED/UNDER_REVIEW/PAID/PENDING/REJECTED`
   source values and the multi-column status table CSV. Confirm:
   - Mappings show `Approved (3)`, `Under Review (2)` etc. in the UI.
   - `dest_row` in DB is `{"id": "3", "label": "Approved"}` (not a UUID).

---

## Pitfalls

- `dest_entry_by_id` is keyed by UUID (`entry_id`). The AI echoes `_ref` as `dest_id`. These match
  — do not change the dict key.
- The field name `id` on `_LookupProposal` is a business key string, not a DB primary key. Pydantic
  allows it but be careful in code that it doesn't shadow the model's own `id` attribute.
- If destination CSV has no clearly identifiable business key column, AI may guess incorrectly.
  This is acceptable for now — the operator can manually patch via the UI.
- `_extract_destination_label` is still used by the `patch_mapping` manual path. Do NOT remove
  the function — only remove the import from the AI payload section.

---

## Commit

```
fix(lookup-fiber): have AI extract business id and label from raw dest rows (#001fb)
```

Single commit. Squash if needed. No migration attached.
