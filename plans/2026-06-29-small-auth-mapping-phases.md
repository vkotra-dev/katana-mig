# Small Auth + Mapping Phases Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver the smallest independently testable slices for login, password reset, roles, and mapping without coupling them into one large release.

**Architecture:** This repo currently contains the domain contract pages only, so the plan is organized as a roadmap from those contracts to implementation. Phase boundaries are chosen so each slice can be validated on its own: authentication first, self-service password recovery second, role and membership authority third, and a minimal migration mapping slice last. The mapping phase is intentionally narrow: one approved mapping path, one unmapped-value failure path, and explicit snapshot/lineage recording.

**Tech Stack:** Python 3.11+, `pytest`, `ruff`, `mypy --strict`, typed protocols, frozen dataclasses, append-only audit events.

## Global Constraints

- Python 3.11+
- full type hints everywhere
- `mypy --strict` must stay clean
- `ruff` must stay clean
- no bare `Any` in committed code
- use `typing.Protocol` for collaborators
- prefer frozen dataclasses for artifacts and audit records
- keep audit append-only
- do not add business logic to wiring
- do not cross the harness / migration boundary in imports
- authentication state is authoritative; request bodies are not
- passwords are hashed, never stored in plaintext
- service accounts are explicit and scoped
- project membership is separate from role
- source/mapping/lookup artifacts are versioned and immutable

---

## Phase 1: Login and Session

**Scope**
- Password login for human callers
- Stateless JWT session issuance
- Authenticated identity and role as the only authority source
- Bootstrap path for the first administrative identity

**Files**
- Modify: `docs/domain/auth.md`
- Modify: `docs/domain/security.md`
- Modify: `docs/domain/management.md`
- Modify: `docs/domain/launch-gate.md`

**Exit Criteria**
- Login succeeds with valid credentials and fails closed for invalid credentials
- JWTs carry the minimum identity state needed by downstream authorization
- Soft-deleted and disabled users cannot continue to act
- Request bodies cannot override authenticated identity or role

**Tests**
- Login with a valid password issues a JWT
- Login with an invalid password is rejected
- A soft-deleted user is rejected even with a previously issued JWT
- A caller-supplied role is ignored when it conflicts with authenticated state

---

## Phase 2: Password Reset

**Scope**
- Self-service password recovery or reset flow
- Password replacement without role escalation
- Invalidation of prior credentials after reset

**Files**
- Modify: `docs/domain/auth.md`
- Modify: `docs/domain/management.md`
- Modify: `docs/domain/security.md`
- Modify: `docs/domain/ui.md`
- Modify: `docs/domain/launch-gate.md`

**Exit Criteria**
- A user can recover access without administrative role changes
- Reset flow requires proof of control over the account
- Password reset rotates the credential and invalidates the old one
- The reset path cannot change role or project access

**Tests**
- Reset token or equivalent challenge works once and cannot be reused
- Password reset stores only a new hash
- Old password stops working after reset
- Reset cannot be used to promote the user’s role

---

## Phase 3: Roles and Membership

**Scope**
- Role assignment for `central_team`, `project_stakeholder`, and `read_only_auditor`
- Project membership as a separate mapping from user role
- Central-team administrative controls

**Files**
- Modify: `docs/domain/management.md`
- Modify: `docs/domain/auth.md`
- Modify: `docs/domain/security.md`
- Modify: `docs/domain/ui.md`
- Modify: `docs/domain/launch-gate.md`

**Exit Criteria**
- Role changes are explicit administrative actions
- Project access for stakeholders depends on membership, not role alone
- Read-only auditors can inspect but not mutate
- Role changes and membership changes are auditable

**Tests**
- Non-admin role changes are rejected
- Stakeholder without membership cannot access project-scoped actions
- Admin can add and remove project membership
- Read-only auditor cannot perform management actions

---

## Phase 4: Minimal Mapping Slice

**Scope**
- One narrow migration mapping workflow
- Approved mapping snapshot selection
- Unmapped-value handling through the governed delta path

**Files**
- Modify: `docs/domain/source-model.md`
- Modify: `docs/domain/runs.md`
- Modify: `docs/domain/security.md`
- Modify: `docs/domain/launch-gate.md`

**Exit Criteria**
- Mapping consumes approved, immutable snapshots
- A known mapping case completes end to end
- An unmapped value fails through the governed `LookupDeltaCR` path
- Mapping provenance is recorded in the run history

**Tests**
- Approved mapping path produces the expected mapping artifact
- Unmapped value path raises the governed delta condition
- Mapping artifacts remain immutable after approval
- Run records identify the mapping snapshot version used

---

## Phase Order

1. Login and session
2. Password reset
3. Roles and membership
4. Minimal mapping slice

Each phase should be shippable and testable before the next phase starts.

## Open Assumption

This plan treats “mapping” as the smallest migration mapping slice described in the domain docs, not the full migration code-generation pipeline.

