# Task 001br — AI Tracing and Mapping Hints

**Plan:** `plans/2026-07-07-001br-ai-tracing-and-mapping-hints.md`

## Context

When "Analyze with AI" runs, the raw AI exchange (prompt, response, model used) is discarded after the `MappingSnapshot` rows are created. Operators have no way to understand why the AI made a specific mapping decision. Additionally, source data often has encoding quirks (dates as `yyyymmdd` strings, leading-zero padded codes) that the AI gets wrong on first analysis. There is no mechanism to inject operator-supplied hints before re-analysis, and no way to carry those hints to the next project cycle.

## Scope

**Backend:**
- New Alembic migration `0025_feed_hints_and_ai_trace`:
  - `source_definitions.mapping_hints` — nullable `TEXT` column on `Feed`
  - `mapping_snapshots.ai_trace` — nullable `JSON` column on `MappingSnapshot`
- `propose_mapping` in `review.py`: append `mapping_hints` + project `constraints` to the user message before calling AI; store `{system_prompt, user_prompt, raw_response, model_id}` in `ai_trace` on each created snapshot
- New `PATCH /projects/{id}/sources/{feedId}/hints` route to save `mapping_hints` on a feed
- `MappingSnapshotResponse` and `list_approved_mapping_snapshots` route: include `ai_trace` in response

**Frontend:**
- Feed workspace: editable "Mapping hints" text area in the Field Mappings section header (loads from feed, saves on button click via new PATCH endpoint)
- Feed workspace: collapsible "AI reasoning" panel per table accordion (shows model used, the user message sent, and the raw AI response JSON)

## Out of Scope

- Lookup value mapping AI tracing (separate prompt/path)
- Prompt versioning / A-B testing infrastructure
- Project copy feature

## Acceptance Criteria

- `mapping_hints` typed in the feed workspace persists on the `Feed` row
- On re-analysis, hints appear appended to the user message in `ai_trace.user_prompt`
- The AI reasoning panel in the feed workspace shows the stored trace for each table
- Old snapshots (no `ai_trace`) show "No trace available" gracefully

## Pitfalls

- `ai_trace` can be large (full DDL + full AI response). Store on `mapping_snapshots`, not in the list-route response body by default — add a `include_trace=true` query param or fetch it on demand per table
- Project-level `constraints` and `assumptions` are `list[str]` — join them as a bullet list before appending to the user message
- `mapping_hints` carries forward when the project is copied (future task 001bt); no action needed now but the column design should not assume single-use

## Commit

- `feat(001br): add mapping hints field and AI trace to mapping snapshot`
