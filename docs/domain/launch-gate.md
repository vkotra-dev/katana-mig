# Launch Gate

This page is the production-readiness checkpoint for the current bundle.

It answers a narrow question: what still has to be true before the system can be
treated as launch-ready?

Status legend:

- `Done` means the bundle already specifies it clearly enough.
- `Pending` means the bundle still needs a decision or tighter wording.
- `Blocked` means the decision depends on an external product or platform choice.

## Checklist

| Area | Item | Done | Pending | Blocked | Notes |
|---|---|---:|---:|---:|---|
| Auth | Finalize authentication mechanism | x |  |  | Password login for human callers |
| Auth | Finalize session model | x |  |  | Stateless JWT sessions |
| Auth | Finalize login and password-reset API contract | x |  |  | `POST /auth/login`, password-reset request/confirm, session lookup |
| Auth | Finalize service-account behavior | x |  |  | Client secrets, scope, and allowed channels |
| Auth | Finalize project-scope binding | x |  |  | Registry resolves project scope separately |
| Project | Finalize snapshot selection end to end | x |  |  | Stage-local selection is pinned across the bundle |
| Project | Finalize project registry storage model | x |  |  | `definition_id` pointer plus frozen artifact store |
| Project | Finalize per-environment configuration placement | x |  |  | Settings live in the frozen project definition |
| Project | Finalize destination-schema sharing policy | x |  |  | Exclusive destination ownership per project definition |
| Runs | Finalize run-record contents for audit and recovery | x |  |  | Version refs plus frozen snapshot summary |
| Runs | Finalize multi-environment run semantics | x |  |  | Separate environment-specific runs in declared order |
| Source model | Finalize source invalidation rules | x |  |  | Source contract changes invalidate downstream artifacts |
| Source model | Finalize source slicing granularity | x |  |  | One shared approved slice per source contract version |
| Security | Define production token revocation and expiry policy | x |  |  | Short-lived JWTs with explicit revocation support |
| Security | Define audit retention and access policy | x |  |  | 365-day minimum, read-only project-scoped access |
| Harness | Define outage handling for policy, audit, and approval services | x |  |  | Fail closed; parked approvals never bypass review |
| Harness | Define backup, restore, and disaster recovery expectations | x |  |  | Durable state is backup/restore boundary; frozen artifacts stay immutable |
| Harness | Define observability requirements | x |  |  | Structured logs, metrics, traces, and failure alerts |
| Governance | Define rollout and rollback expectations | x |  |  | Versioned rollout by environment; rollback restores prior known-good versions |
| Governance | Resolve remaining open questions in the bundle | x |  |  | Harness questions moved to future considerations |

## Done Enough Today

The bundle is already strong enough on:

- repo governance and task flow
- harness control flow and safety invariants
- project, runs, source model, auth, management, UI, and security structure
- auditability, sandboxing, and cross-project isolation

Those areas are documented; the remaining work is mainly production hardening and
decision closure.

## Launch Rule

The system is not launch-ready until every `Pending` item above has either:

- been decided and documented, or
- been explicitly accepted as a release deferral with an owner and date

## Changelog

- 2026-06-29: Added a production-readiness gate for the current domain bundle.
