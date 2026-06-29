# Task
- [001d-minimal-mapping-slice](/Users/vjkotra/projects/katana/tasks/001d-minimal-mapping-slice.md)

# Domain
- [source-model.md](/Users/vjkotra/projects/katana/docs/domain/source-model.md)
- [runs.md](/Users/vjkotra/projects/katana/docs/domain/runs.md)
- [security.md](/Users/vjkotra/projects/katana/docs/domain/security.md)

## Current State
- `run_records` and `change_requests` tables exist but no mapping/lookup snapshot tables.
- Auth and management APIs are implemented; no mapping execution path yet.
- Domain pages describe immutable snapshots, `LookupDeltaCR`, and run provenance.

## Objective
Deliver the smallest governed mapping slice: approved snapshot selection, one
lookup-mapping path end to end, unmapped values via `LookupDeltaCR`, and run
provenance recording.

## Out of Scope
- HTTP routes for mapping
- Full code generation or reconciliation
- Source adapter broadening

## Blast Radius
- `engine/migrations/versions/0007_mapping_lookup_snapshots.py`
- `engine/src/migrations_engine/db/models.py`
- `engine/src/migrations_engine/mapping/`
- `engine/tests/test_mapping_slice.py`

## File Changes
- Add `mapping_snapshots`, `lookup_snapshots`, `mapping_artifacts` tables
- Add mapping package with snapshot selection, lookup apply, delta CR, run pinning
- Add pytest coverage for happy path, unmapped path, immutability, provenance

## Tests
- Approved mapping path produces expected mapping artifact
- Unmapped value creates `lookup_delta` change request and fails run
- Approved snapshots cannot be mutated through service API
- Run record pins mapping and lookup snapshot versions

## Verification
- `pytest engine/tests/test_mapping_slice.py -q` passes
- `alembic upgrade head` applies `0007`

## Pitfalls
- Do not silently map unknown lookup values
- Pin snapshot versions on run start, not after execution
- Keep snapshots append-only after approval

## Commit
- `feat(engine): minimal governed mapping slice with LookupDeltaCR`
