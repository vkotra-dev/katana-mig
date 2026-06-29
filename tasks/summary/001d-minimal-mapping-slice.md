# 001d-minimal-mapping-slice Summary

- Added `mapping_snapshots`, `lookup_snapshots`, and `mapping_artifacts` tables
  (migration `0007`).
- Implemented governed mapping service: approved snapshot selection, lookup
  apply, `LookupDeltaCR` on unmapped values, and run provenance pinning.
- Added `engine/tests/test_mapping_slice.py` (3 tests, all passing).
