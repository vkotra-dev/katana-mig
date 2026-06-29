# Runs

This page defines the migration-domain run as an auditable, restart-safe unit of
work for one destination object in one project.

It is about the object-level execution unit, not the harness run manager. The
run consumes frozen project state and produces auditable execution results.

## Purpose

Provide a durable execution container that:

- owns exactly one project-scoped object-level execution
- consumes pinned approved artifacts rather than re-deriving them
- preserves checkpoints for restart-safe resume
- records which approved snapshots were used
- preserves lineage and reconciliation evidence

The run is the unit of observability for migration execution.

## Responsibilities

- Bind execution to exactly one `project_id`.
- Bind execution to exactly one destination object.
- Record the source slice and downstream snapshot versions consumed.
- Preserve pause and resume checkpoints.
- Keep execution auditable per object.
- Resume from the exact pinned work that was approved.
- Surface failures as recorded outcomes rather than silent fallback behavior.

## Out of scope

- Defining the source contract itself.
- Defining the project world description.
- Planning implementation work.
- Replacing source analysis when the source has changed.
- Mutating approved source, mapping, lookup, or freeze artifacts.

## Relationship to other pages

- Source contracts and source slices are defined in `source-model.md`.
- Project ownership and version identity are defined in `project.md`.
- Intake and frozen project definition mechanics live in
  `specs/16-intake-project-definition.md`.
- Multi-project routing and isolation live in `specs/18-project-registry.md`.
- Lifecycle pause/resume and baton flow are defined in `specs/17-lifecycle-conductor.md`.

## Data model

### Run record

A run belongs to one project and one destination object.

Relevant fields:

- `run_id`
- `project_id`
- destination object name
- source definition reference
- source slice version
- mapping snapshot version
- lookup snapshot version
- code-generation input snapshot version
- knowledge-freeze version
- status
- current stage
- approvals and checkpoints
- environment
- start metadata
- pause metadata
- resume metadata
- completion metadata

The exact persisted representation may include more operational fields, but these
facts are the minimum needed to explain what happened.

The run record may also keep a frozen summary of selected snapshot metadata for
audit queries, but the version references remain authoritative.

### Snapshot set

A run should be able to identify the approved artifact set it consumed:

- source definition version or reference
- approved source slice version
- approved mapping snapshot version
- approved lookup snapshot version
- approved code-generation input version
- knowledge-freeze version, where applicable

The run does not own those artifacts. It records their version identities.

### Checkpoint

A checkpoint is the exact pinned work position from which the run can resume.

It should capture enough information to restart without guessing:

- current stage
- current object
- current environment
- approved snapshots already selected
- last completed checkpoint boundary
- reason for pause, if any

## Execution behavior

Runs should be:

- restart-safe
- queue-backed
- lease-backed
- auditable per object
- resumable from the last approved checkpoint
- isolated to the project's declared source and destination scope

Runs do not re-derive source structure from runtime inputs. They consume the
approved source slice and downstream snapshots already produced by the project's
source/run workflow.

### Execution flow

The normal execution flow is:

1. The project definition and registry resolve the owning project.
2. The latest approved source slice and downstream snapshots are selected for
   the stage about to start and pinned on the run record.
3. The run is leased and started for one destination object.
4. Execution proceeds against the pinned artifacts.
5. Reconciliation records lineage and outcomes.
6. The run completes, pauses, or fails with a recorded reason.

Each run targets exactly one environment. Projects that must traverse multiple
execution environments create separate environment-specific runs in declared
order rather than one run with hidden sub-runs.

### Resume rule

Resume must continue from the exact approved work position that was already
recorded. It must not silently substitute a different object, project, or
approved artifact set.

## Pause and retry behavior

Runs can pause for:

- human approval
- provider limits
- lifecycle budget exhaustion
- missing prerequisite approvals or frozen artifacts
- policy rejection

When a run pauses, the reason and checkpoint must be preserved so the system can
resume the exact pinned work later.

### Source change handling

If the source changes, source analysis must rerun.

If only mapping or lookup changes, only those approvals rerun. The next stage
start selects the latest approved snapshots and pins them for that stage.
Resume uses the pinned checkpoint state; it does not silently swap to newer
approvals while a stage is already in flight.

## Progress and history

The run history should make it possible to see:

- what object was processed
- which approved source, mapping, lookup, code-generation, and freeze snapshots
  were used
- where the run paused
- whether the run completed, failed, or is awaiting approval
- which project owned the run
- which environment the run targeted
- which checkpoint the run resumed from

The execution history should be sufficient to reconstruct the run without
consulting mutable external state.

## Reconciliation and lineage

Every run must leave behind enough evidence to answer:

- which source row produced which destination row
- which destination row came from which source row
- which mapping rules were used
- which rows were rejected, duplicated, or partially mapped

Reconciliation is not optional. If execution completes without lineage and
outcome evidence, the run is incomplete.

## Failure modes

| Situation | Handling |
|-----------|----------|
| Run starts without a frozen project definition | Block start |
| Run starts without the required source slice | Block start or escalate |
| Run starts without approved downstream snapshots | Block start or escalate |
| Run targets the wrong project | Reject as isolation breach |
| Source changed after approval | Re-run source analysis before continuing |
| Mapping or lookup changed after approval | Re-run affected approval path before continuing |
| Unmapped lookup value encountered during execution | Record rejected lineage and raise `LookupDeltaCR` |
| Reconciliation check fails | Record logical failure; do not treat infra success as success |
| Provider limit pauses execution | Preserve checkpoint and resume later |
| Budget exhausted | Stop gracefully; do not throw as if it were unexpected |
| Checkpoint cannot be restored | Escalate as a durable execution failure |

## Acceptance criteria

- [ ] A run is scoped to exactly one project and one destination object.
- [ ] The run record captures the exact approved snapshot versions it used.
- [ ] The run preserves enough checkpoint data to resume without guessing.
- [ ] A source change forces source analysis to rerun.
- [ ] Mapping or lookup changes rerun only their approval path.
- [ ] Unmapped lookup values are not silently handled.
- [ ] Reconciliation evidence is produced for every execution run.
- [ ] The run history is sufficient to reconstruct the execution path later.
- [ ] The page makes clear which behavior belongs here and which belongs in
      `source-model.md`, `project.md`, or the lifecycle specs.

## Changelog

- 2026-06-29: Expanded into a spec-style run page covering ownership,
  snapshot recording, checkpoints, resume rules, reconciliation evidence,
  failure modes, and acceptance criteria.
- 2026-06-29: Clarified that the run record can keep frozen snapshot summaries
  and that multi-environment work is represented as separate environment runs.
