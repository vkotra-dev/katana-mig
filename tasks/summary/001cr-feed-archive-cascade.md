# Summary: 001cr — Feed Archive Cascade

## What was done
1. **Cascade Discard Implementation**: 
   - Modified `discard_feed` in `engine/src/migrations_engine/management/feeds.py` to cascade feed discard operations to child entities.
   - Now correctly marks `MappingSnapshot` and `ProjectFiber` rows associated with the discarded feed as `"discarded"`.
2. **Shared-lookup Protection**:
   - Implemented logic in `discard_feed` to safely handle `LookupValueMap` objects.
   - Introduced `_shared_lookup_names` logic to check if a lookup map is referenced by any other active feed's mapping snapshots within the project. Only discards exclusive lookups.
3. **Duplicate Prevention on Re-upload**:
   - Updated `propose_mapping` in `engine/src/migrations_engine/mapping/review.py` to check for project-wide approved mappings.
   - When a feed is discarded and re-uploaded as a new feed, the system now treats destination tables that already have an approved snapshot in the project as "already-mapped", preventing duplicate mapping snapshots from being created.
4. **Testing**:
   - Created comprehensive unit tests in `test_feed_discard_cascade.py` to verify the cascading logic and shared lookup protection.
   - Resolved minor test fixture issues to ensure the entire test suite passes perfectly.

## Files changed
- `engine/src/migrations_engine/management/feeds.py`
- `engine/src/migrations_engine/mapping/review.py`
- `engine/tests/test_feed_discard_cascade.py` (New)
- `engine/tests/test_mapping_review_api.py`
