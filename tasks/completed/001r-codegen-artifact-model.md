# Task 001r — CodeGenerationArtifact Model and Migration

**Plan:** `plans/2026-06-29-001r-codegen-artifact-model.md`

## Domain

- `docs/domain/source-model.md` — CodeGenerationArtifact spec (model fields, status, supersession rule)
- `docs/domain/runs.md` — baton_4 references codegen_artifact_id
- `docs/domain/governance.md` — I18 invariant: every DDL change ships with a migration

## Scope

Add the `CodeGenerationArtifact` ORM model to `models.py` and ship migration `0009`.

No routes, no schemas, no UI in this task. The model must exist before any code generation
run stage can be implemented.

## Model to add

```python
class CodeGenerationArtifact(Base):
    __tablename__ = "code_generation_artifacts"

    codegen_artifact_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("project_registry.project_id"), nullable=False, index=True)
    destination_object_name: Mapped[str] = mapped_column(String(255), nullable=False)
    run_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("runs.run_id"), nullable=True, index=True)
    source_slice_version: Mapped[str | None] = mapped_column(String(255))
    mapping_snapshot_version: Mapped[str | None] = mapped_column(String(255))
    lookup_snapshot_version: Mapped[str | None] = mapped_column(String(255))
    sql_bundle: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    superseded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
```

Status values: `"active"` | `"superseded"`.

Supersession rule: when a new code gen run completes for `(project_id, destination_object_name)`,
mark all existing `active` rows for that pair `superseded` (set `superseded_at = now()`) before
inserting the new `active` artifact.

## Migration `0009_codegen_artifact.py`

- `down_revision`: read from `engine/migrations/versions/0008_source_intake_fields.py` before
  writing (I18 — do not guess)
- `upgrade()`: `CREATE TABLE code_generation_artifacts` with all columns above;
  index on `project_id`; index on `run_id`
- `downgrade()`: `DROP TABLE code_generation_artifacts`

## Acceptance criteria

- [ ] `CodeGenerationArtifact` importable from `migrations_engine.db.models`
- [ ] `alembic upgrade head` runs cleanly from 0008
- [ ] `alembic downgrade -1` drops the table cleanly
- [ ] A unit test inserts one artifact, marks it superseded, inserts a second, and asserts
      only the second has `status = "active"`

## Notes

- `run_id` is nullable: an artifact may be created outside a formal run (e.g. dry-run preview)
- `sql_bundle` is nullable until the code generation stage writes it
- No `destination_ddl` on `SourceDefinition` — that column was intentionally excluded;
  all generated SQL lives here
- Depends on migration `0008` (001q) being applied first
