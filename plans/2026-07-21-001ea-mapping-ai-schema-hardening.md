# Plan: 001ea — Harden Mapping AI Call (Nullable Contract + Strict Response Schema)

## Task and Domain links

- Task: `tasks/001ea-mapping-ai-schema-hardening.md`
- Domain: `docs/domain/ui.md` (no UI screen changes — backend/schema only,
  check whether any domain page documents the mapping AI response
  contract before deciding if I22 applies; likely not since this is an
  internal contract, not a UI/API-surface change visible to operators)

## Current State

- `propose_mapping` (`engine/src/migrations_engine/mapping/review.py:288-`)
  builds a system prompt (`review.py:361-375`) that already includes 1-to-N
  mapping guidance and `destination_data_type` capture — landed ahead of
  this task, presumably as part of 001dy's AI-prompt step.
- Response schema (`review.py:34-50`): `_ProposedBinding` (source_field,
  destination_field, binding_type with a silent `"direct"` default,
  reference_table_name, destination_data_type — no `nullable`),
  `_TableMapping`, `_FieldMappingProposal`. None declare `extra="forbid"`;
  no validators.
- `destination_data_type` already round-trips: stored in `field_bindings`
  (`review.py:505`), read in `_snapshot_to_response` (`review.py:247`),
  exposed on `MappingFieldBindingResponse` (`api/schemas.py:562-569`).
  `nullable` has none of this plumbing.
- `patch_mapping`'s binding reconstruction (`review.py:637-647`) is
  already keyed by `(source_field, destination_field)` pairs (the 001dy
  rework landed), but only copies `binding_type`/`reference_table_name`
  forward from `existing` — `destination_data_type` is silently dropped
  on every edit today, a live bug independent of this task but inherited
  by `nullable` if not fixed here.
- `validate_source_fields()` — a new utility function — is not called
  anywhere in the current codebase.
- `adapter.call(system, user, response_model)` (`ai/adapter.py:20`) takes
  a Pydantic model class and returns `AICallResult[T]` with `.parsed`;
  swapping the `response_model` argument is a drop-in change at the call
  site (`review.py`, inside `propose_mapping`'s try block).

## Objective

1. Replace the system prompt with the new, stricter version.
2. Add a new schema module (`Binding`/`TableProposal`/
   `AIFieldMappingProposal`/`validate_source_fields`), `extra="forbid"`,
   with a `nullable` bool-or-null validator and a `reference_table_name`
   required-iff-`*_fk` validator (type-corrected: `info: ValidationInfo`).
   Delete the old permissive classes from `review.py`, import the new ones.
3. Thread `nullable` end-to-end: stored dict → `MappingFieldBindingResponse`
   → `_snapshot_to_response` → `web/lib/mapping-api.ts`.
4. Fix `patch_mapping` to preserve `destination_data_type` **and**
   `nullable` from `existing` across edits.
5. Wire `validate_source_fields` into `propose_mapping`: unknown
   `source_field` → `AuthApiError` 422, before any `MappingSnapshot` is
   created.
6. Move the module's smoke-test scenarios into a real pytest file.
7. Rewrite the 3 fake-adapter test helpers in `test_mapping_review_api.py`
   that hardcode `_ProposedBinding`/`_TableMapping` construction — they'd
   otherwise raise `AttributeError` the moment those classes are deleted.
8. Remove `propose_mapping`'s now-dead `reference_table_name` synthesis
   fallback (`review.py:495-497`) — unreachable once the new validator
   rejects `*_fk` bindings missing it before parsing succeeds.

## Out of Scope

- Any UI display of `nullable` in `ReviewGrid.tsx` — data is available to
  a future task, not rendered by this one.
- 001dz's codegen NOT NULL gate — separate, DDL-reparsing-based, not this
  task's `nullable` field (which only exists for *mapped* bindings).
- Re-running 001dy's AI-prompt step separately — this task's prompt
  already contains that instruction; flag 001dy's corresponding bullet as
  satisfied once this lands, don't duplicate the edit.
- Any change to `_parse_all_ddl_tables` (still name-only; unrelated to
  this task's AI-side `nullable`, which comes from the model reading the
  DDL text directly, not from Python-side parsing).

## Blast Radius

- `engine/src/migrations_engine/mapping/review.py` (edited — prompt,
  schema import swap, `propose_mapping`, `patch_mapping`,
  `_snapshot_to_response`)
- `engine/src/migrations_engine/mapping/ai_schemas.py` (new — the
  hardened Pydantic module)
- `engine/src/migrations_engine/api/schemas.py` (edited —
  `MappingFieldBindingResponse.nullable`)
- `web/lib/mapping-api.ts` (edited — `nullable` field + mapping)
- `engine/tests/mapping/test_ai_schemas.py` (new — moved smoke-test
  scenarios as real assertions)
- `engine/tests/test_mapping_review_api.py` (edited — 3 fake-adapter
  helpers rewritten off the deleted classes)
- No DB migration — `field_bindings` is JSON, no schema change needed to
  add a new key inside it.
- No role-gating change.

## File Changes

**`engine/src/migrations_engine/mapping/ai_schemas.py` (new)**
- Exactly the module from this task's spec, with one fix:
  `_require_ref_for_fk(cls, v: str | None, info: ValidationInfo) -> str | None`
  (import `ValidationInfo` from `pydantic`), and with the
  `if __name__ == "__main__":` block removed (moved to the test file below).

**`engine/src/migrations_engine/mapping/review.py`**
- Delete `_ProposedBinding`, `_TableMapping`, `_FieldMappingProposal`
  (lines 34-50); `from .ai_schemas import AIFieldMappingProposal, Binding, validate_source_fields`.
- Replace the system prompt string (lines 361-375) with the new version
  verbatim.
- `adapter.call(system_prompt, user_prompt, AIFieldMappingProposal)` —
  swap the response-model argument.
- After `proposal = result.parsed` (~line 411) and before the
  `error_code`/`tables` checks (~line 452-456): call
  `unknown = validate_source_fields(proposal, source_columns)`. By this
  point the success `log_ai_call` (~line 400-409) has already written a
  row and `call_log` is bound to it — if `unknown`, mutate that row
  instead of writing a second one: `call_log.error_detail = f"Unknown source field(s): {', '.join(sorted(set(unknown)))}"; db.commit()`,
  then raise `AuthApiError("mapping_unknown_source_field", f"AI proposed mapping from unknown source field(s): {', '.join(sorted(set(unknown)))}.", 422)`.
- In the `field_bindings.append({...})` block (~line 499-506): add
  `"nullable": binding.nullable,`.
- Delete the now-dead fallback at ~line 495-497
  (`if not ref_table: clean_field = ...; ref_table = f"{clean_field}_ref"`)
  — `binding.reference_table_name` is guaranteed non-empty for any
  `*_fk` binding that survives `Binding`'s validator, so `ref_table` can
  no longer be falsy at this point. Use `ref_table = binding.reference_table_name`
  directly.
- In `patch_mapping`'s `new_bindings.append({...})` (~line 641-647): add
  `"destination_data_type": existing.get("destination_data_type"),` and
  `"nullable": existing.get("nullable"),`.
- In `_snapshot_to_response`'s `MappingFieldBindingResponse(...)`
  construction (~line 240-248): add `nullable=binding.get("nullable"),`.

**`engine/src/migrations_engine/api/schemas.py`**
- `MappingFieldBindingResponse`: add `nullable: bool | None = None`
  (~after line 569).

**`web/lib/mapping-api.ts`**
- Add `nullable: boolean | null` to the field-binding interface and its
  request/response mapping (mirror however `destinationDataType` is
  already handled there).

**`engine/tests/mapping/test_ai_schemas.py` (new)**
- The good-path parse, the camelCase-key rejection, the string-`nullable`
  rejection, and the unknown-`source_field` detection — as real
  `pytest` assertions (`pytest.raises(ValidationError)` etc.), not a
  printed smoke test.

## Tests

- `test_ai_schemas.py` (above).
- `review.py` engine tests: `propose_mapping` persists `nullable` on
  newly created bindings; `patch_mapping` preserves
  `destination_data_type` and `nullable` across an edit that only changes
  `destination_field`; `propose_mapping` raises 422 when the (mocked) AI
  response contains a `source_field` not in the real source columns.
- `test_mapping_review_api.py`: rewrite `FakeAdapter` (line 30) and the
  two inline fake adapters (~480, ~544) to build `Binding`/`TableProposal`
  instances instead of `_ProposedBinding`/`_TableMapping`. Add one test
  asserting a `lookup_fk` binding missing `reference_table_name` now
  fails at the `Binding(**data)` construction step inside the fake
  adapter (i.e. the synthesis fallback really is gone, not just skipped).
- Existing `review.py`/`mapping` test suite: rerun in full after the
  rewrite above — confirm nothing else references the deleted classes.

## Verification

- `mypy --strict` clean on `ai_schemas.py` and `review.py` (specifically:
  no untyped `info` parameter).
- `ruff` clean.
- Manually trigger "AI Analyze" on a feed with a destination DDL that has
  a mix of `NOT NULL` and nullable destination columns; inspect the
  created `MappingSnapshot.field_bindings` (via DB or the API response)
  and confirm `nullable` is populated correctly per binding, matching the
  DDL.
- Manually edit a mapping via PATCH (e.g. via the "Add Destination"
  button from 001dy, once that lands) and confirm `destination_data_type`
  and `nullable` survive the edit instead of becoming `null`.
- Feed a deliberately malformed AI response (wrong-cased key, string
  `"nullable"`) through a unit test and confirm it raises instead of
  silently coercing/dropping.

## Pitfalls

- The stricter schema (`extra="forbid"` + validators) will reject AI
  responses that the old permissive schema would have silently accepted
  — expect a higher `ai_schema_mismatch` (422) rate immediately after
  this ships, at least until the model's behavior is confirmed to match
  the new prompt consistently. Not a reason to loosen validation, but
  worth watching in the first real usage after deploy.
- Don't forget `patch_mapping`'s `new_bindings` dict is a plain `dict`,
  not a Pydantic model — the two new keys must be added as plain dict
  entries, matching the existing style, not accidentally introduced only
  on the `Binding` model side.
- `validate_source_fields`'s fatal-422 behavior means a single
  hallucinated/corrupted `source_field` anywhere in a multi-table
  proposal blocks the *entire* proposal (all tables), not just the
  offending binding — confirm this matches intent before shipping; it's
  the stricter of two reasonable choices (the alternative being to drop
  just the bad binding and keep the rest).
- Coordinate with whoever implements 001dy: once this task's prompt
  change lands, 001dy's own "AI Prompt Engineering" step becomes a no-op
  if attempted again — check `review.py`'s system prompt before editing
  it a second time.

## Commit

Own commit. No hard ordering dependency on 001dy/001dz, but touches the
same system prompt and response-schema code 001dy's diffing/sign-off
rework touches — coordinate to avoid a merge conflict on `review.py`.
