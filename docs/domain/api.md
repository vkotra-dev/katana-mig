---
type: API Contract
title: HTTP API
description: The complete HTTP contract for the Katana migration platform — request/response shapes, status codes, error envelopes, and endpoint specifications for auth, management, projects, feeds, fibers, mapping, codegen, notifications, and AI observability.
tags:
  - api
  - http
  - endpoints
  - contract
timestamp: 2026-07-16
---

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
| `admin` | User management only |
| `pm` | Project lifecycle and member management |
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

## Out of scope

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
| `domain_config` | object or null | `MigrationProjectConfig`: `target_db_engine` ("mssql"\|"oracle"\|"postgresql"\|"mysql"), `staging_schema` (string\|null), `destination_schema` (string\|null), `dry_run` (bool), `sample_policy` (`SamplePolicy`: `strategy`, `max_rows`, `stratified_column`), `destination_schema_ddl` (string\|null), `environments` (array of strings\|null) |
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

### `GET /config/ai-model-defaults`

Fetch the resolved global AI model defaults from `engine.yaml`. Requires
authentication.

Response `200`:

| Field | Type | Notes |
|---|---|---|
| `source` | string | Always `engine.yaml` |
| `platform_models` | object | Resolved defaults for `planning`, `review`, `implementation` |
| `migration_models` | object | Resolved defaults for `pii_review`, `field_mapping`, `lookup_mapping`, `script_generation`, `script_correction`, `schema_dependency`, `impact_analysis`, `feed_analysis` |

The response contains the live resolved model names only. It does not expose
provider API keys or environment variable names.

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

## Notification endpoints

These endpoints implement the notification contract in [`ui.md`](./ui.md).
They are user-scoped, so project membership is resolved from the authenticated
session rather than a `project_id` path segment.

### Notification event type enum

| Value | Meaning |
|---|---|
| `gate_1_waiting` | Gate 1 waiting for review |
| `gate_2_waiting` | Gate 2 waiting for review |
| `impact_review_waiting` | Impact review waiting for operator action |
| `dry_run_waiting` | Dry-run review waiting for operator action |
| `lookup_delta_discovered` | New lookup delta is ready |
| `reconciliation_failed` | Reconciliation failed |
| `knowledge_freeze_published` | A new freeze was published |
| `execution_complete` | Run execution completed |
| `feed_comment_added` | A comment was added to a feed thread |

### `NotificationResponse`

```json
{
  "notification_id": "...",
  "user_id": "...",
  "project_id": "...",
  "event_type": "gate_1_waiting",
  "deep_link": "/projects/.../runs/...",
  "read": false,
  "payload": {"run_id": "..."},
  "read_at": null,
  "created_at": "..."
}
```

### `NotificationCountResponse`

```json
{
  "unread_count": 4
}
```

### `NotificationMarkAllResponse`

```json
{
  "marked_count": 4
}
```

### `GET /notifications`

List the authenticated user's notifications. Returns unread items first, then
most recent items.

Response `200`: array of `NotificationResponse`.

### `GET /notifications/count`

Return the authenticated user's unread notification count.

Response `200`: `NotificationCountResponse`.

### `POST /notifications/{notification_id}/read`

Mark one notification as read. Returns the updated `NotificationResponse`.

Failures:
- `404` + `notification_not_found`

### `POST /notifications/read-all`

Mark all notifications for the authenticated user as read.

Response `200`: `NotificationMarkAllResponse`.

### Notification error codes

| Code | Typical status |
|---|---|
| `notification_not_found` | `404` |

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

Response `201`: `FeedSliceResponse`

### `GET /projects/{project_id}/sources/{contract_id}/slices`

List slices for a contract. Any authenticated user.

Response `200`: array of `FeedSliceResponse`

### `GET /projects/{project_id}/sources/{contract_id}/slices/{slice_id}`

Get one slice with header and row preview. Any authenticated user.

Response `200`: `FeedSliceResponse`

### `GET /approvals` *(removed)*

> Removed in 001bg. Global approvals inbox has been replaced by
> project-scoped notification and sign-off workflows.

### `GET /approvals/count` *(removed)*

> Removed in 001bg. Use `GET /notifications/count` instead.

### `POST /projects/{project_id}/sources/{contract_id}/slices/{slice_id}/approve`

Approve a pending slice. Requires `central_team`.

Response `200`: `FeedSliceResponse`

### `POST /projects/{project_id}/sources/{contract_id}/slices/{slice_id}/reject`

Reject a pending slice. Requires `central_team`.

Request:

```json
{
  "reason": "Needs a corrected delimiter"
}
```

Response `200`: `FeedSliceResponse`

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

Response `200`: `FeedSliceResponse`

## Feed comment endpoints

Feed comments belong to a feed and are used for threaded operator/stakeholder
discussion. Comments are project-scoped for access and feed-scoped for storage.

### `GET /projects/{project_id}/feeds/{feed_id}/comments`

List comments for one feed. Any authenticated user with access to the project.

Response `200`: array of `FeedCommentResponse`

### `POST /projects/{project_id}/feeds/{feed_id}/comments`

Create a comment on one feed. Requires an authenticated non-auditor user with
project access.

Request:

```json
{
  "body": "ACCT_TYPE value RETD should map to Retired."
}
```

Response `201`: `FeedCommentResponse`

## Slice comment endpoints

Slice comments are scoped to an individual data slice within a source feed.

### `GET /projects/{project_id}/sources/{feed_id}/slices/{slice_id}/comments`

List comments for one slice. Any authenticated user with access to the project.

Response `200`: array of `SliceCommentResponse`

### `POST /projects/{project_id}/sources/{feed_id}/slices/{slice_id}/comments`

Create a comment on one slice. Requires an authenticated non-auditor user with
project access.

Request:

```json
{
  "body": "Row 42 has a truncated SURNAME value."
}
```

Response `201`: `SliceCommentResponse`

## Fiber endpoints

Fibers are project-scoped records attached to a feed. They live under the feed
route so the path identifies both the owning project and the input feed.

### `POST /projects/{project_id}/feeds/{feed_id}/fibers`

Create a fiber for one feed. Requires `central_team`.

Request:

```json
{
  "fiber_type": "lookup",
  "fiber_key": "status_code",
  "source": "manual"
}
```

Response `201`: `FiberResponse`

### `GET /projects/{project_id}/feeds/{feed_id}/fibers`

List fibers for one feed. Any authenticated user with access to the project.

Response `200`: array of `FiberResponse`

### `GET /projects/{project_id}/feeds/{feed_id}/fibers/{fiber_id}`

Get one fiber for one feed. Any authenticated user with access to the project.

Response `200`: `FiberResponse`

### `POST /projects/{project_id}/feeds/{feed_id}/fibers/{fiber_id}/assign`

Advance a mapped fiber to `operator_assigned`. Requires `central_team`.

Request body: `{ "comment": string | null }` or `{}`.

Response `200`: `FiberResponse`

### `POST /projects/{project_id}/feeds/{feed_id}/fibers/{fiber_id}/approve`

Advance an `operator_assigned` fiber to `business_approved`. Requires
`project_stakeholder` project access.

Request body: `{ "comment": string | null }` or `{}`.

Response `200`: `FiberResponse`

### `POST /projects/{project_id}/feeds/{feed_id}/fibers/{fiber_id}/trigger`

Advance a `business_approved` fiber to `operator_triggered`. Requires
`central_team`.

Request body: `{ "comment": string | null }` or `{}`.

Response `200`: `FiberResponse`

### `POST /projects/{project_id}/feeds/{feed_id}/analyze`

Analyze one approved feed slice and create or update the fibers attached to the
feed. Requires `central_team`.

Response `200`: array of `FiberResponse`

### `POST /projects/{project_id}/feeds/{feed_id}/fibers/{fiber_id}/lookup-inputs`

Submit the lookup source values and destination reference CSV for a lookup
fiber. Requires `central_team`.

Request:

```json
{
  "source_values": ["active", "inactive"],
  "destination_lookup_csv": "code,label\nA,Active\nI,Inactive"
}
```

| Field | Type | Required |
|---|---|---|
| `source_values` | array of strings | yes |
| `destination_lookup_csv` | string | yes |

Response `200`: `FiberResponse`

### `GET /projects/{project_id}/feeds/{feed_id}/fibers/{fiber_id}/source-entries`

List the source lookup values recorded for one lookup fiber. Any authenticated
user with access to the project.

Response `200`: array of `LookupSourceEntryResponse`

### `POST /projects/{project_id}/feeds/{feed_id}/fibers/{fiber_id}/source-entries`

Append source lookup values to one lookup fiber. Requires `central_team`.

Request:

```json
{
  "values": ["active", "inactive"],
  "discovery_type": "sample"
}
```

Response `201`: array of `LookupSourceEntryResponse`

### `POST /projects/{project_id}/feeds/{feed_id}/fibers/{fiber_id}/dest-feed`

Create or replace the destination lookup feed for one lookup fiber. Requires
`central_team`.

Request:

```json
{
  "columns": ["code", "label"],
  "rows": [
    {"code": "A", "label": "Active"},
    {"code": "I", "label": "Inactive"}
  ]
}
```

Response `201`: `LookupDestFeedResponse`

### `GET /projects/{project_id}/feeds/{feed_id}/fibers/{fiber_id}/dest-feed/entries`

List the destination rows recorded for one lookup fiber. Any authenticated user
with access to the project.

Response `200`: array of `LookupDestEntryResponse`

### `GET /projects/{project_id}/feeds/{feed_id}/fibers/{fiber_id}/mappings`

List the lookup mappings for one lookup fiber. Any authenticated user with
access to the project.

Response `200`: array of `LookupMappingResponse`

### `PATCH /projects/{project_id}/feeds/{feed_id}/fibers/{fiber_id}/mappings/{mapping_id}`

Update a proposed mapping after operator review. Requires a non-auditor user
with project access.

Request:

```json
{
  "dest_entry_id": "1a2b3c4d-5e6f-7890-abcd-ef1234567890",
  "status": "confirmed"
}
```

| Field | Type | Required |
|---|---|---|
| `dest_entry_id` | string | yes |
| `status` | `confirmed` or `overridden` | yes |

Response `200`: `LookupMappingResponse`

## Lookup mapping endpoints

Lookup value maps are project-scoped. Lookup snapshot approval is also
project-scoped because the resulting snapshot is consumed project-wide.

### `POST /projects/{project_id}/lookup-maps`

Create or update a lookup draft for the project. Requires `central_team`.

Response `201`: `LookupValueMapResponse`

### `GET /projects/{project_id}/lookup-maps`

List lookup drafts for the project. Any authenticated user with access to the
project.

Response `200`: array of `LookupValueMapResponse`

### `POST /projects/{project_id}/sources/{contract_id}/lookup-snapshots`

Generate a draft lookup snapshot for one source contract. Requires
`central_team`.

Response `201`: `LookupSnapshotResponse`

### `POST /projects/{project_id}/lookup-snapshots/{lookup_snapshot_id}/approve`

Approve a generated lookup snapshot at the project level. Requires
`central_team`.

Response `200`: `LookupSnapshotResponse`

## Dry-run review endpoints

Dry-run review is project-scoped and run-scoped. The engine writes a
`DryRunArtifact` for a run when the project is configured for dry-run mode.
Central team operators can inspect the artifact, approve it to resume the run,
or push it back with a comment.

### `GET /projects/{project_id}/runs/{run_id}/dry-run`

Return the dry-run artifact for one run. Any authenticated user with project
access.

Response `200`: `DryRunArtifactResponse`

### `POST /projects/{project_id}/runs/{run_id}/dry-run/approve`

Approve the dry-run artifact and resume the run. Requires `central_team`.

Response `200`: `RunResponse`

### `POST /projects/{project_id}/runs/{run_id}/dry-run/push-back`

Push the dry-run back with a comment. Requires `central_team`.

Request:

```json
{
  "comment": "Row 142 maps RETD to the wrong destination."
}
```

Response `200`: `RunResponse`

### `DryRunArtifactResponse`

```json
{
  "dry_run_artifact_id": "...",
  "run_id": "...",
  "project_id": "...",
  "destination_object_name": "customers",
  "success_count": 1840,
  "failure_count": 2,
  "field_coverage_pct": 94.3,
  "pii_fields": [{"field": "SURNAME", "token": "EMAIL_XXXX"}],
  "sample_rows": [{"source": {"CUST_ID": "100042"}, "mapped": {"customer_id": "100042"}}],
  "failures": [{"row_index": 141, "reason": "unmapped_lookup", "field": "ACCT_TYPE", "value": "RETD"}],
  "push_back_comment": null,
  "status": "pending",
  "created_at": "2026-07-01T10:00:00Z"
}
```

`status` is one of `pending`, `approved`, or `pushed_back`.

## Change request endpoints

Change requests are project-scoped review records. Lookup delta CRs are opened
when a run pauses on an unmapped lookup value and are resolved by a project
stakeholder.

### `GET /projects/{project_id}/change-requests`

List open change requests for a project. Any authenticated user with project
access.

Response `200`: array of `ChangeRequestSummary`

### `GET /projects/{project_id}/change-requests/{cr_id}`

Return one change request in detail. Any authenticated user with project access.

Response `200`: `ChangeRequestDetail`

### `POST /projects/{project_id}/change-requests/{cr_id}/resolve`

Resolve a lookup delta change request by accepting a mapped value. Requires a
`project_stakeholder` with project access.

Request:

```json
{
  "accepted_value": "RETIRED"
}
```

Response `200`: `ChangeRequestResolveResponse`

### `ChangeRequestSummary`

```json
{
  "change_request_id": "...",
  "project_id": "...",
  "change_request_type": "lookup_delta",
  "status": "open",
  "title": "Lookup delta for account_type",
  "created_at": "2026-07-01T10:00:00Z"
}
```

### `ChangeRequestDetail`

```json
{
  "change_request_id": "...",
  "project_id": "...",
  "change_request_type": "lookup_delta",
  "status": "open",
  "title": "Lookup delta for account_type",
  "payload": {
    "run_id": "...",
    "lookup_name": "account_type",
    "unmapped_value": "RETD",
    "destination_object_name": "customers"
  },
  "created_at": "2026-07-01T10:00:00Z",
  "updated_at": "2026-07-01T10:05:00Z"
}
```

### `ChangeRequestResolveResponse`

```json
{
  "change_request_id": "...",
  "status": "resolved"
}
```

## Sign-off endpoints

Sign-off routes allow stakeholders to sign individual mapping bindings and
PMs to track overall sign-off status on a mapping snapshot.

### `POST /projects/{project_id}/sources/{feed_id}/mapping-snapshots/{snapshot_id}/bindings/{binding_index}/sign`

Sign a binding. Requires an authenticated non-auditor user with project access.

Response `200`: `BindingSignResponse`

### `DELETE /projects/{project_id}/sources/{feed_id}/mapping-snapshots/{snapshot_id}/bindings/{binding_index}/sign`

Unsign a previously signed binding. Requires the original signer or
`central_team`.

Response `204`: no content.

### `GET /projects/{project_id}/sources/{feed_id}/mapping-snapshots/{snapshot_id}/sign-off-status`

Get the sign-off status for a mapping snapshot. Any authenticated user with
project access.

Response `200`: `SignOffStatusResponse`

### `POST /projects/{project_id}/sources/{feed_id}/mapping-snapshots/{snapshot_id}/poke`

PM poke for sign-off. Sends a reminder notification to unsigned stakeholders.
Requires `pm` or `central_team`.

Response `202`: `{ "poked_count": 3 }`

## Code generation endpoints

Code generation is source-triggered but project-scoped in persistence. The
trigger route is central-team only; read routes follow normal project access.

### `POST /projects/{project_id}/sources/{contract_id}/codegen`

Generate a new SQL bundle for the source's destination object. Requires
`central_team`.

Response `201`: `CodegenTriggerResponse`

### `GET /projects/{project_id}/codegen-artifacts`

List code generation artifacts for a project. Any authenticated user with
project access.

Response `200`: array of `CodegenArtifactResponse`

### `GET /projects/{project_id}/codegen-artifacts/{codegen_artifact_id}`

Return one code generation artifact. Any authenticated user with project
access.

Response `200`: `CodegenArtifactResponse`

### `GET /projects/{project_id}/delivery-bundle`

Download the concatenated SQL delivery bundle for all active artifacts in the
project. Any authenticated user with project access.

If a schema analysis exists for the project, artifacts are ordered by the
FK dependency sequence and each SQL block is prefixed with `-- [01] table_name`,
`-- [02] table_name`, etc. Without an analysis, blocks are ordered alphabetically
with plain `-- table_name` headings.

Response `200`: `text/plain` attachment named `delivery-bundle.sql`

### `PATCH /projects/{project_id}/codegen-instructions`

Save project-wide codegen instructions. Requires `central_team`.

Request:

```json
{
  "codegen_instructions": "Use MERGE instead of INSERT for all upsert targets."
}
```

Response `200`: `ProjectResponse`

### `PATCH /projects/{project_id}/sources/{source_id}/transformation-instructions`

Save per-feed transformation instructions. Requires `central_team`.

Request:

```json
{
  "transformation_instructions": "Convert dates from YYYYMMDD to ISO-8601."
}
```

Response `200`: `SourceContractResponse`

### `GET /projects/{project_id}/knowledge-freezes`

List runs for this project where a knowledge freeze was recorded
(`knowledge_freeze_version IS NOT NULL`), ordered newest first. Any
authenticated user with project access.

Response `200`: array of `KnowledgeFreezeRecord`

### `KnowledgeFreezeRecord`

```json
{
  "run_id": "...",
  "knowledge_freeze_version": "...",
  "destination_object_name": "Customer",
  "environment": "UAT",
  "status": "completed",
  "started_at": "2026-07-01T10:00:00Z",
  "created_at": "2026-07-01T09:58:00Z"
}
```

`knowledge_freeze_version` is the `codegen_artifact_id` that was frozen at
baton_4 of the run.

### `POST /projects/{project_id}/schema-analysis`

Analyse the project's `destination_schema_ddl` using AI to extract all
destination objects and their FK/REFERENCES dependencies. Produces a
topologically-sorted execution sequence. Creates or overwrites the existing
analysis for the project (one record per project). Any authenticated user
with project access.

Returns `422 missing_ddl` if the project has no `destination_schema_ddl` set.

Response `200`: `ProjectSchemaAnalysisResponse`

### `GET /projects/{project_id}/schema-analysis`

Return the current schema analysis record for a project, or `null` if no
analysis has been run yet. Any authenticated user with project access.

Response `200`: `ProjectSchemaAnalysisResponse | null`

### `ProjectSchemaAnalysisResponse`

```json
{
  "analysis_id": "...",
  "project_id": "...",
  "destination_object_sequence": ["customers", "orders", "order_items"],
  "identified_count": 3,
  "processed_count": 2,
  "analyzed_at": "2026-07-01T12:00:00Z"
}
```

`identified_count` — total destination objects found in the DDL.
`processed_count` — of those, how many currently have an active codegen artifact.
`destination_object_sequence` — FK-ordered list; items not in the sequence sort to the end of the bundle.

## AI call log endpoints

### `GET /projects/{project_id}/ai-calls`

List AI call logs for a project. Requires `admin` or `central_team`.

Query parameters:

| Parameter | Type | Notes |
|---|---|---|
| `call_type` | string | Optional; filter by call type |
| `artifact_id` | string | Optional; filter by related artifact |

Response `200`: array of `AiCallLogResponse`

## Project copy endpoints

### `POST /projects/{project_id}/copy`

Copy a project with config carry-forward. Requires `central_team`.

Response `201`: `ProjectResponse` (the newly created copy).

## PM assignment endpoints

### `PATCH /projects/{project_id}/manager`

Reassign the PM for a project. Requires `admin`.

Request:

```json
{
  "pm_user_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

Response `200`: `ProjectResponse`

## Mapping hints endpoints

### `PATCH /projects/{project_id}/sources/{feed_id}/hints`

Save mapping hints on a feed. Requires `central_team`.

Response `200`: `SourceContractResponse`

## Copybook masking endpoints

### `GET /projects/{project_id}/sources/{feed_id}/slices/{slice_id}/rows`

Return rows for a slice with display-time masking. Any authenticated user with
project access. PII columns are masked unless the caller has the `central_team`
or `admin` role.

Query parameters:

| Parameter | Type | Default | Notes |
|---|---|---|---|
| `masked` | boolean | `true` | `false` returns unmasked values (role-gated) |

Response `200`: array of row objects.

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

### `FeedSliceResponse`

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

### `FeedSliceApprovalItemResponse`

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

### `FeedSliceApprovalCountResponse`

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
- 2026-07-01: Added fiber endpoints and the fiber entity response model family.
- 2026-06-30: Added lookup mapping endpoints and documented the project-scoped
  lookup snapshot approval route.
- 2026-07 — Added 15+ endpoints (comments, sign-offs, codegen instructions, AI
  calls, project copy, PM assignment, mapping hints, copybook masking); removed
  global approvals endpoints; updated lookup-maps to project scope; expanded
  PlatformRole enum with admin and pm.
