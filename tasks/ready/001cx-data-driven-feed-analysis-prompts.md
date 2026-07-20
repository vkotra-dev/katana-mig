# Task: 001cx — Data-Driven Feed Analysis Prompts + AI Log Viewer

## Status
Ready

## Background

The "Analyze with AI" flow makes three sequential AI calls — feed analysis, field mapping per fiber, and lookup value mapping. All three already log to the database, but the prompts only send column **headers** with no actual sample data. The AI guesses at data patterns, which produces zombie table mappings and spurious field bindings. The feed page also has no way to view what was sent to the AI or what came back.

## Goal

1. **Include sample CSV rows in all AI prompts** — load up to `sample_policy.max_rows` rows from the approved feed slice and pass them as the primary data signal, replacing the header-only approach.
2. **Rewrite all three system prompts** with explicit, rule-driven instructions that prevent zombie tables, spurious bindings, and ambiguous lookup matches.
3. **Tighten the Pydantic output schemas** — add `unmatched_columns`, `unmatched_source_fields`, `unmatched_source_values`, `sample_values` on lookups, and `binding_type` + `reference_table_name` on field bindings (aligning `fibers.py` with what `review.py` already produces).
4. **Tag the step-1 feed-analysis log** with `artifact_id = feed.source_definition_id` so it is queryable by feed.
5. **Add AI log viewer to the feed page** — collapsible panel per fiber showing model ID, system prompt, user prompt, and raw response. Fetches from the existing `GET /projects/{id}/ai-calls?artifact_id=` endpoint.

## Expected JSON Output Shapes

**Feed analysis:**
```json
{
  "lookups": [{"column_name": "STATUS_CODE", "lookup_name": "status_lkp", "sample_values": ["A","I","P"]}],
  "domain_objects": [{"destination_table": "customer"}],
  "unmatched_columns": ["INTERNAL_SEQ", "BATCH_DATE"]
}
```

**Field mapping:**
```json
{
  "field_bindings": [
    {"source_field": "CUST_ID", "destination_field": "customer_id", "lookup_name": null, "binding_type": "direct", "reference_table_name": null, "destination_data_type": "INT"},
    {"source_field": "STATUS_CODE", "destination_field": "status_id", "lookup_name": "status_lkp", "binding_type": "lookup_fk", "reference_table_name": "status", "destination_data_type": "INT"}
  ],
  "unmatched_source_fields": ["INTERNAL_SEQ", "BATCH_DATE"]
}
```

**Lookup mapping:**
```json
{
  "proposals": [
    {"source_value": "A", "dest_entry_id": "entry-1", "confidence_score": 0.98}
  ],
  "unmatched_source_values": ["X"]
}
```

## Files Changed

- `engine/src/migrations_engine/management/fibers.py` — sample rows, rewritten prompts, tightened schemas, step-1 artifact tag
- `web/lib/feeds-api.ts` (or new `web/lib/ai-calls-api.ts`) — `listAiCallLogs` client function
- `web/app/projects/[id]/feeds/[feedId]/page.tsx` — fetch logs after analyze/lookup submit, render collapsible AI log panel

## Plan

[2026-07-20-001cx-data-driven-feed-analysis-prompts.md](../../plans/2026-07-20-001cx-data-driven-feed-analysis-prompts.md)

## Verification

1. After "Analyze with AI": `ai_call_log` rows have `artifact_id` populated and user prompts contain CSV rows.
2. `GET /projects/{id}/ai-calls?artifact_id={feedId}` returns step-1 log.
3. `GET /projects/{id}/ai-calls?artifact_id={fiberId}` returns field-mapping log.
4. Feed page shows collapsible AI log panel per fiber after analyze completes.
5. Lookup mapping log appears after lookup inputs are submitted.
6. `unmatched_*` fields populated in AI responses.
7. `pytest engine/tests/ -x -q` passes.
