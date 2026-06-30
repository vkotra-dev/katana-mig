# Summary 001u — Runs UI

Implemented the runs UI surfaces and wired them to the run API:

- Added `web/lib/runs-api.ts` with typed helpers for runs, launches, resumes, and checkpoints.
- Added `RunStatusChip` for status-aware display across the runs surfaces.
- Added `LaunchRunDialog` with project, source contract, destination object, and environment selection.
- Added the runs list page at `/runs` with filters, quick actions, and central-team launch access.
- Added the run detail page at `/runs/[id]` with five tabs, polling while running, pause/resume handling, and reconciliation linking.

Verification:

- `cd web && npm test -- lib/runs-api.test.ts components/runs/RunStatusChip.test.tsx components/runs/LaunchRunDialog.test.tsx app/runs/page.test.tsx 'app/runs/[id]/page.test.tsx'`

Result:

- 5 test files passed
- 15 tests passed
