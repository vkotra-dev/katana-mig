---
type: Domain Spec
title: Authentication
description: Defines identity, authentication, and role derivation — password-based login, stateless JWT sessions, the 5-role model (admin, pm, central_team, project_stakeholder, read_only_auditor), and session authority rules.
tags:
  - auth
  - identity
  - jwt
  - roles
  - session
timestamp: 2026-07-24
---

# Auth

This page defines identity, authentication, and role derivation for the
migration platform.

It is about how a human or service proves identity and how the application
derives the authoritative role and session state from that identity. It is not
about authorization policy itself; that lives with the gate or feature that uses
the identity.

## Purpose

Provide a consistent authentication model that:

- uses password login as the primary human authentication mechanism
- proves who the caller is
- derives the caller’s role from authenticated state
- rejects soft-deleted or disabled identities
- supports both interactive users and non-human service principals
- supports bootstrap of the first administrative identity
- makes request bodies non-authoritative for identity claims

The rest of the system should be able to trust that authenticated identity and
role are already established before business logic runs.

## Responsibilities

- Authenticate callers with a supported credential flow.
- Derive role from authenticated session state, not from request bodies.
- Reject soft-deleted, disabled, or otherwise inactive identities.
- Support seeded bootstrap identity creation for first-time startup.
- Support long-lived non-human identities for integrations where required.
- Make authentication state available to downstream authorization checks.
- Keep credential material out of logs and nonessential records.

## Out of scope

- Authorization policy for a given action.
- Project-level routing and tenancy.
- Human approval flow.
- PII classification.
- Audit sink mechanics.

## Relationship to other pages

- Role-sensitive approval behavior is enforced by the approval-service route in
  the harness bundle, then surfaced through `ui.md` and `management.md`.
- UI role surfaces are defined in `ui.md`.
- Project scoping and per-project isolation are defined in `project.md`,
  `runs.md`, and `security.md`.
- Administrative user and membership lifecycle is defined in `management.md`.
- Security-sensitive decisions and audit expectations are summarized in
  `security.md`.

## Data model

### User

Users live in the shared application database.

Relevant fields:

- `user_id`
- `email` — max length 320
- `display_name`
- `password_hash`
- `role`
- `status` — default "declared"
- `session_version` — int, incremented on password change/reset/logout
- `soft_deleted_at`
- `created_at`
- `updated_at`

The role stored on the user is the application role currently associated with
that identity. The authoritative role used at request time comes from the
authenticated session state, not from a caller-supplied body field.

### Auth session

An authenticated request must carry enough state to prove identity and to derive
the current authorization context.

Relevant fields:

- authenticated `user_id`
- authenticated role
- session or token identifier
- issued-at timestamp
- expiry timestamp
- revocation/version marker
- optional principal kind or service-account indicator for non-human callers

The session format is stateless JWT. Authenticated state is persisted in the
`auth_sessions` table (fields: `session_id`, `user_id`, `role`, `token_identifier`,
`issued_at`, `expires_at`, `revocation_version`, `principal_kind`, `revoked_at`,
`created_at`). The JWT payload mirrors these claims. Session revocation works by
incrementing `revocation_version` on the User record and recording the token
identifier in `token_identifier` so it can be checked.

### Bootstrap identity

The system must support creation of the first administrative identity during
startup or via a CLI bootstrap path.

Relevant fields:

- email or username
- password or bootstrap secret
- initial role
- activation marker

Bootstrap credentials must not be stored in plaintext after creation.

## Authentication flow

The standard flow is:

1. Caller submits credentials.
2. For human callers, credentials are validated against the stored identity
   record using password login.
3. The application derives authenticated identity and role.
4. A JWT is issued.
5. Subsequent requests use only the authenticated session state.
6. Request bodies never override the authenticated identity.

### Session authority rule

The following must come from authenticated state only:

- user identity
- role
- service-account status
- session validity
- expiry

If a request body attempts to assert a different role or identity, the body is
ignored for authority purposes and may be rejected if it conflicts with the
authenticated state.

## API contract

The auth API is intentionally small and explicit. JSON schemas, status codes,
error envelopes, and JWT claim shapes are defined in [`api.md`](./api.md). The
matching OpenAPI artifact lives at
[`engine/openapi/auth.yaml`](../../engine/openapi/auth.yaml).

### `POST /auth/login`

Starts an authenticated human session.

Request body:

- `email`
- `password`

Behavior:

- validates the credentials
- rejects soft-deleted, disabled, or revoked identities
- derives the authoritative role from authenticated state
- returns a short-lived JWT plus session metadata

Response:

- authenticated `user_id`
- authenticated role
- token or session value
- expiry timestamp
- revocation marker or session version

### `POST /auth/logout`

Ends the current session or marks the current token version revoked.

Behavior:

- accepts the current authenticated session only
- invalidates the presented token or its version marker
- fails closed if the request is unauthenticated

### `POST /auth/password-reset/request`

Starts a self-service password reset.

Request body:

- `email`

Behavior:

- accepts the request without revealing whether the email exists
- issues a reset challenge only when the account is eligible
- records the reset request for audit and expiry tracking

### `POST /auth/password-reset/confirm`

Completes a password reset.

Request body:

- `reset_token`
- `new_password`

Behavior:

- validates the reset token
- stores only the new password hash
- revokes outstanding sessions for the affected identity
- fails closed if the token is invalid or expired

### `GET /auth/session`

Returns the current authenticated session context.

Behavior:

- requires a valid authenticated session
- returns the authoritative user identity, role, and expiry state
- never trusts caller-supplied identity fields

## Role model

The system uses role-bearing authenticated identities. The exact human role set
may be expanded by the product, but role derivation must always be
session-scoped and must never rely on caller-asserted strings.

Current roles surfaced elsewhere in the platform include:

- `admin` — user management (create, edit, delete users; assign roles). Route
  guard: `get_admin_user`.
- `pm` — project lifecycle (create, copy, edit projects; assign project
  members; owns projects via `pm_user_id` on `ProjectRegistry`). Route guard:
  `get_pm_user`.
- `central_team` — in-project operators. Requires explicit project membership;
  no longer has global project access. Can perform in-project work (mapping,
  codegen, review, approval) only on projects they are a member of.
- `project_stakeholder` — business stakeholders with project membership.
  View and approve within assigned projects.
- `read_only_auditor` — view-only across all projects.

`service_account` is not a human role. It is a non-human authentication
principal used by integrations such as API and bulk approval channels. It may
use client secrets for authentication. Its credential policy and scope are
managed explicitly, but it does not add a new platform role.

If the platform introduces additional human roles, they must be added to the
canonical role model rather than inferred ad hoc in request handlers.

## Lifecycle and invalidation

Authentication state must respect user lifecycle:

- active users may authenticate
- soft-deleted users must be rejected at request time
- disabled users must be rejected at request time
- expired sessions must be rejected
- revoked sessions or tokens must be rejected if revocation is supported
- revocation must be supported for human JWTs and service-account secrets

The system must not continue to honor a token simply because it was once valid.

The six session invalidation triggers match actual user lifecycle changes:
- password change → increments `session_version`
- role change → increments `session_version`
- disable → sets `status` to disabled
- logout → records `revoked_at` and stores `revoked_at` on AuthSession
- secret rotation (service accounts) → new `token_identifier`
- soft-delete → sets `soft_deleted_at`

## Security properties

- Passwords are stored as hashes, not plaintext.
- Tokens or session cookies carry only the minimum required identity state.
- Role is derived from authenticated state, not from request data.
- Soft-deleted users cannot continue to act.
- Service accounts are explicit and distinguishable from human users.

## Failure modes

| Situation | Handling |
|-----------|----------|
| Invalid credentials | Reject authentication |
| Expired session or token | Reject request |
| Soft-deleted user | Reject request even if token is still valid |
| Disabled user | Reject request |
| Caller-supplied role conflicts with authenticated role | Ignore caller claim and reject if inconsistent |
| Missing authentication | Reject as unauthenticated |
| Bootstrap secret missing or invalid | Bootstrap path fails closed |

## Acceptance criteria

- [ ] Login uses authenticated credentials rather than request-body role claims.
- [ ] Passwords are stored hashed, never plaintext.
- [ ] A soft-deleted user is rejected even if they still have a valid token.
- [ ] Request bodies cannot override the authenticated role.
- [ ] The system supports bootstrap of the first administrative identity.
- [ ] Service accounts can be represented explicitly without masquerading as
      human users.
- [ ] Authentication state is sufficient for downstream authorization checks.

## Changelog

- 2026-06-29: Linked behavioral auth contract to formal HTTP schemas in
  `api.md` and `engine/openapi/auth.yaml`.
- 2026-06-29: Expanded into a spec-style auth page covering identity model,
  session authority, lifecycle invalidation, bootstrap, failure modes, and
  acceptance criteria.
- 2026-06-29: Added explicit revocation/version tracking for authenticated
  sessions.
- 2026-06-29: Added explicit login, logout, password-reset, and session API
  contracts.
- 2026-07-24: Updated User model fields — added `session_version`, `email` max length (320),
  `status` default "declared". AuthSession now documented with actual table fields
  (`session_id`, `token_identifier`, `revocation_version`, `principal_kind`, `revoked_at`).
  Session authority now accurately describes JWT + session table persistence.
  Added six session invalidation triggers.
- 2026-07-16: Role model expanded from 3 to 5 roles (`admin`, `pm` added);
  `central_team` scoped to explicit project membership; route guards
  documented per role.
