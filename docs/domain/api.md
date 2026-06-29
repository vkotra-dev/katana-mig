# API

This page is the machine-facing HTTP contract for the migration platform API.

Behavioral rules live in the domain pages (`auth.md`, `management.md`, and so
on). This page pins down request/response shapes, status codes, enums, and
error envelopes so the backend and UI can integrate without guessing.

The OpenAPI artifact at [`engine/openapi/auth.yaml`](../../engine/openapi/auth.yaml)
is generated from this page for the first auth slice. When behavior changes,
update this page and the OpenAPI file together.

## Conventions

### Base URL

- Local development: `http://127.0.0.1:8000`
- All paths below are relative to the API root.

### Content type

- Requests and responses use `application/json` unless noted otherwise.
- Request bodies must be JSON objects.

### Authentication header

Authenticated routes require:

```http
Authorization: Bearer <access_token>
```

The access token is the JWT returned by `POST /auth/login`. Request bodies must
not assert identity or role; authority comes from the token only.

### Role enum

Human platform roles (`PlatformRole`):

| Value | Meaning |
|---|---|
| `central_team` | Administrative operator |
| `project_stakeholder` | Project-scoped stakeholder |
| `read_only_auditor` | View-only operator |

### User status enum

| Value | Meaning |
|---|---|
| `active` | May authenticate |
| `disabled` | Must be rejected at authentication and request time |

### Error envelope

Failed requests return:

```json
{
  "error": {
    "code": "invalid_credentials",
    "message": "Human-readable summary safe to show in the UI."
  }
}
```

| HTTP status | When |
|---|---|
| `400` | Malformed JSON or missing required fields |
| `401` | Missing, invalid, or expired token; invalid login credentials |
| `403` | Authenticated but not permitted; disabled or soft-deleted identity |
| `404` | Resource not found |
| `409` | Conflicting state (duplicate email, reused reset token) |
| `422` | Semantically invalid input |
| `500` | Unexpected server failure |

Stable `error.code` values for the auth slice:

| Code | Typical status |
|---|---|
| `invalid_credentials` | `401` |
| `unauthenticated` | `401` |
| `session_expired` | `401` |
| `session_revoked` | `401` |
| `account_disabled` | `403` |
| `account_deleted` | `403` |
| `validation_error` | `400` or `422` |
| `reset_token_invalid` | `400` |
| `reset_token_expired` | `400` |

## Auth endpoints

These endpoints implement the contract summarized in [`auth.md`](./auth.md).

### `GET /auth/bootstrap/status`

Reports whether first-time administrator bootstrap is still required.

Authentication: none.

Response `200`:

```json
{
  "bootstrap_required": false
}
```

| Field | Type | Notes |
|---|---|---|
| `bootstrap_required` | boolean | `true` when the `users` table is empty |

UI uses this for the first-run administrator screen. Bootstrap **creation**
remains the CLI path (`katana-seed-admin`) in the first implementation slice.

### `POST /auth/login`

Starts an authenticated human session.

Authentication: none.

Request:

```json
{
  "email": "operator@example.com",
  "password": "secret"
}
```

| Field | Type | Required |
|---|---|---|
| `email` | string (email) | yes |
| `password` | string | yes |

Response `200`:

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "bearer",
  "expires_at": "2026-06-30T12:00:00Z",
  "session_version": 1,
  "user": {
    "user_id": "550e8400-e29b-41d4-a716-446655440000",
    "email": "operator@example.com",
    "display_name": "Operator",
    "role": "central_team",
    "status": "active"
  }
}
```

| Field | Type | Notes |
|---|---|---|
| `access_token` | string | Short-lived JWT |
| `token_type` | string | Always `bearer` |
| `expires_at` | string (ISO-8601 UTC) | Token expiry |
| `session_version` | integer | Revocation marker; incremented on logout/password reset |
| `user.user_id` | string (uuid) | Authoritative identity |
| `user.email` | string (email) | Login identifier |
| `user.display_name` | string or null | Display label |
| `user.role` | `PlatformRole` | Authoritative role |
| `user.status` | string | `active` or `disabled` |

Failures:

- `401` + `invalid_credentials` for unknown email or wrong password
- `403` + `account_disabled` or `account_deleted` for inactive identities

### `GET /auth/session`

Returns the current authenticated session context.

Authentication: required.

Response `200`:

```json
{
  "user_id": "550e8400-e29b-41d4-a716-446655440000",
  "email": "operator@example.com",
  "display_name": "Operator",
  "role": "central_team",
  "status": "active",
  "expires_at": "2026-06-30T12:00:00Z",
  "session_version": 1
}
```

Failures:

- `401` + `unauthenticated`, `session_expired`, or `session_revoked`
- `403` + `account_disabled` or `account_deleted` if the identity became inactive
  after the token was issued

### `POST /auth/logout`

Revokes the current session by bumping the user's session version.

Authentication: required.

Request: empty body.

Response `204`: no content.

Failures:

- `401` + `unauthenticated` when no valid token is presented

### `POST /auth/password-reset/request`

Starts a self-service password reset.

Authentication: none.

Request:

```json
{
  "email": "operator@example.com"
}
```

Response `202`:

```json
{
  "accepted": true
}
```

Always returns `202` with `accepted: true` whether or not the email exists.

### `POST /auth/password-reset/confirm`

Completes a password reset.

Authentication: none.

Request:

```json
{
  "reset_token": "opaque-reset-token",
  "new_password": "new-secret"
}
```

Response `204`: no content.

Failures:

- `400` + `reset_token_invalid` or `reset_token_expired`
- `422` + `validation_error` when `new_password` fails policy checks

## JWT claims

Access tokens are stateless JWTs. Minimum claims:

| Claim | Type | Notes |
|---|---|---|
| `sub` | string | `user_id` |
| `email` | string | Authenticated email |
| `role` | string | `PlatformRole` |
| `sv` | integer | `session_version` from `auth_sessions` / user revocation marker |
| `exp` | integer | Expiry (Unix timestamp) |
| `iat` | integer | Issued-at (Unix timestamp) |

Default access-token lifetime: **8 hours** unless overridden by deployment
configuration.

## UI mapping (auth slice)

| UI surface | Endpoints |
|---|---|
| First-run bootstrap gate | `GET /auth/bootstrap/status` |
| Login | `POST /auth/login` |
| Session restore on load | `GET /auth/session` |
| Logout | `POST /auth/logout` |
| Password-reset request | `POST /auth/password-reset/request` |
| Password-reset confirm | `POST /auth/password-reset/confirm` |

## Out of scope for this slice

- Project, run, and migration endpoints
- Service-account authentication headers

## Management endpoints

These endpoints implement [`management.md`](./management.md). All require authentication.
User-management routes require `central_team` unless noted.

### `GET /users`

List active users. Requires `central_team`.

### `POST /users`

Create a user. Requires `central_team`.

Request:

```json
{
  "email": "stakeholder@example.com",
  "password": "initial-password",
  "display_name": "Stakeholder",
  "role": "project_stakeholder"
}
```

### `GET /users/{user_id}`

Fetch a user. Requires `central_team` or self.

### `PATCH /users/{user_id}`

Update profile, role, or status. Requires `central_team`.

### `DELETE /users/{user_id}`

Soft-delete a user. Requires `central_team`. Returns `204`.

### `GET /projects/{project_id}/members`

List project members. Requires `central_team`.

### `POST /projects/{project_id}/members`

Add a `project_stakeholder` member. Requires `central_team`.

Request:

```json
{
  "user_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

Duplicate membership returns `200` with:

```json
{
  "project_id": "...",
  "user_id": "...",
  "warning": "User is already a member of this project."
}
```

### `DELETE /projects/{project_id}/members/{user_id}`

Remove project membership. Requires `central_team`. Returns `204`.

## Changelog

- 2026-06-29: Added management HTTP contract for users and project membership.
- 2026-06-29: Added auth HTTP contract with JSON schemas, error envelope, JWT
  claims, bootstrap status probe, and UI mapping for the first implementation
  slice.
