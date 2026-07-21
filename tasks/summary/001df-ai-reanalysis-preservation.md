# Task Summary: 001df-ai-reanalysis-preservation

**Status**: Completed
**Date**: 2026-07-21

## What was done
Implemented AI re-analysis and sign-off preservation (Upsert) across source analysis, field mapping, and lookup fibers.

1. **Source Analysis (`source_analysis.py`)**: 
   - Removed early-exit cache that threw a 409 error.
   - Replaced it with logic to explicitly delete the old `SourceSchemaArtifact` and `SourceValueSummary` artifacts for that version to prevent unique constraint errors during re-analysis.
2. **Field Mapping (`review.py`)**:
   - Removed early-exit cache that threw a 409 error when tables were already mapped.
   - Refactored `already_mapped_tables` to only consider `status == "approved"`, so AI re-proposes mappings for unapproved destination tables.
3. **Lookup Fiber Mapping (`fibers.py`)**:
   - Removed the 409 error when re-submitting lookup inputs for a lookup that has sign-offs.
   - Changed deletion behavior to only delete unapproved mappings.
   - Filtered out source values that are already approved so they are skipped from re-insertion, effectively preserving their sign-offs.
4. **Tests**:
   - Adjusted `test_lookup_fiber_api.py` to expect 200 instead of 409.
   - Adjusted `test_source_analysis_service.py` to reflect the new idempotency behavior (new IDs are generated on rerun, fake adapter called multiple times).
   - Cleaned up outdated `ai_trace` assertion that failed due to prior task `001dc`.
   
All 309 tests passed successfully.
