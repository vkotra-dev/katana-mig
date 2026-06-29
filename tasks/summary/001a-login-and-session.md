# 001a-login-and-session Summary

- Implemented `GET /auth/bootstrap/status`, `POST /auth/login`, `GET /auth/session`,
  and `POST /auth/logout`.
- Added bcrypt password verification, stateless JWT issuance, and
  `session_version` revocation on logout.
- Wired auth routes into the FastAPI app with dependency-injected session checks.
- Added `engine/tests/test_auth_api.py` (5 tests, all passing).
