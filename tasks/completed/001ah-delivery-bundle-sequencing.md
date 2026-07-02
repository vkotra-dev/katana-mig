# Task 001ah — AI-Assisted Delivery Bundle Sequencing

**Plan:** `plans/2026-07-01-001ah-delivery-bundle-sequencing.md`
**Spec:** `docs/superpowers/specs/2026-07-01-delivery-bundle-sequencing-design.md`

## Domain

- `docs/domain/ui.md` — authoritative screen contract
- `docs/domain/api.md` — endpoint reference
- Mockmigration is styling reference only; spec is content authority

## Scope

Use AI to analyse `destination_schema_ddl` once per project, produce a
FK-dependency-ordered sequence of destination objects, store it in a new
`ProjectSchemaAnalysis` model, and apply it to the delivery bundle output
(`-- [01] table_name` prefixes). Surface a prompt banner in the Sources tab
(when first source exists but no analysis yet) and a report panel in the
codegen page (identified / processed / pending counts + Re-analyze button).

## Execution order

**001ag must complete before this task starts** — Task 7 of this plan modifies
`web/app/projects/[id]/page.tsx`, which 001ag also touches. Run 001ag first to
avoid merge conflicts.

Within this task, run Tasks 1–5 (backend) before Tasks 6–8 (frontend). The
frontend helpers in Task 6 are consumed by Tasks 7 and 8; those cannot be
tested until the helpers exist.

## Tasks (8)

1. AI config — add `schema_dependency` slot to `engine.yaml`, `config.py`, `factory.py`
2. DB model + migration `0016_project_schema_analysis`
3. Service `codegen/schema_analysis.py` — AI call, topological sort, upsert, `get`/`run` functions
4. Routes — `POST` and `GET /projects/{id}/schema-analysis` on `codegen.py` router
5. Update `build_delivery_bundle_text` — sequence ordering + `-- [01]` prefixes
6. Frontend API helpers — `SchemaAnalysisRecord`, `getSchemaAnalysis`, `triggerSchemaAnalysis` in `codegen-api.ts`
7. SourceList banner — fetch analysis on mount; show prompt when null + sources exist
8. Codegen page report panel — identified/processed/pending counts + Re-analyze DDL button

## Success criteria

- `alembic upgrade head` applies migration 0016 cleanly
- `POST /projects/{id}/schema-analysis` calls AI, returns ordered sequence, upserts
- `GET /projects/{id}/delivery-bundle` prefixes blocks with `-- [01]` when analysis exists
- Sources tab shows banner when first source added and no analysis exists
- Codegen page shows identified / processed / pending counts
- All engine and web tests pass
