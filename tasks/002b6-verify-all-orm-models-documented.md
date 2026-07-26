---
id: 002b6
title: Verify every ORM model has a documented home across docs/domain
status: completed
created: 2026-07-24
priority: medium
domain: docs
depends-on: [002aa, 002ab, 002ac, 002ad, 002ae, 002af, 002b0, 002b1, 002b2, 002b3, 002b4, 002b5]
---

# Verify all ORM models have a documented home

## Objective

Run a code-first completeness check: enumerate all 31 ORM model classes from `db/models.py`, confirm each one is mentioned in at least one `docs/domain/*.md` file, and verify the mentioning doc accurately describes the model's fields.

This is the "002b3 for models" — mirroring the exhaustive approach used in the API plan (grep `@router.`) rather than the checklist approach used elsewhere.

## What to do

1. Run: `grep "^class .*(Base)" engine/src/migrations_engine/db/models.py` — get all 31 model names
2. For each model, run: `grep -rl "ModelName" docs/domain/*.md` — find which doc(s) mention it
3. For any model with no doc reference, create a fix: add it to the most relevant doc sync task
4. For models that ARE mentioned, spot-check that the doc's field descriptions match the ORM (not just that the name appears)
5. Report any gaps

## Expected output

A table: Model | Mentioned In Doc(s) | Accurately Described (Yes/No/NA) | Gap

## Results (completed during task execution)

### Found (25/31) — accurately described
User, ProjectDefinition, ProjectRegistry, ProjectMembership, AuthSession, PasswordResetToken,
ChangeRequest, ApprovalRecord, RunRecord, RunCheckpoint, Feed, FeedSlice, SourceSchemaArtifact,
SourceValueSummary, MappingSnapshot, LookupSnapshot, LookupValueMap, CodeGenerationArtifact,
AuditEvent, Notification, ReconciliationReport, ReconciliationLineageRow, AICallLog

### Partial matches (4 models need doc updates)
- **FeedComment** — docs describe `author_id`, ORM uses `user_id`. Also documents non-existent `FeedSliceComment`.
- **MappingBindingSignOff** — docs describe different schema than ORM (per-binding vs per-object sign-off)
- **LookupSignOff** — docs describe fiber-based schema, ORM uses `lookup_value_map_id` (project-scoped)
- **ProjectFiber** — sub-entities (`LookupSourceEntry`, etc.) removed from ORM but still in docs

### Not found in any doc (2 models need docs)
- **FeedSliceRow** — stores `source_slice_id`, `row_index`, `row_csv` for copybook data
- **ProjectSchemaAnalysis** — only referenced via API response names in `api.md`, no domain doc

Follow-up: these should be addressed in the relevant source-model.md and api.md sync tasks.

## Out of scope

- Updating any doc files (that's done by the individual task plans)
- This is a verification/completeness-check task only

## Acceptance criteria

- [ ] All 31 ORM models are mentioned in at least one domain doc
- [ ] Any gaps found are either assigned to a task or documented as a known gap
- [ ] Spot-checked models have field descriptions that match the ORM, not just name mentions
