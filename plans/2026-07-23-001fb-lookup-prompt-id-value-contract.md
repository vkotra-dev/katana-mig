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

### AI prompt (`lookup_mapping.yaml`)
- Only asks AI to return `source_value`, `dest_id` (system UUID), `confidence_score`.
- No instruction to identify the business key column or human label column.
- No example provided — local LLMs need examples.

### Payload construction (`fibers.py` ~line 850)
```python
# CURRENT — broken
payload = {
    "source_values": [...],
    "destination_options": [
        {"id": entry.entry_id,   # UUID — not the business key
         "value": _extract_destination_label(entry.row_data)}  # heuristic, often garbled
        for entry in dest_entries   # no deduplication — duplicates sent to AI
    ]
}
```

### Pydantic model (`fibers.py` ~line 93)
```python
class _LookupProposal(BaseModel):
    source_value: str
    dest_id: str          # UUID
    confidence_score: float
    # missing: id (business key), dest_value (human label)
```

### `dest_row` saved to DB (`fibers.py` ~line 926)
```python
dest_row = {
    "id": dest_entry.entry_id,                         # UUID — wrong
    "label": _extract_destination_label(dest_entry.row_data)  # heuristic — often garbled
}
```

### `patch_mapping` — manual operator edit (`fibers.py` ~line 1105)
```python
mapping.dest_row = {
    "id": dest_entry.entry_id,                         # UUID — wrong
    "label": _extract_destination_label(dest_entry.row_data)  # heuristic — often garbled
}
```

### Display
- Feed page fiber detail → `LookupMappingTable` renders `dest_row.label (dest_row.id)` → shows garbled UUID and concatenated column dump.
- Review page → same `LookupMappingTable` via `ReviewGrid` → same garbled output.

---

## Objective

```
AI input:
  source_values: ["APPROVED", "UNDER_REVIEW", "PAID", "PENDING", "REJECTED"]
  destination_rows: [     ← deduplicated raw rows from the pasted CSV
    {"id": "3", "is_payable": "Y", "is_terminal": "N", "status_code": "APPROVED",  "status_name": "Approved",    "display_order": "3"},
    {"id": "2", "is_payable": "N", "is_terminal": "N", "status_code": "UNDER_REVIEW","status_name": "Under Review","display_order": "2"},
    ...
  ]

AI output:
  proposals:
    - { source_value: "APPROVED",     id: "3", dest_value: "Approved",     confidence_score: 0.99 }
    - { source_value: "UNDER_REVIEW", id: "2", dest_value: "Under Review", confidence_score: 0.99 }
    - { source_value: "PAID",         id: "5", dest_value: "Paid",         confidence_score: 0.99 }
    - { source_value: "PENDING",      id: "1", dest_value: "Pending",      confidence_score: 0.99 }
    - { source_value: "REJECTED",     id: "4", dest_value: "Rejected",     confidence_score: 0.99 }

dest_row saved to LookupMapping:
  { "id": "3", "label": "Approved" }    ← business key + clean label. No UUID. No heuristic.

UI display (feed page + review page):
  Column 1: APPROVED
  Column 2: Approved (3)

Codegen:
  reads dest_row["id"] = "3" → FK value into the proc
```

---

## Out of Scope

- No DB model change — `LookupMapping.dest_row` JSON column already exists
- No migration
- No UI component change — `LookupMappingTable` already renders `label (id)` format
- No codegen change — already reads `dest_row["id"]`

---

## Blast Radius

| File | Nature |
|---|---|
| `engine/src/migrations_engine/ai/prompts/lookup_mapping.yaml` | Full rewrite |
| `engine/src/migrations_engine/management/fibers.py` | Payload, Pydantic model, AI path dest_row, patch_mapping dest_row |
| `engine/tests/test_lookup_fiber_api.py` | FakeLookupAdapter + assertions |

---

## File Changes — Detailed

### 1. `lookup_mapping.yaml` — full rewrite

The system prompt must be explicit enough for a local LLM (Ollama). The OllamaAdapter appends
the Pydantic JSON schema automatically so the prompt must not duplicate it — but it must:
- Describe each input field clearly
- Name exactly what each output field must contain
- Include a concrete worked example (critical for local LLMs)

```yaml
system: |
  You are a lookup value mapper for a data migration project.

  You will receive:
  - "source_values": a list of distinct values extracted from the source system
  - "destination_rows": a list of rows from the destination reference/lookup table.
    Each row contains multiple columns. One column is the business primary key (usually
    named "id"). Another column contains the best human-readable label (usually named
    "name", "status_name", "display_name", "description", or similar).

  Your job:
  For each source value, find the destination row that best represents the same concept.
  Use semantic matching — not just string equality. Abbreviations, codes, and full names
  that mean the same thing should match (e.g. "UNDER_REVIEW" matches "Under Review",
  "A" matches "Active", "M" matches "Male").

  For each match, return:
  - "source_value": the original source value (copy exactly from input)
  - "id": the value from the "id" column of the matched destination row (the business key)
  - "dest_value": the value from the most human-readable column of the matched row
    (prefer "name", "status_name", "display_name", "description" — avoid flag columns like
    "is_payable", "is_terminal", or numeric-only columns)
  - "confidence_score": a float between 0.0 and 1.0 representing your confidence

  If a source value has no confident match (confidence < 0.5), add it to
  "unmatched_source_values" instead of proposals.

  EXAMPLE:
  Input source_values: ["APPROVED", "PENDING"]
  Input destination_rows:
    [{"id": "3", "status_code": "APPROVED", "status_name": "Approved"},
     {"id": "1", "status_code": "PENDING",  "status_name": "Pending"}]
  Correct output:
    proposals: [
      {"source_value": "APPROVED", "id": "3", "dest_value": "Approved", "confidence_score": 0.99},
      {"source_value": "PENDING",  "id": "1", "dest_value": "Pending",  "confidence_score": 0.99}
    ]
    unmatched_source_values: []

  RULES:
  - Return strictly valid JSON only. No markdown fences. No extra keys.
  - "id" must be the exact string value from the "id" column of the matched row.
  - "dest_value" must be a human-readable label, NOT a flag like "Y"/"N" or a numeric ID.
  - Every source value must appear in exactly one of: proposals or unmatched_source_values.

user: |
  $payload
```

### 2. `fibers.py` — payload construction (replace ~lines 850–863)

**Remove** the old `from .lookup_mapping import _extract_destination_id, _extract_destination_label`
import from this function.

**Add deduplication + raw row payload:**
```python
# Deduplicate destination rows by content before sending to AI
seen_sigs: set[str] = set()
deduped_dest_entries: list[LookupDestEntry] = []
for entry in dest_entries:
    sig = json.dumps(entry.row_data, sort_keys=True)
    if sig not in seen_sigs:
        seen_sigs.add(sig)
        deduped_dest_entries.append(entry)

payload = json.dumps({
    "source_values": [e.source_value for e in source_entries],
    "destination_rows": [e.row_data for e in deduped_dest_entries],
})
```

### 3. `fibers.py` — `_LookupProposal` Pydantic (replace ~lines 93–96)

```python
class _LookupProposal(BaseModel):
    source_value: str
    id: str             # business key from matched destination row (e.g. "3")
    dest_value: str     # human-readable label from matched destination row (e.g. "Approved")
    confidence_score: float
```

Note: `dest_id` (UUID) is removed entirely from the AI output contract. We no longer pass UUIDs
to the AI.

### 4. `fibers.py` — `dest_entry_by_id` lookup (replace ~line 916)

Since the AI now returns the business `id` (not a UUID), change the lookup dict:
```python
# Build lookup keyed by the row_data "id" field value
dest_entry_by_row_id: dict[str, LookupDestEntry] = {}
for entry in deduped_dest_entries:
    row_id = str(entry.row_data.get("id", "")).strip()
    if row_id:
        dest_entry_by_row_id[row_id] = entry
```

Then in the proposal loop:
```python
dest_entry = dest_entry_by_row_id.get(proposal.id)
```

### 5. `fibers.py` — `dest_row` save in AI path (replace ~lines 926–932)

```python
dest_row = None
if dest_entry:
    dest_row = {
        "id": proposal.id,          # business key e.g. "3"
        "label": proposal.dest_value,  # human label e.g. "Approved"
    }
```

No heuristic. AI did the extraction.

### 6. `fibers.py` — `patch_mapping` manual edit path (~lines 1105–1112)

Currently saves UUID as `id` and heuristic label. Fix to:
```python
dest_entry = db.get(LookupDestEntry, body.dest_entry_id)
mapping.dest_entry_id = body.dest_entry_id
if dest_entry is not None:
    from .lookup_mapping import _extract_destination_label
    row_data = dest_entry.row_data or {}
    mapping.dest_row = {
        "id": str(row_data.get("id", dest_entry.entry_id)),  # prefer business key; fallback UUID
        "label": _extract_destination_label(row_data),        # heuristic still acceptable for manual path
    }
else:
    mapping.dest_row = None
```

This means operator-patched mappings also display correctly with the same `label (id)` format.

### 7. `test_lookup_fiber_api.py` — `FakeLookupAdapter`

```python
def call(self, system, user, response_model):
    self.calls.append(...)
    payload = json.loads(user)
    destination_rows = payload["destination_rows"]
    proposals = []
    for src in payload["source_values"]:
        row = destination_rows[0] if src != "B" else destination_rows[1]
        proposals.append({
            "source_value": src,
            "id": str(row.get("id", "1")),
            "dest_value": str(row.get("label") or row.get("name") or list(row.values())[0]),
            "confidence_score": 0.95,
        })
    return response_model(proposals=proposals, unmatched_source_values=[])
```

Update any assertions that check `dest_row` to expect `{"id": "...", "label": "..."}` with
business key (not UUID) in the `id` field.

---

## Display Result

Both pages use `LookupMappingTable` via `ReviewGrid`. No UI changes needed.

| Page | Path | Result |
|---|---|---|
| Feed page — fiber detail | `LookupMappingTable` (editing enabled) | Source: `APPROVED` / Dest: `Approved (3)` |
| Review page | `ReviewGrid` → `LookupMappingTable` (read-only) | Source: `APPROVED` / Dest: `Approved (3)` |

---

## Tests

```bash
cd engine && source ../.venv/bin/activate
pytest tests/test_lookup_fiber_api.py -v   # all 8 must pass
```

```bash
cd web && npm run test   # confirm no regression (317 tests)
```

---

## Verification

1. All 8 backend tests pass.
2. All 317 frontend tests pass.
3. Manual smoke check: submit lookup fiber with `APPROVED/UNDER_REVIEW/PAID/PENDING/REJECTED`
   source values and the multi-column status CSV. Confirm:
   - Feed page shows `APPROVED → Approved (3)` in the mapping table.
   - Review page shows the same.
   - DB `dest_row` is `{"id": "3", "label": "Approved"}` (not a UUID).
   - Manually patching a mapping from the feed page also stores a clean `dest_row`.

---

## Pitfalls

- If the CSV has no `id` column (e.g. uses `status_id` or `code`), `dest_entry_by_row_id` will be
  empty and all `dest_entry` lookups will return `None`. The mapping will still be saved but
  `dest_entry_id` FK will be null. Acceptable limitation — follow-up task if needed.
- Local LLMs (Ollama) are strict about JSON schema — the Pydantic schema is appended by the adapter.
  Do not add markdown or extra explanation inside the `user:` section.
- Remove `dest_id` completely from `_LookupProposal`. Do not leave it as an optional field — it
  will confuse the model into thinking it needs to return a UUID.

---

## Commit

```
fix(lookup-fiber): AI extracts business id and label from raw dest rows (#001fb)
```
