# Source Model

This page defines how source data is declared, analyzed, sliced, approved, and
consumed in the migration domain.

It is the source-side counterpart to the project and run pages. It owns the
structured description of source inputs, the immutable approved source slice,
and the downstream snapshot relationships that drive mapping, lookup mapping,
code generation, and patch generation.

## Purpose

Provide a governed source model that:

- declares source structure explicitly
- preserves source provenance and source-type awareness
- produces an immutable approved source slice
- supports object-level runs against the approved slice
- records snapshot versions consumed by downstream work
- triggers impact analysis when mapping or lookup changes

This page is about source truth and approved source consumption, not destination
schema invention or execution scheduling.

## Responsibilities

- Represent source contracts in structured form.
- Preserve source-type-specific fields rather than flattening them away.
- Produce an approved, immutable source slice for downstream analysis.
- Support object-level runs that share source slices where appropriate.
- Record source, mapping, lookup, and code-generation snapshot versions.
- Provide the source-side inputs to impact analysis and patch generation.
- Keep source analysis separate from mapping, lookup mapping, and codegen.

## Out of scope

- Defining the top-level project container.
- Routing projects or enforcing tenancy.
- User identity or role management.
- Human approval policy.
- Destination schema invention.

## Relationship to other pages

- Project ownership and snapshot policy are defined in `project.md`.
- Object-level execution behavior is defined in `runs.md`.
- Intake and `MigrationProjectConfig` live in `governance.md` and the intake
  behavior described in the harness bundle.
- Source adapter mechanics, schema discovery, PII classification, domain
  object mapping, lookup mapping, rule generation, code generation, and
  reconciliation are all part of the migration analysis pipeline in the harness
  bundle; this page defines the source-side inputs they consume.

## Source modeling tiers

The migration domain uses three distinct source modeling tiers.

### Physical

The physical tier is the concrete introspection unit.

Examples:

- a file
- a table
- a sheet
- a periodic feed pattern

The physical tier is what the adapter sees and what `source_ref` refers to.

### Structural

The structural tier is the approved source schema representation.

It answers:

- what columns exist
- what types are inferred
- what relationships appear to exist
- what candidate keys or repeats were detected

This tier is represented by `SourceSchemaArtifact`.

### Logical

The logical tier is the business entity view.

It answers:

- which source refs belong to which domain object
- which source refs join together
- which source refs are authoritative for overlapping data
- which source rows feed which destination objects

This tier is represented downstream by `DomainObjectMapArtifact` and related
artifacts.

## Source definition

The source definition is the intake contract for a project source. It is
structured and source-type aware.

Supported source types:

- `database`
- `fixed_length_file`
- `xls`
- `csv`
- composite source definitions built from multiple backing sources

Common fields:

- access reference or connection reference
- selection information
- layout information
- destination object references
- sample policy

Source-specific fields:

- database: schema, table, view, query, filters, key hints
- fixed-length file: file path or pattern, record length, offsets, widths,
  encoding, header/trailer rules
- xls / csv: sheet name, delimiter rules, headers, column hints

### Source contract rules

- Source contracts are declared, not inferred from runtime connection strings.
- Source contracts are versioned.
- Source-type-specific structure must be preserved.
- A project may declare more than one source contract.
- A source contract may be composite.

## Source slice

A source slice is the approved, immutable slice of source data used for analysis
and downstream runs.

Rules:

- created once from the declared source definition
- masked before any AI-facing step
- reused by downstream object runs
- versioned and auditable
- does not mutate after approval

The source slice is the approved form of source data. It is the source-side
equivalent of a freeze: once approved, it becomes the basis for downstream
analysis and execution until the source changes.

The default granularity is one approved slice per source contract version,
shared by all object runs that consume that contract. If a source type needs
finer physical slicing, those slices are derived from the approved slice and
remain versioned artifacts rather than untracked subsets.

## Object runs

Runs are object-specific for auditability.

- one destination object per run
- many object runs may share the same approved source slice
- each run records the source slice version it consumed

Object runs do not re-infer source structure. They consume the already approved
source slice and the downstream snapshots derived from it.

## Mapping, lookup, and code generation

After source analysis:

- field mapping produces the object-level field map
- lookup mapping produces approved lookup value snapshots
- code generation consumes the latest approved mapping and lookup snapshots
  available when the codegen stage starts
- code generation records the exact snapshot versions it used

If the source changes, source analysis reruns.
If only mapping or lookup changes, only those approvals rerun, then codegen
reruns.

### Source/run snapshot policy

The selection rule is explicit:

- source analysis produces an immutable approved source slice
- object runs consume a pinned source slice version
- mapping and lookup approvals produce immutable snapshots
- code generation selects the latest approved mapping and lookup snapshots that
  are available when the codegen stage starts
- every downstream execution records the exact snapshot versions it consumed

Once a run has selected a snapshot set for a stage, that set is pinned in the
run record and checkpoint. Resume uses the pinned set rather than silently
switching to newer approvals mid-run.

### Snapshot coherence rule

The system must not silently mix incompatible versions. Every downstream
execution must be able to explain exactly which approved source slice, mapping
snapshot, lookup snapshot, and code-generation input it consumed.

## Impact analysis and patch generation

Mapping or lookup changes trigger impact analysis.

The impact path should:

- identify impacted destination objects
- identify exact impacted record IDs or keys
- generate a patch artifact for those impacted records only
- record the mapping and lookup versions that caused the scope

Patch generation is downstream of approval and impact analysis. It does not
replace source analysis.

### Change-trigger rules

- Source change → re-run source analysis.
- Mapping change only → re-run mapping-related approvals and downstream codegen.
- Lookup change only → re-run lookup approvals and downstream codegen.
- Patch generation follows the approved snapshot policy and never mutates old
  versions.
- A source contract change invalidates every downstream artifact derived from
  the previous source contract version.

## Failure modes

| Situation | Handling |
|-----------|----------|
| Source contract missing required shape information | Intake rejects or preserves as unresolved, depending on stage |
| Fixed-width spec cannot be parsed | Reject before analysis proceeds |
| Source is unreadable or unavailable | Surface as fatal or transient according to adapter policy |
| Source analysis sees structure drift | Mint a new version and require downstream re-approval |
| Source slice would expose raw PII to an AI-facing step | Mask before exposure or deny the step |
| Approved snapshot set cannot be resolved | Block until the required approvals exist |
| Downstream artifact references an unapproved snapshot version | Reject or escalate |
| Impact scope cannot be determined | Escalate rather than fabricate scope |

## Acceptance criteria

- [ ] Source definitions are structured and source-type aware.
- [ ] Source contracts are declared rather than inferred from connection strings.
- [ ] The approved source slice is immutable and versioned.
- [ ] Object runs consume a pinned source slice version.
- [ ] Source analysis reruns when the source changes.
- [ ] Mapping or lookup-only changes rerun only their respective approval path.
- [ ] Downstream work records the exact snapshot versions it used.
- [ ] Patch generation is downstream of approval and impact analysis.
- [ ] Snapshot selection is explicit, deterministic, and recorded.

## Changelog

- 2026-06-29: Expanded into a spec-style source model page covering source
  contracts, modeling tiers, immutable source slices, object runs, snapshot
  policy, impact analysis, failure modes, and acceptance criteria.
- 2026-06-29: Clarified default shared slice granularity and downstream
  invalidation on source contract change.
