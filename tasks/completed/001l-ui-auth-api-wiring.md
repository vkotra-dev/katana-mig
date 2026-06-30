# 001l-ui-auth-api-wiring

## Domain

- [ui.md](/Users/vjkotra/projects/katana/docs/domain/ui.md)
- [auth.md](/Users/vjkotra/projects/katana/docs/domain/auth.md)
- [security.md](/Users/vjkotra/projects/katana/docs/domain/security.md)
- [api.md](/Users/vjkotra/projects/katana/docs/domain/api.md)

## Objective

Wire the existing login and password-reset UI surfaces to the auth API so the
UI can create, restore, and invalidate authenticated sessions against the
backend instead of relying on local stubs.

## Scope

- Login form submission to `POST /auth/login`
- Session restore on app load via `GET /auth/session`
- Logout action via `POST /auth/logout`
- Password-reset request and confirm forms
- Bootstrap-status probe for first-run entry selection
- Shared auth client and session storage helpers

## Out of Scope

- Management user CRUD
- Project membership screens
- Role-based menu pruning beyond the authenticated session bootstrap path
- Backend auth implementation changes

## Acceptance Criteria

- The login flow posts email and password to the API and stores the returned
  access token and session state
- The app restores the authenticated session from the API on reload
- Logout clears the stored session and calls the API logout endpoint
- Password reset request and confirm screens call the matching auth endpoints
- The app chooses login versus authenticated shell from session state, not from
  request-body role claims

## Test Expectations

- Login submits the expected JSON payload to `/auth/login`
- Session restore uses `Authorization: Bearer <token>` and reads `/auth/session`
- Logout removes persisted session data and calls `/auth/logout`
- Password-reset request and confirm forms call the expected endpoints
- Unauthenticated users still reach the login surface

