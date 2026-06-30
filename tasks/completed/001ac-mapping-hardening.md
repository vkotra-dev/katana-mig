# Task 001ac — Mapping Hardening

**Plan:** `plans/2026-06-30-001ac-mapping-hardening.md`

## Domain

- `docs/domain/source-model.md` — lookup mapping, snapshot selection, downstream provenance
- `docs/domain/project.md` — snapshot policy, downstream execution consistency
- `docs/domain/governance.md` — migration rules, task traceability

## Depends on

- 001d (minimal mapping slice baseline exists)
- 001x (lookup mapping flow already implemented)

## Scope

Harden the governed mapping path so approved mapping snapshots fail closed on
duplicate versions, unsupported multi-binding snapshots are rejected explicitly,
and the lookup-value-map migration chain no longer exposes a transient unique
constraint window between `0012` and `0013`.

## Current State

- `engine/src/migrations_engine/mapping/snapshots.py` inserts approved mapping
  snapshots directly and lets the database unique index raise an unhandled
  integrity error on duplicate `(project_id, destination_object_name,
  mapping_snapshot_version)`.
- `parse_primary_field_binding()` silently returns `field_bindings[0]`, which
  truncates snapshots with multiple bindings.
- `engine/migrations/versions/0012_lookup_value_maps.py` creates
  `lookup_value_maps` with a unique constraint that `0013` immediately removes.

## Objective

Make mapping snapshot creation and parsing fail deterministically with a
governed conflict/error path, and collapse the lookup-value-map migration chain
into a single consistent table definition for fresh installs.

## Out of Scope

- New mapping UI
- Lookup-value-map API shape changes
- Runtime lookup delta execution
- Reworking unrelated migration chains

## Blast Radius

- `docs/domain/source-model.md`
- `engine/src/migrations_engine/mapping/snapshots.py`
- `engine/src/migrations_engine/mapping/exceptions.py`
- `engine/src/migrations_engine/mapping/__init__.py`
- `engine/migrations/versions/0012_lookup_value_maps.py`
- `engine/migrations/versions/0013_lookup_value_map_source_value_map.py`
- `engine/tests/test_mapping_slice.py`
- `engine/tests/test_lookup_mapping_models.py`

## File Changes

- Add a mapping snapshot version conflict exception and pre-insert lookup.
- Guard multi-binding mapping snapshots with an explicit `MappingError`.
- Rewrite the `0012`/`0013` lookup-value-map migrations so fresh installs never
  see the temporary unique-constraint window.
- Update the source-model doc to state the governed lookup/mapping behavior.
- Add regression tests for duplicate mapping snapshot version and unsupported
  multi-binding snapshots.

## Tests

- `cd engine && PYTHONPATH=src pytest tests/test_mapping_slice.py -q`
- `cd engine && PYTHONPATH=src pytest tests/test_lookup_mapping_models.py -q`
- `cd engine && source ../.venv/bin/activate && PYTHONPATH=src python -m alembic upgrade head`

## Verification

- Duplicate mapping snapshot versions return a governed conflict instead of a
  raw database integrity error.
- Mapping snapshots with more than one binding are rejected explicitly.
- Fresh migration installs land on the final `lookup_value_maps` table shape
  without a transient unique constraint.

## Pitfalls

- Do not silently discard the second and later field bindings.
- Do not leave the migration chain in a state that depends on a manual cleanup
  step between `0012` and `0013`.
- Do not weaken the snapshot version uniqueness invariant.

## Commit

- `fix(mapping): harden snapshot conflicts and lookup migration chain`
