# Summary: Task 001h — UI Portfolio Project Screens

## What changed

- Replaced the `/dashboard` placeholder with a real portfolio dashboard page.
- Added `SummaryStrip` to show total, active, archived, and pending-approval counts.
- Added `PortfolioTable` with search, status, environment filters, and sortable name / last-updated columns.
- Wired the dashboard page to load projects and pending approval count in parallel.
- Preserved the existing `/projects` page and `ProjectTable` component unchanged.
- Added component-level and page-level Vitest coverage for the dashboard slice.

## Verification

- `cd web && npm test -- --run 'components/portfolio/SummaryStrip.test.tsx' 'components/portfolio/PortfolioTable.test.tsx' 'app/dashboard/page.test.tsx'`
- `cd web && npm run build`
- `git diff --check`

## Notes

- `PortfolioTable` defaults to `status=active`.
- Archived projects are still included in the summary counts because the page loads with `includeArchived=true`.
