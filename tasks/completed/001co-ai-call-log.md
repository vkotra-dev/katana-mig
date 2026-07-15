# Task: 001co — AI Call Log

## Status
Ready

## Background

Every AI adapter call (codegen, mapping, source analysis, lookup mapping) builds system and user prompts in Python, passes them to `AIAdapter.call()`, and discards them. The only output stored is the parsed artifact — there is no record of what the AI was told or what it returned raw. Debugging prompt issues and auditing AI behavior requires reading source code.

## Goal

Capture every AI call — system prompt, user prompt, raw model response, model ID — in a single `ai_call_log` table. No per-caller boilerplate; new adapters get logging automatically.

## Data Model

New table `ai_call_log` (migration 0033):

```
call_id         UUID PK
project_id      FK → project_registry
call_type       VARCHAR  -- 'codegen' | 'mapping' | 'source_analysis' | 'lookup_mapping'
artifact_id     VARCHAR  -- back-filled after artifact is committed (no FK — points to different tables)
model_id        VARCHAR
system_prompt   TEXT
user_prompt     TEXT
raw_response    TEXT     -- null if call failed
error_detail    TEXT     -- null if call succeeded
called_at       DATETIME
```

## Architecture

1. `AIAdapter.call()` return type changes from `T` to `AICallResult[T]` (adds `.raw_response: str`)
2. `log_ai_call()` helper in `ai/logging.py` writes to `ai_call_log`
3. Each of 5 callers: call adapter → log → persist artifact → `backfill_artifact_id()`
4. On exception: log with `raw_response=None`, `error_detail=str(exc)`, re-raise

## Callers

| File | call_type | artifact back-fill |
|---|---|---|
| `codegen/service.py` | `codegen` | `codegen_artifact_id` |
| `mapping/review.py` | `mapping` | `mapping_snapshot_id` |
| `management/source_analysis.py` | `source_analysis` | `schema_artifact_id` |
| `management/fibers.py` | `lookup_mapping` | `fiber_id` |
| `codegen/schema_analysis.py` | `source_analysis` | artifact id if exists |

## API

```
GET /projects/{project_id}/ai-calls
  ?call_type=codegen          (optional filter)
  ?artifact_id=<uuid>         (optional filter)
Response: list[AICallLogResponse]
Role: admin | central_team
```

## Files Changed

- `engine/migrations/versions/0033_ai_call_log.py` (new, down_revision="0032")
- `engine/src/migrations_engine/db/models.py` — `AICallLog` model
- `engine/src/migrations_engine/ai/adapter.py` — `AICallResult`, updated protocol
- `engine/src/migrations_engine/ai/*.py` — concrete adapters return `AICallResult`
- `engine/src/migrations_engine/ai/logging.py` (new) — `log_ai_call`, `backfill_artifact_id`
- `engine/src/migrations_engine/management/ai_calls.py` (new) — `list_ai_calls`
- `engine/src/migrations_engine/api/schemas.py` — `AICallLogResponse`
- `engine/src/migrations_engine/routes/ai_calls.py` (new)
- `engine/src/migrations_engine/app.py` — register router
- 5 caller files — add log_ai_call + backfill

## Plan

[2026-07-10-ai-call-log.md](../docs/superpowers/plans/2026-07-10-ai-call-log.md)

## Spec

[2026-07-10-ai-call-log-design.md](../docs/superpowers/specs/2026-07-10-ai-call-log-design.md)

## Verification

1. Generate SQL → row in `ai_call_log` with prompts + `artifact_id` populated
2. Trigger mapping AI → `call_type='mapping'` row present
3. Force adapter failure → row with `raw_response=NULL`, `error_detail` set
4. `GET /projects/{id}/ai-calls` returns all rows; filters work
5. `project_stakeholder` → 403
