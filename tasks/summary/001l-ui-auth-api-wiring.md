# 001l-ui-auth-api-wiring Summary

- Added `web/lib/api-base.ts` and `web/lib/auth-api.ts` for auth endpoint
  wiring, including login, session restore, logout, bootstrap status, and
  password reset helpers.
- Reworked `web/lib/session.ts` to persist the UI session and provide a
  test-friendly fallback store.
- Wired `web/app/page.tsx` to restore sessions, submit login requests, handle
  logout, and switch into an authenticated shell.
- Added password-reset request and confirm pages plus reusable views under
  `web/components/`.
- Added and passed the web test suite and production build verification.
