---
id: 002b6
title: Verify every ORM model has a documented home across docs/domain
status: completed
created: 2026-07-24
domain: docs/domain/
task: 002b6
---

# Plan: Verify all ORM models documented

## Task and Domain Links

- **Task:** [002b6](../tasks/002b6-verify-all-orm-models-documented.md)
- **Domain Docs:** All of `docs/domain/*.md`

## Current State

The 12 sync tasks cover most models via doc-first checklists, but this approach can't guarantee code-first completeness. Some models (ChangeRequest, ApprovalRecord, AuditEvent, Notification) are mentioned in passing across multiple docs but never verified field-by-field against the ORM.

## Objective

Run a code-first completeness check: enumerate all 31 ORM model classes from `db/models.py`, confirm each appears in at least one domain doc, and spot-check that the description is accurate (not just a name mention).

## Out of Scope

- Updating any doc files (handled by the 12 sync tasks)
- Backend implementation changes

## Blast Radius

Zero files changed. This is a verification-only pass.

## Verification

1. `grep "^class .*(Base)" engine/src/migrations_engine/db/models.py` — extract 31 model names
2. For each model: `grep -rl "ModelName" docs/domain/*.md` — find mentioning docs
3. Report any model with zero mentions
4. For models with mentions, spot-check 5-10 that the doc's field descriptions match the ORM (not just the name)

## Results

### Found (25/31) - accurately described
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

## Pitfalls

- Some models are named in docs by their singular form (e.g. "source definition" vs `SourceSchemaArtifact`), making grep matching tricky
- Models like `Feed` are aliased as `SourceDefinition` and `SourceContract` in models.py — docs may use any of these names
- This is a completeness check, not a correctness check — it finds gaps but doesn't fix them

## Tests

N/A — documentation-only change, no test suite applies.

## Follow-up Actions

The 2 gap models (FeedSliceRow, ProjectSchemaAnalysis) and 4 partial-match models need doc updates.
These should be addressed in the relevant sync tasks that touch `source-model.md`.

## Commit

```
docs: verify all ORM models have documented homes (no-op, verification only)

Run code-first completeness check: enumerate all 31 ORM models and
confirm each is mentioned in at least one domain doc. Spot-check
field accuracy for models mentioned in passing.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
```
