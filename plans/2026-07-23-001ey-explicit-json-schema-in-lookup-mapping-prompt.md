---
type: Plan
task: 001ey-explicit-json-schema-in-lookup-mapping-prompt
date: 2026-07-23
---

# Plan: 001ey — Make lookup mapping output schema explicit

**Task:** [001ey-explicit-json-schema-in-lookup-mapping-prompt](../tasks/001ey-explicit-json-schema-in-lookup-mapping-prompt.md)  
**Domain:** [governance.md](../docs/domain/governance.md)

---

## Current State

- `lookup_mapping.yaml` relies on the LLM magically knowing the `_LookupMappingResult` Pydantic schema.
- This causes failures when switching to local LLMs that need explicit instructions.

---

## File Changes

### Step 1 — Update Prompt

**Path:** `engine/src/migrations_engine/ai/prompts/lookup_mapping.yaml`
- Modify the `system` block to append an `OUTPUT CONTRACT` at the end (similar to `mapping.yaml`).
- The contract must explicitly state:
  ```yaml
    OUTPUT CONTRACT:
    Return strictly valid JSON with no markdown fences, no invented keys, and exact adherence to this schema:
    - Top-level keys: "proposals" (list), "unmatched_source_values" (list of strings)
    - Proposal keys: "source_value" (string), "dest_entry_id" (string), "confidence_score" (float)
  ```

---

## Blast Radius

| Layer | Impact |
|-------|--------|
| `lookup_mapping.yaml` | Safer parsing, better cross-LLM compatibility |

---

## Tests

1. No new tests are strictly required, but verify that the prompt change does not break existing `pytest` tests that run mocked AI calls (if any).
