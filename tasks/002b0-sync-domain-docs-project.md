---
id: 002b0
title: Sync docs/domain/project.md against actual codebase
status: pending
created: 2026-07-24
priority: medium
domain: docs
depends-on: []
---

# Sync docs/domain/project.md

## Objective

Update `docs/domain/project.md` to accurately reflect the current project models. Last updated 2026-07-26.

## Scope

- `docs/domain/project.md` only

## What to verify

1. **ProjectDefinition fields** — Compare against ORM `ProjectDefinition` class:
   - `definition_id`, `project_id`, `name`, `goal` — verify
   - `repos` (JSON), `workspace` (JSON) — verify types
   - `project_resources` (Text) — verify
   - `execution_environments` (JSON list) — verify
   - `model_policy` (JSON) — verify
   - `canonical_terms` (JSON list), `constraints` (JSON list) — verify
   - `unresolved_questions` (JSON list), `assumptions` (JSON list) — verify
   - `domain_config` (JSON) — verify
   - `codegen_instructions` (Text) — verify
   - `status` (default "active") — verify
   - `created_at`, `updated_at` — verify

2. **ProjectRegistry fields** — Compare against ORM `ProjectRegistry` class:
   - `pm_user_id` nullable FK — verify
   - `lexicon_scope` (Text) — verify
   - `archived_at`, `soft_deleted_at` — verify

3. **MigrationProjectConfig fields** — Verify against actual `domain_config` usage:
   - `target_db_engine`, `staging_schema`, `destination_schema` — verify
   - `dry_run`, `sample_policy`, `destination_schema_ddl` — verify
   - `environments` list — verify

4. **API endpoints** — Verify `PATCH /projects/{id}/manager`, `POST /projects/{id}/copy`, `POST /projects/{id}/codegen-instructions/reset`, `GET /config/ai-model-defaults`

5. **Snapshot policy** — Verify the snapshot selection rules match actual code

6. **Project copy** — Verify the carry-forward fields match actual implementation

## Out of scope

- Any other domain doc files
- Backend implementation changes

## Acceptance criteria

- [ ] All ProjectDefinition fields match ORM model
- [ ] All ProjectRegistry fields match ORM model
- [ ] MigrationProjectConfig fields are accurate
- [ ] All API endpoints listed exist
- [ ] Snapshot policy is accurate
- [ ] Changelog updated
- [ ] timestamp updated
