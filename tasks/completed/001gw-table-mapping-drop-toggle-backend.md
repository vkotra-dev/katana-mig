---
id: 001gw
title: Table Mapping "Drop Source Field" as a Soft-Delete Toggle (Backend)
status: active
created: 2026-07-25
priority: high
domain: backend / mapping / codegen
depends-on: []
---

# Task 001gw — Table Mapping "Drop Source Field" as a Soft-Delete Toggle (Backend)

- **Plan**: [2026-07-25-001gw-table-mapping-drop-toggle-backend.md](../plans/2026-07-25-001gw-table-mapping-drop-toggle-backend.md)
- **Domain**: [source-model.md](../docs/domain/source-model.md)

## Context

**Scope note**: this is about the *table/field mapping* grid in `ReviewGrid.tsx` (source column → destination column bindings), **not** `LookupMappingTable.tsx` (lookup value mappings, already covered by tasks 001gq-001gu). Do not touch `LookupMappingTable.tsx` or any lookup-value-map backend code in this task.

Today, dropping a source field from the mapping is a hard delete: `handleRemoveSourceField` (`web/app/projects/[id]/feeds/[feedId]/review/page.tsx:360-386`) filters the field's bindings out of the array client-side and PATCHes the reduced list. The backend, `patch_mapping` (`engine/src/migrations_engine/mapping/review.py:59-152`), fully overwrites `snapshot.field_bindings` with whatever the request contains (`snapshot.field_bindings = new_bindings`, line 137) — anything omitted is permanently gone from the JSON, and its `MappingBindingSignOff` rows are deleted (lines 110-135, via `changed_pairs` detection).

This task converts "drop" into a soft-delete toggle: add a `dropped: bool` flag to each field-binding entry (kept in the array, never removed), and update every place that reads `field_bindings` to skip `dropped=true` entries. Sign-offs must be preserved across a toggle-off-then-back-on, since `changed_pairs` already keys on `(source_field, destination_field)` — a `dropped` flip alone doesn't change that tuple, so this is automatic *if* implemented correctly (see Requirement 2).

**Companion frontend task**: 001gx (depends on this task — needs the `dropped` field in the API before it can build the toggle UI).

### Naming collision to be careful about

`mapping/proposal.py:268` already has a comment "Keep signed-off bindings that the AI dropped" — this refers to a *different* concept: a pair the AI's fresh re-proposal simply no longer suggests. That is **not** the same as this task's `dropped` flag (a user-initiated, explicit soft-delete). Do not conflate the two in code or comments — when discussing this task's flag, always say "the `dropped` flag" or "soft-deleted," never just "dropped" in a context where it could mean the AI-omission concept.

## Requirements

### 1. Data model — `dropped: bool = False` everywhere a field-binding dict is constructed

- `engine/src/migrations_engine/api/schemas.py:533-541` (`MappingFieldBindingResponse` — this single model is reused for both the PATCH request body and every response, per `MappingPatchRequest.field_bindings: list[MappingFieldBindingResponse]` at line 572): add `dropped: bool = False`.
- `engine/src/migrations_engine/mapping/snapshots.py:15-19` (`FieldBinding` dataclass) and its serialization at lines 45-52 (`create_approved_mapping_snapshot`): add `dropped: bool = False` to the dataclass (with a default so existing call sites, mostly test fixtures, don't break) and include it in `serialized_bindings`.
- `engine/src/migrations_engine/mapping/review_repository.py:137-149` (`snapshot_to_response`'s `MappingFieldBindingResponse(...)` construction): add `dropped=bool(binding.get("dropped", False))`.
- `engine/src/migrations_engine/mapping/proposal.py:240-248` (`fresh_bindings.append({...})`, the AI re-propose path): does **not** need `dropped` added here — see Requirement 3, this is handled by the merge step instead, not by seeding it into fresh proposals.

Existing rows in the DB have no `dropped` key in their binding dicts — `.get("dropped", False)`/Pydantic's default both read that as `False`, so no data migration or backfill is needed.

### 2. `patch_mapping` (`engine/src/migrations_engine/mapping/review.py:59-152`) — carry `dropped` through

The `new_bindings.append({...})` block (lines 100-108) must include `"dropped": binding.dropped`. Since `existing_by_pair`/`changed_pairs` (lines 96, 117-125) already key purely on `(source_field, destination_field)`, a `dropped` flip on an existing pair does **not** register as a changed pair — so `MappingBindingSignOff` rows are untouched, and sign-off state is preserved automatically. Verify this is actually true with a test (see Requirement 5) rather than assuming — the `changed_pairs` logic is subtle enough (line 117-125, two separate loops) that it's worth confirming directly.

**Frontend contract this depends on**: the frontend must send the *full* current bindings list (all fields, with the toggled field's `dropped` flag flipped), not a filtered-down list — this task assumes that contract; task 001gx implements the frontend side of it.

### 3. `mapping/proposal.py` re-propose/merge path (lines 250-282) — preserve `dropped` across re-proposals

Today, the merge logic only carries forward the *old* binding's full field set when `is_signed_off and pair in old_bindings_map` (lines 262-264); otherwise it uses `fresh_b` as-is (line 266), which has no `dropped` key (defaults to `False`). This means: if a user soft-deletes an *unsigned* field, then AI re-propose runs, the `dropped` flag would silently reset to `False` — the field would un-drop itself without the user asking. Fix: carry forward `dropped` from `old_bindings_map[pair]` onto `fresh_b` whenever the pair survives into the fresh proposal, **independent of sign-off status** (this is intentionally a broader condition than the existing `is_signed_off` gate — `dropped` and "signed off" are orthogonal pieces of state).

### 4. Codegen blast radius — 4 sites, all must skip `dropped=true` bindings

Verified by tracing every read of `mapping_snapshot.field_bindings` in the codegen path:

1. `engine/src/migrations_engine/codegen/service.py:89-93` — `mapped_dest_fields` set comprehension (required-NOT-NULL-destination-field validation, lines 85-101). A source field that was the *only* mapping for a required destination column, now soft-deleted, must correctly re-trigger the existing `unmapped_required_destination_fields` 422 — this is the existing safeguard, it just needs to see through the `dropped` flag correctly.
2. `engine/src/migrations_engine/codegen/service.py:439-444` (`_select_lookup_snapshot_version`).
3. `engine/src/migrations_engine/codegen/service.py:470-475` (`_build_lookup_tables`).
4. `engine/src/migrations_engine/codegen/templates/user_prompt.txt.j2:10` — **the most consequential site**: this Jinja template is what the SQL-generation AI actually reads to know which fields to migrate (`{% for binding in mapping_snapshot.field_bindings %}`, line 10, rendering `- {{ binding.get('source_field') }} -> {{ binding.get('destination_field') }}...` for each). Miss this one and a "soft-deleted" field still gets generated into the migration SQL — the toggle would be cosmetic only.

For all 4, the fix is a `dropped` filter: Python sites use `if not binding.get("dropped")` added to the existing comprehension/loop condition; the Jinja site uses `{% for binding in mapping_snapshot.field_bindings if not binding.get('dropped') %}`.

### 5. Tests

Add to whichever existing test file covers `patch_mapping`/mapping snapshot PATCH (locate it first — do not guess a filename; search `engine/tests/` for the mapping PATCH endpoint's existing tests and follow that file's fixture/auth patterns exactly):

1. **Toggle preserves sign-off**: sign off a binding, PATCH with `dropped=true` for that binding (full bindings list, only the flag changed), confirm the sign-off record still exists (query `MappingBindingSignOff` directly, or use whatever the existing test file's pattern is for checking sign-off state) and the response still reports it signed. Then PATCH again with `dropped=false`, confirm still signed, unchanged.
2. **Dropped field excluded from all 4 codegen sites**: soft-delete a field, then either call `generate_codegen_artifact` directly (mocking the AI adapter — follow whatever mocking pattern the existing codegen tests use) or, at minimum, directly render `user_prompt.txt.j2` with a `dropped=true` binding present and assert its `source_field`/`destination_field` text does not appear in the rendered output while a sibling non-dropped binding's does.
3. **Dropping the only source for a required field blocks codegen**: soft-delete the field mapped to a NOT-NULL destination column, confirm codegen generation raises `unmapped_required_destination_fields` (422), matching the existing behavior for a field that was never mapped at all.
4. **Re-propose preserves `dropped` for an unsigned field**: soft-delete an unsigned field, trigger a re-propose (whatever function/endpoint drives `mapping/proposal.py`'s merge path), confirm the field's `dropped` flag survives into the new/updated draft snapshot.

## Files to Change

1. `engine/src/migrations_engine/api/schemas.py` — `MappingFieldBindingResponse.dropped`.
2. `engine/src/migrations_engine/mapping/snapshots.py` — `FieldBinding.dropped`, serialization.
3. `engine/src/migrations_engine/mapping/review_repository.py` — response mapping.
4. `engine/src/migrations_engine/mapping/review.py` — `patch_mapping`'s `new_bindings` construction.
5. `engine/src/migrations_engine/mapping/proposal.py` — merge logic, carry `dropped` forward independent of sign-off.
6. `engine/src/migrations_engine/codegen/service.py` — 3 Python filter sites.
7. `engine/src/migrations_engine/codegen/templates/user_prompt.txt.j2` — 1 Jinja filter site.
8. Whichever test file covers `patch_mapping` — 4 new tests per Requirement 5.

## Environment

Same as tasks 001gr/001gs/001gu: use `.venv/bin/python` for everything, never bare `python`/`pytest` — see 001gr's task file for why (stale global editable install of an unrelated sibling package shadows the real one).

## Verification

```bash
.venv/bin/python -m pytest engine/tests -q
```

Confirm zero failures, and the count grew by exactly the number of new tests added in Requirement 5 (4, unless the chosen test file's existing patterns require more setup helpers that end up as additional test functions — use judgment, but don't silently add fewer than the 4 scenarios listed).
