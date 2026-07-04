# Task 001ba — Feed Slice Terminology Sweep

**Plan:** `plans/2026-07-04-001ba-feed-slice-terminology-sweep.md`

**Depends on:** 001aj (Feed / FeedSlice rename)

## Domain

- [ui.md](/Users/vjkotra/projects/katana/docs/domain/ui.md)
- [source-model.md](/Users/vjkotra/projects/katana/docs/domain/source-model.md)
- [runs.md](/Users/vjkotra/projects/katana/docs/domain/runs.md)
- [project.md](/Users/vjkotra/projects/katana/docs/domain/project.md)
- [api.md](/Users/vjkotra/projects/katana/docs/domain/api.md)

## Current State

- The domain docs now describe the artifact as a feed slice in prose.
- Several web UI labels and a few test descriptions still say "source slice"
  even though the underlying wire fields remain `source_slice_*`.
- Existing API paths, JSON keys, and stored column names still use the legacy
  names and are intentionally preserved for compatibility.

## Objective

Finish the feed-slice terminology sweep so the web app, docs, tests, and
internal TS identifiers use `Feed` / `FeedSlice` / "feed slice" consistently
wherever they refer to the approved artifact, while leaving wire contract
names unchanged.

## Scope

- Update remaining UI copy in approvals, artifacts, and run-launch surfaces
- Rename internal TS identifiers from `source*` to `feed*` where they refer to
  the approved artifact
- Add focused component tests for the copy-heavy screens
- Update test descriptions and expectations that still say "source slice"
- Update any remaining prose in docs or plan text that refers to the approved
  artifact as a source slice

## Out of Scope

- Renaming `source_slice_*` JSON keys
- Renaming route segments such as `/slices`
- Renaming database columns or tables
- Changing runtime behavior, approval flow, or snapshot semantics

## Acceptance Criteria

- User-facing text says "feed slice" when referring to the approved artifact
- Internal TS identifiers for the approved artifact use `feed*` naming where
  the code still models the same thing
- The UI no longer shows plain-English "source slice" labels in the touched
  screens
- Tests reflect the updated terminology
- Compatibility fields and routes remain untouched

## Test Expectations

- Updated component and API helper tests pass after copy updates
- A search across the touched UI files no longer finds stale human-facing
  "source slice" phrasing
- Local TS names in the touched components use `feed*` where they point at the
  approved artifact

## Pitfalls

- Do not rename the `source_slice_*` wire fields yet
- Do not change route URLs or database names in the name of wording cleanup
- Keep the term `FeedSlice` aligned with the existing 001aj rename

## Commit

- `feat(001ba): finish feed slice terminology sweep`
