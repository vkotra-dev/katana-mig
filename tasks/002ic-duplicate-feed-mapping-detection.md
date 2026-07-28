# 002ic: Duplicate feed mapping detection — per-table ownership report

## Problem (post-002ib)

After 002ib, proposing mapping on a duplicate feed raises 409 with the message
`"All proposed tables already have approved mappings. No changes to apply."`.
The message states _what_ happened but not _where_ — it omits which feed/source_definition_id
owns each approved mapping. The frontend silently catches the 409 and shows
"No mapping proposals generated yet", giving no actionable guidance.

The 409 status code is correct (it _is_ a conflict). The gap is only the missing
ownership detail so the UI can tell the user where the existing mappings live.

**Depends on:** 002ib (the dedup, rejected-status handling, and 409-per_table_status
improvements landed in the same session).

## Scope

### 1. Backend: attach ownership detail to the 409

**File:** `engine/src/migrations_engine/mapping/proposal.py`

In the existing `if not snapshots:` block (line 347), instead of raising the bare 409,
query the existing approved snapshots for the conflicting tables and attach
`per_table_ownership` to the 409 detail:

```python
{
  "per_table_ownership": {
    "policy_master": {
      "source_definition_id": "feed-uuid",
      "status": "approved",
      "destination_object_name": "policy_master",
      "mapping_snapshot_id": "snap-uuid"
    },
    "policy_claims": { ... }
  }
}
```

**Do NOT** change the 409 status to 200. 002ib deliberately kept it as 409.
**Do NOT** try to squeeze a multi-table list into `MappingReviewResponse` (it's
inherently one-table-shaped). The ownership data goes on the 409's `detail` dict,
same pattern as the existing `per_table_status` on the other 409 site (line 327).

### 2. Frontend: show ownership in the 409 error

**File:** `web/app/projects/[id]/feeds/[feedId]/page.tsx`

When `proposeMappingSnapshot` rejects with a 409 containing `per_table_ownership`:
- Render a card titled "Duplicate mappings found" listing each table
- Show the source feed name (resolved via `listFeedContracts`) and link to that feed's page
- The feed link pattern: `/projects/{projectId}/sources/{sourceDefId}`

### 3. Codegen page: mapping status badge

**File:** `web/lib/feeds-api.ts`

Add `mapping_status` field to `FeedContractRecord` interface (1 field) and
map it in `mapFeedContractResponse` (1 mapper line). The backend already
returns `mapping_status` on `FeedResponse` (schemas.py:273), including all the
dedup, rejected→partial, cross-feed batch correctness from 002ib.

**File:** `web/app/projects/[id]/codegen/page.tsx`

Add a "Mapping" column to the sources table, reading status from
`sources[].mappingStatus` — **do not** make separate API requests to
`getAllApprovedMappingSnapshots` (that reinvents 002ib's correctness at
N+1 scale with no dedup/partial support). Keep the "Generate SQL" button
enabled (partial generation is valid). The result message already says
"no tables had approved mapping."

### 4. Governance

- Update `docs/domain/api.md` — add `per_table_ownership` field to the 409 error detail for the propose endpoint
- Update `MappingReviewResponse` doc in api.md if any new fields are added

### 5. Tests

**File:** `engine/tests/test_duplicate_feed_detection.py` (new)
- Create project with 2 feeds (same schema)
- Approve mapping on feed 1
- Propose on feed 2 → verify 409 with `per_table_ownership` detail
- Verify each entry has `source_definition_id`, `status`, `mapping_snapshot_id`
- Verify codegen skips feeds with no approved mapping (existing behavior, regression guard)

## Domain Updates Required

- `docs/domain/api.md`: 409 on POST /mapping/propose now includes `per_table_ownership`
  in the error detail object (per-table ownership map keyed by `destination_object_name`)
