# Plan: 001dc — Backend AI Log Consolidation for Feeds

## Background
Currently, the AI Call Logs generated on the Feed Detail page are fragmented across three different `artifact_id`s:
- **Source Analysis:** Accidentally backfilled to `schema_artifact_id` (causing the UI to find 0 logs).
- **Mapping:** Backfilled to `mapping_snapshot_id`.
- **Lookup Fibers:** Backfilled to `fiber_id`.

To support a unified "Feed-Level AI Log Viewer" at the bottom of the UI, we need all AI calls related to a feed to share the same `artifact_id` (which should be the `feedId` / `source_definition_id`). The UI can then simply fetch all logs where `artifact_id = feedId` and they will naturally appear chronologically in a single table, with their `call_type` ("source_analysis", "mapping", "lookup_mapping") distinguishing them.

## Objective
Update all backend functions that perform AI calls for a feed to use the `feedId` (`source_definition_id`) as the `artifact_id` in the `ai_call_log` table.

## Implementation Steps
1. **Source Analysis (`engine/src/migrations_engine/management/source_analysis.py`):**
   - In `analyze_source_slice`, `log_ai_call` already correctly sets `artifact_id=source_definition_id`.
   - Delete the legacy `backfill_artifact_id(db, call_log.call_id, schema_artifact.schema_artifact_id)` line at the bottom so it stops overwriting it.

2. **Mapping (`engine/src/migrations_engine/mapping/review.py`):**
   - In `propose_mapping`, update the `log_ai_call` creation to initially pass `artifact_id=source_definition_id` OR update the backfill at the end from `snapshots[0].mapping_snapshot_id` to `source_definition_id`.

3. **Lookup Fibers (`engine/src/migrations_engine/management/fibers.py`):**
   - In `create_lookup_snapshot` (and any related fiber mapping logic that logs AI calls), change the backfill target from `fiber_id` to the `feed.source_definition_id`.
   - *Note: `analyze_feed` (which proposes fibers) already backfills to `feed.source_definition_id`, so it is already compliant.*

## Blast Radius
- `engine/src/migrations_engine/management/source_analysis.py`
- `engine/src/migrations_engine/mapping/review.py`
- `engine/src/migrations_engine/management/fibers.py`
- No DB migrations needed. No schema changes.

## Verification
- Running Source Analysis, Propose Mapping, and Analyze Lookup on a feed will produce `ai_call_log` rows that all share the exact same `artifact_id` (`feedId`).
- A direct API query `GET /projects/{id}/ai-calls?artifactId={feedId}` will return all of them mixed chronologically.
