# Plan: 001bj — Remove Feed Slice Upload

- **Task Link:** [001bj-remove-feed-slice-upload.md](file:///Users/vjkotra/projects/katana/tasks/001bj-remove-feed-slice-upload.md)
- **Domain Link:** [ui.md](file:///Users/vjkotra/projects/katana/docs/domain/ui.md)

## Current State

- The feed detail page (`web/app/projects/[id]/feeds/[feedId]/page.tsx`) contains:
  - `uploadText` and `uploading` states.
  - `handleUploadSlice` handler.
  - `uploadFeedSlice` import.
  - An "Upload New Slice" `<textarea>` and button card for operators.
  - A locked workspace message saying: *"Slice approval is required before mapping and lookups can proceed. Approve the uploaded slice or submit a new version."*

## Objective

Remove the slice upload card from the detail workspace to ensure feed immutability, preventing operators from uploading new csv slices onto existing feed workspaces.

## Out of Scope

- Removing the backend slice upload endpoints.
- Modifying slice approval or rejection workflows.

## Blast Radius

Minimal. Affects only operator capabilities on the feed detail page.

## File Changes

### `web/app/projects/[id]/feeds/[feedId]/page.tsx`

- Remove imports, state, handlers, and JSX for uploading slices.
- Edit locked workspace message to: *"Slice approval is required before mapping and lookups can proceed. Approve the uploaded slice."*

## Tests

- Run `npm test` to ensure all tests continue to pass.

## Verification

- Confirm page compile is clean and no references to `uploadText` or `uploadFeedSlice` remain.

## Pitfalls

- Ensure that only the upload components are deleted and that `listFeedSlices` and other critical feed query/state loops remain unaffected.

## Commit

- `fix(001bj): remove feed slice upload card from feed detail workspace`
