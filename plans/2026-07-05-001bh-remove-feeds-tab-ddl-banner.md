# Plan: 001bh — Remove Schema Analysis Banner from Feeds Tab

- **Task Link:** [001bh-remove-feeds-tab-ddl-banner.md](file:///Users/vjkotra/projects/katana/tasks/001bh-remove-feeds-tab-ddl-banner.md)
- **Domain Link:** [ui.md](file:///Users/vjkotra/projects/katana/docs/domain/ui.md)

## Current State

- `web/components/projects/SourceList.tsx` renders a schema analysis banner above the feed list.
- It fetches and displays the project-level DDL dependency sequence using `getSchemaAnalysis` and allows triggering/re-triggering analysis.
- The project detail page `web/app/projects/[id]/page.tsx` passes `destinationSchemaDdl` to `<SourceList>`.
- The SQL bundle page (`web/app/projects/[id]/codegen/page.tsx`) already has the dedicated interface for this DDL dependency analysis.

## Objective

Remove the duplicate schema analysis banner entry point from the Feeds tab, decoupling the feed list component from DDL analysis states, actions, and dependency parameters.

## Out of Scope

- Modifying the dependency analysis sequence generation or execution backends.
- Modifying the SQL bundle page.

## Blast Radius

Minimal. Only affects the Feeds tab interface.

## File Changes

### `web/components/projects/SourceList.tsx`

- Remove imports from `../../lib/codegen-api`.
- Remove `destinationSchemaDdl` from `SourceListProps`.
- Remove analysis states (`analysis`, `analysisLoading`, `analysisErrorMessage`, `analysisActionLoading`).
- Remove `handleAnalyze` and `useEffect` fetch logic.
- Remove banner render JSX block.

### `web/app/projects/[id]/page.tsx`

- Remove `destinationSchemaDdl={...}` prop from `<SourceList>`.

### `web/components/projects/__tests__/SourceList.test.tsx`

- Remove DDL banner test suites.

## Tests

- Run `npm test` to verify all remaining tests pass.

## Verification

- Confirm clean TypeScript compilation.

## Pitfalls

- Ensure that removing `destinationSchemaDdl` from `SourceListProps` is synchronized with the caller `page.tsx` to prevent compilation errors.

## Commit

- `fix(001bh): remove schema analysis banner from feeds tab`
