---
type: Task
id: 001ey
slug: 001ey-explicit-json-schema-in-lookup-mapping-prompt
title: Make lookup mapping prompt output schema explicit
status: ready
domain: docs/domain/governance.md
plan: plans/2026-07-23-001ey-explicit-json-schema-in-lookup-mapping-prompt.md
---

## Context
The `lookup_mapping.yaml` AI prompt tells the LLM to "Return valid JSON matching the schema", but unlike `mapping.yaml`, it does not explicitly define what that JSON schema is in the prompt itself. This causes different LLMs (or local LLMs) to hallucinate the output format, leading to `ValidationError` when `Pydantic` tries to parse it into `_LookupMappingResult`.

## Objective
Update the `lookup_mapping.yaml` prompt to explicitly include an `OUTPUT CONTRACT` block that clearly defines the expected keys and types for the output JSON.

## Out of Scope
- Modifying the Python backend Pydantic models (the models are fine, the prompt just needs to match them).
- Modifying other prompt files.

## Acceptance
- `lookup_mapping.yaml` contains an `OUTPUT CONTRACT` section.
- The contract explicitly lists `proposals` and `unmatched_source_values`.
- The contract explicitly lists the keys for a proposal: `source_value`, `dest_entry_id`, and `confidence_score`.
