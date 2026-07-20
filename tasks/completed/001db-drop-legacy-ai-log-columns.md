# Task 001db: Drop Legacy AI Prompt/Response Columns Superseded by ai_call_log

## Objective
Once task 001da's `AiLogViewer` is the only UI surface reading AI
prompt/response data (via `ai_call_log`), drop the columns that used to
duplicate it directly on `MappingSnapshot` and `CodeGenerationArtifact`.

## Requirements

1. **Drop `MappingSnapshot.ai_trace`** (`db/models.py`): remove the
   column, remove the write in `mapping/review.py`'s `propose_mapping`
   (`ai_trace = {...}` / `ai_trace=ai_trace`), remove it from
   `_snapshot_to_response`, `api/schemas.py`, and `web/lib/mapping-api.ts`
   (`aiTrace` field + mapping). The `log_ai_call(..., call_type="mapping",
   ...)` + `backfill_artifact_id` calls in `propose_mapping` are
   untouched — they're the surviving source of truth, already consumed
   by 001da's viewer.
2. **Drop `CodeGenerationArtifact.compiled_system_prompt` /
   `compiled_user_prompt` / `raw_llm_response`** (`db/models.py`): remove
   the columns, remove the writes and response-mapping reads in
   `codegen/service.py`, remove from `api/schemas.py`, and remove from
   `web/lib/codegen-api.ts`. Confirm 001da's Codegen page changes are the
   last reader before removing — the `sql_bundle` column is unrelated and
   stays.
3. **One hand-written Alembic migration** dropping all 4 columns
   (down_revision = 001cz's migration `0034`), with a `downgrade()` that
   re-adds them with original types.
4. **Docs**: update `docs/domain/ui.md` — remove the "AI Trace &
   Reasoning" panel description (already replaced in the UI by 001da),
   describe the unified AI Prompt Log viewer covering all 6 call types
   across the `feed_mapping`/`codegen` features. Bump `timestamp`, add a
   changelog line (governance I22).

## Out of Scope
- Any further schema change beyond dropping these 4 named columns.
- Backfilling historical `ai_trace`/`compiled_*` data into `ai_call_log`
  — those calls were already dual-written to `ai_call_log` at the time,
  so no data is lost by dropping the duplicate columns.

## Dependencies
Requires 001da to be complete, verified, and its own commit landed —
this task assumes no code anywhere still reads the columns being
dropped.
