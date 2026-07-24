---
id: 001gq
title: Fix camelCase Inner-Key Bug in add_source_value/remove_source_value/move_source_value PATCH Actions
status: active
created: 2026-07-24
priority: high
domain: frontend / lookup-api
depends-on: [001go]
---

# Task 001gq — Fix camelCase Inner-Key Bug in `add_source_value`/`remove_source_value`/`move_source_value` PATCH Actions

## Context

Task [[001go]] fixed the *outer* key bug (`removeSourceValue` → `remove_source_value`). There is a second, deeper bug in the same function that survived that fix: the **inner** action-object keys are never converted from camelCase to snake_case, so the "Add source value" and "Remove source value" buttons on the Review Page silently no-op.

`web/lib/lookup-api.ts`'s `patchLookupValueMap` does:

```ts
if (input.addSourceValue) body.add_source_value = input.addSourceValue;       // {destId, sourceValue}
if (input.removeSourceValue) body.remove_source_value = input.removeSourceValue; // {destId, sourceValue}
if (input.moveSourceValue) body.move_source_value = input.moveSourceValue;       // {sourceValue, oldDestId, newDestId}
```

The outer key is snake_cased but the nested object is passed through as-is, so the wire body looks like `{"add_source_value": {"destId": "ACTIVE", "sourceValue": "B"}}`.

The backend (`engine/src/migrations_engine/management/lookup_mapping.py:102-104, 131-133, 179-181`) reads snake_case keys off these dicts, e.g. `body.add_source_value.get("dest_id", "")`. Since `LookupValueMapPatchRequest` (`engine/src/migrations_engine/api/schemas.py:496-501`) types these fields as plain `dict[str, str]` rather than nested Pydantic models, Pydantic never validates or rejects the mismatched keys — `.get("dest_id", "")` just returns `""`, the `if dest_id and src_val:` guard fails, and the whole block is skipped.

**Net effect**: the PATCH request returns `200 OK` with the lookup map unchanged. No exception is raised anywhere. The frontend (`review/page.tsx:208-232`) then shows a false success toast ("Added source value ... to ...") even though nothing was written to the DB, and the value reverts after the next `loadData()`/reload.

**Why existing tests didn't catch it**: `web/lib/lookup-api.test.ts:144-238` has three tests (`patchLookupValueMap` describe block) that assert the *buggy* camelCase body shape as the expected output — they encode the bug as correct behavior. The backend test added in [[001gp]] (`test_patch_lookup_value_map_resets_approved_snapshots_to_draft`) sends correct snake_case keys directly, so it never exercises the frontend's serialization path. No test currently drives the real frontend→backend contract end-to-end for these three actions.

## Requirements

1. **Bug fix**: In `web/lib/lookup-api.ts`, convert the inner keys of `addSourceValue`, `removeSourceValue`, and `moveSourceValue` to the snake_case shape the backend expects:
   - `add_source_value: { dest_id, source_value }`
   - `remove_source_value: { dest_id, source_value }`
   - `move_source_value: { source_value, old_dest_id, new_dest_id }`
2. **Test fix**: Update the three tests in `web/lib/lookup-api.test.ts` (`patchLookupValueMap` describe block, ~line 144-238) that currently assert the camelCase (buggy) body shape — they must assert the corrected snake_case shape instead.
3. **New regression coverage**: Add a test that proves a same-name group already present in a `LookupValueMapRecord.destinationMappings` response round-trips correctly — i.e. call `patchLookupValueMap` with `addSourceValue` and assert the exact snake_case JSON body sent, not just that `fetch` was called.
4. No backend changes are required — `lookup_mapping.py` and `schemas.py` already expect (and correctly handle) snake_case keys; this is a frontend serialization bug only.

## Files to Change

1. `web/lib/lookup-api.ts` — fix `patchLookupValueMap`'s inner-key serialization for `add_source_value`, `remove_source_value`, `move_source_value`.
2. `web/lib/lookup-api.test.ts` — correct the three tests that assert the buggy shape.

## Verification

```bash
cd web && npm test -- --run lookup-api.test.ts
cd web && npm test -- --run
```

Manual check on the Review Page (with a draft lookup map, signed in as the role holding the ball): click "+ Add another source value" on a destination group, type a new alias, submit, then **reload the page** and confirm the value is still there (proves it actually persisted, not just optimistic local state). Repeat for the `×` remove button.
