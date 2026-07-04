# Task 001bb Summary

- Added a state-controlled disclosure (accordion toggle) for the "Model Policy" section in `ProjectEditForm.tsx` to keep the UI clean and compact by default.
- Refactored `ProjectDetailView.tsx` metadata layout to match the edit form's 3-column grid structure and section ordering.
- Removed the separate one-off white KeyValue card backgrounds and borders in `ProjectDetailView.tsx` so that fields render as simple, clean label + value layouts, aligning with the visual rhythm of the edit form.
- Updated field labels in the detail view to match the edit form (e.g., "Target database engine" and "Execution environments").
- Updated the TS types for `lexiconScope` from `Record<string, unknown> | null` to `string | null` in `projects-api.ts` since `001ax` changed database field to text. Updated detail view to display it directly as plain text.
- Aligned `docs/domain/ui.md` Overview and Edit tab descriptions.
- Added tests to cover the collapsed accordion and labels alignment in `ProjectEditForm.test.tsx` and `ProjectDetailView.test.tsx`. Verified all tests pass.
