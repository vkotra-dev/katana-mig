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
- Intake and frozen project definition mechanics live in `governance.md` and
  the intake behavior described in the harness bundle.
- Multi-project routing and isolation live in `security.md`, `project.md`, and
  the harness bundle.
- Lifecycle pause/resume and baton flow are defined in `harness.md`.

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
- lookup snapshot versions
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

`lookup_snapshot_versions` is a JSON object keyed by lookup name. Each value is
the approved lookup snapshot version pinned for that lookup during execution.
When a run only consumes one lookup, the map contains a single entry. When a run
consumes multiple lookups, the map preserves every version so the audit trail is
complete.

### Snapshot set

A run should be able to identify the approved artifact set it consumed:

- source definition version or reference
- approved source slice version
- approved mapping snapshot version
- approved lookup snapshot versions
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

### Run loop

The run loop operates at two levels: an outer object loop and an inner row loop.

#### Outer loop — per destination object

```
for each destination_object in project:
    receive stage baton (carries approved snapshot versions)
    pin source_slice_version, mapping_snapshot_version,
        lookup_snapshot_versions, code_generation_input_snapshot_version
        onto RunRecord
    execute inner row loop
    generate SQL from MappingArtifact.mapped_rows
    record reconciliation evidence
    sign off → mint frozen stage baton (carries artifact versions consumed)
    pass baton to next stage
```

One run record per destination object. The outer loop does not share run
records across objects; each object is independently auditable and restartable.

#### Inner loop — per source row

```
for each source_row in approved SourceSlice:
    apply MappingSnapshot.field_bindings
        → rename and select fields to destination shape
    apply LookupSnapshot.value_map to each translated field
        → if source value is missing from value_map:
            pause loop
            raise LookupDeltaCR (change request)
            wait for human resolution and approval
            resume from last checkpoint with updated LookupSnapshot
    write destination-shaped row → MappingArtifact.mapped_rows
    if checkpoint_boundary reached:
        write RunCheckpoint (stage, object, environment,
            approved_snapshots, last_completed_checkpoint_boundary)
```

The checkpoint boundary is every 500 rows by default. It is configurable per
project via `domain_config`. The checkpoint records the exact row offset and
approved snapshot set so the inner loop can resume from the correct position
without reprocessing already-committed rows.

#### LookupDeltaCR interrupt

When the inner loop encounters a source value absent from `LookupSnapshot.value_map`:

1. The loop pauses at the current row; the checkpoint is written first.
2. A `ChangeRequest` of type `LookupDeltaCR` is raised, carrying the lookup
   name, the unmapped source value, and the run and object context.
3. A human operator resolves the CR by adding the missing mapping to the lookup.
4. The approval gate produces a new `LookupSnapshot` version.
5. The stage baton is updated with the new lookup version.
6. The run resumes from the last checkpoint using the updated snapshot — it
   does not restart the whole object loop from row zero.

The run never silently substitutes a default or skips an unmapped value.

### Baton handoff

A **baton** is the frozen artifact passed between lifecycle stages. It is the
formal unit of stage sign-off and handoff.

Each baton carries:

- the stage that produced it
- the approved artifact versions it consumed or produced
- the destination object and environment scope
- a reference to the approval record that authorised the sign-off

When a stage completes and is approved, it mints a new frozen baton and passes
it to the next stage. The next stage reads the baton to discover exactly which
artifact versions to consume — it does not re-query for the latest approved
versions, because the baton already encodes the approved decision.

**Backward transitions** (rejection, rework) mint a new baton pointing back to
the earlier stage. The rejected baton is never mutated. Both the original and the
rework baton are preserved for audit.

Stage sequence and baton chain for a migration object run:

```
[source analysis approved]
    → baton_1: {source_slice_version}
        → [mapping approved]
            → baton_2: {source_slice_version, mapping_snapshot_version}
                → [lookup approved]
                    → baton_3: {source_slice_version, mapping_snapshot_version,
                                lookup_snapshot_versions}
                        → [code generation run — mints CodeGenerationArtifact,
                                               supersedes prior active artifact for
                                               (project, destination_object_name)]
                            → baton_4: {…, code_generation_input_snapshot_version,
                                        codegen_artifact_id}
                                → [review gate (Gate 1 / Gate 2 / impact review)]
                                    → baton_5: {…, knowledge_freeze_version}
                                        → [delivery / environment promotion]
```

`knowledge_freeze_version` is the `codegen_artifact_id` from baton_4 after it
clears the review gate. No new artifact is minted — the `CodeGenerationArtifact`
already captures every upstream version (source slice, mapping snapshot, lookup
snapshot set) and the generated SQL bundle. Gate approval is the act of
freezing; the artifact was already the knowledge container.
```

A baton arriving at a stage without the required approved versions causes the
stage to block rather than proceed with incomplete inputs.

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

### Reconciliation report schema

A `ReconciliationReport` is the persisted evidence record for a reconciliation
run:

- `report_id` links the evidence bundle to the run
- `run_id` ties the report to one run in one project
- `checks` stores the ordered list of `{check_name, status, detail}` results
- `overall_status` is `"in_progress"`, `"pass"`, or `"fail"`
- `row_count_summary` stores `source_rows`, `destination_rows`, `rejected`,
  `duplicated`, and `partially_mapped`
- `created_at` and `completed_at` define the report lifetime

Failed checks are surfaced at the top of the reconciliation screen, but the
stored order remains the execution order for auditability. Re-running
reconciliation creates a new report; older reports remain available for review.

### Lineage evidence schema

A `ReconciliationLineageRow` records the row-level evidence that the screen
explores:

- `lineage_row_id`, `report_id`, and `run_id`
- `source_row_index` identifies the approved source row position; `null` means
  an orphaned mapped row with no matching source row
- `source_row_key` stores the display key extracted from the first CSV column
- `destination_row_id` stores the display identifier for the mapped destination
- `mapping_rules_applied` records the `src_field → dst_field` rules used
- `outcome` is `"confirmed"`, `"rejected"`, `"duplicated"`, or
  `"partially_mapped"`
- `outcome_detail` explains non-confirmed outcomes

The Reconciliation & Lineage screen lets a reviewer drill in both directions:
source row to destination row(s), and destination row back to its source row.
The evidence export bundles the report and lineage rows into one auditable JSON
artifact.

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

- 2026-06-29: Updated baton_4 to reference codegen_artifact_id (CodeGenerationArtifact)
  instead of mapping_artifact_id; added supersession note on code generation run.
- 2026-06-29: Added run loop section covering outer per-object loop, inner
  per-row loop, LookupDeltaCR interrupt, checkpoint boundary rule, and baton
  handoff chain across lifecycle stages.
- 2026-06-29: Expanded into a spec-style run page covering ownership,
  snapshot recording, checkpoints, resume rules, reconciliation evidence,
  failure modes, and acceptance criteria.
- 2026-06-29: Clarified that the run record can keep frozen snapshot summaries
  and that multi-environment work is represented as separate environment runs.
