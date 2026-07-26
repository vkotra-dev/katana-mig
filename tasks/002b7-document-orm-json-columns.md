---
id: 002b7
title: Document all JSON column shapes across ORM models in domain docs
status: pending
created: 2026-07-24
priority: medium
domain: docs/domain/
depends-on: [002aa, 002ab, 002ac, 002ad, 002ae, 002af, 002b0, 002b1, 002b2, 002b3, 002b4, 002b5]
---

# Document all JSON column shapes

## Objective

Every ORM model has 20+ JSON columns that store the core data model of the platform.
The domain docs mention "JSON column" but rarely describe the actual data shape stored inside.
This task fills that gap.

## Schema fixes from 002b6 verification

Three known mismatches discovered by 002b6 must be fixed in source-model.md:

1. **MappingBindingSignOff** (line ~495-504): Replace `binding_index`+`status` (pending/approved/rejected) with `source_field`+`destination_field`. No status enum — sign-off is existence-based via unique constraint on `(mapping_snapshot_id, destination_object_name, source_field, destination_field, user_id)`.

2. **LookupSignOff** (line ~506-515): Replace fiber-based schema (`fiber_id`, `lookup_name`, `status`) with project-scoped model (`lookup_value_map_id`, `user_id`, `role`, `signed_at`). No `fiber_id`, no `lookup_name`, no `status`.

3. **Stale fiber entities** (lines 314-338): Delete `LookupSourceEntry`/`LookupDestFeed`/`LookupDestEntry`/`LookupMapping` descriptions — they contradict line 452 which says they "were removed by tasks 001fg/001fh."

## What's missing

Out of ~40 JSON columns across 31 ORM models, only ~8 have their data shape described in `docs/domain/*.md`.
The rest are undocumented — just "JSON column" with no hint of the structure.

## Insertion map (by doc, by section)

### 1. `source-model.md` — Source definition section (Feed model)

**Location:** After line 141 (after "Source-specific fields" bullet list)

**JSON columns to document:**

```
selection_information   dict — structured source schema info:
  schema_name           string
  table_name            string
  columns               list[{name, data_type, nullable, ...}]

layout_information      dict — how the source data is laid out physically:
  record_length         int | null
  delimiter             string | null
  encoding              string | null
  header_rows           int | null
  ...

source_details          dict — raw source-type-specific connection details:
  (varies by source_type: database/fixed_length_file/xls/csv)
```

**Note:** `sample_policy` and `destination_object_references` are already documented at lines 130-135.

---

### 2. `source-model.md` — Feed slice section (FeedSlice model)

**Location:** After line 223 (after the `slice_purpose` field in the Model fields code block)

**JSON columns to add:**

```
source_schema_artifact  dict — the parsed source schema snapshot for this slice:
  version               string
  columns               list[{name, data_type, nullable, ...}]
  ...

masking_policy          dict — masking rules applied to this slice:
  strategy              "hash" | "tokenize" | "mask" | "null"
  fields                list[str]

slice_payload           dict — the actual row payload for this slice:
  row_count             int
  first_row_at          datetime | null
  last_row_at           datetime | null
  ...

data_profile            dict — statistical profile of the slice data:
  column_stats          dict[str, {min, max, mean, std_dev, null_count, ...}]
  row_count             int
  sampled_rows          int
  ...
```

**Note:** `parse_warnings` is already documented at line 216.

---

### 3. `source-model.md` — FeedSliceRow (new model section needed)

**Location:** New section after line 278 (before "## Fiber model")

**New subsection:**

```markdown
### Feed slice row

Each approved feed slice is split into row-level records for downstream processing.

```
source_slice_id   UUID — FK → feed_slices
row_index         int — zero-based row index within the slice
row_csv           string — the raw CSV row data (one source record)
```

`FeedSliceRow` is the granular unit of source data. Each row is stored as a raw CSV
string so downstream mapping and lookup stages can access the exact source value
for any column without re-parsing.

**JSON columns:** None — all fields are scalar.
```

---

### 4. `source-model.md` — Source analysis section (SourceSchemaArtifact)

**Location:** After line 374 (after the SourceSchemaArtifact field list)

**JSON column to add:**

```
columns             list[{name: str, data_type: str, nullable: bool, ...}]
                    The parsed column list from the source schema. Each entry
                    describes one column in the source definition.
```

**Note:** `columns` is listed at line 372 as a field but its JSON shape is not described.

---

### 5. `source-model.md` — Source analysis section (SourceValueSummary)

**Location:** After the SourceValueSummary field list

**JSON column to add:**

```
value_counts        dict[str, int] — histogram of distinct source values and their
                    frequency counts in the approved slice.
```

**Note:** `value_counts` is listed as a field but its JSON shape is not described.

---

### 6. `source-model.md` — Mapping section (MappingSnapshot)

**Location:** After line 425 (after `field_bindings` description)

**JSON columns to add:**

```
field_bindings      list[{source_column: str, destination_column: str, ...}]
                    Proposed bindings between source and destination columns.
                    Each entry has: source_column, destination_column, confidence,
                    binding_type (explicit|inferred), and reference_table_name.

destination_columns list[str]
                    The list of destination column names extracted from DDL.
```

**Note:** `destination_fields` is already documented at line 424.

---

### 7. `source-model.md` — Mapping section (LookupValueMap)

**Location:** Line 458 (the LookupValueMap paragraph) — update the existing description

**JSON columns to add detail to:**

```
destination_table   list[{ref_id, ref_label, ref_row, ...}]
                    Raw reference rows from the destination mapping input.
                    Each entry is a destination row with its display identifiers.

destination_mappings list[{dest_id, dest_label, dest_row, source_values: list[str], status: str}]
                    The core lookup mapping: maps destination rows to source values.
                    The Review Page renders these groups as rows.
                    Status values: "confirmed" | "proposed" | "overridden".

unmapped_source_values  list[str]
                    Source values that had no matching destination row.
                    Populated by the AI during mapping proposal.
```

**Note:** `source_value_map` (flat `{source_value: dest_id}`) is already documented at line 458.

---

### 8. `source-model.md` — Mapping section (MappingArtifact — NEW)

**Location:** New subsection after MappingSnapshot section (~line 430)

```markdown
### Mapping artifact

The mapping artifact is the output of the mapping stage. It captures the approved
field bindings and the rows that were processed.

```
artifact_id       UUID — primary key
project_id        UUID — FK → projects
source_slice_id   UUID — FK → feed_slices
source_slice_version  string
mapping_snapshot_version  string
status            "proposed" | "approved" | "rejected"
mapped_rows       list[{source_key: str, source_values: dict, destination_values: dict}]
                    The rows produced by the mapping stage. Each entry maps one
                    source row to its destination equivalent.
created_at        datetime
```

`MappingArtifact.mapped_rows` is consumed by the code generation stage as input
for SQL generation. The codegen layer reads `mapped_rows` to produce the INSERT/UPDATE
statements that populate destination tables.
```

---

### 9. `runs.md` — RunRecord (JSON metadata fields)

**Location:** After the RunRecord field list (~line 111, before RunCheckpoint)

**JSON columns to add:**

```
approvals                   list[{approval_id, user_id, role, approved_at, decision}]
                            Snapshot of all approvals recorded for this run.
                            Each entry has the approver's ID, role, timestamp,
                            and decision ("approved" | "rejected").

start_metadata              dict — metadata recorded when the run started:
  trigger                   "manual" | "scheduled" | "chain"
  trigger_user_id           UUID | null
  previous_run_id           UUID | null

pause_metadata              dict — metadata recorded when the run paused:
  pause_stage               string — current stage at pause time
  pause_reason              string | null

resume_metadata             dict — metadata recorded when the run resumed:
  resume_stage              string — current stage at resume time
  resumed_by                UUID | null

completion_metadata         dict — metadata recorded when the run completed:
  total_rows_processed      int | null
  total_rows_errored        int | null
  elapsed_seconds           float | null
```

---

### 10. `runs.md` — RunCheckpoint (JSON metadata fields)

**Location:** After the RunCheckpoint field list (~line 124)

**JSON columns to add:**

```
approved_snapshots          dict[str, {artifact_id: str, version: str, approved_at: str}]
                            Snapshot of all approved artifacts at checkpoint time.
                            Keys are artifact type names; values have the artifact
                            ID, version, and approval timestamp.

checkpoint_payload          dict — additional context stored at checkpoint time:
  current_object            string — destination object being processed
  current_environment       string — environment name
  progress_percent          float | null
```

---

### 11. `runs.md` — DryRunArtifact (destination_object_sequence)

**Location:** After the DryRunArtifact section (~line 155)

**JSON column to add:**

```
destination_object_sequence  list[str] — ordered list of destination object names
                              that this dry run targets. The order determines the
                              sequence in which generated scripts will be executed.
```

---

### 12. `runs.md` — ReconciliationReport (checks, row_count_summary)

**Already documented** at lines 336-340. No action needed.

---

### 13. `runs.md` — ReconciliationLineageRow (mapping_rules_applied)

**Already documented** at line 356. No action needed.

---

### 14. `source-model.md` — ProjectSchemaAnalysis (new model section)

**Location:** New subsection in `source-model.md` after CodeGenerationArtifact (~line 590)

```markdown
### Project schema analysis

When the platform analyzes a source definition, it also generates a schema analysis
report that captures the discovered schema structure, potential issues, and sample data.

```
analysis_id         UUID — primary key
project_id          UUID — FK → projects
source_definition_id UUID — FK → source_definitions
destination_object_sequence  list[str] — ordered destination objects this source feeds
identified_count    int — number of distinct source structures identified
analyzed_at         datetime
pii_fields          list[{field: str, token: str}]
                    Fields detected as potentially containing PII and the
                    suggested tokenization method. E.g.:
                    [{field: "SURNAME", token: "EMAIL_XXXX"}]

sample_rows         list[{source: dict, mapped: dict}]
                    Sample rows showing source values alongside their proposed
                    mapping targets. Used for review and validation.

failures            list[{error: str, context: dict, occurred_at: str}]
                    Errors encountered during schema analysis. Each entry has the
                    error message, the context where it occurred, and timestamp.
```

---

### 15. `security.md` — AuditEvent (event_payload)

**Location:** After the AuditEvent field list in security.md (~line 188-195)

**JSON column to add:**

```
event_payload             dict — contextual data about the audit event:
                          {detail: str, diff: dict, old_value: any, new_value: any}
                          Varies by event_type. Carries the "before and after"
                          state for change-type events.
```

---

### 16. `ui.md` — Notification (payload)

**Location:** After the Notifications section (~line 510)

**JSON column to add:**

```
payload                     dict — event-specific data for deep-linking and display:
                            {event_type: str, project_id: UUID | null,
                             feed_id: UUID | null, action: str, ...}
                            Carries the data needed to render the notification
                            and navigate to the correct target when clicked.
```

---

### 17. `ChangeRequest` — payload (runs.md)

**Location:** After the ChangeRequest section (~line 207 in runs.md)

**JSON column to add:**

```
payload                     dict — change request context:
                            {change_type: str, description: str,
                             affected_tables: list[str], ...}
                            Carries the full change request details for display
                            in the change review UI.
```

---

### 18. `ApprovalRecord` — decision_payload (runs.md)

**Location:** After the ApprovalRecord section (~line 230 in runs.md)

**JSON column to add:**

```
decision_payload            dict — approval decision details:
                            {decision: str, justification: str,
                             conditions: list[str]}
                            Carries the decision context and any conditions
                            attached to the approval/rejection.
```

---

## Verification

For each insertion, verify:
1. The JSON shape matches the ORM definition exactly
2. The field types match (str, int, list, dict, bool)
3. Any nested structures are accurately described
4. Nullable fields are marked as `| null`

## Tests

N/A — documentation-only change.

## Commit

```
docs: document all JSON column shapes in domain docs

Add detailed data shape descriptions for 20+ undocumented JSON columns
across 12 ORM models. Covers Feed, FeedSlice, FeedSliceRow,
SourceSchemaArtifact, SourceValueSummary, MappingSnapshot, LookupValueMap,
MappingArtifact, RunRecord, RunCheckpoint, ProjectSchemaAnalysis,
and others.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
```
