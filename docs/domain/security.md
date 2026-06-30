# Security

This page defines the security boundaries the migration platform must preserve.

It is a cross-cutting policy page. It states the hard boundaries that the rest
of the bundle must obey.

## Purpose

Protect the platform from unauthorized access, cross-project leakage, unsafe
PII handling, and non-auditable security-sensitive actions.

The security model must ensure:

- authenticated identity is authoritative
- request bodies cannot smuggle identity or role claims
- project and workspace isolation is preserved
- PII is not exposed beyond permitted stages
- approvals and denials are auditable
- secrets and credentials are not leaked into logs or artifacts

## Responsibilities

- Enforce identity-derived authorization context.
- Preserve project isolation and tenancy boundaries.
- Preserve approval, denial, and pause auditability.
- Prevent raw PII from being exposed to unauthorized stages or logs.
- Prevent secrets, credentials, and session tokens from appearing in artifacts.
- Fail closed when security backends are unavailable.
- Ensure security-sensitive decisions are explicit and reviewable.

## Out of scope

- The mechanics of login itself.
- Per-feature authorization policy details.
- Human approval business logic.
- Source analysis and migration behavior beyond their security boundaries.

## Relationship to other pages

- Authentication mechanics are defined in `auth.md`.
- Administrative user and membership lifecycle is defined in `management.md`.
- Role-sensitive approval behavior is enforced by the approval-service route in
  the harness bundle and surfaced through `ui.md`.
- Project tenancy and isolation are defined in `project.md`, `runs.md`, and
  the project registry behavior in the harness bundle.
- PII handling is constrained by `source-model.md` and the migration analysis
  pipeline in the harness bundle.
- Policy gating is defined in the harness bundle.
- Audit event emission is defined in the harness bundle.

## Security boundaries

### Identity boundary

All request identity comes from authenticated session state. Request bodies are
not authoritative for identity or role.

Security consequence:

- caller-asserted roles are ignored
- spoofed identity claims are rejected
- unauthorized or stale sessions are rejected

### Project boundary

Every project, run, baton, lease, and audit event belongs to exactly one
project. A request for one project must not read or mutate another project’s
state.

Security consequence:

- cross-project access is rejected
- ambiguous routing is escalated rather than guessed
- project scope is an explicit input to every sensitive operation

### Workspace and artifact boundary

Sandboxed execution and artifact handling must never leak into unrelated
workspaces, projects, or logs.

Security consequence:

- a run executes only in its own project workspace
- generated artifacts stay within the intended scope
- credentials and secrets remain out of artifacts

### PII boundary

PII must be classified before value-level analysis. Once classified, the policy
gate enforces what can be read, logged, or passed to models.

Security consequence:

- personal data columns are not sent to a model unless explicitly permitted
- masked or approved slices are used for AI-facing steps
- downstream tools obey the classification result

### Audit boundary

Security-sensitive decisions must be logged.

Security consequence:

- denials are auditable
- approval pauses are auditable
- policy-relevant rejections are auditable
- sink failure is treated as a serious operational issue, not a silent drop

## Threat model

The main risks the system must control are:

- unauthorized user access
- stale user sessions
- request-body spoofing of roles or project identity
- cross-project data leakage
- PII exposure to model or log sinks
- secret leakage in artifacts or telemetry
- approval bypass or unlogged approval decisions
- failure-open behavior in policy or identity checks

## Control requirements

### Authentication and authorization

- Authenticated identity is authoritative.
- Role is derived from authentication state.
- Request bodies cannot override identity or role.
- Soft-deleted and disabled users cannot act.
- Service accounts must be explicit and scoped.
- Human sessions use short-lived JWTs with explicit revocation support.
- A `central_team` user cannot delete their own account or downgrade their own
  role. Platform operators must always retain at least one recovery path.

### Project isolation

- All project-scoped resources remain partitioned by `project_id`.
- Routing must be unambiguous.
- Shared infrastructure must not imply shared access.
- Any attempt to cross project boundaries is a bug, not a warning.
- Project scope is resolved separately by the registry and then enforced on
  sensitive operations.

### PII handling

- Raw PII never reaches unauthorized analysis stages.
- Masked slices are the approved AI-facing form.
- PII-bearing inputs are scoped as narrowly as possible.
- Policy gate decisions are enforced before execution, not after.

### Secrets and credentials

- Passwords are hashed.
- Service accounts authenticate with client secrets.
- Tokens, secrets, and connection credentials are never stored in plaintext.
- Credentials are not emitted in logs, audit payloads, or generated artifacts.
- External connections should use the minimum required credential scope.
- Password changes, role changes, disable events, logout, and secret rotation
  revoke outstanding sessions.

### Auditability

- Denials, approvals, and pauses are recorded.
- Security-sensitive failures are visible in audit.
- The system must be able to explain why access was granted or denied.
- If audit storage is unavailable, the system stops rather than continuing with
  unaudited changes.

### Dependency outages

- Policy services fail closed; gated actions do not proceed when policy cannot
  be evaluated.
- Approval services do not bypass human review when unavailable; pending
  approvals remain parked until the service returns.
- Audit services do not fail open; if a durable record cannot be written, the
  run stops or remains parked depending on the current stage.

### Retention and access

- Audit records are retained for at least 365 days unless a longer contractual
  or legal hold applies.
- Audit access is read-only and project-scoped.
- Central team operators and read-only auditors may read audit history; writes
  remain system-only.

## Failure modes

| Situation | Handling |
|-----------|----------|
| Unauthenticated request | Reject |
| Caller attempts to assert role in request body | Ignore claim; reject if inconsistent |
| Soft-deleted user attempts access | Reject |
| Disabled session or expired token | Reject |
| Cross-project access attempt | Reject |
| PII-bearing value reaches a forbidden stage | Deny or stop the run, depending on the stage boundary |
| Secret appears in artifact or log | Treat as security defect; do not silently accept |
| Policy backend unavailable | Fail closed |
| Audit sink unavailable | Surface as serious failure; do not continue silently |

## Acceptance criteria

- [ ] A caller cannot elevate privileges by changing the request body.
- [ ] Soft-deleted users are blocked at request time.
- [ ] Cross-project access is rejected.
- [ ] PII is blocked before unauthorized value-level analysis.
- [ ] Secrets do not appear in logs or generated artifacts.
- [ ] Denials, approvals, and pauses are auditable.
- [ ] Policy failures fail closed rather than open.

## Changelog

- 2026-06-29: Expanded into a spec-style security page covering boundaries,
  threat model, controls, failure modes, and acceptance criteria.
- 2026-06-29: Added short-lived JWT revocation, explicit session invalidation
  triggers, and audit retention/access policy.
