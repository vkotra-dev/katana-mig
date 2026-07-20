# Task 001da: Dedicated AI Log Viewer (hook + component), wired into Feed and Codegen pages

## Objective
Replace the per-page, hand-duplicated AI-log grid/modal pattern with one
reusable hook + viewer component, parameterized by `feature`/`callType`/
`artifactId`, and wire it into both the Feed Detail page and the Codegen
page. Builds on task 001cz's `feature` taxonomy and pagination.

## Requirements

1. **`useAiCallLogs(projectId, filter)` hook** (`web/lib/` or
   `web/hooks/`) — `filter: { feature: "feed_mapping" | "codegen";
   callType?: string; artifactId?: string }`. Fetches via
   `listAiCallLogs` (extended for `feature` + pagination per 001cz),
   returns `{ logs, loading, error, hasMore, loadMore }`.
2. **`AiLogViewer` component** (`web/components/ai-logs/`) — table
   (Call Type, Model ID, Timestamp, error indicator, Inspect) +
   inspect modal (tabs: System Prompt / User Prompt / Raw JSON, copy
   with feedback, `break-words` preserved), built on the hook. Replaces
   the `AiLogTable`/`AiLogInspectModal` split originally designed for
   001cy — same behavior, now feature/hook-driven instead of
   per-page-duplicated.
3. **Feed Detail page**: replace the in-progress inline grid/modal
   (currently uncommitted in `page.tsx`, covering `feed_analysis` and
   `lookup_mapping` only) with `<AiLogViewer feature="feed_mapping" .../>`
   instances, scoped per artifact as before (feed-level, per
   domain_object fiber, per lookup fiber) — plus a new instance per
   destination-object table card scoped to `call_type=mapping,
   artifactId=mappingSnapshotId`, and one for `call_type=source_analysis,
   artifactId=feedId` (now visible for the first time, per 001cz's fix).
   Delete the legacy "AI Trace & Reasoning" `<details>` panel
   (`page.tsx:951-989`) — the new `mapping`-scoped viewer instance
   replaces it.
4. **Codegen page**: replace the current inline modal (reads
   `compiledSystemPrompt` etc. directly) with
   `<AiLogViewer feature="codegen" callType="codegen"
   artifactId={artifact.codegenArtifactId} />`. Add a project/feed
   filter control above the artifact table, using the new `feed_id`
   column (001cz) — "All feeds" (current behavior) vs. one specific feed,
   to make it easier to locate a specific feed's generated SQL when a
   project has many feeds.
5. Preserve the `central_team`/`admin` role gate on every viewer
   instance, matching current behavior on both pages.

## Out of Scope
- `schema_analysis` gets no dedicated viewer instance in this task (it's
  project-wide with no natural per-row anchor on the Codegen page today)
  — can be added later if needed.
- Dropping the legacy columns the old Codegen modal read from — 001db.
- Any backend change beyond what 001cz already ships.

## Dependencies
Requires 001cz (feature taxonomy, pagination, `feed_id` on
`CodeGenerationArtifact`) to be complete first.
