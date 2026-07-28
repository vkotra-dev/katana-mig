# Plan: 002ic - Duplicate feed mapping detection — per-table ownership report

## Goal

When proposing mapping on a duplicate feed, show the user _which feed owns each approved mapping_
instead of silently showing "No mapping proposals generated yet."

**Current state (post-002ib):**
- `proposal.py` line 347 raises 409 with `"All proposed tables already have approved mappings. No changes to apply."`
- 409 has no `detail` payload — no ownership info
- Frontend silently catches 409 and falls through to `loadAllData`
- Feed page has no mapping snapshot card (because `loadAllData` doesn't fetch mappings)
- Codegen page doesn't show mapping status per source

## Approach

### 1. Backend: enrich the 409 with per-table ownership

**File:** `engine/src/migrations_engine/mapping/proposal.py` (line ~347)

Replace the bare 409 with one that includes ownership detail:

```python
ownership: dict[str, dict] = {}
for tbl_name in mapped_table_names:
    snap = db.scalar(
        select(MappingSnapshot).where(
            MappingSnapshot.project_id == project_id,
            MappingSnapshot.status == "approved",
            MappingSnapshot.destination_object_name == tbl_name,
        ).order_by(MappingSnapshot.created_at.desc())
    )
    if snap:
        ownership[tbl_name] = {
            "source_definition_id": snap.source_definition_id,
            "status": snap.status,
            "mapping_snapshot_id": snap.mapping_snapshot_id,
            "destination_object_name": snap.destination_object_name,
        }

raise AuthApiError(
    "mapping_already_proposed",
    "All proposed tables already have approved mappings.",
    409,
    {"per_table_ownership": ownership} if ownership else None,
)
```

Key decisions:
- **Keep 409 status** — 002ib deliberately chose this. The frontend handles 409 gracefully.
- **Use `detail` dict, not `MappingReviewResponse`** — that type is one-table-shaped.
- **N queries for N tables** — acceptable for small N (1-3 tables typical).

### 2. Frontend: show ownership card in the 409 error

**File:** `web/app/projects/[id]/feeds/[feedId]/page.tsx`

In `handleAnalyzeWithAi`, extend the catch block to check for `per_table_ownership`
in the 409 detail. Render a "Duplicate mappings found" card listing each table
with a link to the owning feed.

Resolve feed names from the existing `sources` state (populated by `listFeedContracts`).

### 3. Codegen page: mapping status badge (reuse 002ib backend work)

**File:** `web/lib/feeds-api.ts`

Two changes — both are required or the mapper won't compile:

1. Add `mapping_status` to the `mapFeedContractResponse` parameter type (line ~152):
   ```typescript
   mapping_status?: string | null;
   ```
2. Add `mappingStatus` to `FeedContractRecord` interface:
   ```typescript
   mappingStatus: "draft" | "partial" | "approved" | null;
   ```
3. Map it in `mapFeedContractResponse` return body (1 line):
   ```typescript
   mappingStatus: (response.mapping_status as "draft" | "partial" | "approved" | null) ?? null,
   ```

The backend already returns `mapping_status` on `FeedResponse` (schemas.py:273) with all
the correctness from 002ib: dedup to latest-per-table, rejected→partial, cross-feed batch safety.

**File:** `web/app/projects/[id]/codegen/page.tsx`

Add a "Mapping" column to the sources table. Read status from `sources[].mappingStatus`
— **do not** make new API calls. The codegen page already has the `sources` list from
`listFeedContracts`; just render a badge per row:
- Green "Approved" / Amber "Draft" / Gray "—"

**Do NOT** call `getAllApprovedMappingSnapshots` per source in the codegen page — that
reinvents 002ib's correctness at N+1 scale with no dedup/partial support, undoing
everything the 6-round backend review fixed.

### 4. Governance: update api.md

**File:** `docs/domain/api.md`

- Fix pre-existing drift: the propose endpoint returns 200, not 201 (already fixed in this plan's scope)
- Document the 409 error detail: `per_table_ownership` object

### 5. Tests

**File:** `engine/tests/test_duplicate_feed_detection.py` (new)
- Create project with 2 feeds (same schema)
- Approve mapping on feed 1
- Propose on feed 2 → verify 409 with `per_table_ownership` detail
- Verify `per_table_ownership` contains correct `source_definition_id`
- Verify 409 status code (not changed to 200)
- Regression: verify codegen still skips feeds with no approved mapping

## Steps

1. Modify `proposal.py` line 347 to build `per_table_ownership` detail
2. Enrich `AuthApiError` call with the detail dict (already supported)
3. Add `mapping_status` to `FeedContractRecord` + mapper in `feeds-api.ts`
4. Add mapping badge to codegen page, reading from `sources[].mappingStatus`
5. Update frontend error handler in feed page to render ownership card
6. Update `docs/domain/api.md` with the new error detail
7. Add integration tests
