# Plan: 001cz — ai_call_log Feature Taxonomy + Pagination + Codegen feed_id

## Task and Domain links

- Task: `tasks/001cz-ai-call-log-feature-model.md`
- Domain: `docs/domain/ui.md` (consumed by task 001da; this task is
  backend-only, no UI-facing behavior change yet)

## Current State

- `ai_call_log` (`engine/src/migrations_engine/db/models.py:724`,
  migration `0033_ai_call_log.py`) has 6 `call_type` values written
  across 6 call sites: `feed_analysis`/`lookup_mapping`
  (`management/fibers.py`), `mapping` (`mapping/review.py`),
  `source_analysis` (`management/source_analysis.py`), `codegen`
  (`codegen/service.py`), `schema_analysis` (`codegen/schema_analysis.py`).
- `source_analysis`'s `log_ai_call()` calls
  (`management/source_analysis.py:101-119`) never pass `artifact_id`,
  even though `source_definition_id` (the feed_id) is a parameter of the
  enclosing `analyze_source_slice` function (line 59) — it's simply not
  threaded through.
- `GET /projects/{id}/ai-calls` (`routes/ai_calls.py:16-41`) →
  `list_ai_calls()` (`management/ai_calls.py:9-21`) has no
  `limit`/`offset` — returns every row matching `call_type`/`artifact_id`
  filters, full text columns included, ordered by `called_at desc`.
- `CodeGenerationArtifact` (`db/models.py:608-630`) has no feed linkage —
  only `mapping_snapshot_version` (a version string) and
  `source_slice_version`, neither a FK. The artifact-creation function in
  `codegen/service.py` (starts ~line 54, constructs the artifact at
  ~line 148) receives `source_definition_id` as a parameter but never
  stores it on the artifact.
- Migration chain head is `0033_ai_call_log.py`.

## Objective

1. Add `feature: str` (not nullable) to `ai_call_log`, values
   `feed_mapping` and `codegen`.
2. Update `log_ai_call()`'s signature to require `feature`, update all 6
   call sites.
3. Fix `source_analysis` to pass `artifact_id=source_definition_id`.
4. Add `limit`/`offset` pagination to `list_ai_calls()` and the route.
5. Add `feature` as a filter on the same route/query, alongside existing
   `call_type`/`artifact_id`.
6. Add nullable `source_definition_id` (feed_id) FK to
   `code_generation_artifacts`; populate on creation in
   `codegen/service.py`.
7. One migration for both schema changes.

## Out of Scope

- Frontend changes — task 001da consumes this.
- Dropping `MappingSnapshot.ai_trace` /
  `CodeGenerationArtifact.compiled_*` — task 001db.
- Backfilling `feed_id` on existing `CodeGenerationArtifact` rows, or
  `feature` on existing `ai_call_log` rows written before this migration
  (existing rows can be backfilled trivially from their `call_type` via a
  data migration step if desired — see Pitfalls; deferred unless
  requested).
- `schema_analysis`'s artifact scoping — stays `artifact_id=None`, it's
  genuinely project-wide.

## Blast Radius

- `engine/src/migrations_engine/db/models.py` (edited)
- `engine/migrations/versions/0034_ai_call_log_feature_and_codegen_feed_id.py` (new)
- `engine/src/migrations_engine/ai/logging.py` (edited — `log_ai_call` signature)
- `engine/src/migrations_engine/management/fibers.py` (edited — 2 call sites)
- `engine/src/migrations_engine/mapping/review.py` (edited — 4 call sites)
- `engine/src/migrations_engine/management/source_analysis.py` (edited — 2 call sites)
- `engine/src/migrations_engine/codegen/service.py` (edited — 2 call sites + artifact `feed_id`)
- `engine/src/migrations_engine/codegen/schema_analysis.py` (edited — 2 call sites)
- `engine/src/migrations_engine/management/ai_calls.py` (edited — pagination + feature filter)
- `engine/src/migrations_engine/routes/ai_calls.py` (edited — query params)
- `engine/src/migrations_engine/api/schemas.py` (edited — `AICallLogResponse.feature`, pagination params, `feed_id` on codegen artifact schemas)
- `web/lib/ai-calls-api.ts` (edited — `feature` field, pagination params; consumed by 001da, safe to ship ahead of it)
- `web/lib/codegen-api.ts` (edited — `feedId` field on `CodegenArtifactRecord`)
- No role-gating change.

## File Changes

**`engine/src/migrations_engine/db/models.py`**
- `AICallLog`: add `feature: Mapped[str] = mapped_column(String(32), nullable=False, index=True)`.
- `CodeGenerationArtifact`: add `source_definition_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("source_definitions.source_definition_id"), nullable=True, index=True)`.

**`engine/migrations/versions/0034_ai_call_log_feature_and_codegen_feed_id.py` (new)**
- `revision = "0034"`, `down_revision = "0033"`.
- `upgrade()`: `op.add_column("ai_call_log", sa.Column("feature", sa.String(32), nullable=False, server_default="feed_mapping"))` then drop the server_default after backfilling `feature` per `call_type` (`schema_analysis`/`codegen` → `"codegen"`, everything else → `"feed_mapping"`) via a data-migration `UPDATE` statement inside `upgrade()`; `op.create_index` on `feature`. `op.add_column("code_generation_artifacts", sa.Column("source_definition_id", sa.String(36), sa.ForeignKey("source_definitions.source_definition_id"), nullable=True))`, `op.create_index`.
- `downgrade()`: drop both columns/indexes.

**`engine/src/migrations_engine/ai/logging.py`**
- `log_ai_call(...)` gains a required `feature: str` kwarg, stored on the
  `AICallLog(...)` construction.

**`engine/src/migrations_engine/management/fibers.py`**
- Both `call_type="feed_analysis"` sites → `feature="feed_mapping"`.
- Both `call_type="lookup_mapping"` sites → `feature="feed_mapping"`.

**`engine/src/migrations_engine/mapping/review.py`**
- All 4 `call_type="mapping"` sites → `feature="feed_mapping"`.

**`engine/src/migrations_engine/management/source_analysis.py`**
- Both `call_type="source_analysis"` sites → `feature="feed_mapping"`,
  and add `artifact_id=source_definition_id` (currently missing
  entirely).

**`engine/src/migrations_engine/codegen/service.py`**
- Both `call_type="codegen"` sites → `feature="codegen"`.
- `CodeGenerationArtifact(...)` construction (~line 148): add
  `source_definition_id=source_definition_id`.

**`engine/src/migrations_engine/codegen/schema_analysis.py`**
- Both `call_type="schema_analysis"` sites → `feature="codegen"`.

**`engine/src/migrations_engine/management/ai_calls.py`**
- `list_ai_calls(..., feature: str | None = None, limit: int = 50, offset: int = 0)`:
  add `.where(AICallLog.feature == feature)` when set, `.limit(limit).offset(offset)`,
  cap `limit` at e.g. 200.

**`engine/src/migrations_engine/routes/ai_calls.py`**
- Add `feature`, `limit`, `offset` query params to `get_ai_calls`, pass
  through to `list_ai_calls`.

**`engine/src/migrations_engine/api/schemas.py`**
- `AICallLogResponse`: add `feature: str`.
- Codegen artifact response schemas (~lines 492-509): add
  `feed_id: str | None` (mapped from `source_definition_id`).

**`web/lib/ai-calls-api.ts`**
- `AICallLogRecord`: add `feature: string`.
- `listAiCallLogs(...)`: accept `{ feature?, limit?, offset? }` in
  `options`, add to querystring, map `feature` in the response parse.

**`web/lib/codegen-api.ts`**
- `CodegenArtifactRecord` (both interfaces): add `feedId?: string | null`,
  mapped from `feed_id`.

## Tests

- `ai_calls` engine tests: `list_ai_calls` respects `feature` filter and
  `limit`/`offset`; `log_ai_call` requires `feature`.
- `source_analysis` engine test: assert the logged row now has
  `artifact_id == source_definition_id`.
- `codegen/service` engine test: assert a newly created
  `CodeGenerationArtifact` has `source_definition_id` populated.
- Migration test: `alembic upgrade head` from `0033`, confirm existing
  `ai_call_log` rows get a non-null `feature` backfilled correctly per
  `call_type`; `alembic downgrade -1` then `upgrade head` again runs
  cleanly.

## Verification

- `alembic upgrade head` runs cleanly against a local DB with existing
  `ai_call_log`/`code_generation_artifacts` data; spot-check backfilled
  `feature` values.
- `mypy --strict` / `ruff` clean on all touched engine files.
- `GET /projects/{id}/ai-calls?feature=codegen&limit=10` returns only
  `codegen`/`schema_analysis` rows, capped at 10.
- Manually trigger a source analysis (Feed page "AI Analyze") and confirm
  the resulting `ai_call_log` row has both `feature="feed_mapping"` and
  `artifact_id` set to the feed_id.
- Manually generate SQL on the Codegen page and confirm the new
  `CodeGenerationArtifact` row has `source_definition_id` populated.

## Pitfalls

- The `feature` backfill for pre-existing `ai_call_log` rows must run
  inside the migration's `upgrade()` (data migration), not be left for
  application code — otherwise old rows have `feature=NULL` (or the
  server_default) forever and silently disappear from
  `feature`-filtered queries.
- Don't add `feature` as a free-form string without validating call
  sites — a typo'd feature value (e.g. `"codgen"`) silently orphans that
  call type from all `feature`-filtered views. Consider a `Literal["feed_mapping", "codegen"]` type hint on `log_ai_call`'s `feature` param (even though the DB column is a plain string) to catch this at the call sites during type-check.
- `source_analysis`'s early-return path (`existing_artifact is not None`,
  line 70-71) never calls `log_ai_call` at all — no change needed there,
  but don't assume every call to `analyze_source_slice` produces a log
  row.
- Keep `schema_analysis` at `artifact_id=None` — don't be tempted to set
  it to `project_id` just because a value is expected; `project_id` is
  already the row's own `project_id` column, redundant as `artifact_id`.

## Commit

Own commit, first of the three (001cz → 001da → 001db).
