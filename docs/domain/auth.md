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

- Role-sensitive approval behavior is defined in `specs/29-approval-service.md`.
- UI role surfaces are defined in `specs/28-ui.md`.
- Project scoping and per-project isolation are defined in
  `specs/18-project-registry.md`.
- Administrative user and membership lifecycle is defined in `management.md`.
- Security-sensitive decisions and audit expectations are summarized in
  `security.md`.

## Data model

### User

Users live in the shared application database.

Relevant fields:

- `user_id`
- `email`
- `display_name`
- `password_hash`
- `role`
- `status`
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

The session format is stateless JWT. The derived state must be equivalent across
requests and must not depend on server-side session storage.

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

## Role model

The system uses role-bearing authenticated identities. The exact human role set
may be expanded by the product, but role derivation must always be
session-scoped and must never rely on caller-asserted strings.

Current roles surfaced elsewhere in the platform include:

- `central_team`
- `project_stakeholder`
- `read_only_auditor`

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

- 2026-06-29: Expanded into a spec-style auth page covering identity model,
  session authority, lifecycle invalidation, bootstrap, failure modes, and
  acceptance criteria.
- 2026-06-29: Added explicit revocation/version tracking for authenticated
  sessions.
