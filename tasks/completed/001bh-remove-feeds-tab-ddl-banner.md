# Task 001bh — Remove Schema Analysis Banner from Feeds Tab

**Plan:** `plans/2026-07-05-001bh-remove-feeds-tab-ddl-banner.md`

## Current State

`web/components/projects/SourceList.tsx` renders a schema analysis banner above the feed list. The banner shows "Analyze DDL" or "Re-analyze DDL" and calls `triggerSchemaAnalysis` — a project-level operation that analyzes the destination DDL for FK dependency ordering of the SQL delivery bundle.

The SQL bundle page (`/projects/[id]/codegen`) already owns this action: it shows the same schema dependency analysis panel with an "Re-analyze DDL" button. The banner in the Feeds tab is a duplicate entry point that does not belong there.

## Problem

The per-feed mapping proposal (001bd) is the correct entry point for AI analysis in the Feeds workspace — it receives the feed's PII-masked slice data alongside the DDL and runs per-feed. The project-level schema analysis banner implies DDL analysis is a prerequisite for feed work, which is misleading. It also pollutes `SourceList` with state and imports that have nothing to do with the feed list itself.

## Scope

Remove from `web/components/projects/SourceList.tsx`:
- The analysis banner JSX (lines ~132–168: loading state, error alert, and the banner panel with Analyze/Re-analyze button)
- `analysis` state and `setAnalysis`
- `analysisLoading` state and `setAnalysisLoading`
- `analysisErrorMessage` state and `setAnalysisErrorMessage`
- `analysisActionLoading` state and `setAnalysisActionLoading`
- The `useEffect` that calls `getSchemaAnalysis`
- The `handleAnalyze` function
- Imports: `getSchemaAnalysis`, `triggerSchemaAnalysis`, `SchemaAnalysisRecord` from `../../lib/codegen-api`
- `destinationSchemaDdl` prop from `SourceListProps` (used only by the banner)

Remove the `destinationSchemaDdl` prop pass-through from `web/app/projects/[id]/page.tsx`:
- Remove `destinationSchemaDdl={project?.domainConfig?.destinationSchemaDdl ?? null}` from the `<SourceList>` call

Update `web/components/projects/__tests__/SourceList.test.tsx`:
- Remove any tests that assert the DDL analysis banner, Analyze DDL button, or `destinationSchemaDdl` prop behaviour

## Out of Scope

- Changing the SQL bundle page — it retains its DDL analysis panel unchanged.
- Any changes to the `getSchemaAnalysis` or `triggerSchemaAnalysis` API functions.
- The per-feed mapping proposal button — that lives in the Feed Detail workspace (already delivered in 001bf).

## Acceptance Criteria

- The Feeds tab shows only the feed list with no schema analysis banner above it.
- `SourceList` has no imports from `codegen-api`.
- `SourceListProps` has no `destinationSchemaDdl` field.
- The SQL bundle page DDL analysis panel is unchanged.
- All remaining `SourceList` tests pass.

## Pitfalls

- `destinationSchemaDdl` is passed from `page.tsx` — removing it from `SourceListProps` will cause a TypeScript error at the call site if not cleaned up simultaneously.
- Confirm no other consumer passes `destinationSchemaDdl` to `SourceList` before removing the prop.

## Commit

- `fix(001bh): remove schema analysis banner from feeds tab`
