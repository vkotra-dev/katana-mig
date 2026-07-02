# Summary: Task 001am — Mapping Fiber AI Flow

## What changed

- Added the `feed_analysis` AI slot to the engine config stack and slot map.
- Added `analyze_feed` in `engine/src/migrations_engine/management/fibers.py`.
- Wired a new `POST /projects/{project_id}/feeds/{feed_id}/analyze` endpoint.
- Registered the feed-level fiber analysis router in `app.py`.
- Added focused tests for the new service and API flow.

## Behavior

- The service reads the latest approved `FeedSlice` for the feed.
- It calls `feed_analysis` to identify lookup fibers and domain-object fibers.
- Lookup fibers are created with `status="deferred"` and `source="auto"`.
- Domain-object fibers are created with `status="ai_running"` and then enriched with `field_bindings` from `field_mapping`.
- The API is restricted to central team users.

## Verification

- `PYTHONPATH=src python -m pytest tests/test_fiber_ai_flow.py tests/test_source_analysis_api.py -q`
- `PYTHONPATH=src python -m pytest tests/test_fiber_ai_flow.py tests/test_source_analysis_api.py tests/test_lookup_mapping_service.py tests/test_ai_config.py tests/test_ai_adapter.py -q`

## Notes

- The full engine suite still has unrelated MySQL/environment failures outside this change set.
- Existing compatibility edits in `lookup_mapping.py` and `test_impact_review_config.py` were left untouched.
