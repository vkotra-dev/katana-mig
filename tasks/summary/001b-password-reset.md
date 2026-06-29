# 001b-password-reset Summary

- Implemented `POST /auth/password-reset/request` (always `202`, no email enumeration).
- Implemented `POST /auth/password-reset/confirm` with single-use tokens and session
  revocation on success.
- Added `password_reset_tokens` persistence and timezone-safe expiry handling.
- Added `engine/tests/test_password_reset_api.py` (3 tests, all passing).
