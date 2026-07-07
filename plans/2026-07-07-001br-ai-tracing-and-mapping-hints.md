# Plan: 001br — AI Tracing and Mapping Hints

- **Task Link:** [tasks/001br-ai-tracing-and-mapping-hints.md](../tasks/001br-ai-tracing-and-mapping-hints.md)
- **Domain Link:** [docs/domain/mapping.md](../docs/domain/mapping.md)

## Current State

`propose_mapping` calls the AI adapter, discards both the prompt it sent and the response it received. The `MappingSnapshot` row stores only the interpreted binding list. Operators have no way to see how the AI reasoned. Additionally, source data has frequent encoding quirks (dates as `yyyymmdd` strings, leading-zero padded codes) that the AI gets wrong on first pass, and there is no per-feed mechanism to inject operator-supplied hints before analysis. Project-level `constraints` / `assumptions` / `lexicon_scope` exist on `ProjectDefinition` but are never forwarded to the AI.

## Objective

1. Store the full AI exchange (system prompt, user message, raw response, model id) on `MappingSnapshot.ai_trace`
2. Add a `mapping_hints` freetext column to `Feed` that operators can fill in the feed workspace
3. Inject `mapping_hints` + project `constraints` into the `propose_mapping` user message
4. Surface the stored trace in the feed workspace under a collapsible "AI reasoning" section per table

## Out of Scope

- Lookup value mapping tracing (separate AI call path)
- Prompt versioning or A-B testing
- Project copy propagation of hints (future 001bt)

## Blast Radius

| Layer | Files |
|---|---|
| Migration | `engine/migrations/versions/0025_feed_hints_and_ai_trace.py` |
| DB model | `engine/src/migrations_engine/db/models.py` |
| API schema | `engine/src/migrations_engine/api/schemas.py` |
| Mapping logic | `engine/src/migrations_engine/mapping/review.py` |
| Route | `engine/src/migrations_engine/routes/feeds.py` |
| Frontend API client | `web/lib/feeds-api.ts`, `web/lib/mapping-api.ts` |
| Feed workspace UI | `web/app/projects/[id]/feeds/[feedId]/page.tsx` |

## File Changes

### 1. Migration — `engine/migrations/versions/0025_feed_hints_and_ai_trace.py`

New Alembic migration. Down revision: `0024_mapping_per_feed`.

```python
def upgrade() -> None:
    op.add_column("source_definitions",
        sa.Column("mapping_hints", sa.Text(), nullable=True))
    op.add_column("mapping_snapshots",
        sa.Column("ai_trace", sa.JSON(), nullable=True))

def downgrade() -> None:
    op.drop_column("mapping_snapshots", "ai_trace")
    op.drop_column("source_definitions", "mapping_hints")
```

### 2. DB Models — `engine/src/migrations_engine/db/models.py`

On `Feed` (mapped to `source_definitions`):
```python
mapping_hints: Mapped[str | None] = mapped_column(Text, nullable=True)
```

On `MappingSnapshot`:
```python
ai_trace: Mapped[dict | None] = mapped_column(JSON, nullable=True)
```

### 3. API Schemas — `engine/src/migrations_engine/api/schemas.py`

On `FeedResponse`: add `mapping_hints: str | None = None`

New request body for the hints PATCH:
```python
class FeedMappingHintsRequest(BaseModel):
    mapping_hints: str | None
```

On `MappingSnapshotResponse`: add `ai_trace: dict | None = None`

### 4. Mapping Logic — `engine/src/migrations_engine/mapping/review.py`

In `propose_mapping`, after building the base user message string and before calling `adapter.call(...)`:

```python
extra_context: list[str] = []

if feed.mapping_hints:
    extra_context.append(f"Mapping hints (operator-supplied):\n{feed.mapping_hints}")

project_constraints = project.constraints or []
if project_constraints:
    bullet_list = "\n".join(f"- {c}" for c in project_constraints)
    extra_context.append(f"Project constraints:\n{bullet_list}")

if extra_context:
    user_message = user_message + "\n\n" + "\n\n".join(extra_context)
```

After `adapter.call(...)` returns, build the trace dict:
```python
ai_trace = {
    "system_prompt": system_prompt,
    "user_prompt": user_message,
    "raw_response": result.model_dump(),
    "model_id": getattr(adapter, "model_id", None),
}
```

When calling `create_approved_mapping_snapshot` (or the insert path), pass `ai_trace=ai_trace`. Set `ai_trace` on each created `MappingSnapshot` row.

> **Note:** `propose_mapping` creates one snapshot per destination table in a loop. Each snapshot gets the same trace object (same prompts, same response — the response contains proposals for all tables).

### 5. Feeds Route — `engine/src/migrations_engine/routes/feeds.py`

Add a PATCH endpoint:

```python
@router.patch("/{source_definition_id}/hints", response_model=FeedResponse)
def patch_source_hints(
    project_id: str,
    source_definition_id: str,
    body: FeedMappingHintsRequest,
    actor: User = Depends(get_central_team_user),
    db: Session = Depends(get_db),
) -> FeedResponse:
    feed = get_source_contract(db, project_id=project_id,
                               source_definition_id=source_definition_id)
    feed.mapping_hints = body.mapping_hints
    db.commit()
    db.refresh(feed)
    return FeedResponse.model_validate(feed)
```

Also make sure `list_source_contracts` / `get_source_contract` in `management/feeds.py` return `mapping_hints` — since `FeedResponse` uses `model_validate(feed)`, no extra changes needed if the field is on the model.

### 6. Frontend API Client

**`web/lib/feeds-api.ts`** — add to `FeedRecord` interface:
```ts
mappingHints: string | null;
```

Map `response.mapping_hints` → `mappingHints` in `mapFeedResponse`.

Add new function:
```ts
export async function patchFeedMappingHints(
  token: string,
  projectId: string,
  feedId: string,
  hints: string | null,
): Promise<FeedRecord> { ... }
```

**`web/lib/mapping-api.ts`** — add to `MappingSnapshotRecord`:
```ts
aiTrace: Record<string, unknown> | null;
```

Map `response.ai_trace` → `aiTrace` in the snapshot mapper.

### 7. Feed Workspace UI — `web/app/projects/[id]/feeds/[feedId]/page.tsx`

**Mapping hints textarea** (shown to `central_team` only, above the field mapping accordions):
```tsx
{role === "central_team" && (
  <div className="mb-4">
    <label className="text-sm font-medium text-gray-700">Mapping hints</label>
    <textarea
      className="mt-1 w-full rounded border p-2 text-sm font-mono"
      rows={4}
      placeholder="Describe source encoding quirks, date formats, code lists, etc."
      value={mappingHints}
      onChange={(e) => setMappingHints(e.target.value)}
    />
    <button
      onClick={handleSaveMappingHints}
      disabled={savingHints}
      className="mt-1 text-sm text-blue-600 hover:underline"
    >
      {savingHints ? "Saving…" : "Save hints"}
    </button>
  </div>
)}
```

State: `const [mappingHints, setMappingHints] = useState<string>("")` — loaded from `feed.mappingHints` on load.

`handleSaveMappingHints`: calls `patchFeedMappingHints(token, projectId, feedId, mappingHints)`.

**AI reasoning collapsible panel** (inside each table accordion, below the bindings table, `central_team` only):

```tsx
{role === "central_team" && snapshot.aiTrace && (
  <details className="mt-2 text-xs text-gray-500">
    <summary className="cursor-pointer font-medium">AI reasoning</summary>
    <div className="mt-1 space-y-2">
      <p><strong>Model:</strong> {snapshot.aiTrace.model_id as string ?? "—"}</p>
      <pre className="whitespace-pre-wrap rounded bg-gray-50 p-2 overflow-auto max-h-60">
        {snapshot.aiTrace.user_prompt as string}
      </pre>
      <pre className="whitespace-pre-wrap rounded bg-gray-50 p-2 overflow-auto max-h-60">
        {JSON.stringify(snapshot.aiTrace.raw_response, null, 2)}
      </pre>
    </div>
  </details>
)}
{role === "central_team" && !snapshot.aiTrace && (
  <p className="mt-2 text-xs text-gray-400">No AI trace available for this snapshot.</p>
)}
```

## Pitfalls

- `ai_trace` stores the full system prompt + full DDL + full AI response. It can be 4–20 KB per snapshot. **Do NOT return it from the list-snapshots route by default.** The feed workspace already fetches snapshots individually per table open; if trace is only rendered when the accordion is open, the existing per-table fetch is fine. If `MappingSnapshotResponse` already returns all fields, gate the `ai_trace` read behind `include_trace=true` query param on the list route, or move the AI reasoning fetch to a dedicated `GET /mapping-snapshots/{id}/trace` endpoint. Simplest first: include in full response and see if payload size is an issue.
- `adapter.model_id` may not be an attribute on the adapter protocol — check `AIAdapter` before referencing it. Fallback: omit `model_id` from the trace dict and use only `system_prompt`, `user_prompt`, `raw_response`.
- `project.constraints` might be `None` — guard with `or []`.
- Old snapshots (`ai_trace IS NULL`) must render gracefully — the "No AI trace available" fallback handles this.
- The PATCH hints route uses `get_central_team_user` dep — only operators can write hints.

## Tests

- No automated tests for the feed workspace page. Manual verification only.
- Backend: `propose_mapping` integration test (if one exists) should check that `mapping_snapshots.ai_trace` is populated post-call.

## Verification

1. Run `alembic upgrade head` — migration applies cleanly
2. Open feed workspace as `central_team` — "Mapping hints" textarea appears above field mappings
3. Type hints, click Save — no error; reload page and hints reappear
4. Click "Analyze with AI" — after completion, expand a table accordion → "AI reasoning" section is present with model, user message, and raw response
5. Old snapshots show "No AI trace available"
6. TypeScript compiles with no new errors

## Commit

- `feat(001br): add mapping hints field and AI trace to mapping snapshot`
