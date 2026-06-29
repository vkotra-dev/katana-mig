# Harness

This page is the derived bundle for the harness and harness-adjacent platform
layer.

It consolidates the current execution, orchestration, durability, and lifecycle
behavior from the numbered specs so there is one place to read how the system
runs.

**Derived from:** `specs/00-architecture-overview.md`, `specs/01-run-manager.md`,
`specs/02-context-assembler.md`, `specs/03-model-adapter.md`,
`specs/04-tool-router.md`, `specs/05-policy-gate.md`, `specs/06-sandbox.md`,
`specs/07-verifier.md`, `specs/08-audit-bus.md`, `specs/09-failure-taxonomy.md`,
`specs/10-contract-registry.md`, `specs/11-change-requests.md`,
`specs/12-persistence.md`, `specs/13-runtime-orchestrator.md`,
`specs/14-planning-orchestrator.md`, `specs/15-domain-lexicon.md`,
`specs/16-intake-project-definition.md`, `specs/17-lifecycle-conductor.md`,
`specs/18-project-registry.md`, `specs/19-review-gate.md`,
`specs/30-model-router.md`, `specs/31-ingestion-trigger.md`,
`specs/32-notification-handler.md`, plus the current domain bundle pages.

This page is the working contract for the harness bundle. The numbered specs
remain the historical derivation archive.

## Purpose

Provide the operational contract for:

- one-run execution
- tool routing and policy gating
- sandboxed tool execution
- result verification
- audit logging
- run durability and resume
- multi-project isolation and routing
- lifecycle baton passing
- planning and review above the run loop
- notification plumbing

## Layer map

### Core harness

The core harness is the single-run execution engine:

- `01` Run Manager
- `02` Context Assembler
- `03` Model Adapter
- `04` Tool Router
- `05` Policy Gate
- `06` Sandbox
- `07` Verifier
- `08` Audit Bus
- `09` Failure Taxonomy

This layer owns the run loop and the disposition model.

### Platform harness

The platform layer turns the harness into a multi-project operating system:

- `10` Contract Registry
- `11` Change Requests
- `12` Persistence
- `13` Runtime Orchestrator
- `14` Planning Orchestrator
- `15` Domain Lexicon
- `16` Intake / Project Definition
- `17` Lifecycle Conductor
- `18` Project Registry
- `19` Review Gate
- `30` Model Router
- `31` Ingestion Trigger
- `32` Notification Handler

This layer owns persistence, orchestration, lifecycle handoff, and cross-cutting
policy surfaces.

## Core execution model

The run manager owns the loop. Everything else proposes or reports.

Run loop order:

1. budget check
2. audit health check
3. resume pinned action if present
4. build context
5. call model
6. classify final or tool calls
7. route, gate, execute, verify, and dispose

The run manager decides whether the run continues, retries, blocks, escalates,
or stops.

## Disposition and failure handling

The harness treats these as first-class outcomes:

- transient failure
- logical failure
- fatal failure
- policy denial
- approval pause
- budget exhaustion
- success

Budget exhaustion is a graceful terminal state, not an exception.

## Tool flow

Tool calls are always treated as an array.

The run manager:

- validates each call
- applies policy to each call
- pauses the entire batch if any call requires approval
- executes allowed calls in array order
- fans results back into exactly one next step

This preserves deterministic fan-in and keeps approval pinning exact.

## Audit and verification

The audit bus records every decision branch:

- model calls
- tool calls
- denials
- approval pauses
- verifier outcomes
- budget stops
- errors

The verifier is the final authority on whether a result is successful.
Infrastructure success alone is not sufficient.

## Observability

The harness must be observable enough to answer, after the fact:

- what ran
- what decision was made
- why the run paused, retried, or stopped
- which project and environment were involved
- which tool calls, approvals, and policy checks occurred

Minimum observability requirements:

- structured logs for run lifecycle events, tool calls, pauses, and failures
- metrics for run starts, completions, pauses, retries, denials, and fatal
  stops
- traces or equivalent correlation for the run loop and downstream tool calls
- alerting for policy failures, audit sink failures, approval-service failures,
  and sustained run-stop spikes
- correlation IDs that tie together model calls, tool calls, audit events, and
  the owning project

Observability data must not leak secrets, credentials, or raw PII.

## Sandbox boundary

All tool execution occurs through the sandbox interface.

This includes:

- source access
- database access where allowed
- file and script execution
- model-adjacent tooling invoked by the harness

Nothing executes outside the sandbox boundary.

## Persistence and resume

The harness preserves enough state to reconstruct a paused run.

Durable state includes:

- paused run state
- audit events
- change requests
- contracts
- queue items
- leases
- persisted rule sets and related artifacts where configured

Resume must re-execute the exact approved pinned action. Side-effecting tools
must be idempotent by key.

### Backup and restore

The durable state above is the restore boundary. Backup and restore are defined
around those persisted records, not around ephemeral in-memory execution state.

The system backs up:

- run state and checkpoints
- audit events
- change requests and approvals
- contracts and frozen artifacts
- queue and lease state needed to resume safely

The system restores by:

- rehydrating the durable records from the latest trusted backup
- rebuilding queue state from persisted work items and leases
- leaving frozen artifacts immutable during recovery
- resuming only pinned actions that still match the restored durable record

If the restored state cannot be reconciled with the durable records, the system
remains paused or blocks new work until the inconsistency is resolved.

## Lifecycle orchestration

The lifecycle conductor advances a change through the outer graph:

- ingestion / trigger
- intake
- planning
- approval gate
- implementation
- verification
- review
- delivery

The conductor passes frozen batons between stages.
Backward transitions mint new batons; they never mutate prior ones.

## Multi-project scope

The project registry partitions the platform by `project_id`.

This means:

- runs are project-scoped
- audits are project-scoped
- leases are project-scoped
- routing is project-scoped
- membership and stakeholder access are project-scoped where applicable

Cross-project access is rejected rather than guessed.

## Planning and review

Planning sits above the harness loop.

The planner produces a frozen `PlanArtifact`. The review gate reconciles the
implementation result against that frozen plan before delivery.

The harness itself does not decide what to build. It executes the approved work.

## Notifications and external surfaces

The notification handler is an audit-event-driven adapter.

The UI and approval service sit above the harness and use the approved routes:

- the UI submits structured approvals
- the approval service resumes parked batons
- the ingestion trigger routes new work into the lifecycle conductor

## Failure modes

| Situation | Handling |
|-----------|----------|
| Policy backend unavailable | Fail closed; stop the run fatally before any gated action proceeds |
| Audit sink unavailable | Stop the run fatally; do not continue without a durable record |
| Approval service unavailable on pause | Keep the run parked; do not bypass approval |
| Approval service unavailable on resume | Keep the baton parked and retry later; do not substitute a different action |
| Approved action on resume is missing | Reject resume |
| Tool call arguments invalid | Schema reject |
| Any tool call requires approval | Pause the batch before execution |
| Sandbox execution crashes | Classify and dispose through the run manager |
| Cross-project access attempt | Reject |

## Acceptance criteria

- [ ] The run manager owns the loop and the disposition decision.
- [ ] Tool calls are handled as arrays with deterministic fan-in.
- [ ] The verifier is the final authority on success.
- [ ] All tool execution goes through the sandbox.
- [ ] Audit events cover every branch.
- [ ] Durable pause/resume can reconstruct a run.
- [ ] Backup and restore can rehydrate durable state without mutating frozen
      artifacts.
- [ ] Lifecycle stages communicate through frozen batons.
- [ ] Project boundaries are enforced by `project_id`.
- [ ] Policy, audit, and approval outages fail closed without bypassing the
      governing gate.
- [ ] The harness emits structured logs, metrics, traces, and alerts for the
      lifecycle and failure states it controls.

## Future considerations

These are not launch blockers. They can be revisited after the bundle is in
production use:

- context compression once long-run metrics exist
- whether delivery should remain outside the current bundle or become a future
  derived page
- whether the platform bundle should split into separate core-harness and
  platform docs later

## Changelog

- 2026-06-29: Added derived harness bundle page to consolidate the execution,
  orchestration, durability, and lifecycle behavior from the numbered specs.
