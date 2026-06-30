# 001m-ui-management-user-admin Summary

- Added `web/lib/management-api.ts` for user and project membership API calls,
  including list, fetch, create, update, and delete helpers.
- Added shared admin components: `UserForm`, `UserList`, and
  `ProjectMembersPanel`.
- Added admin route pages for user list, user creation, user detail/update, and
  project membership management under `web/app/admin/...`.
- Wired the admin screens to the authenticated session token and the backend
  management endpoints.
- Added tests for the management API, shared components, and admin route pages.
- Verified the full web test suite and the Next.js production build.
