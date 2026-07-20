# Plan: 001da — Dedicated AI Log Viewer (hook + component)

## Task and Domain links

- Task: `tasks/001da-ai-log-viewer.md`
- Domain: `docs/domain/ui.md` — Feed Detail workspace (items 4, 5, 7) and
  Codegen page (not yet documented as its own item — check before
  editing whether it needs one added)

## Current State

- Task 001cz (must land first) adds `feature`/pagination to
  `GET /projects/{id}/ai-calls` and `feed_id` to
  `CodeGenerationArtifact`.
- The Feed Detail page (`page.tsx`) currently has an **uncommitted**,
  in-progress inline grid+modal for `feed_analysis`/`lookup_mapping`
  only (3 duplicated table blocks, one modal), plus the legacy "AI Trace
  & Reasoning" `<details>` panel (`page.tsx:951-989`) reading
  `snapshot.aiTrace` directly — the only current surface for the
  `mapping` call type. `source_analysis` has no UI surface at all today.
- The Codegen page (`codegen/page.tsx:927-1020`) has its own
  independently hand-rolled modal reading
  `inspectingArtifact.compiledSystemPrompt`/`compiledUserPrompt`/
  `rawLlmResponse` directly — not `ai_call_log`.
- `AICallLogRecord` (`web/lib/ai-calls-api.ts`) gains a `feature` field
  in 001cz.

## Objective

1. `useAiCallLogs(projectId, filter)` hook, paginated, feature/callType/
   artifactId-filterable.
2. `AiLogViewer` component (table + inspect modal) built on the hook.
3. Feed page: replace the inline grid/modal and the legacy "AI Trace &
   Reasoning" panel with `AiLogViewer` instances covering all 4
   `feed_mapping` call types.
4. Codegen page: replace the inline modal with an `AiLogViewer` instance
   sourced from `ai_call_log`; add a project/feed filter on the artifact
   table using `feed_id`.

## Out of Scope

- No `schema_analysis` viewer instance (no natural per-row anchor on the
  Codegen page's project-wide "Analyze DDL" step).
- Dropping the legacy columns the old Codegen modal used to read —
  001db, after this task's Codegen change is verified as the last
  reader.
- Any further backend change beyond what 001cz already ships.

## Blast Radius

- `web/lib/ai-hooks.ts` or `web/hooks/useAiCallLogs.ts` (new)
- `web/components/ai-logs/AiLogViewer.tsx` (new)
- `web/components/ai-logs/__tests__/AiLogViewer.test.tsx` (new)
- `web/app/projects/[id]/feeds/[feedId]/page.tsx` (edited — replace
  inline grid/modal + delete "AI Trace & Reasoning" panel)
- `web/app/projects/[id]/feeds/[feedId]/page.test.tsx` (edited)
- `web/app/projects/[id]/codegen/page.tsx` (edited — replace inline
  modal, add feed filter)
- `web/app/projects/[id]/codegen/page.test.tsx` (edited)
- `docs/domain/ui.md` (edited)
- `scratch.py` (deleted — stray file from earlier session, still present, unrelated to this task's scope but flagged for cleanup here since it's still sitting in the repo root)
- No role-gating change — `central_team`/`admin` gate preserved on every
  `AiLogViewer` instance.

## File Changes

**`web/hooks/useAiCallLogs.ts` (new)**
- `useAiCallLogs(projectId, { feature, callType?, artifactId? })` →
  `{ logs, loading, error, hasMore, loadMore }`. Wraps
  `listAiCallLogs` (001cz's extended version), re-fetches when any filter
  argument changes, paginates via `limit`/`offset`.

**`web/components/ai-logs/AiLogViewer.tsx` (new)**
- Props: `projectId: string`, `feature: "feed_mapping" | "codegen"`,
  `callType?: string`, `artifactId?: string`, `emptyLabel?: string`.
- Internally: calls `useAiCallLogs`, renders the table (Call Type, Model
  ID, Timestamp, error indicator, Inspect) sorted newest-first, and the
  inspect modal (tabs: System Prompt / User Prompt / Raw JSON, copy with
  "Copied!"/"Copy failed" feedback, `break-words` preserved). Modal state
  keyed by `callId` (not object reference) so it can't show stale data if
  the underlying list refetches.
- This supersedes the `AiLogTable`/`AiLogInspectModal` split originally
  drafted for 001cy — same UI behavior, collapsed into one
  hook-driven component so every call site is a single `<AiLogViewer
  feature=... callType=... artifactId=... />` line instead of
  hand-wired fetch/state per page.

**`web/app/projects/[id]/feeds/[feedId]/page.tsx`**
- Delete the 3 duplicated inline table/modal blocks and their
  `inspectingAiLog`/`inspectAiActiveTab`/`expandedAiLogs`/`fiberAiLogs`
  state (all superseded by `AiLogViewer` owning its own fetch/state via
  the hook).
- Delete the "AI Trace & Reasoning" `<details>` panel (`page.tsx:951-989`)
  and its `snapshot?.aiTrace` guard.
- Add `<AiLogViewer feature="feed_mapping" callType="source_analysis"
  artifactId={feedId} />` (new — first UI surface for this call type),
  `callType="feed_analysis" artifactId={feedId}` (feed-level),
  `callType="feed_analysis" artifactId={fiber.fiberId}` (per
  domain_object fiber), `callType="mapping"
  artifactId={snapshot.mappingSnapshotId}` (per destination-object table
  card, replacing the deleted panel), `callType="lookup_mapping"
  artifactId={fiber.fiberId}` (per lookup fiber).
- `handleAnalyzeWithAi` no longer needs its manual `listAiCallLogs`
  refresh loop (`page.tsx:234-259`) — each `AiLogViewer` instance fetches
  its own data on mount/filter-change via the hook, so a re-render after
  analysis (triggered by the existing `loadAllData()` call) is enough to
  pick up new logs. This also resolves the lookup-fiber-logs-on-main-
  button gap from the original 001cy scope, without needing the bespoke
  fetch-loop extension that was planned there — the lookup fiber's
  `AiLogViewer` instance just fetches on its own whenever it's visible.

**`web/app/projects/[id]/codegen/page.tsx`**
- Replace the inline modal (~lines 927-1020) with
  `<AiLogViewer feature="codegen" callType="codegen"
  artifactId={inspectingArtifact.codegenArtifactId} />`, triggered the
  same way (Inspect button sets `inspectingArtifact`).
- Add a feed filter control above the artifact table: a `<select>`
  populated from the distinct `feedId` values present in `artifacts`
  (client-side, no new endpoint needed), defaulting to "All feeds";
  filters the rendered `artifacts` list by `artifact.feedId` when set.

**`docs/domain/ui.md`**
- Item 7: describe the unified `AiLogViewer`, all 5 UI-surfaced call
  types (`source_analysis`, `feed_analysis`, `mapping`,
  `lookup_mapping` on the Feed page; `codegen` on the Codegen page).
- Add the feed filter to the Codegen page's description (check whether
  Codegen has its own numbered item in `ui.md` today — add one if not).
- Bump `timestamp`, add a changelog line.

## Tests

- `useAiCallLogs.test.ts`: fetches on mount with the given filter,
  re-fetches on filter change, paginates via `loadMore`.
- `AiLogViewer.test.tsx`: renders sorted rows, error indicator, tab
  switching, copy feedback, empty-state message, modal doesn't show stale
  data after the underlying list changes.
- `page.test.tsx` (Feed): remove/replace tests asserting the old
  `<details>`-based structure and the `"AI Trace & Reasoning"` text
  (`page.test.tsx:284-302`); add coverage for at least one
  `AiLogViewer` instance rendering.
- `page.test.tsx` (Codegen): remove/replace tests asserting the old
  inline-modal structure and `compiledSystemPrompt` fixtures
  (`codegen/page.test.tsx:357-359`); add coverage for the feed filter.

## Verification

- `web/` typechecks clean.
- Manual: Feed Detail page as `central_team` — all 5 grid instances
  (source_analysis, feed_analysis x2 keys, mapping, lookup_mapping)
  render correctly with real data after running "AI Analyze" and a
  lookup's own "AI Analyze".
- Manual: old "AI Trace & Reasoning" panel is gone; the same content is
  visible via the new `mapping`-scoped viewer instance instead.
- Manual: Codegen page's Inspect button opens the new viewer with
  correct content; feed filter narrows the artifact table correctly.
- `docs/domain/ui.md` updated.

## Pitfalls

- Don't let `AiLogViewer` accept a raw log object for its modal state —
  key by `callId` and re-derive from the hook's current `logs` each
  render, so a background refetch can't leave it showing stale content
  (this was a confirmed bug in the original 001cy draft).
- The Feed page currently gates the AI-log UI behind
  `role === "central_team" || role === "admin"` in several places — make
  sure every new `AiLogViewer` placement stays behind that same check,
  not just the ones that had it in the deleted draft.
- `handleAnalyzeWithAi`'s existing fetch-and-store-into-state pattern for
  AI logs is being deleted, not just extended — make sure nothing else in
  `page.tsx` still reads the old `fiberAiLogs` state after this change
  (grep for it before removing the state declaration).
- `scratch.py` cleanup: still present in the repo root from earlier this
  session — remove it as part of this task's diff since it's unrelated
  clutter sitting in a directory this task is already touching.

## Commit

Own commit, second of three. Requires 001cz merged/landed first.
