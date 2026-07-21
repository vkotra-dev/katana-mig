# Summary: 001ea — Mapping AI Call Schema Hardening

## What was built
`propose_mapping`'s AI call now has an explicit, rule-driven system prompt and a strict response
schema, closing the gap between what the prompt asks for and what's actually enforced.

### Key changes
- **`ai_schemas.py`** (new module): `Binding`/`TableProposal`/`AIFieldMappingProposal` with
  `extra="forbid"`, a `nullable` bool-strict validator, and a `model_validator(mode="after")`
  enforcing `reference_table_name` is present iff `binding_type` is `detail_fk`/`lookup_fk`.
  Replaced the old permissive `_ProposedBinding`/`_TableMapping`/`_FieldMappingProposal`.
- **New system prompt**: adds destination-column `nullable` capture and a strict output-contract
  section (exact key lists, no markdown fences, no invented keys).
- **`nullable` end-to-end**: stored `field_bindings` dict → `MappingFieldBindingResponse` →
  `_snapshot_to_response` → `web/lib/mapping-api.ts`.
- **`patch_mapping` fix**: was silently dropping `destination_data_type` on every operator edit
  (pre-existing bug); now carries both `destination_data_type` and `nullable` forward from the
  existing binding.
- **`validate_source_fields`**: wired into `propose_mapping`, case-sensitive (matches the
  prompt's "copied verbatim" instruction exactly); an unknown `source_field` mutates the
  already-written `ai_call_log` row's `error_detail` and raises 422, rather than creating a
  duplicate log row.
- **Dead code removed**: the `reference_table_name` synthesis fallback in `propose_mapping`
  (`if not ref_table: ... f"{clean_field}_ref"`) is unreachable once the new validator requires
  it upfront — removed rather than left as dead code.

## Verification
Test suite rewritten off the deleted schema classes (3 fake-adapter helpers in
`test_mapping_review_api.py`). A review pass caught and fixed: a duplicate `source_field` that
had crept into a test fixture while dodging the new validation, a lost test for the
`lookup_fk`→`detail_fk` server-side reclassification path, an `Any` type annotation typo, and
unused imports — all confirmed fixed in follow-up commits.
