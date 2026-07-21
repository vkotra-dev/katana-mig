---
type: Task Plan
title: Harden Mapping AI Call — Nullable Contract + Strict Response Schema
status: ready
---

# Task: 001ea-mapping-ai-schema-hardening

## Context
`propose_mapping` (`engine/src/migrations_engine/mapping/review.py`) calls
the AI with a system prompt that already covers 1-to-N mapping and
`destination_data_type`, but is missing destination-column `nullable`
capture, and its response schema (`_ProposedBinding`/`_TableMapping`/
`_FieldMappingProposal`, `review.py:34-50`) is permissive: no `extra="forbid"`,
`binding_type` has a silent default, no validation that `nullable` arrives
as a real JSON boolean, and no check that `reference_table_name` is
present/absent consistent with `binding_type`.

This task replaces the system prompt with a stricter, fully-specified
version and swaps the response schema for a hardened one with real
validation, so a corrupted/aliased/wrongly-typed field from any given LLM
model raises `model_validate_json` instead of flowing downstream.

## Requirements

1. **System prompt**: replace `propose_mapping`'s system prompt
   (`review.py:361-375`) with the new version — adds destination-column
   `nullable` (item 7), and a strict, explicit output-contract section
   (exact top-level/table/binding key lists, no markdown/fences,
   `nullable` must be a JSON boolean, no invented keys).
2. **Response schema**: add a new module with `Binding`, `TableProposal`,
   `AIFieldMappingProposal` (all `extra="forbid"`), `nullable: bool | None`
   with a validator rejecting non-bool values, a validator enforcing
   `reference_table_name` is present iff `binding_type` is `*_fk`, and
   `validate_source_fields()`. Replace `_ProposedBinding`/`_TableMapping`/
   `_FieldMappingProposal` in `review.py` with imports from this module.
3. **`nullable` end-to-end**: stored `field_bindings` dict, `MappingFieldBindingResponse`,
   `_snapshot_to_response`, and `web/lib/mapping-api.ts` — full round-trip,
   matching how `destination_data_type` already works. No UI display
   required by this task.
4. **Fix `patch_mapping` dropping binding metadata on edit**: its
   reconstruction (`review.py:641-647`, keyed by `(source_field,
   destination_field)` pairs since the 001dy rework landed) only carries
   forward `binding_type`/`reference_table_name` from the existing
   binding — it silently drops `destination_data_type` today, and would
   drop `nullable` too without a fix. Carry both forward from `existing`.
5. **Wire `validate_source_fields` into `propose_mapping`**: call it after
   parsing the AI response; if it returns any unknown `source_field`
   values, raise `AuthApiError` (422) before creating any `MappingSnapshot`
   — a corrupted/hallucinated source field name is treated as fatal, not
   silently dropped. By this point the AI call's `ai_call_log` row has
   already been written as a success — don't call `log_ai_call` again
   (that creates a duplicate row for one call); mutate the existing row's
   `error_detail` and commit before raising.
6. **Fix the new validator's type hint**: `_require_ref_for_fk`'s `info`
   parameter needs `info: ValidationInfo` (from `pydantic`) to satisfy
   this repo's `mypy --strict` requirement.
7. **No inline smoke test**: move the `if __name__ == "__main__":` block's
   scenarios into a real pytest file under `engine/tests/`, not shipped in
   the module itself.
8. **Fix the fake-adapter test helpers**: `engine/tests/test_mapping_review_api.py`
   has 3 fake-adapter helpers (`FakeAdapter` at line 30, plus inline fakes
   at ~480 and ~544) that construct AI responses via
   `mapping_review_module._ProposedBinding(...)` /
   `mapping_review_module._TableMapping(...)` — hardcoded references to
   the classes being deleted in requirement 2. All 3 must be rewritten to
   construct `Binding`/`TableProposal` from `ai_schemas` instead, or every
   test using them raises `AttributeError` at collection time.
9. **Remove the now-dead `reference_table_name` fallback**: `propose_mapping`
   (`review.py:495-497`) synthesizes a `reference_table_name`
   (`f"{clean_field}_ref"`) when the AI omits it on a `lookup_fk` binding.
   The new `_require_ref_for_fk` validator rejects any `*_fk` binding
   missing `reference_table_name` before `propose_mapping` ever sees it,
   so this branch becomes unreachable (and is untested today — no
   existing fixture omits it). Remove the dead fallback rather than leave
   unreachable code behind.

## Relationship to other tasks
- This task's system prompt already contains 001dy's "AI Prompt
  Engineering" instruction (1-to-N mapping, item 2) — once this lands,
  001dy's corresponding step is satisfied and shouldn't be duplicated.
- Independent of 001dz's codegen NOT NULL gate — that gate needs
  nullability for *unmapped* destination fields (no binding exists), which
  this task's per-binding `nullable` can't provide; 001dz's DDL-reparsing
  approach in `codegen/service.py` stays as planned.
