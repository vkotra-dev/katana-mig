# Project

This page defines the project as the top-level governed container for a
migration effort.

It is intentionally about the **world** the system operates in, not the work
plan. The project captures ownership, scope, source contracts, destination
ownership, and the snapshot policy that downstream execution consumes.

## Purpose

Provide a durable business container that owns:

- the client-owned destination schema
- one or more declared source contracts
- project-level approvals and source-slice policy
- run grouping and audit boundaries
- lifecycle state
- contacts and escalation paths
- the snapshot policy used by execution and code generation

The project is the stable anchor for intake, planning, execution, and
reconciliation. Everything else is scoped to a `project_id`.

## Responsibilities

- Own the project definition and its current version identity.
- Preserve declared source contracts instead of inferring them from runtime
  connection strings.
- Keep destination schema ownership with the client.
- Define the source/run policy that downstream stages must obey.
- Keep project state partitioned from all other projects.
- Carry unresolved project questions explicitly instead of guessing.

## Out of scope

- Defining implementation steps or task lists.
- Planning the work to perform.
- Running the migration.
- Discovering source structure from connection strings alone.
- Mutating the destination schema.

## Relationship to other pages

- The shape of each source contract is defined in `source-model.md`.
- The intake and freeze mechanics are defined in `governance.md` and the
  intake behavior described in the harness bundle.
- Project isolation and multi-project routing are defined in `security.md`,
  `runs.md`, and the harness bundle.
- The run unit of work is defined in `runs.md`.

## Data model

The system needs two closely related project records.

### `ProjectDefinition`

`ProjectDefinition` is the frozen world description produced by intake.
It captures the current project contract and is versioned.

Relevant fields:

- `project_id`
- `definition_id`
- `name`
- `goal`
- `repos`
- `workspace`
- `environment`
- `execution_environments`
- `model_policy`
- `canonical_terms`
- `constraints`
- `unresolved_questions`
- `assumptions`
- `domain_config`
- `status`

For migration workloads, `domain_config` carries the frozen
`MigrationProjectConfig`. The known fields are:

```
MigrationProjectConfig:
  target_db_engine        "mssql" | "oracle" | "postgresql" | "mysql"
                          Required before code generation. The destination database
                          engine; drives SQL dialect selection for all generated DDL
                          and stored procedures.
  staging_schema          string | null
                          Schema name for staging tables (e.g. "stg", "staging").
                          If null, staging tables land in the default schema.
                          Combined with the naming convention stg_{destination_object_name}
                          to form the full table reference used in generated scripts.
  dry_run                 bool (default false)
                          When true, generated scripts are validated but not executed
                          in the target environment.
  sample_policy           object | null
                          Controls how many source rows are included in the approved
                          source slice for analysis purposes.
  destination_schema_ddl  string | null
                          Raw DDL of the client-owned destination schema, submitted
                          during project initiation (stitch 07, Step 3). Stored verbatim.
                          Parsed by the mapping stage (001w) to extract the list of
                          destination field names available for binding.
  environments            list[str]
                          Ordered list of execution environment names declared during
                          project initiation (e.g. ["dev", "uat", "prod"]).
                          The order is the intended promotion sequence; runs reference
                          one environment by name.
```

`target_db_engine` and `staging_schema` are required before any code generation
run can start. They must be set on the project definition before the baton
reaches the code generation stage.

`destination_schema_ddl` is required before the mapping stage can propose field
bindings — the mapping AI reads it to know which destination fields exist.

`environments` is declared at project initiation and determines the valid values
for `RunRecord.environment`.

### `ProjectRegistry` record

The registry record is the durable routing and ownership entry for a project.
It stores `definition_id` and points to the current frozen definition in the
artifact store. The registry stays small and stable while the frozen definition
remains versioned and immutable.

Relevant fields:

- `project_id`
- `name`
- `definition_id`
- `lexicon_scope`
- `status`
- `created_at`
- `updated_at`
- `archived_at`
- `soft_deleted_at`

The registry record does not replace the frozen project definition. It points to
it.

## What a project owns

- destination schema ownership
- structured source definitions
- source approval scope
- source slice policy
- object-level run grouping
- audit boundaries
- per-project lifecycle state
- contact and escalation details
- execution-environment ordering
- snapshot-selection rule

## Source relationship

A project can have multiple source definitions. Each source definition is
structured and source-type aware. The project stores the declared contract
rather than inferring source shape from a connection string.

Supported source families include:

- database sources
- fixed-length file sources
- CSV sources
- XLS sources
- composite sources made from multiple backing sources

The detailed source contract shape remains in `source-model.md`. This page owns
the project-level fact that those contracts are declared, versioned, and
approved under the project.

### Source ownership rules

- A project may own more than one source definition.
- A project may declare a source approval scope that is narrower than the full
  source contract.
- A project may declare a composite source contract, but the project still owns
  the resulting approved source slice as a project-scoped artifact.
- Source contracts are versioned; changing the contract requires a new frozen
  project definition.

## Destination ownership

The destination schema is client-owned.

The project describes how source data maps into destination objects and fields,
but it does not invent or silently mutate the target schema.

The destination schema belongs in the project definition because downstream
analysis and generation require it as an explicit input, not as an inferred
runtime fact.

Destination ownership is exclusive at the project-definition level. A given
destination schema is owned by one project definition at a time.

## Snapshot policy

Project-level source and run behavior is snapshot-driven.

The project declares which approved artifacts are authoritative for execution:

- source slice versions
- mapping snapshot versions
- lookup snapshot versions
- code generation input versions
- knowledge-freeze versions

The selection rule is explicit:

- source analysis produces an immutable approved source slice
- object runs consume a pinned source slice version
- mapping and lookup approvals produce immutable snapshots
- code generation selects the latest approved mapping and lookup snapshots that
  are available when the codegen stage starts
- every downstream execution records the exact snapshot versions it consumed

This is the end-to-end snapshot selection contract used across the bundle: each
stage chooses the latest approved artifact set available when that stage starts,
pins the choice in the run record and checkpoint, and resumes from the pinned
set rather than swapping to newer approvals mid-run.

Once a run has selected a snapshot set for a stage, that set is pinned in the
run record and checkpoint. Resume uses the pinned set rather than silently
switching to newer approvals mid-run.

### Snapshot coherence rule

The system must not silently mix incompatible versions. A run must be able to
explain exactly which approved source slice, mapping snapshot, lookup snapshot,
and code-generation input it consumed.

## Lifecycle

Project lifecycle and definition lifecycle are related but not identical.

- The `ProjectDefinition` is frozen once created.
- The registry record can remain active while pointing at newer definitions.
- Archiving a project stops new routing to it.
- In-flight work may finish, pause, or escalate depending on stage and policy.

### Definition evolution

If a project source contract, destination schema, or operational policy changes,
the change should be represented as a new frozen project definition rather than
mutating the old one.

This is what keeps the lineage reconstructable: the system can explain which
project world existed at the time a run began.

## Failure modes

| Situation | Handling |
|-----------|----------|
| Incoming work matches no project | Escalate rather than guess |
| Incoming work matches multiple projects | Escalate as ambiguous |
| Project is archived | Reject new routing to it |
| Project references another project’s workspace or state | Reject as isolation breach |
| Source contract is malformed | Intake rejects before freeze |
| Destination schema is missing or inconsistent with the declared contract | Intake rejects or blocks approval |
| Approved snapshot policy is missing for the project | Block until the required approvals exist |
| Run attempts to use a snapshot version that is not approved for the project | Reject or escalate, depending on stage |

## Acceptance criteria

- [ ] The project record carries a stable `project_id`.
- [ ] A project can own multiple structured source definitions.
- [ ] The project stores declared source contracts rather than inferring them.
- [ ] The destination schema remains client-owned and is not invented.
- [ ] Project lifecycle state is explicit and does not leak across projects.
- [ ] A project can be archived without mutating historical definitions.
- [ ] Every downstream execution can trace back to a specific frozen project
      definition.
- [ ] Snapshot selection is explicit, deterministic, and recorded.
- [ ] The project page makes clear which facts belong here and which belong in
      `source-model.md`, `runs.md`, and the registry spec.

## Changelog

- 2026-06-29: Defined MigrationProjectConfig explicitly — target_db_engine, staging_schema, dry_run, sample_policy.
- 2026-06-29: Expanded into a spec-style project page covering ownership,
  frozen definition identity, registry relationship, snapshot policy, failure
  modes, and acceptance criteria.
- 2026-06-29: Clarified that environment-specific settings live in the frozen
  project definition and destination ownership is exclusive per project
  definition.
- 2026-06-29: Clarified the end-to-end snapshot selection contract used by the
  project, source, and run pages.
