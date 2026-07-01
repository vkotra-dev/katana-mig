# Task 001aj — Feed / FeedSlice Rename

**Plan:** `plans/2026-07-01-001aj-feed-rename.md`

## Scope

Rename `SourceDefinition` to `Feed` and `SourceSlice` to `FeedSlice` across the
codebase, including models, routes, API types, docs, and tests. This was a pure
rename with no functional changes.

## What changed

- Renamed engine models, schemas, routes, services, and tests to the new feed
  vocabulary.
- Updated the web client and route references to use feed/feed-slice names.
- Renamed the underlying Alembic tables from `source_definitions` /
  `source_slices` to `feeds` / `feed_slices`.
- Updated domain docs to use the new terminology.

## Verification

- Backend and frontend tests passed for the rename set.
- The migration chain applied cleanly after the table rename.

