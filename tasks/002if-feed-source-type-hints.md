---
id: 002if
title: Surface feed source-side inferred type hints in codegen prompt
status: pending
created: 2026-07-28
priority: low
depends-on: []
domain: web
---

# Task 002if — Feed source-side type hints for codegen variable setup

## Context

Earlier this session, before the mapping/duplicate-detection thread took over, the brainstorm was:
does codegen give the AI any hint about a source column's **inferred type** (captured during feed
source analysis) when generating variable declarations/CASTs for the staging→destination
transform? This is a feed-domain question, not a codegen-domain one — the data in question
(`SourceSchemaArtifact.columns`, inferred per feed during source analysis) is feed-specific, the
same as `mapping_ownership_warnings` (task 002ie) is feed-specific; codegen is just the consumer.

**Finding:** `codegen/service.py`'s `_build_user_prompt()`/templates only surface the
**destination**-side type per field binding (`destination_data_type`, rendered as `[TYPE]` in the
field-bindings list). The **source**-side inferred type — captured during source analysis in the
`SourceSchemaArtifact` table (`columns: list[dict]`, each with `name`/`inferred_type`/`nullable`/
`max_length`, fetched via `get_latest_source_schema_artifact()` in
`management/source_analysis.py:206`) — is never fetched or passed into codegen's prompt at all.
The AI generating variable declarations/CASTs for the transform has to guess the source type from
column naming or raw sample data alone, with no explicit signal.

## Open design question (not yet resolved — brainstorm before writing a plan)

Should the source inferred type be surfaced for **every** field binding (direct, detail_fk,
lookup_fk alike — likely the right call, since any binding can hit a type-mismatch CAST issue, not
just lookups), or only for lookup-resolution bindings (narrower, smaller diff, but leaves the same
risk for direct/detail_fk bindings unaddressed)? This needs a decision — and probably a second
question about exactly where in the prompt/template it should render — before a plan can be
written.

## Status

Backlog. `status: pending`, no plan file yet — not ready for implementation until the scope
question above is resolved via the normal brainstorm step.

## Domain Updates Required

Not yet determined — depends on the scope decision above. Likely `docs/domain/source-model.md`
(source analysis artifacts) and/or a codegen-prompt-contract note; revisit once scoped.
