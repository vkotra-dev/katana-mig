# 001n-ui-role-based-navigation Summary

- Added `web/lib/navigation-access.ts` with role-based admin and project access
  helpers plus visible action mapping.
- Updated `web/lib/ui-model.ts`, `web/components/Topbar.tsx`, and
  `web/components/Sidebar.tsx` to render role-specific menus for central-team,
  project-stakeholder, and read-only auditor users.
- Added client-side route guards for admin and project sections in
  `web/app/admin/layout.tsx` and `web/app/projects/layout.tsx`.
- Added tests for the navigation policy, the role-specific menus, and the two
  route guards.
- Verified the full web test suite and the Next.js production build.
