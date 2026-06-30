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
- User identity, role management, or membership policy.
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
- destination object references — list of destination object names (e.g. `["Customer", "Address"]`)
  this source feeds; written as the mapping stage output baton when field mapping is approved;
  not declared upfront by the operator
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

### Status

A source slice moves through three states:

```
upload + parse success
        │
        ▼
 pending_approval  ──── approve ───▶  approved  (terminal, immutable)
        │
        └────────── reject ────────▶  rejected
                                          │
                                       resubmit (new SourceSlice record, version + 1)
                                          │
                                          ▼
                                   pending_approval
```

- `pending_approval`: set automatically on parse success; awaits `central_team` approval
- `approved`: terminal and immutable; downstream stages may consume this slice
- `rejected`: terminal for this record; operator may resubmit with corrected settings

At most one slice per `SourceDefinition` is in `pending_approval` at a time. If a resubmit
is triggered while another pending slice exists, that pending slice is automatically
rejected with reason `"superseded_by_resubmit"`.

### Versioning

`source_slice_version` is a human-readable string: `"v1"`, `"v2"`, …. The first slice for
a source contract is `"v1"`. Each resubmit increments the version on the new record.
Multiple versions may exist for one `SourceDefinition`; only the latest `approved` version
is consumed by downstream stages.

### Model fields (approval-relevant)

```
status                      "pending_approval" | "approved" | "rejected"
approval_rejection_reason   string | null — written on rejection
parse_warnings              list[str] — parser-time warnings (e.g. "3 rows skipped: missing field")
file_storage_path           string | null — server-side path or object-storage key to the
                            original uploaded file; required for resubmit to re-parse
slice_purpose               "full_load" | "patch" — set at upload time
                            full_load: complete extract; codegen generates TRUNCATE + INSERT
                            patch: delta rows only; codegen generates MERGE / UPDATE + INSERT
                            for only the rows in this slice
```

## Source slice approval

Approval is the human gate that converts a parsed slice into an immutable, consumable artifact.

**Who approves:** `central_team` only.

**What triggers the approval opportunity:** the upload endpoint sets `status = "pending_approval"`
automatically on parse success. No operator action is needed to promote a slice to the
approval queue.

**What the approver sees** (no row-level data shown):

| Field | Display |
|---|---|
| `row_count` | e.g. "12,450 rows" |
| `encoding` | e.g. "utf-8" |
| `parse_warnings` | amber list if non-empty; hidden otherwise |
| `source_type` | "csv" / "fixed_length_file" |
| `source_slice_id` | monospace + copy icon |
| `created_at` | monospace timestamp |

**Actions:**

- **Approve** — `status → "approved"`; emits `AuditEvent(event_type="source_slice_approved")`
- **Reject** — requires a reason string (max 1000 chars); `status → "rejected"`;
  emits `AuditEvent(event_type="source_slice_rejected", payload={reason})`
- **Resubmit** (on a rejected slice) — re-parses the original file (via `file_storage_path`)
  with corrected encoding or parse settings; creates a new `SourceSlice` record at version
  `v{n+1}` with `status = "pending_approval"`;
  emits `AuditEvent(event_type="source_slice_resubmitted", payload={old_slice_id, new_slice_id})`

**API pattern:**

```
POST /projects/{project_id}/sources/{source_definition_id}/slices/{source_slice_id}/approve
POST /projects/{project_id}/sources/{source_definition_id}/slices/{source_slice_id}/reject
     body: { "reason": str }
POST /projects/{project_id}/sources/{source_definition_id}/slices/{source_slice_id}/resubmit
     body: { "encoding": str | null, "parse_settings": dict | null }
```

**Error codes:**

| Code | HTTP | When |
|---|---|---|
| `slice_not_pending` | 409 | Approve or reject called on a non-pending slice |
| `slice_not_rejected` | 409 | Resubmit called on a non-rejected slice |
| `file_not_retained` | 422 | Resubmit attempted but `file_storage_path` is null |
| `slice_not_found` | 404 | Slice does not belong to this project/source |

**UI entry points:**

1. **Approvals page** (`/approvals`) — global inbox listing all `pending_approval` slices
   across projects visible to the user. Amber count badge on the Approvals nav item.
   Per-row inline Approve + Reject actions.

2. **Project detail — Artifacts tab** — shows the current slice with its status chip.
   If `pending_approval`: inline Approve + Reject buttons.
   If `rejected`: rejection reason + Resubmit button (opens modal for encoding/settings override).

## Source analysis

Source analysis consumes the latest approved source slice for a source definition
and produces immutable analysis artifacts for downstream mapping and lookup work.

Rules:

- the analysis target is the latest approved `SourceSlice` for the source definition
- the AI-facing schema sample is capped at 200 rows
- `SourceSchemaArtifact.columns` stores the analyzed column schemas
- `SourceValueSummary.value_counts` stores distinct values and counts per field
- value summaries are capped at 500 distinct values per field
- source analysis reruns when the source slice changes

### Source analysis artifacts

`SourceSchemaArtifact`:

- `schema_artifact_id`
- `source_definition_id`
- `source_slice_version`
- `columns`
- `created_at`

`SourceValueSummary`:

- `summary_id`
- `source_definition_id`
- `source_slice_version`
- `field_name`
- `value_counts`
- `created_at`

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

### Lookup mapping

Lookup mapping is the operator-managed pre-run table flow that feeds the
runtime lookup snapshot consumed by later execution stages.

The flow is:

1. operator saves a draft `LookupValueMap` for a `(source_definition_id, lookup_name)` pair
2. operator maps each observed source value to a destination identifier
3. the platform generates a draft `LookupSnapshot` from the source value summary and the selected destination ids
4. the operator approves the generated snapshot

Rules:

- the lookup draft stores the destination table rows and the current
  source-value-to-destination-id selections for the lookup
- the snapshot stores the final `value_map` of source value -> destination id
- unmapped source values block snapshot generation
- snapshot approval records audit evidence and preserves the snapshot version
- runtime lookup delta handling remains a separate path

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

## Code generation artifact

Code generation produces a versioned `CodeGenerationArtifact` per destination object. It is not
stored on `SourceDefinition` — it lives in its own table, linked to the run that produced it.

### Contents

One artifact covers one destination object and contains the complete SQL bundle:

- staging table DDL: `CREATE TABLE stg_{object}` for the destination object
- lookup table DDL + data: `CREATE TABLE lookup_{field}` + `INSERT` rows from the approved
  `LookupValueMap`
- views: any `CREATE VIEW` statements needed for the transformation
- stored procedures: `CREATE PROCEDURE proc_load_{object}` that reads from the staging table,
  applies lookup translations, and writes to the destination table

### Model fields

```
CodeGenerationArtifact:
  codegen_artifact_id         UUID — primary key
  project_id                  FK → project_registry
  destination_object_name     string — e.g. "Customer"
  run_id                      FK → runs — the run that produced this artifact
  source_slice_version        string — pinned source slice version consumed
  mapping_snapshot_version    string — pinned mapping snapshot consumed
  lookup_snapshot_version     string — pinned lookup snapshot consumed
  sql_bundle                  Text — full generated SQL (staging DDL + lookup DDL/data + views + SPs)
  status                      "active" | "superseded"
  created_at                  timestamp
  superseded_at               timestamp | null
```

### Versioning and supersession

If mapping or lookup changes and code generation reruns, a new artifact is minted for the same
`(project_id, destination_object_name)`. The previous artifact for that pair is marked
`status = "superseded"`, `superseded_at = now()` before the new one becomes `active`.

Old artifacts are never deleted — the run record that consumed them still points to them as the
audit trail. Only `active` artifacts are included in the delivery bundle.

### Run reference

The run record for the code generation stage carries `codegen_artifact_id` pointing to the
`CodeGenerationArtifact` it produced. This is the baton_4 artifact reference.

### Delivery bundle

The complete delivery bundle is assembled by collecting all `status = "active"`
`CodeGenerationArtifact` records for a project, ordered by destination object name. There is no
`destination_ddl` column on `SourceDefinition`.

## Patch runs and multi-object derivation

### New destination object from the same source

When a second destination object (e.g. `Address`) can be derived from the same
source contract (e.g. `customers.csv`), the operator creates a new `MappingSnapshot`
for that object and launches a new run — all against the same already-approved
`SourceSlice`. No re-upload, no new analysis. Many runs may share one approved slice.

### Source data patch (delta re-run)

When source data changes partially — some records updated, new records added —
the operator uploads a new `SourceSlice` containing **only the changed rows**
(`slice_purpose = "patch"`). The pipeline reuses the same approved `MappingSnapshot`
and `LookupSnapshot` (structure is unchanged). A new run processes the delta slice
and produces a new `CodeGenerationArtifact` whose `sql_bundle` contains
`MERGE / UPDATE + INSERT` statements for only those rows.

This makes a patch run identical to a full run in mechanism — the same pipeline,
the same approval chain, the same baton handoff — with the operator controlling
scope by controlling what rows are in the slice.

Full source re-extract: upload a new slice with `slice_purpose = "full_load"`;
codegen generates `TRUNCATE + INSERT`. Partial re-extract: upload a delta slice with
`slice_purpose = "patch"`; codegen generates `MERGE / UPDATE + INSERT`.

### Impact analysis — mapping or lookup changes

Mapping or lookup changes trigger impact analysis when structure changes, not data.

The impact path should:

- identify impacted destination objects
- identify exact impacted record IDs or keys
- generate a patch artifact for those impacted records only
- record the mapping and lookup versions that caused the scope

Patch generation is downstream of approval and impact analysis. It does not
replace source analysis.

### Change-trigger rules

- Source data change (full extract) → new `full_load` slice → re-run source analysis.
- Source data change (delta) → new `patch` slice → reuse approved mapping/lookup → patch run.
- New destination object from same source → new mapping/lookup/run → reuse approved slice.
- Mapping change only → re-run mapping-related approvals and downstream codegen.
- Lookup change only → re-run lookup approvals and downstream codegen.
- Patch generation follows the approved snapshot policy and never mutates old versions.
- A source contract change (schema drift) invalidates every downstream artifact derived
  from the previous source contract version.

## Failure modes

| Situation | Handling |
|-----------|----------|
| Source contract missing required shape information | Intake rejects or preserves as unresolved, depending on stage |
| Fixed-width spec cannot be parsed | Reject before analysis proceeds |
| Source is unreadable or unavailable | Surface as fatal or transient according to adapter policy |
| Slice rejected, `file_storage_path` null (file not retained) | Return `file_not_retained` (422); operator must upload a new file via the normal upload flow |
| Resubmit parse fails with new settings | Return `parse_failed` (422) with error detail; rejected slice remains as-is |
| Source analysis sees structure drift | Mint a new version and require downstream re-approval |
| Source slice would expose raw PII to an AI-facing step | Mask before exposure or deny the step |
| Approved snapshot set cannot be resolved | Block until the required approvals exist |
| Downstream artifact references an unapproved snapshot version | Reject or escalate |
| Impact scope cannot be determined | Escalate rather than fabricate scope |

## Acceptance criteria

- [ ] Source definitions are structured and source-type aware.
- [ ] Source contracts are declared rather than inferred from connection strings.
- [ ] Source definitions are structured and source-type aware.
- [ ] Source contracts are declared rather than inferred from connection strings.
- [ ] Parse success automatically sets slice status to `pending_approval`.
- [ ] The approved source slice is immutable and versioned.
- [ ] Approval, rejection, and resubmit each emit an `AuditEvent`.
- [ ] At most one slice per `SourceDefinition` is in `pending_approval` at a time.
- [ ] Resubmit creates a new slice record at the next version; the rejected slice is retained.
- [ ] Object runs consume a pinned source slice version.
- [ ] Source analysis reruns when the source changes.
- [ ] Mapping or lookup-only changes rerun only their respective approval path.
- [ ] Downstream work records the exact snapshot versions it used.
- [ ] Patch generation is downstream of approval and impact analysis.
- [ ] Snapshot selection is explicit, deterministic, and recorded.

## Changelog

- 2026-06-29: Added source slice approval flow — status state machine, model fields, approval/reject/resubmit API pattern, UI entry points, failure modes, and acceptance criteria.
- 2026-06-29: Expanded CodeGenerationArtifact into a full model spec with fields, status values, supersession rule, and delivery bundle assembly.
- 2026-06-29: Clarified destination_object_references as mapping stage output baton (not an operator input); introduced CodeGenerationArtifact as the versioned output of code generation.
- 2026-06-29: Expanded into a spec-style source model page covering source
  contracts, modeling tiers, immutable source slices, object runs, snapshot
  policy, impact analysis, failure modes, and acceptance criteria.
- 2026-06-29: Clarified default shared slice granularity and downstream
  invalidation on source contract change.
