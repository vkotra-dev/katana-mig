# Task: 001cr — Feed Archive Cascade

## Status
Ready

## Background

When a feed is discarded today, only `Feed.status` is set to `"discarded"`. Its mapping snapshots, fibers, and lookup value maps are left orphaned with no status change. This means:

1. Mapping objects accumulate silently and are never cleaned up.
2. When the same feed is re-uploaded (new `source_definition_id`), `propose_mapping` finds no existing snapshots for the new ID and freely re-creates mapping snapshots for destination tables that already have approved snapshots elsewhere in the project — producing duplicates.

## Goal

1. **Cascade discard** — when a feed is discarded, mark its `MappingSnapshot` and `ProjectFiber` rows as `"discarded"` in the same transaction.
2. **Shared-lookup protection** — only discard a `LookupValueMap` if no other active feed's mapping snapshot references the same `lookup_name`.
3. **Re-upload precondition** — extend `propose_mapping` to treat destination tables that already have a project-wide approved snapshot as already-mapped, preventing duplicate creation when a feed is re-uploaded.

## Design Decisions

- No new DB columns or migrations — use existing `status` fields.
- Lookup sharing detection: scan `MappingSnapshot.field_bindings` for `binding_type == "lookup_fk"` across all non-discarded feeds in the project at discard time.
- Re-upload guard: union of `(feed-scoped snapshots)` and `(project-wide approved snapshots)` forms the `already_mapped_tables` set in `propose_mapping`.
- `LookupSnapshot` is project-scoped with no feed link — leave untouched.

## Changes

- `engine/src/migrations_engine/management/feeds.py` — extend `discard_feed` to cascade; add `_lookup_names_for_feed` and `_shared_lookup_names` helpers
- `engine/src/migrations_engine/mapping/review.py:317-327` — extend `already_mapped_tables` to include project-wide approved snapshots
- `engine/tests/test_feed_discard_cascade.py` (new) — cascade tests
- `engine/tests/test_mapping_review_api.py` — one new test for re-upload precondition

## Plan

[2026-07-15-001cr-feed-archive-cascade.md](../docs/superpowers/plans/2026-07-15-001cr-feed-archive-cascade.md)

## Verification

1. Discard a feed → its `MappingSnapshot` rows show `status = "discarded"` in the DB.
2. Discard a feed → its `ProjectFiber` rows show `status = "discarded"` in the DB.
3. Discard a feed that exclusively owns a lookup → `LookupValueMap` shows `status = "discarded"`.
4. Discard one of two feeds sharing a lookup → `LookupValueMap` stays unchanged.
5. Upload a new feed for the same destination tables as an already-approved mapping → `POST /mapping/propose` returns 409 `mapping_already_proposed`.
