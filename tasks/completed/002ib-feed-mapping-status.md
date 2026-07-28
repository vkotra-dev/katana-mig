---
id: 002ib
title: Show mapping status on every feed view; include snapshot context in 409 errors
status: completed
created: 2026-07-28
priority: medium
depends-on: []
domain: engine
task: tasks/002ib-feed-mapping-status.md
plan: plans/2026-07-28-002ib-feed-mapping-status.md
---

# Task 002ib — Feed mapping status + 409 error context

## Context

When a user tries to propose a new mapping for a feed that already has one, the API returns 409 Conflict with `"Mapping has already been proposed for this feed."` — no context about the current mapping state. The user has no way to know if the mapping is still in draft, approved, or assigned.

Additionally, the feed view (both list and detail) never shows the current mapping status. The status lives in `MappingSnapshot` records (status: `"draft"`, `"approved"`, or `"rejected"`) and in `ProjectFiber` records, but it's never surfaced on the feed endpoint.

## Current State

- `FeedResponse` schema has no `mapping_status` field
- `FeedResponse` is constructed in `feeds.py:454` without reading `MappingSnapshot`
- The 409 handler in `propose_mapping()` raises `AuthApiError` with no extra detail
- The fiber list endpoint already reads `MappingSnapshot` and infers status — but this doesn't flow to `FeedResponse`
- `MappingSnapshot` has three status values: `"draft"`, `"approved"`, `"rejected"`. Multiple snapshots per table possible (rejected → re-proposed → draft creates two rows). Status computation must dedup to latest per table and handle rejected correctly.

## Implementation

See `plans/2026-07-28-002ib-feed-mapping-status.md` for the complete implementation plan with file-level changes.

Key changes:
1. `AuthApiError` gains optional `detail` dict parameter
2. `FeedResponse` gains `mapping_status: Literal["draft", "partial", "approved"] | None`
3. `_compute_mapping_status` / `_batch_mapping_status` / `_dedup_snapshots` helpers in `feeds.py`
4. `proposal.py` IntegrityError handler includes `per_table_status` detail
5. All `_source_contract_response` callers pass `db`

## Testing

- `_dedup_snapshots` returns latest per table when duplicates exist
- `_compute_status_from_snapshots` handles draft/approved/partial/rejected/empty
- Key test: rejected+draft deduped → "draft" (not "partial")
- Key test: approved+rejected → "partial" (rejected pulls toward partial, doesn't get silently ignored)
- Feed response includes `mapping_status`
- 409 error includes `per_table_status`

## Domain Updates Required

- `docs/domain/api.md:2046` — `SourceContractResponse` JSON example must include the new `mapping_status` field and updated field list
- The `SourceContractResponse` type (documented at docs/domain/api.md:2046) maps directly to the `FeedResponse` schema; the example JSON at lines 2048-2061 needs `mapping_status` added to match the new schema
