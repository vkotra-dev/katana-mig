# Summary 001ac — Mapping Hardening

Implemented the mapping hardening follow-up from the review batch:

- Added `SnapshotVersionConflictError` and exported it from `migrations_engine.mapping`.
- Made `create_approved_mapping_snapshot()` fail closed before insert when the same
  `(project_id, destination_object_name, mapping_snapshot_version)` already exists.
- Made `parse_primary_field_binding()` reject multi-binding snapshots explicitly instead of
  silently truncating to the first binding.
- Updated `docs/domain/source-model.md` to state the duplicate-version and single-binding rules.
- Rewrote `0012_lookup_value_maps.py` so fresh installs create the final table shape immediately,
  including `source_value_map`, and removed the transient unique-constraint window.
- Turned `0013_lookup_value_map_source_value_map.py` into a no-op chain anchor.
- Added regression coverage for duplicate mapping snapshot versions and multi-binding rejection.
- Updated the lookup value map model test to assert `source_value_map` persistence.

Verification:

- `PYTHONPATH=src pytest tests/test_mapping_slice.py -k 'duplicate_version or multiple_bindings' -q`
- `PYTHONPATH=src pytest tests/test_lookup_mapping_models.py -q`
- `python -m compileall engine/src engine/tests`
- `git diff --check`
- `python -m ruff check docs/domain/source-model.md engine/src/migrations_engine/mapping/exceptions.py engine/src/migrations_engine/mapping/__init__.py engine/src/migrations_engine/mapping/snapshots.py engine/migrations/versions/0012_lookup_value_maps.py engine/migrations/versions/0013_lookup_value_map_source_value_map.py engine/tests/test_mapping_slice.py engine/tests/test_lookup_mapping_models.py`

Result:

- 2 targeted mapping tests passed
- 1 lookup model test passed
- compileall passed
- diff check passed
- ruff check passed
