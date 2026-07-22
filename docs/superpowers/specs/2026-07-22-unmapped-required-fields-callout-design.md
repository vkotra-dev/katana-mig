# Design: Surface Unmapped Required Destination Fields in Feed-Specific Codegen Instructions

## Context

`codegen/service.py` validates that every NOT-NULL destination column has a field binding before
generating code, using `MappingSnapshot.destination_columns` (added in migration `0036`). Two gaps
around this validation:

1. `destination_columns` is `None` for any `MappingSnapshot` created before migration `0036`. The
   current check (`if mapping_snapshot.destination_columns is not None: ...`) silently skips
   validation entirely for those rows instead of failing — bad code can be generated with no
   warning. (In the current dev DB this is 2 approved snapshots, both on one active feed; that
   feed will be discarded directly rather than backfilled, since this is a dev box.)
2. Even when the check correctly identifies a genuinely-unmapped required field and raises
   `unmapped_required_destination_fields`, there's no in-product path from "codegen is blocked" to
   "here's how to unblock it." The operator has no visible, actionable place to say what value
   should fill that field.

## Objective

1. Close the silent-skip gap: the required-field check must always run, not only when
   `destination_columns` happens to be populated.
2. Give the operator a feed-scoped, visible way to resolve an unmapped-required-field block: surface
   it directly in the feed's existing "Feed-specific transformation instructions" box
   (`Feed.transformation_instructions`), which is already rendered verbatim into the codegen AI's
   prompt (`user_prompt.txt.j2:13-15`). This is a different field from `mapping_hints` (which only
   feeds the earlier mapping-proposal AI call, not codegen) — `transformation_instructions` is the
   right one because it's what the script-generation AI actually reads.

## Design

### 1. Backend — `codegen/service.py`

Remove the `if mapping_snapshot.destination_columns is not None:` guard around the required-field
check. If `destination_columns` is `None` (pre-migration row, never re-proposed), raise the same
class of error as a genuinely-unmapped field — e.g. a dedicated `destination_metadata_missing` code
telling the operator to unapprove → re-analyze → re-approve that table so `destination_columns`
gets populated. If `destination_columns` is present, keep today's existing
`unmapped_required_destination_fields` check unchanged.

### 2. Backend — expose `destination_columns` in the API response

`MappingSnapshotResponse` (`api/schemas.py:578`) currently only serializes `destination_fields:
list[str]` (names only) — it does not carry the `nullable` flag needed to know which fields are
required. Add `destination_columns: list[dict] | None = None` (same shape as the model column:
`{"name", "destination_data_type", "nullable"}`) to `MappingSnapshotResponse`, and thread it through
`snapshot_to_response` (`mapping/review_repository.py`). Add the matching field to the frontend
`MappingSnapshotRecord` type (`web/lib/mapping-api.ts`). Without this, the frontend has no way to
know which destination fields are NOT NULL at all — it's a real, not cosmetic, prerequisite for
step 3.

### 3. Frontend — automatic, feed-scoped banner on the codegen page

On the codegen page (`web/app/projects/[id]/codegen/page.tsx`), for each feed with an approved
mapping snapshot, compute (client-side, from the now-loaded `snapshots[].destinationColumns`) the
set of NOT-NULL destination fields with no matching binding. If non-empty for that feed, show a
visible warning banner directly above that feed's "Feed-specific transformation instructions" box —
scoped to that feed only, never aggregated across feeds (mixing multiple feeds' issues in one place
was explicitly ruled out as confusing). The banner lists each unmapped field by table.column name.

### 4. Callout text feeds into `transformation_instructions`

Extend `generateTransformationInstructionsTemplate` with a new section (appended when unmapped
required fields exist for that feed):

```
### 4. Unmapped Required Destination Fields
- "policy_master.status" is NOT NULL with no source mapping. Specify a default value or
  expression for the generated SQL to use.
```

The operator edits this section in place to say what the actual default should be (e.g. replace
the placeholder line with `Use default 'ACTIVE' for policy_master.status`). Saving updates
`Feed.transformation_instructions` through the existing `saveTransformationInstructions` endpoint —
no new field, no new endpoint. Because this field is rendered directly into the codegen AI's
prompt, the script-generation call sees the operator's stated default every time it runs, without
depending on the mapping-analysis AI ever producing a matching binding.

### 5. No automatic re-trigger

Saving the instructions text does not automatically re-run anything. The operator re-runs codegen
manually when ready, same as today.

## Out of Scope

- No backfill migration for existing pre-`0036` `MappingSnapshot` rows — the 2 affected dev-box
  rows will be resolved by discarding their feed directly.
- No structured "default value" storage — the default lives as free text inside
  `transformation_instructions`, read by the codegen AI, not enforced deterministically by Python
  code. If the AI doesn't honor it, codegen still blocks with the same error as today; there is no
  second, code-level fallback.
- No changes to `mapping_hints` or the mapping-proposal AI flow.

## Testing

- Backend: `codegen/service.py` — new test for `destination_columns is None` raising
  `destination_metadata_missing` instead of silently proceeding; existing
  `unmapped_required_destination_fields` tests unchanged.
- Backend: `mapping/review_repository.py`/`snapshot_to_response` — new test asserting
  `destination_columns` round-trips into `MappingSnapshotResponse`.
- Frontend: `codegen/page.tsx` — new test asserting the banner appears only for a feed with actual
  unmapped required fields (not for other feeds in the same project), and that
  `generateTransformationInstructionsTemplate` includes the new section when applicable.
