# Source Model

This page defines how source data is declared, analyzed, sliced, approved, and
consumed in the migration domain.

It is the source-side counterpart to the project and run pages. It owns the
structured description of source inputs, the immutable approved feed slice,
and the downstream snapshot relationships that drive mapping, lookup mapping,
code generation, and patch generation.

## Purpose

Provide a governed source model that:

- declares source structure explicitly
- preserves source provenance and source-type awareness
- produces an immutable approved feed slice
- supports object-level runs against the approved slice
- records snapshot versions consumed by downstream work
- triggers impact analysis when mapping or lookup changes

This page is about source truth and approved source consumption, not destination
schema invention or execution scheduling.

## Responsibilities

- Represent source contracts in structured form.
- Preserve source-type-specific fields rather than flattening them away.
- Produce an approved, immutable feed slice for downstream analysis.
- Support object-level runs that share feed slices where appropriate.
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
- sample policy — controls how the approved source rows are selected when the
  source is materialized into the staged table used by downstream mapping and
  lookup work

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

## Feed slice

A feed slice is the approved, immutable slice of source data used for analysis
and downstream runs.

Rules:

- created once from the declared source definition
- masked before any AI-facing step
- reused by downstream object runs
- versioned and auditable
- does not mutate after approval

The feed slice is the approved form of source data. It is the source-side
equivalent of a freeze: once approved, it becomes the basis for downstream
analysis and execution until the source changes.

The default granularity is one approved feed slice per source contract version,
shared by all object runs that consume that contract. If a source type needs
finer physical slicing, those slices are derived from the approved feed slice and
remain versioned artifacts rather than untracked subsets.

For execution, the approved feed slice is materialized into a staging-table
representation under the project `staging_schema`. The feed or source-derived
name is the table identity used by downstream SQL generation.

### Status

A feed slice moves through three states:

```
upload + parse success
        │
        ▼
 pending_approval  ──── approve ───▶  approved  (terminal, immutable)
        │
        └────────── reject ────────▶  rejected
                                          │
                                       resubmit (new FeedSlice record, version + 1)
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

`source_slice_version` is a human-readable string: `"v1"`, `"v2"`, …. The first feed slice for
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

## Feed slice approval

Approval is the human gate that converts a parsed slice into an immutable, consumable artifact.

**Who approves:** `central_team` only.

**What triggers the approval opportunity:** the upload endpoint sets `status = "pending_approval"`
automatically on parse success. No operator action is needed to promote a feed slice to the
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
- **Resubmit** (on a rejected feed slice) — re-parses the original file (via `file_storage_path`)
  with corrected encoding or parse settings; creates a new `FeedSlice` record at version
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

**UI entry point:**

**Per-feed workspace** (`/projects/[id]/feeds/[feedId]`) — slice status panel shows the current slice status chip. If `pending_approval`: inline Approve + Reject buttons for `central_team`. If `rejected`: rejection reason + Resubmit button (opens modal for encoding/settings override). There is no global approvals inbox; approval surfaces only within the feed's own workspace.

## Fiber model

Fibers are project-scoped work units attached to a feed. They are the root
entity for the lookup-fiber and mapping-fiber workflows that build on top of
the approved feed and slice history.

Rules:

- one fiber belongs to one feed and one project
- `fiber_type` identifies the workflow family: `lookup` or `domain_object`
- `source` records whether the fiber was created by the operator (`manual`) or
  by automation (`auto`)
- `ProjectFiber` stores the shared lifecycle and output fields for later stages
- lookup-specific child tables store discovered source entries, destination
  feeds, destination entries, and value mappings
- lookup mappings preserve the proposed/confirmed/overridden state so the UI
  can show review provenance later

### Fiber model fields

`ProjectFiber`:

- `fiber_id`
- `feed_id`
- `project_id`
- `fiber_type`
- `fiber_key`
- `status`
- `source`
- `proposed_mappings`
- `field_bindings`
- `output_sql`
- `created_at`
- `updated_at`

`LookupSourceEntry`:

- `entry_id`
- `fiber_id`
- `lookup_name`
- `source_value`
- `discovery_type` — `"sample"` (value seen in the feed window) or `"operator"` (value supplied by the operator from the complete production domain, beyond what the feed window contains)
- `created_at`

`LookupDestFeed`:

- `dest_feed_id`
- `fiber_id`
- `lookup_name`
- `columns`
- `created_at`

`LookupDestEntry`:

- `entry_id`
- `dest_feed_id`
- `row_data`
- `created_at`

`LookupMapping`:

- `mapping_id`
- `fiber_id`
- `lookup_name`
- `source_entry_id`
- `source_value`
- `dest_entry_id`
- `dest_row`
- `confidence_score`
- `status`
- `mapped_by`
- `created_at`
- `updated_at`

## Source analysis

Source analysis consumes the latest approved feed slice for a source definition
and produces immutable analysis artifacts for downstream mapping and lookup work.

Rules:

- the analysis target is the latest approved `FeedSlice` for the source definition
- the AI-facing schema sample is capped at 200 rows
- `SourceSchemaArtifact.columns` stores the analyzed column schemas
- `SourceValueSummary.value_counts` stores distinct values and counts per field
- value summaries are capped at 500 distinct values per field
- source analysis reruns when the feed slice changes

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
- many object runs may share the same approved feed slice
- each run records the feed slice version it consumed

Object runs do not re-infer source structure. They consume the already approved
feed slice and the downstream snapshots derived from it.

## Mapping, lookup, and code generation

After source analysis:

- field mapping produces the object-level field map (one `MappingSnapshot` per destination table)
- mapping proposals are AI-driven (replaced the earlier regex DDL parser)
- lookup mapping produces approved lookup value snapshots
- code generation consumes the latest approved mapping and lookup snapshots
  available when the codegen stage starts
- code generation records the exact snapshot versions it used

If the source changes, source analysis reruns.
If only mapping or lookup changes, only those approvals rerun, then codegen reruns.

### Field mapping — multi-table AI extraction

One AI call per feed receives the full destination schema DDL and the feed's source columns. The AI identifies all destination tables the feed populates and maps each source field to a destination field. The AI also classifies every binding:

- `direct` — source field maps to a destination column with no FK dependency
- `detail_fk` — destination column is a FK whose referenced table is also produced by this same feed (i.e. the AI assigned that table too)
- `lookup_fk` — destination column is a FK whose referenced table is a reference/lookup table not produced by this feed; a lookup fiber is needed to map values

For every `lookup_fk` binding the AI returns the `reference_table_name` (the referenced lookup table in the DDL).

The backend creates one `MappingSnapshot` per identified destination table in a single transaction. Each snapshot stores:
- `source_definition_id` — feed-scoped FK
- `destination_object_name` (the AI-returned table name, validated against the DDL)
- `destination_fields` — JSON column storing the column list for that table, derived from DDL at proposal time
- `field_bindings` (bindings for that table, including `binding_type` and `reference_table_name`)

The unique index on `MappingSnapshot` is feed-scoped: `(project_id, source_definition_id, destination_object_name, version)`.

The propose API response also returns `lookup_table_references` — one entry per `lookup_fk` binding across all tables — so the UI knows which reference table backs each lookup field without re-parsing the DDL.

#### Mapping hints

`Feed.mapping_hints` — an operator-supplied TEXT field containing mapping intent and guidance. Operators use this to describe expected field relationships, naming conventions, or domain context that the AI should consider. Mapping hints are included in the AI user prompt when proposing mappings.

#### AI trace

`MappingSnapshot.ai_trace` — a JSON column storing the full AI interaction that produced the snapshot:

```
{
  "system_prompt": string,
  "user_prompt": string,
  "raw_response": string,
  "model_id": string
}
```

This enables post-hoc debugging and audit of AI mapping decisions.

### Lookup mapping

Lookup mapping is the operator-managed flow that maps unique source values for each `lookup_fk` field to destination reference rows.

The flow per lookup field:

1. Operator supplies the complete production value list for the source field (`LookupSourceEntry` records with `discovery_type="operator"`). The feed window alone is insufficient — the operator extracts distinct values from the full source system.
2. Operator uploads reference rows from the destination lookup table (`LookupDestFeed` / `LookupDestEntry` records). These rows come from the destination DB (id, description, and any domain-specific codes).
3. AI maps source values to destination rows, producing `LookupMapping` records with confidence scores. This AI run happens once per production cycle.
4. After first approval, new unmapped source values surface in the review grid as delta rows. No AI re-run — the additive path simply creates new `LookupMapping` records without overwriting existing `confirmed` or `human`-mapped entries.

Rules:

- `submit_lookup_inputs` is additive and re-runnable: existing `LookupMapping` records with `status="confirmed"` or `mapped_by="human"` are never overwritten
- AI re-runs are allowed any number of times before the first production approval; after first approval, delta additions only
- unmapped source values are directly queryable; they do not block the call but will surface as gaps in the review grid
- runtime lookup delta handling (values discovered during execution) follows the same additive path

#### LookupValueMap — project-scoped

`LookupValueMap` is promoted from feed-scoped `(source_definition_id, lookup_name)` to project-scoped `(project_id, lookup_name)`. This means a single lookup value mapping is shared across all feeds in the project that reference the same lookup name.

On fiber approval, all confirmed `LookupMapping` rows are auto-written to `LookupValueMap`, making them available project-wide for codegen and other feeds.

### Source/run snapshot policy

The selection rule is explicit:

- source analysis produces an immutable approved feed slice
- object runs consume a pinned feed slice version
- mapping and lookup approvals produce immutable snapshots
- code generation selects the latest approved mapping and lookup snapshots that
  are available when the codegen stage starts
- every downstream execution records the exact snapshot versions it consumed

Once a run has selected a snapshot set for a stage, that set is pinned in the
run record and checkpoint. Resume uses the pinned set rather than silently
switching to newer approvals mid-run.

### Snapshot coherence rule

The system must not silently mix incompatible versions. Every downstream
execution must be able to explain exactly which approved feed slice, mapping
snapshot, lookup snapshot, and code-generation input it consumed.

### Multi-party sign-off

Mapping and lookup approvals follow a multi-party sign-off model.

`MappingBindingSignOff` — tracks per-binding sign-offs by operator and stakeholder:

- `sign_off_id`
- `mapping_snapshot_id`
- `binding_index`
- `signer_role` — `"operator"` or `"stakeholder"`
- `signer_id`
- `status` — `"pending"` | `"approved"` | `"rejected"`
- `created_at`
- `updated_at`

`LookupSignOff` — tracks lookup sign-offs:

- `sign_off_id`
- `fiber_id`
- `lookup_name`
- `signer_role`
- `signer_id`
- `status`
- `created_at`
- `updated_at`

Approval chain (3 steps):

1. **Operator assigns** — operator marks bindings or lookups as ready for review
2. **Stakeholder approves** — stakeholder reviews and signs off on individual bindings or lookup mappings
3. **Operator triggers** — once all stakeholder sign-offs are collected, operator triggers the downstream stage (codegen)

PM can "poke" for outstanding sign-offs — this sends a notification to assignees with pending sign-off items.

Editing is gated by inbox status: a binding or lookup mapping cannot be modified while its sign-off is in `pending` or `approved` state. The operator must reset the sign-off before editing.

## Code generation artifact

Code generation produces a versioned `CodeGenerationArtifact` per destination object. It is not
stored on `SourceDefinition` — it lives in its own table, linked to the run that produced it.

### Contents

One artifact covers one destination object and contains the complete SQL bundle:

- staging table DDL: `CREATE TABLE stg_{object}` for the destination object; staging tables
  include `_row_num BIGINT IDENTITY(1,1)` as the first column
- lookup table DDL + data: `CREATE TABLE lookup_{field}` + `INSERT` rows from the approved
  `LookupValueMap`
- views: any `CREATE VIEW` statements needed for the transformation
- stored procedures: `CREATE PROCEDURE proc_load_{object}` that reads from the staging table,
  applies lookup translations, and writes to the destination table

#### Codegen instructions

`ProjectDefinition.codegen_instructions` — project-wide coding standards (TEXT). Injected as
`GLOBAL CODING STANDARDS` in the AI system prompt for every codegen call in the project.

`Feed.transformation_instructions` — per-feed transformation rules (TEXT). Injected into the
AI user prompt for codegen calls scoped to that feed.

Both fields are editable via their respective PATCH endpoints.

#### Migration run logging

Every SQL bundle is prepended with a `CREATE TABLE IF NOT EXISTS mig_upsert_log` DDL statement.
The AI system prompt instructs codegen to emit `MERGE` + `OUTPUT INTO mig_upsert_log` for every
upsert operation, producing a row-level audit trail.

The `run_ref` literal is baked into the SQL as `'{project_id}_{source_definition_id}'`, uniquely
identifying the migration run context.

### Model fields

```
CodeGenerationArtifact:
  codegen_artifact_id         UUID — primary key
  project_id                  FK → project_registry
  destination_object_name     string — e.g. "Customer"
  run_id                      FK → runs — the run that produced this artifact
  source_slice_version        string — pinned feed slice version consumed
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

## AI observability

### AI call logging

Every AI adapter call is logged via the `log_ai_call()` helper into the `AICallLog` table.

`AICallLog`:

```
call_id           UUID — primary key
project_id        FK → project_registry
call_type         string — e.g. "mapping_proposal", "lookup_mapping", "codegen"
model_id          string — AI model identifier used for the call
system_prompt     Text — full system prompt sent
user_prompt       Text — full user prompt sent
raw_response      Text — raw AI response
error_detail      Text | null — error message if the call failed
artifact_id       UUID | null — FK to the artifact produced by this call
created_at        timestamp
```

After artifact creation, `backfill_artifact_id()` is called to link the log entry to the
produced artifact. This enables tracing from any artifact back to the exact AI call that
generated it.

## Feed and slice comments

`FeedComment` — threaded commenting on feeds:

- `comment_id`
- `source_definition_id` — FK to source_definitions
- `author_id`
- `body` — comment text
- `parent_comment_id` — nullable FK for threading
- `created_at`
- `updated_at`

`FeedSliceComment` — slice-level commenting:

- `comment_id`
- `source_slice_id` — FK to feed_slices
- `author_id`
- `body`
- `parent_comment_id`
- `created_at`
- `updated_at`

Comments trigger cross-role notifications (operator ↔ stakeholder ↔ PM).

Both `FeedComment` and `FeedSliceComment` content is injected into the AI codegen prompt as
additional context, giving the AI visibility into operator/stakeholder discussion and intent.

## Feed slice workflow changes

- Feed slices are immutable post-creation — the upload card is removed after initial
  upload; no re-upload of data into an existing slice
- Rejection triggers a replacement upload flow — operator must create a new slice rather
  than editing the rejected one
- The approval gate overlay is removed; replaced with a slice preview card and an
  'Analyze with AI' button that initiates source analysis
- Dedicated data profile review card for stakeholders with PII scan results;
  stakeholders see field-level PII classification and can flag concerns
- Copybook `row_csv` is stored unmasked; display-time masking is applied with an
  admin/PM toggle to reveal raw values when needed

## Patch runs and multi-object derivation

### New destination object from the same source

When a second destination object (e.g. `Address`) can be derived from the same
source contract (e.g. `customers.csv`), the operator creates a new `MappingSnapshot`
for that object and launches a new run — all against the same already-approved
`FeedSlice`. No re-upload, no new analysis. Many runs may share one approved feed slice.

### Source data patch (delta re-run)

When source data changes partially — some records updated, new records added —
the operator uploads a new `FeedSlice` containing **only the changed rows**
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
| Feed slice would expose raw PII to an AI-facing step | Mask before exposure or deny the step |
| Approved snapshot set cannot be resolved | Block until the required approvals exist |
| Downstream artifact references an unapproved snapshot version | Reject or escalate |
| Impact scope cannot be determined | Escalate rather than fabricate scope |

## Acceptance criteria

- [ ] Source definitions are structured and source-type aware.
- [ ] Source contracts are declared rather than inferred from connection strings.
- [ ] Parse success automatically sets slice status to `pending_approval`.
- [ ] The approved feed slice is immutable and versioned.
- [ ] Approval, rejection, and resubmit each emit an `AuditEvent`.
- [ ] At most one slice per `SourceDefinition` is in `pending_approval` at a time.
- [ ] Resubmit creates a new slice record at the next version; the rejected slice is retained.
- [ ] Object runs consume a pinned feed slice version.
- [ ] Source analysis reruns when the source changes.
- [ ] Mapping or lookup-only changes rerun only their respective approval path.
- [ ] Downstream work records the exact snapshot versions it used.
- [ ] Patch generation is downstream of approval and impact analysis.
- [ ] Snapshot selection is explicit, deterministic, and recorded.

## Changelog

- 2026-07 — AI-driven multi-table mapping extraction with binding type classification; multi-party sign-off model; LookupValueMap promoted to project scope; feed/slice comments with codegen injection; mapping hints and AI trace; codegen instructions (project-wide + per-feed); migration run logging (mig_upsert_log); AI call logging; feed slice immutability and workflow overhaul
- 2026-07-04: Replaced global approvals inbox UI entry point with per-feed workspace entry point; documented multi-table AI mapping (binding types, MappingSnapshot per table, lookup_table_references); documented LookupSourceEntry discovery_type="operator" and additive submit_lookup_inputs rule.
- 2026-06-29: Added feed slice approval flow — status state machine, model fields, approval/reject/resubmit API pattern, UI entry points, failure modes, and acceptance criteria.
- 2026-06-29: Expanded CodeGenerationArtifact into a full model spec with fields, status values, supersession rule, and delivery bundle assembly.
- 2026-06-29: Clarified destination_object_references as mapping stage output baton (not an operator input); introduced CodeGenerationArtifact as the versioned output of code generation.
- 2026-06-29: Expanded into a spec-style source model page covering source
  contracts, modeling tiers, immutable feed slices, object runs, snapshot
  policy, impact analysis, failure modes, and acceptance criteria.
- 2026-06-29: Clarified default shared slice granularity and downstream
  invalidation on source contract change.
