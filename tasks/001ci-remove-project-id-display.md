# Task: 001ci — Remove Project GUID ID from UI Views

## Status
Ready

## Problem

The UI currently displays the internal project UUID/GUID on:
1. The dashboard portfolio table.
2. The projects listing table.
3. The project details header.

Since these GUIDs are internal database identifiers and are not meaningful to end-users, they clutter the view and should be removed.

## Solution

Remove the project ID/GUID rendering from these three frontend components:
1. **Portfolio Table** (`web/components/portfolio/PortfolioTable.tsx`): Remove the `mono-id` project ID element under the project name.
2. **Project Detail View** (`web/components/projects/ProjectDetailView.tsx`): Remove the `mono-id` project ID element next to the project name in the header.
3. **Project Table** (`web/components/projects/ProjectTable.tsx`): Remove the `mono-id` project ID element under the project name.

Additionally, update the unit test suite in `web/components/projects/__tests__/ProjectDetailView.test.tsx` to remove the assertion checking for the project ID string.

## Files Changed

- `web/components/portfolio/PortfolioTable.tsx`
- `web/components/projects/ProjectDetailView.tsx`
- `web/components/projects/ProjectTable.tsx`
- `web/components/projects/__tests__/ProjectDetailView.test.tsx`

## Verification

1. Load dashboard -> project list does not show GUIDs.
2. Load projects tab -> list does not show GUIDs.
3. Open any project detail -> header does not show GUID.
4. TypeScript compiles successfully.
5. All Vitest unit tests pass.
