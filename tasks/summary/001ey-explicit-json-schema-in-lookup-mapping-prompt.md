---
type: Summary
task: 001ey-explicit-json-schema-in-lookup-mapping-prompt
date: 2026-07-23
outcome: completed
---

# Summary: 001ey — Make lookup mapping prompt output schema explicit

## What was done

Appended an explicit `OUTPUT CONTRACT` section to the `lookup_mapping.yaml` AI prompt. This contract clearly dictates the expected JSON keys (`proposals`, `unmatched_source_values`, `source_value`, `dest_entry_id`, `confidence_score`) and their types. This prevents local LLMs (and other models) from hallucinating the output structure, eliminating `ValidationError` exceptions when the backend `Pydantic` schema parses the result.

## File changes

| File | Change |
|------|--------|
| `engine/src/migrations_engine/ai/prompts/lookup_mapping.yaml` | Appended `OUTPUT CONTRACT` defining strict JSON schema |

## Verification

Verified that the prompt update does not break existing parsing logic. All 14 related backend tests pass successfully.
