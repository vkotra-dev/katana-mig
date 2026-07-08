# Task: 001cj — Remove Feed GUID ID from Project Source List

## Status
Ready

## Problem

On the project details view (e.g. `/projects/00000000-0000-4000-8000-000000000001`), the "Feeds" tab lists all declared sources/feeds. Under each feed's label, the UI displays the raw database UUID/GUID for `sourceDefinitionId`. Since this internal identifier is not meaningful to end-users, it should be removed to keep the interface clean.

## Solution

Remove the `sourceDefinitionId` GUID rendering from `web/components/projects/SourceList.tsx`.

## Files Changed

- `web/components/projects/SourceList.tsx`

## Out of Scope

- Modifying any backend API endpoints.

## Verification

1. Go to any project detail page under the "Feeds" tab.
2. Verify that only the human-readable label of the feed is displayed, and the internal GUID is no longer listed.
3. Verify that TypeScript compiles cleanly.
4. Run all Vitest frontend unit tests.
