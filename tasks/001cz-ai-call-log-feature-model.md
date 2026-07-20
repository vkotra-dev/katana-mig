# Task 001cz: ai_call_log Feature Taxonomy + Pagination + Codegen feed_id

## Objective
`ai_call_log` (task 001co) has grown to 6 `call_type` values across 2
unrelated product surfaces (Feed Detail page, Codegen page) with no
pagination on its list endpoint and, for `codegen`, no way to scope
results to one feed. Add a `feature` taxonomy, paginate the list
endpoint, and add feed-level scoping to codegen artifacts — the
foundation for task 001da's dedicated AI log viewer.

## Requirements

1. **`feature` column on `ai_call_log`.** Two values today:
   - `feed_mapping` — call_types `source_analysis`, `feed_analysis`,
     `mapping`, `lookup_mapping` (all Feed Detail page)
   - `codegen` — call_types `schema_analysis`, `codegen` (all Codegen
     page)

   Update `log_ai_call()` to require `feature`, and update all 6
   call sites (`management/fibers.py` x2 call_types, `mapping/review.py`,
   `management/source_analysis.py`, `codegen/service.py`,
   `codegen/schema_analysis.py`) to pass the correct value.
2. **Fix `source_analysis`'s missing `artifact_id`.** It's currently
   logged with no `artifact_id` at all (`management/source_analysis.py`),
   even though `source_definition_id` (the feed_id) is in scope at the
   call site. Pass `artifact_id=source_definition_id` directly — no
   backfill needed, unlike `mapping`'s snapshot-id backfill pattern,
   since the feed_id is known before the AI call runs.
   `schema_analysis` stays `artifact_id=None` — it's genuinely
   project-wide (the "Analyze DDL" step is not feed-scoped).
3. **Pagination on `GET /projects/{id}/ai-calls`.** Add `limit`
   (default/max e.g. 50/200) and `offset` (or cursor) query params;
   `list_ai_calls()` applies them. This is the direct fix for the
   "bulky" concern — today the query returns every matching row,
   full prompt/response text included, unbounded.
4. **`feature` filter on the same endpoint**, alongside the existing
   `call_type`/`artifact_id` filters.
5. **`feed_id` on `CodeGenerationArtifact`.** New nullable
   `source_definition_id` FK column (`code_generation_artifacts` table).
   Populate it at creation time in `codegen/service.py` — the
   artifact-creation function already receives `source_definition_id` as
   a parameter (line ~54), so this is a one-line addition at the
   `CodeGenerationArtifact(...)` construction (~line 148), not a
   backfill/join problem. Historical rows stay `feed_id=NULL` — no
   backfill (can't be reliably derived from `mapping_snapshot_version`,
   which is a version string, not a FK).
6. **One hand-written Alembic migration** (current head `0033`, new file
   `0034_ai_call_log_feature_and_codegen_feed_id.py`,
   `down_revision = "0033"`) adding both columns.

## Out of Scope
- Building the viewer UI itself — task 001da.
- Dropping `MappingSnapshot.ai_trace` /
  `CodeGenerationArtifact.compiled_*` — task 001db, sequenced after
  001da moves every reader off them.
- Backfilling `feed_id` on existing `CodeGenerationArtifact` rows.
- Any change to `schema_analysis`'s artifact scoping — stays
  project-wide by design.

## Dependencies
None — this is the first of the three tasks (001cz → 001da → 001db).
