Task: tasks/completed/002b9-version-history-frontend.md
Commits: b45bfa5 (feat), 4b0e975 (close), b5d367d (docs fix)

## Housekeeping note

Implemented and closed by direct commits; no summary file existed in `tasks/summary/` even though
the task was already moved to `tasks/completed/` and `TASK_INDEX.md` was partially updated (rows
removed from Ready but never re-added to Completed). Writing this summary now for consistency —
every other completed task in the index links to one — and adding the missing index row.

## Changes Made

- `VersionHistoryPanel` component (`web/components/projects/VersionHistoryPanel.tsx`) — reusable
  collapsible panel rendering version entries with timestamp, author, field name, and collapsible
  old/new diff.
- `listVersionHistory(token, projectId, entityType)` (`web/lib/feeds-api.ts`) — fetches hints and
  transformation version history.
- `listCodegenVersionHistory(token, projectId)` (`web/lib/projects-api.ts`) — fetches codegen
  instructions version history.
- "View History" toggle wired into the feed page's mapping hints editor and the codegen page's
  coding standards editor, both refreshing history after save.
- `transformation_instructions` intentionally has no History button — no editor for that field
  exists on the feed page (it's edited on the codegen page instead, a separate textarea not in
  this task's scope) — confirmed correct per the task's own "Out of Scope."

## Tests

Manual verification only, per the task's own "Tests" section (no dedicated test file was planned).
Frontend suite: 336 passed / 2 failed at the time of implementation, both pre-existing and
unrelated (a `codegen/page.test.tsx` failure about a "Source Characteristics" section in
`generateTransformationInstructionsTemplate`, untouched by this change) — verified independently
during review.

## Domain Updates Required

- `docs/domain/ui.md` — **Updated**. Changelog entry (line ~583) documents the "View History"
  toggle alongside the same-day Source DDL/lookup-lock changes.
