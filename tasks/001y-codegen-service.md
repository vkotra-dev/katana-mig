# Task 001y — Code Generation Service

**Plan:** `plans/2026-06-29-001y-codegen-service.md` _(to be written)_

## Domain

- `docs/domain/source-model.md` — CodeGenerationArtifact spec, supersession rule
- `docs/domain/runs.md` — baton_4 carries `codegen_artifact_id`; code gen stage annotated
- `docs/domain/governance.md` — I18, audit

## Depends on

- 001r (CodeGenerationArtifact model + migration 0009)
- 001s (AI adapter)
- 001w (MappingSnapshot must be approved)
- 001x (LookupSnapshot must be approved)

## Scope

Given an approved `MappingSnapshot` and `LookupSnapshot`, use the AI adapter to generate
the SQL bundle (DDL for the staging table, views, stored procedures) and write a
`CodeGenerationArtifact`. If a prior artifact exists for the same
`(project_id, destination_object_name)`, mark it `superseded`.

## What the AI generates

Input to AI:
- Field bindings from `MappingSnapshot.field_bindings`
- Destination object name (e.g. `"Customer"`)
- Staging schema name from `MigrationProjectConfig.staging_schema`
- Target DB engine (`"sql_server"` | `"postgres"`) from `MigrationProjectConfig.target_db_engine`

Output (`sql_bundle`): SQL text containing:
- `CREATE TABLE stg_{destination_object_name_snake_case}` DDL
- Column definitions inferred from field bindings and type information
- Standard audit columns: `_katana_run_id`, `_katana_loaded_at`, `_katana_source_slice_version`

Response model:
```python
class GeneratedSQL(BaseModel):
    staging_table_ddl: str
    views: list[str]       # optional helper views
    notes: str | None      # AI notes on assumptions made
```

`sql_bundle = staging_table_ddl + "\n".join(views)` (concatenated for storage).

## API routes (`routes/codegen.py`)

```
POST /projects/{project_id}/sources/{source_definition_id}/codegen
  — triggers code generation for the given source's approved mapping+lookup
  — mints CodeGenerationArtifact; supersedes previous active artifact for same
    (project_id, destination_object_name)
  — returns {codegen_artifact_id, status, sql_bundle (first 500 chars), created_at}
  — central_team only

GET  /projects/{project_id}/codegen-artifacts
  — list all CodeGenerationArtifact rows for the project
  — supports ?status=active|superseded filter
  — returns full records including sql_bundle

GET  /projects/{project_id}/codegen-artifacts/{codegen_artifact_id}
  — get one artifact (full sql_bundle)

GET  /projects/{project_id}/delivery-bundle
  — returns all active CodeGenerationArtifact rows for the project
  — this is the complete delivery bundle (one sql_bundle per destination object)
```

## Supersession logic

```python
def supersede_previous(project_id: str, destination_object_name: str, db: Session) -> None:
    now = datetime.now(UTC)
    db.query(CodeGenerationArtifact).filter_by(
        project_id=project_id,
        destination_object_name=destination_object_name,
        status="active",
    ).update({"status": "superseded", "superseded_at": now})
```

Must be called inside the same transaction that inserts the new artifact.

## UI integration (`web/app/projects/[id]/codegen/page.tsx`)

- Per-source "Generate SQL" button (central_team only)
- Shows latest `active` artifact: scrollable SQL preview with copy-to-clipboard
- Delivery bundle tab: table of all `active` artifacts across the project with download button
- Shows `superseded` history in a collapsible section

## Acceptance criteria

- [ ] `POST .../codegen` creates a `CodeGenerationArtifact` with `status="active"`
- [ ] Prior `active` artifact for same `(project_id, destination_object_name)` is marked `superseded`
- [ ] `sql_bundle` contains `CREATE TABLE stg_...` DDL
- [ ] `GET .../delivery-bundle` returns only `active` artifacts
- [ ] AI adapter is mocked in tests
- [ ] Supersession atomicity: both the update and insert are committed together

## Notes

- Staging table name convention: `stg_{destination_object_name.lower().replace(" ", "_")}`
- The `sql_bundle` is stored verbatim; no post-processing or validation
- Code generation does not execute the SQL — that happens during the run stage
- AI can make assumptions (e.g. all `text` columns → `VARCHAR(255)`); assumptions are
  recorded in `notes` field of `GeneratedSQL` for operator review
- `codegen_artifact_id` is written to `RunRecord` when the run reaches the code gen stage
  (001t implementation); this task just produces the artifact
