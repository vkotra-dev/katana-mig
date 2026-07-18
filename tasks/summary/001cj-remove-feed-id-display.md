# Task: 001cj — Remove Feed GUID ID from Project Source List

## Status
Completed

## Problem

On the project details view (e.g. `/projects/00000000-0000-4000-8000-000000000001`), the "Feeds" tab lists all declared sources/feeds. Under each feed's label, the UI displays the raw database UUID/GUID for `sourceDefinitionId`. Since this internal identifier is not meaningful to end-users, it should be removed to keep the interface clean.

## Solution

1. Removed the `sourceDefinitionId` GUID rendering from `web/components/projects/SourceList.tsx`
2. Updated the task status and summary file
3. Removed feedId from `web/app/projects/[id]/feeds/[feedId]/page.tsx` 
4. Removed feedId and projectId from `web/app/projects/[id]/feeds/[feedId]/fibers/[fiberId]/page.tsx`

## Files Changed

- `web/components/projects/SourceList.tsx`
- `web/app/projects/[id]/feeds/[feedId]/page.tsx`
- `web/app/projects/[id]/feeds/[feedId]/fibers/[fiberId]/page.tsx`

## Out of Scope

- Modifying any backend API endpoints.

## Verification

1. Go to any project detail page under the "Feeds" tab.
2. Verify that only the human-readable label of the feed is displayed, and the internal GUID is no longer listed.
3. Verify that TypeScript compiles cleanly.
4. Run all Vitest frontend unit tests.