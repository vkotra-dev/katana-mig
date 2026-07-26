---
id: 002b7
title: Document all JSON column shapes in ORM models
status: ready
created: 2026-07-24
domain: docs/domain/
task: 002b7
---

# Plan: Document all JSON column shapes

## Task Link

- **Task:** [002b7](../tasks/002b7-document-orm-json-columns.md)

## Objective

Document the exact data shape of every JSON column across all 31 ORM models. Currently ~20 JSON columns are undocumented or only described as "JSON column" without detailing the internal structure.

## Insertion map (by doc, by section)

### source-model.md

| Model | Section | Location | What to add |
|---|---|---|---|
| Feed | Source definition | After line 141 | `selection_information`, `layout_information`, `source_details` shapes |
| FeedSlice | Feed slice model fields | After line 223 | `source_schema_artifact`, `masking_policy`, `slice_payload`, `data_profile` shapes |
| FeedSliceRow | **New subsection** | Before line 279 | Full model doc (all scalar fields, no JSON) |
| SourceSchemaArtifact | Source analysis | After line 374 | `columns` array shape |
| SourceValueSummary | Source analysis | After SVA section | `value_counts` histogram shape |
| MappingSnapshot | Mapping section | After line 425 | `field_bindings`, `destination_columns` shapes |
| LookupValueMap | Mapping section | Line 458 | Enrich `destination_table`, `destination_mappings` shapes |
| MappingArtifact | **New subsection** | After ~line 430 | Full model doc with `mapped_rows` shape |
| ProjectSchemaAnalysis | **New subsection** | After ~line 590 | Full model doc with `pii_fields`, `sample_rows`, `failures` shapes |

### runs.md

| Model | Section | Location | What to add |
|---|---|---|---|
| RunRecord | Data model | After line 111 | `approvals`, `start_metadata`, `pause_metadata`, `resume_metadata`, `completion_metadata` shapes |
| RunCheckpoint | Data model | After line 124 | `approved_snapshots`, `checkpoint_payload` shapes |
| DryRunArtifact | Runs section | After ~line 155 | `destination_object_sequence` shape |

### security.md

| Model | Section | Location | What to add |
|---|---|---|---|
| AuditEvent | Security boundaries | After ~line 195 | `event_payload` shape |

### ui.md

| Model | Section | Location | What to add |
|---|---|---|---|
| Notification | Notifications | After ~line 510 | `payload` shape |

### runs.md (additional)

| Model | Section | Location | What to add |
|---|---|---|---|
| ChangeRequest | Change requests | After ~line 207 | `payload` shape |
| ApprovalRecord | Approval records | After ~line 230 | `decision_payload` shape |

## Files changed

- `docs/domain/source-model.md` — 6 insertions + 3 new subsections (FeedSliceRow, MappingArtifact, ProjectSchemaAnalysis)
- `docs/domain/runs.md` — 5 insertions (RunRecord, RunCheckpoint, DryRunArtifact, ChangeRequest, ApprovalRecord)
- `docs/domain/security.md` — 1 insertion (AuditEvent)
- `docs/domain/ui.md` — 1 insertion (Notification)

## Verification

Each insertion must:
1. Match the ORM type exactly (str/int/list/dict/bool)
2. Use `| null` for nullable fields
3. Include nested structure for dict/list types
4. Follow the existing doc convention (backtick field names, dash, description)

## Pitfalls

- Don't invent field names for nested dicts — only document what exists in `models.py`
- `sample_policy` and `destination_object_references` on Feed are already documented — don't duplicate
- `checks` and `row_count_summary` on ReconciliationReport are already documented in runs.md — don't duplicate
- `mapped_rows` on MappingArtifact is mentioned in runs.md (lines 175, 196) but not as a model — document it as a new model section
- `FieldBindingsSignOff` and `LookupSignOff` have no JSON columns — skip them

## Commit

```
docs: document all JSON column shapes in domain docs

Add detailed data shape descriptions for 20+ undocumented JSON columns
across 12 ORM models: Feed, FeedSlice, FeedSliceRow, SourceSchemaArtifact,
SourceValueSummary, MappingSnapshot, LookupValueMap, MappingArtifact,
ReconciliationReport, RunRecord, RunCheckpoint, DryRunArtifact,
ProjectSchemaAnalysis, AuditEvent, Notification.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
```
