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

## Project endpoints

These endpoints implement the contract in [`project.md`](./project.md). All
require authentication.

### Project status enum

| Value | Meaning |
|---|---|
| `active` | Accepting routing and execution |
| `archived` | No new routing; read-only |

### `POST /projects`

Create a project. Requires `central_team` or `project_stakeholder`.

A `project_stakeholder` caller is automatically added as the project's first
member on creation.

Request fields (all optional except `name`):

| Field | Type | Notes |
|---|---|---|
| `name` | string | Required; 1–255 chars |
| `goal` | string or null | Free-text migration goal |
| `repos` | array or null | Git/repo references |
| `workspace` | object or null | Generic workspace config (not migration-specific) |
| `environment` | string or null | Primary environment label |
| `execution_environments` | array of strings or null | Ordered env pipeline e.g. `["STG","UAT","PROD"]` |
| `model_policy` | object or null | AI model governance policy |
| `canonical_terms` | array of strings or null | Domain vocabulary |
| `constraints` | array of strings or null | Compliance constraints |
| `unresolved_questions` | array of strings or null | Open governance questions |
| `assumptions` | array of strings or null | Baseline assumptions |
| `domain_config` | object or null | `MigrationProjectConfig`: `target_db_engine` ("mssql"\|"oracle"\|"postgresql"\|"mysql"), `staging_schema` (string\|null), `dry_run` (bool), `sample_policy` (object\|null), `destination_schema_ddl` (string\|null), `environments` (array of strings\|null) |
| `lexicon_scope` | object or null | Vocabulary scope; stored on registry |

Response `201`: `ProjectResponse` — all fields above plus `project_id`,
`status`, `created_at`, `updated_at`, `archived_at`.

Failures:
- `403` + `forbidden` for `read_only_auditor`

### `GET /projects`

List projects. Requires authentication.

- `central_team` and `read_only_auditor` see all projects.
- `project_stakeholder` sees only projects where they hold membership.

Query parameters:

| Parameter | Type | Default | Notes |
|---|---|---|---|
| `include_archived` | boolean | `false` | When `true`, includes archived projects |

Response `200`: array of `ProjectResponse`.

### `GET /projects/{project_id}`

Fetch one project. Requires authentication.

- `central_team` and `read_only_auditor` may fetch any project.
- `project_stakeholder` may fetch only member projects.

Response `200`: `ProjectResponse`.

Failures:
- `403` + `forbidden` — stakeholder without membership
- `404` + `project_not_found`

### `PATCH /projects/{project_id}`

Update a project. Requires `central_team`.

Omitting a field leaves it unchanged. Creates a new frozen `ProjectDefinition`
row with the changed fields applied and advances `ProjectRegistry.definition_id`
to it. The prior definition row is preserved for run lineage. Cannot update an
archived project.

Request: same fields as `POST /projects`, all optional.

Response `200`: `ProjectResponse`.

Failures:
- `409` + `project_archived`
- `404` + `project_not_found`

### `POST /projects/{project_id}/archive`

Archive a project. Requires `central_team`. Sets `archived_at` and
`status = "archived"` on the registry. No request body.

Response `200`: `ProjectResponse`.

Failures:
- `409` + `project_already_archived`
- `404` + `project_not_found`

### Project error codes

| Code | Typical status |
|---|---|
| `project_not_found` | `404` |
| `project_archived` | `409` |
| `project_already_archived` | `409` |
| `forbidden` | `403` |

## Source contract endpoints

These endpoints implement the contract in [`source-model.md`](./source-model.md).
All require authentication. Mutation routes require `central_team`.

### `POST /projects/{project_id}/sources`

Declare a new source contract. Requires `central_team`.

Request:

```json
{
  "source_type": "csv",
  "label": "Customer Master",
  "encoding": "utf-8"
}
```

| Field | Type | Required | Notes |
|---|---|---|---|
| `source_type` | `"csv"` \| `"fixed_length_file"` | yes | |
| `label` | string | yes | 1–255 chars |
| `encoding` | string | no | Default `utf-8` |

Response `201`: `SourceContractResponse`

### `GET /projects/{project_id}/sources`

List source contracts for a project. Any authenticated user.

Response `200`: array of `SourceContractResponse`

### `GET /projects/{project_id}/sources/{contract_id}`

Get one source contract. Any authenticated user.

Response `200`: `SourceContractResponse`

### `POST /projects/{project_id}/sources/{contract_id}/copybook`

Upload a COBOL copybook. Requires `central_team`. JSON body:

```json
{
  "content": "01 CUSTOMER-RECORD..."
}
```

Parses the copybook into `layout_information` JSON and advances status to `layout_ready`.

Response `200`: `SourceContractResponse`

### `POST /projects/{project_id}/sources/{contract_id}/slices`

Upload a data file. Requires `central_team`. JSON body:

```json
{
  "content": "CUST_ID,SURNAME,DOB\n100042,Smith,19800101"
}
```

Triggers parse → mask → store pipeline. Advances contract status to `active`.

Response `201`: `SourceSliceResponse`

### `GET /projects/{project_id}/sources/{contract_id}/slices`

List slices for a contract. Any authenticated user.

Response `200`: array of `SourceSliceResponse`

### `GET /projects/{project_id}/sources/{contract_id}/slices/{slice_id}`

Get one slice with header and row preview. Any authenticated user.

Response `200`: `SourceSliceResponse`

### `GET /approvals`

List pending source-slice approvals visible to the caller. Any authenticated
user. `project_stakeholder` callers only see member projects.

Response `200`: array of `SourceSliceApprovalItemResponse`

### `GET /approvals/count`

Return the visible pending-approval count for the caller.

Response `200`:

```json
{
  "pending_count": 4
}
```

### `POST /projects/{project_id}/sources/{contract_id}/slices/{slice_id}/approve`

Approve a pending slice. Requires `central_team`.

Response `200`: `SourceSliceResponse`

### `POST /projects/{project_id}/sources/{contract_id}/slices/{slice_id}/reject`

Reject a pending slice. Requires `central_team`.

Request:

```json
{
  "reason": "Needs a corrected delimiter"
}
```

Response `200`: `SourceSliceResponse`

### `POST /projects/{project_id}/sources/{contract_id}/slices/{slice_id}/resubmit`

Resubmit a rejected slice after correcting retained-file parsing settings.
Requires `central_team`.

Request:

```json
{
  "encoding": "utf-8",
  "parse_settings": {
    "delimiter": ","
  }
}
```

Response `200`: `SourceSliceResponse`

### `SourceContractResponse`

```json
{
  "source_definition_id": "...",
  "project_id": "...",
  "source_type": "csv",
  "label": "Customer Master",
  "encoding": "utf-8",
  "destination_object_references": null,
  "layout_information": null,
  "copybook_text": null,
  "status": "declared",
  "created_at": "..."
}
```

`destination_object_references` is `null` at declaration time. It is written by the mapping
stage when field mapping is approved, and contains the destination object names this source
feeds (e.g. `["Customer", "Address"]`). Generated SQL artifacts are tracked separately as
`CodeGenerationArtifact` records linked to the run, not stored on the source contract.

### `SourceSliceResponse`

```json
{
  "source_slice_id": "...",
  "source_definition_id": "...",
  "source_slice_version": "v1",
  "header_csv": "CUST_ID,SURNAME,DOB,ACCOUNT_TYPE",
  "row_count": 1842,
  "status": "pending_approval",
  "approval_rejection_reason": null,
  "parse_warnings": [],
  "file_storage_path": "/tmp/source.csv",
  "preview_rows": ["100042,***,***,DATABASE"],
  "created_at": "..."
}
```

### `SourceSliceApprovalItemResponse`

```json
{
  "project_id": "...",
  "project_name": "Approval Project",
  "source_definition_id": "...",
  "source_label": "Customer Master",
  "source_type": "csv",
  "source_slice_id": "...",
  "source_slice_version": "v1",
  "row_count": 1842,
  "status": "pending_approval",
  "parse_warnings": [],
  "created_at": "..."
}
```

### `SourceSliceApprovalCountResponse`

```json
{
  "pending_count": 4
}
```

### Source contract error codes

| Code | Status | When |
|---|---|---|
| `source_contract_not_found` | 404 | Contract not found or not in this project |
| `source_not_found` | 404 | Contract not found or not in this project |
| `source_slice_not_found` | 404 | Slice not found |
| `layout_not_ready` | 409 | Slice upload before copybook parsed (fixed-length) |
| `copybook_parse_error` | 422 | COBOL copybook cannot be parsed |
| `file_too_large` | 413 | Upload exceeds 50 MB |
| `unsupported_encoding` | 422 | Input cannot be decoded with supported encodings |

### Source approval error codes

| Code | Status | When |
|---|---|---|
| `slice_not_pending` | 409 | Approve or reject called on a non-pending slice |
| `slice_not_rejected` | 409 | Resubmit called on a non-rejected slice |
| `file_not_retained` | 422 | Resubmit attempted but the retained upload path is missing |
| `parse_failed` | 422 | Retained file could not be re-parsed |
| `slice_not_found` | 404 | Slice does not belong to the requested project / source |

## Changelog

- 2026-06-29: Added project CRUD endpoint contract (create, list, get, update,
  archive) with role-scoped access rules and definition immutability notes.
- 2026-06-29: Added management HTTP contract for users and project membership.
- 2026-06-29: Added auth HTTP contract with JSON schemas, error envelope, JWT
  claims, bootstrap status probe, and UI mapping for the first implementation
  slice.
- 2026-06-30: Added source approval routes, inbox count endpoint, and the slice
  approval response models.
