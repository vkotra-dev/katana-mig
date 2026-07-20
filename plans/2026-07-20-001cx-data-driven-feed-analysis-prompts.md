# Data-Driven Feed Analysis Prompts + AI Log Viewer — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace header-only AI prompts in the feed analysis flow with sample-data-driven prompts, rewrite all three system prompts with explicit rules, tighten output schemas, and add a collapsible AI call log panel to the feed page.

**Architecture:** Backend changes are confined to `fibers.py` — import three CSV helpers from `source_analysis.py` and update the two user prompts and the three system prompts in `analyze_feed` and `submit_lookup_inputs`. Frontend adds an `listAiCallLogs` API client function and a collapsible log panel per fiber on the feed page. The existing `GET /projects/{id}/ai-calls?artifact_id=` route is used as-is.

**Tech Stack:** Python / SQLAlchemy / Pydantic (backend), TypeScript / Next.js / React (frontend).

## Global Constraints

- Do not change `source_analysis.py`, `review.py`, codegen templates, or any route file.
- `_load_slice_rows`, `_build_sample_text`, `_parse_csv_row` live in `source_analysis.py` — import them, do not duplicate.
- Masking must be applied to sample rows before they enter the prompt (same pattern as `source_analysis.py` lines 76–83).
- Frontend log panel is visible to `central_team` and `admin` roles only (the existing API already enforces this; just don't render the fetch/panel for other roles).
- No new DB migrations — no schema changes.

---

## File Map

| File | Action | Purpose |
|---|---|---|
| `engine/src/migrations_engine/management/fibers.py` | Modify | Sample rows, rewritten prompts, tightened schemas, step-1 artifact tag |
| `engine/tests/test_fiber_ai_flow.py` | Modify | Update tests for new schema fields + assert sample text in prompt |
| `web/lib/ai-calls-api.ts` | Create | `listAiCallLogs` API client |
| `web/app/projects/[id]/feeds/[feedId]/page.tsx` | Modify | Fetch logs after analyze, render collapsible AI log panel |

---

### Task 1: Backend — tighten schemas, rewrite prompts, inject sample data

**Files:**
- Modify: `engine/src/migrations_engine/management/fibers.py`
- Modify: `engine/tests/test_fiber_ai_flow.py`

**Interfaces:**
- Produces: `_FeedAnalysisResult` gains `unmatched_columns: list[str] = []`; `_LookupIdentified` gains `sample_values: list[str] = []`; `_FieldMappingResult` gains `unmatched_source_fields: list[str] = []`; `_FieldBinding` gains `binding_type` and `reference_table_name`.
- `analyze_feed` user prompts now contain CSV sample rows, not just headers.
- `call_log1.call_id` is backfilled with `feed.source_definition_id` as artifact_id.

- [ ] **Step 1: Add imports from source_analysis**

In `engine/src/migrations_engine/management/fibers.py`, add after existing imports (around line 48):

```python
from ..management.source_analysis import (
    _build_sample_text,
    _load_slice_rows,
    _parse_csv_row,
)
```

- [ ] **Step 2: Update Pydantic schemas**

In `fibers.py`, replace the four Pydantic model classes (currently around lines 60–100):

```python
from typing import Literal

class _LookupIdentified(BaseModel):
    column_name: str
    lookup_name: str
    sample_values: list[str] = []


class _DomainObject(BaseModel):
    destination_table: str


class _FeedAnalysisResult(BaseModel):
    lookups: list[_LookupIdentified]
    domain_objects: list[_DomainObject]
    unmatched_columns: list[str] = []


class _FieldBinding(BaseModel):
    source_field: str | None
    destination_field: str
    lookup_name: str | None
    binding_type: Literal["direct", "lookup_fk", "detail_fk"] = "direct"
    reference_table_name: str | None = None
    destination_data_type: str | None = None


class _FieldMappingResult(BaseModel):
    field_bindings: list[_FieldBinding]
    unmatched_source_fields: list[str] = []


class _LookupProposal(BaseModel):
    source_value: str
    dest_entry_id: str
    confidence_score: float


class _LookupMappingResult(BaseModel):
    proposals: list[_LookupProposal]
    unmatched_source_values: list[str] = []
```

- [ ] **Step 3: Rewrite the three system prompt constants**

Replace `_FEED_ANALYSIS_SYSTEM`, `_FIELD_MAPPING_SYSTEM`, and `_LOOKUP_MAPPING_SYSTEM_PROMPT` (currently around lines 72–88):

```python
_FEED_ANALYSIS_SYSTEM = (
    "You are a data migration analyst. Given CSV sample data and a destination schema DDL, "
    "identify which destination tables this feed populates and which source columns are lookup "
    "references.\n\n"
    "Rules:\n"
    "- Only include a destination table if at least two source columns map directly to its "
    "non-FK columns. Do not include tables that would only receive FK values resolved at runtime.\n"
    "- A source column is a lookup if it has low cardinality (few distinct values visible in "
    "the sample) and its values reference a reference/code table rather than being free-form data. "
    "Set sample_values to the distinct values you observe in the sample.\n"
    "- List source columns that do not belong to any identified table in unmatched_columns.\n"
    "- Return valid JSON matching the schema."
)

_FIELD_MAPPING_SYSTEM = (
    "You are a data migration specialist. Given CSV sample data, a target destination table, "
    "and the full destination schema DDL, map each source column to its destination column.\n\n"
    "Rules:\n"
    "- Only create a binding where a source column has a clear correspondence to a destination "
    "column. Do not invent bindings for auto-generated PKs, identity columns, or audit columns "
    "(created_at, updated_at, modified_by, created_by).\n"
    "- Classify each binding: 'direct' | 'lookup_fk' | 'detail_fk'.\n"
    "- For lookup_fk and detail_fk, set reference_table_name to the referenced table name "
    "(required — never null for these types).\n"
    "- Set destination_data_type to the exact SQL type from the DDL "
    "(e.g. 'INT', 'NVARCHAR(255)', 'DATE', 'DECIMAL(18,2)'). Null only if not in DDL.\n"
    "- List source columns with no mapping in unmatched_source_fields.\n"
    "- Return valid JSON matching the schema."
)

_LOOKUP_MAPPING_SYSTEM_PROMPT = (
    "You are a lookup value mapper. Given a list of source values from a migration feed and "
    "the candidate destination reference rows, propose the best match for each source value.\n\n"
    "Rules:\n"
    "- Match on semantic meaning, not just string equality. Abbreviations, codes, and full "
    "names that mean the same thing should match (e.g. 'A' -> 'Active', 'M' -> 'Male').\n"
    "- Set confidence_score between 0.0 and 1.0. Use < 0.5 only when the match is a best guess.\n"
    "- List source values with no confident match (score < 0.5) in unmatched_source_values.\n"
    "- Return valid JSON matching the schema."
)
```

- [ ] **Step 4: Load sample rows and build sample_text in `analyze_feed`**

In `analyze_feed` (around line 570, after `source_headers = _parse_header_csv(...)`), add:

```python
    _policy = feed.sample_policy or {}
    _limit = int(_policy.get("max_rows") or 10)
    raw_rows = _load_slice_rows(db, source_slice_id=approved_slice.source_slice_id, limit=_limit)
    if approved_slice.header_csv and raw_rows:
        from ..intake.masking import mask_row
        _headers = _parse_csv_row(approved_slice.header_csv)
        raw_rows = [mask_row(_headers, _parse_csv_row(r)) for r in raw_rows]
    sample_text = _build_sample_text(header_csv=approved_slice.header_csv, rows=raw_rows)
```

- [ ] **Step 5: Update the feed-analysis user prompt (step 1)**

Replace the `user_prompt = json.dumps({"source_headers": ..., "destination_schema_ddl": ...})` block with:

```python
    n_rows = len(raw_rows)
    user_prompt = (
        f"Feed: {feed.label}\n"
        f"Sample data ({n_rows} rows):\n"
        f"{sample_text}\n\n"
        f"Destination schema DDL:\n{destination_schema_ddl}"
    )
```

- [ ] **Step 6: Backfill step-1 call log with feed artifact_id**

After the `call_log1 = log_ai_call(...)` call (currently around line 593), add:

```python
        backfill_artifact_id(db, call_log1.call_id, feed.source_definition_id)
```

- [ ] **Step 7: Update the field-mapping user prompt (step 2)**

Replace the `user_prompt2 = json.dumps({"source_columns": ..., "destination_table": ..., "destination_schema_ddl": ...})` block with:

```python
        user_prompt2 = (
            f"Feed: {feed.label}\n"
            f"Target table: {fiber.fiber_key}\n"
            f"Sample data ({n_rows} rows):\n"
            f"{sample_text}\n\n"
            f"Destination schema DDL:\n{destination_schema_ddl}"
        )
```

- [ ] **Step 8: Update existing tests to match new schemas**

In `engine/tests/test_fiber_ai_flow.py`, update the `_FeedAnalysisResult` and `_FieldBinding` usages to include the new optional fields (they default so existing calls still work), and add two new assertions:

```python
def test_analyze_feed_user_prompt_contains_sample_text(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """User prompt sent to the feed-analysis adapter must contain sample CSV rows."""
    from migrations_engine.management.fibers import (
        _DomainObject,
        _FeedAnalysisResult,
        _FieldBinding,
        _FieldMappingResult,
        _LookupIdentified,
        analyze_feed,
    )
    from migrations_engine.db.models import FeedSliceRow

    fake_get_adapter, feed_adapter, _ = _make_fake_get_adapter(
        _FeedAnalysisResult(
            lookups=[],
            domain_objects=[_DomainObject(destination_table="customers")],
        ),
        _FieldMappingResult(field_bindings=[
            _FieldBinding(source_field="CUST_ID", destination_field="id", lookup_name=None),
        ]),
    )
    monkeypatch.setattr("migrations_engine.management.fibers.get_adapter", fake_get_adapter)

    project_id, feed_id = _seed_feed_with_slice(header_csv="CUST_ID,ACCT_TYPE")

    # Seed one sample row
    with SessionLocal() as db:
        slice_row = db.scalar(
            select(FeedSlice).where(FeedSlice.source_definition_id == feed_id)
        )
        db.add(FeedSliceRow(
            source_slice_id=slice_row.source_slice_id,
            row_index=0,
            row_csv="C001,SAVINGS",
        ))
        db.commit()

    with SessionLocal() as db:
        actor = db.scalar(select(User).where(User.role == CENTRAL_TEAM_ROLE))
        analyze_feed(db, feed_id=feed_id, project_id=project_id, actor=actor)

    assert len(feed_adapter.calls) == 1
    prompt = feed_adapter.calls[0].user
    assert "C001" in prompt, "Sample row data must appear in the user prompt"
    assert "CUST_ID" in prompt, "Header must appear in the user prompt"


def test_analyze_feed_step1_log_tagged_with_feed_artifact_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The step-1 AI call log must be backfilled with the feed's source_definition_id."""
    from migrations_engine.management.fibers import (
        _DomainObject,
        _FeedAnalysisResult,
        _FieldBinding,
        _FieldMappingResult,
        _LookupIdentified,
        analyze_feed,
    )
    from migrations_engine.db.models import AICallLog

    fake_get_adapter, _, _ = _make_fake_get_adapter(
        _FeedAnalysisResult(lookups=[], domain_objects=[_DomainObject(destination_table="customers")]),
        _FieldMappingResult(field_bindings=[
            _FieldBinding(source_field="CUST_ID", destination_field="id", lookup_name=None),
        ]),
    )
    monkeypatch.setattr("migrations_engine.management.fibers.get_adapter", fake_get_adapter)

    project_id, feed_id = _seed_feed_with_slice()

    with SessionLocal() as db:
        actor = db.scalar(select(User).where(User.role == CENTRAL_TEAM_ROLE))
        analyze_feed(db, feed_id=feed_id, project_id=project_id, actor=actor)
        feed_analysis_log = db.scalar(
            select(AICallLog)
            .where(AICallLog.artifact_id == feed_id, AICallLog.call_type == "feed_analysis")
        )
    assert feed_analysis_log is not None, "Step-1 log must be tagged with feed_id as artifact_id"
```

- [ ] **Step 9: Run backend tests**

```bash
cd engine && pytest tests/test_fiber_ai_flow.py -v 2>&1 | tail -20
```

Expected: all tests pass including the two new ones.

- [ ] **Step 10: Commit**

```bash
git add engine/src/migrations_engine/management/fibers.py engine/tests/test_fiber_ai_flow.py
git commit -m "feat: data-driven prompts for feed analysis — sample rows, rewritten system prompts, tightened schemas (001cx)"
```

---

### Task 2: Frontend — AI call log API client

**Files:**
- Create: `web/lib/ai-calls-api.ts`

**Interfaces:**
- Produces: `AICallLogRecord` interface and `listAiCallLogs(token, projectId, options?) => Promise<AICallLogRecord[]>`
- Consumes: existing API route `GET /projects/{projectId}/ai-calls` with optional `?call_type=&artifact_id=` query params

- [ ] **Step 1: Create `web/lib/ai-calls-api.ts`**

```typescript
import { API_BASE_URL } from "./api-base";

export interface AICallLogRecord {
  callId: string;
  callType: string;
  artifactId: string | null;
  modelId: string;
  systemPrompt: string;
  userPrompt: string;
  rawResponse: string | null;
  errorDetail: string | null;
  calledAt: string;
}

export async function listAiCallLogs(
  token: string,
  projectId: string,
  options?: { callType?: string; artifactId?: string }
): Promise<AICallLogRecord[]> {
  const params = new URLSearchParams();
  if (options?.callType) params.set("call_type", options.callType);
  if (options?.artifactId) params.set("artifact_id", options.artifactId);
  const qs = params.toString();
  const url = `${API_BASE_URL}/projects/${projectId}/ai-calls${qs ? `?${qs}` : ""}`;
  const res = await fetch(url, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) throw new Error(`Failed to fetch AI call logs: ${res.status}`);
  const data: Array<{
    call_id: string;
    call_type: string;
    artifact_id: string | null;
    model_id: string;
    system_prompt: string;
    user_prompt: string;
    raw_response: string | null;
    error_detail: string | null;
    called_at: string;
  }> = await res.json();
  return data.map((r) => ({
    callId: r.call_id,
    callType: r.call_type,
    artifactId: r.artifact_id,
    modelId: r.model_id,
    systemPrompt: r.system_prompt,
    userPrompt: r.user_prompt,
    rawResponse: r.raw_response,
    errorDetail: r.error_detail,
    calledAt: r.called_at,
  }));
}
```

- [ ] **Step 2: Verify TypeScript compiles**

```bash
cd web && npx tsc --noEmit 2>&1 | head -20
```

Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add web/lib/ai-calls-api.ts
git commit -m "feat: add listAiCallLogs API client (001cx)"
```

---

### Task 3: Frontend — collapsible AI log panel on feed page

**Files:**
- Modify: `web/app/projects/[id]/feeds/[feedId]/page.tsx`

**Interfaces:**
- Consumes: `listAiCallLogs` from `web/lib/ai-calls-api.ts` (Task 2)
- Consumes: `AICallLogRecord` interface
- Produces: collapsible AI log section below each fiber card; visible for `central_team` / `admin` roles

- [ ] **Step 1: Import listAiCallLogs and add state**

At the top of `page.tsx`, add the import alongside existing lib imports:

```typescript
import { listAiCallLogs, type AICallLogRecord } from "../../../../lib/ai-calls-api";
```

Inside the component, add state alongside the existing `lookupDrafts` state (around line 63):

```typescript
const [fiberAiLogs, setFiberAiLogs] = useState<Record<string, AICallLogRecord[]>>({});
const [expandedAiLogs, setExpandedAiLogs] = useState<Set<string>>(new Set());
```

- [ ] **Step 2: Add toggleAiLog helper**

After `toggleTable` (around line 424), add:

```typescript
const toggleAiLog = (key: string) => {
  setExpandedAiLogs((prev) => {
    const next = new Set(prev);
    if (next.has(key)) next.delete(key); else next.add(key);
    return next;
  });
};
```

- [ ] **Step 3: Fetch AI logs after analyze completes**

In `handleAnalyze` (around line 228, after `await loadAllData(session.accessToken)`), add log fetching for central_team/admin only:

```typescript
      await loadAllData(session.accessToken);
      // Fetch AI call logs for each fiber (central_team/admin only)
      if (role === "central_team" || role === "admin") {
        try {
          const feedLog = await listAiCallLogs(session.accessToken, projectId, {
            callType: "feed_analysis",
            artifactId: feedId,
          });
          const nextLogs: Record<string, AICallLogRecord[]> = { [feedId]: feedLog };
          // Per-fiber field-mapping logs
          const refreshedFibers = await listFeedFibers(session.accessToken, projectId, feedId);
          await Promise.all(
            refreshedFibers
              .filter((f) => f.fiberType === "domain_object")
              .map(async (f) => {
                const logs = await listAiCallLogs(session.accessToken, projectId, {
                  callType: "feed_analysis",
                  artifactId: f.fiberId,
                });
                nextLogs[f.fiberId] = logs;
              })
          );
          setFiberAiLogs((prev) => ({ ...prev, ...nextLogs }));
        } catch {
          // AI log fetch is best-effort; don't block the page
        }
      }
```

- [ ] **Step 4: Fetch lookup mapping log after lookup submit**

In `handleLookupSubmit` (or the lookup inputs submit handler, currently around line 362), after the fiber list is refreshed, add:

```typescript
      if (role === "central_team" || role === "admin") {
        try {
          const logs = await listAiCallLogs(session.accessToken, projectId, {
            callType: "lookup_mapping",
            artifactId: targetFiberId,
          });
          setFiberAiLogs((prev) => ({ ...prev, [targetFiberId]: logs }));
        } catch {
          // best-effort
        }
      }
```

- [ ] **Step 5: Render collapsible AI log panel per fiber**

In the fiber card rendering section (wherever each fiber is rendered in the return JSX, after its existing content), add the AI log panel. Find the closing tag of the fiber card content and insert before it:

```tsx
{/* AI Prompt Logs */}
{(role === "central_team" || role === "admin") &&
  fiberAiLogs[fiber.fiberId] &&
  fiberAiLogs[fiber.fiberId].length > 0 && (
    <div className="mt-3 border-t border-outline-variant pt-3">
      <button
        onClick={() => toggleAiLog(fiber.fiberId)}
        className="flex items-center gap-1 text-xs text-slate-500 hover:text-slate-700"
      >
        <svg
          className={`w-3 h-3 transition-transform ${expandedAiLogs.has(fiber.fiberId) ? "rotate-180" : ""}`}
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
        >
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
        AI Prompt Log ({fiberAiLogs[fiber.fiberId].length})
      </button>
      {expandedAiLogs.has(fiber.fiberId) && (
        <div className="mt-2 space-y-3">
          {fiberAiLogs[fiber.fiberId].map((log) => (
            <div key={log.callId} className="rounded border border-outline-variant bg-surface p-2 text-xs">
              <div className="mb-1 font-mono text-slate-500">
                {log.callType} · {log.modelId} · {new Date(log.calledAt).toLocaleString()}
              </div>
              {log.errorDetail && (
                <div className="mb-1 text-red-600">Error: {log.errorDetail}</div>
              )}
              <details className="mb-1">
                <summary className="cursor-pointer text-slate-600 hover:text-slate-900">System prompt</summary>
                <pre className="mt-1 overflow-x-auto whitespace-pre-wrap break-words rounded bg-surface-container p-2 font-mono text-[10px] text-slate-700">
                  {log.systemPrompt}
                </pre>
              </details>
              <details className="mb-1">
                <summary className="cursor-pointer text-slate-600 hover:text-slate-900">User prompt</summary>
                <pre className="mt-1 overflow-x-auto whitespace-pre-wrap break-words rounded bg-surface-container p-2 font-mono text-[10px] text-slate-700">
                  {log.userPrompt}
                </pre>
              </details>
              {log.rawResponse && (
                <details>
                  <summary className="cursor-pointer text-slate-600 hover:text-slate-900">Raw response</summary>
                  <pre className="mt-1 overflow-x-auto whitespace-pre-wrap break-words rounded bg-surface-container p-2 font-mono text-[10px] text-slate-700">
                    {log.rawResponse}
                  </pre>
                </details>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )}
```

Also add the feed-level step-1 log — render it at the top of the fiber section (before the individual fiber cards), using `fiberAiLogs[feedId]` and key `feedId` in `expandedAiLogs`.

- [ ] **Step 6: TypeScript check**

```bash
cd web && npx tsc --noEmit 2>&1 | head -20
```

Expected: no errors.

- [ ] **Step 7: Commit**

```bash
git add web/app/projects/\[id\]/feeds/\[feedId\]/page.tsx
git commit -m "feat: AI call log viewer panel on feed page (001cx)"
```
