# Plan: 001db — Drop Legacy AI Prompt/Response Columns Superseded by ai_call_log

## Task and Domain links

- Task: `tasks/001db-drop-legacy-ai-log-columns.md`
- Domain: `docs/domain/ui.md` (already updated by 001da; this task only
  needs a changelog line, no further behavior description change)

## Current State

- After 001da lands, `MappingSnapshot.ai_trace` and
  `CodeGenerationArtifact.compiled_system_prompt`/`compiled_user_prompt`/
  `raw_llm_response` have no remaining UI readers — both were replaced by
  `AiLogViewer` instances sourced from `ai_call_log`.
- `mapping/review.py`'s `propose_mapping` still writes `ai_trace` (the
  now-dead column) alongside its `ai_call_log` write.
- `codegen/service.py` still writes the 3 dead columns alongside its
  `ai_call_log` write.
- Migration head is `0034` (from 001cz).

## Objective

1. Remove `MappingSnapshot.ai_trace` end-to-end: model, write site,
   response schema, frontend type.
2. Remove `CodeGenerationArtifact.compiled_system_prompt`/
   `compiled_user_prompt`/`raw_llm_response` end-to-end: model, write
   sites, response schemas, frontend types.
3. One migration dropping all 4 columns.
4. `docs/domain/ui.md` changelog entry.

## Out of Scope

- Any change to `ai_call_log` itself, or to 001da's `AiLogViewer`.
- Any change to `CodeGenerationArtifact.sql_bundle` — unrelated, stays.
- Backfilling old data — already covered in task's Out of Scope, no data
  loss since `ai_call_log` already has the same content from the time
  these columns were last written.

## Blast Radius

- `engine/src/migrations_engine/db/models.py` (edited)
- `engine/migrations/versions/0035_drop_legacy_ai_prompt_columns.py` (new)
- `engine/src/migrations_engine/mapping/review.py` (edited)
- `engine/src/migrations_engine/codegen/service.py` (edited)
- `engine/src/migrations_engine/api/schemas.py` (edited)
- `web/lib/mapping-api.ts` (edited)
- `web/lib/codegen-api.ts` (edited)
- `docs/domain/ui.md` (edited — changelog only)
- No UI/frontend page changes — 001da already moved every reader off
  these columns; this task is backend/schema-only.

## File Changes

**`engine/src/migrations_engine/db/models.py`**
- Remove `MappingSnapshot.ai_trace`.
- Remove `CodeGenerationArtifact.compiled_system_prompt`,
  `compiled_user_prompt`, `raw_llm_response`.

**`engine/migrations/versions/0035_drop_legacy_ai_prompt_columns.py` (new)**
- `revision = "0035"`, `down_revision = "0034"`.
- `upgrade()`: `op.drop_column("mapping_snapshots", "ai_trace")`;
  `op.drop_column("code_generation_artifacts", "compiled_system_prompt")`;
  `op.drop_column("code_generation_artifacts", "compiled_user_prompt")`;
  `op.drop_column("code_generation_artifacts", "raw_llm_response")`.
- `downgrade()`: re-add all 4 with original types (`JSON` nullable for
  `ai_trace`; `Text` nullable for the other 3).

**`engine/src/migrations_engine/mapping/review.py`**
- Remove the `ai_trace = {...}` construction and `ai_trace=ai_trace` on
  `MappingSnapshot(...)`.
- Remove `ai_trace=snapshot.ai_trace` from `_snapshot_to_response`.

**`engine/src/migrations_engine/codegen/service.py`**
- Remove `compiled_system_prompt`/`compiled_user_prompt`/
  `raw_llm_response` from the `CodeGenerationArtifact(...)` construction
  and both response-mapping call sites.

**`engine/src/migrations_engine/api/schemas.py`**
- Remove `ai_trace: dict | None = None`.
- Remove `compiled_system_prompt`/`compiled_user_prompt`/
  `raw_llm_response` from both codegen schema classes.

**`web/lib/mapping-api.ts`**
- Remove `aiTrace` field, raw-response field, and mapping.

**`web/lib/codegen-api.ts`**
- Remove `compiledSystemPrompt`/`compiledUserPrompt`/`rawLlmResponse`
  from both interfaces and both raw/mapped pairs.

**`docs/domain/ui.md`**
- Changelog line noting the columns are gone; no description change
  needed (001da already rewrote the relevant items to describe
  `AiLogViewer`, not the old columns).

## Tests

- `review.py` engine test: mapping-snapshot response no longer contains
  `ai_trace`; `propose_mapping` still writes the `ai_call_log` row
  correctly (unchanged behavior).
- `codegen/service` engine test: artifact response no longer contains
  the 3 removed fields.
- `mapping-api.test.ts` / `codegen-api.test.ts` (if present): drop
  fixtures referencing removed fields.
- Migration test: `alembic upgrade head` from `0034`, then
  `downgrade -1` then `upgrade head` again, runs cleanly.

## Verification

- `alembic upgrade head` runs cleanly.
- `mypy --strict` / `ruff` clean.
- Manual: Feed and Codegen pages still work end-to-end (both already
  verified against `ai_call_log` in 001da; this just confirms nothing
  broke after the columns are gone).
- `docs/domain/ui.md` changelog updated.

## Pitfalls

- Confirm 001da's commit is actually merged/landed before starting —
  this task assumes zero remaining readers of the dropped columns; if
  001da is still in flight, dropping these breaks it.
- Don't drop `CodeGenerationArtifact.status`, `sql_bundle`,
  `source_slice_version`, `mapping_snapshot_version`, or the new
  `source_definition_id` from 001cz — only the 3 named prompt/response
  columns are in scope.

## Commit

Own commit, third of three. Requires 001da merged/landed first.
