# Source Analysis Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add approved-source analysis that produces versioned schema and value-summary artifacts, exposes them through project source APIs, and keeps the source-model docs aligned with the new behavior.

**Architecture:** Keep the route thin and move the analysis flow into a dedicated management module. The service will select the latest approved slice, build a capped sample from stored masked rows, call the existing `pii_review` AI slot, validate the structured response with Pydantic, and persist immutable analysis artifacts. Schema extraction uses the 200-row sample; value summaries are derived from the approved slice rows and capped at 500 distinct values per field. Reads expose the latest persisted artifact set for the source definition.

**Tech Stack:** FastAPI, SQLAlchemy 2.x ORM, Pydantic v2, Alembic, Vitest/Pytest, the existing `migrations_engine.ai.factory.get_adapter()` boundary.

## Global Constraints

- Source contracts are declared, not inferred from runtime connection strings.
- Source-type-specific structure must be preserved.
- A source slice is approved, immutable, and versioned before downstream use.
- Source analysis must mask raw PII before any AI-facing step.
- `mypy --strict` must stay clean.
- `ruff` must stay clean.
- Every DDL change ships with a hand-written Alembic migration in the same commit.
- Migration `0011` must run cleanly after `0010`.

## Current State

- `docs/domain/source-model.md` mentions source analysis in the narrative, but it does not yet define the analysis artifacts or their persistence model.
- `engine/src/migrations_engine/db/models.py` has `SourceDefinition`, `SourceSlice`, and `SourceSliceRow`, but no schema/value analysis tables.
- `engine/src/migrations_engine/api/schemas.py` has source contract and slice response models, but no analysis response models.
- `engine/src/migrations_engine/routes/sources.py` and `management/sources.py` already cover contracts, uploads, and approvals.
- The AI adapter boundary already exists, including the `pii_review` task slot.

## Objective

- Analyze the latest approved `SourceSlice` for a source definition.
- Persist one `SourceSchemaArtifact` per `(source_definition_id, source_slice_version)`.
- Persist one `SourceValueSummary` per `(source_definition_id, source_slice_version, field_name)`.
- Expose `POST /projects/{project_id}/sources/{source_definition_id}/analyze`.
- Expose `GET /projects/{project_id}/sources/{source_definition_id}/schema`.
- Expose `GET /projects/{project_id}/sources/{source_definition_id}/value-summary`.

## Out of Scope

- Mapping-stage field binding.
- Lookup value mapping.
- Code generation and delivery bundle assembly.
- New AI config slots or provider wiring.
- UI work for source analysis.

## Blast Radius

- `engine/src/migrations_engine/db/models.py`
- `engine/migrations/versions/0011_source_analysis_artifacts.py`
- `engine/src/migrations_engine/api/schemas.py`
- `engine/src/migrations_engine/management/source_analysis.py`
- `engine/src/migrations_engine/routes/analysis.py`
- `engine/src/migrations_engine/app.py`
- `docs/domain/source-model.md`
- `engine/tests/test_source_analysis_models.py`
- `engine/tests/test_source_analysis_service.py`
- `engine/tests/test_source_analysis_api.py`

## File Changes

| File | Change |
|---|---|
| `docs/domain/source-model.md` | Add a source-analysis section that defines `SourceSchemaArtifact`, `SourceValueSummary`, sample caps, and the latest-approved-slice rule. |
| `engine/src/migrations_engine/db/models.py` | Add ORM models for `SourceSchemaArtifact` and `SourceValueSummary`. |
| `engine/migrations/versions/0011_source_analysis_artifacts.py` | Create the two new analysis tables and their uniqueness constraints. |
| `engine/src/migrations_engine/api/schemas.py` | Add response models for analysis initiation, schema artifacts, value summaries, and column schema rows. |
| `engine/src/migrations_engine/management/source_analysis.py` | Implement the analysis flow, artifact persistence, and lookup helpers. |
| `engine/src/migrations_engine/routes/analysis.py` | Add the three source-analysis endpoints. |
| `engine/src/migrations_engine/app.py` | Register the new analysis router. |
| `engine/tests/test_source_analysis_models.py` | Verify the models persist and the migration target tables exist. |
| `engine/tests/test_source_analysis_service.py` | Verify sample capping, PII masking, artifact persistence, and summary capping. |
| `engine/tests/test_source_analysis_api.py` | Verify the API contract, auth gating, and read endpoints. |

## Tests

- Model / migration check:
  - `cd engine && python -m alembic upgrade head`
  - `cd engine && pytest tests/test_source_analysis_models.py -q`
- Service check:
  - `cd engine && pytest tests/test_source_analysis_service.py -q`
- API check:
  - `cd engine && pytest tests/test_source_analysis_api.py -q`

## Verification

- Run the three focused Pytest files above.
- Confirm the analysis route returns `202` with `{"schema_artifact_id": "artifact-1", "status": "queued"}`.
- Confirm the service only sends 200 sampled rows to the AI adapter.
- Confirm value summaries never persist more than 500 distinct values per field.
- Confirm `alembic upgrade head` applies `0011` cleanly on SQLite.

## Pitfalls

- Do not analyze an unapproved slice. The service must select the latest approved `SourceSlice`.
- Do not leak raw PII into the AI prompt. Use the already-masked stored rows.
- Do not silently analyze more than 200 sampled rows.
- Do not persist more than 500 distinct values per field in `SourceValueSummary`.
- Do not add a new AI config slot when `pii_review` already exists.
- Do not expand the route beyond the three required endpoints.

## Commit

- `feat(source): add source analysis artifacts and API`

### Task 1: Source analysis models, migration, and public schemas

**Files:**
- Modify: `docs/domain/source-model.md`
- Modify: `engine/src/migrations_engine/db/models.py`
- Modify: `engine/src/migrations_engine/api/schemas.py`
- Create: `engine/migrations/versions/0011_source_analysis_artifacts.py`
- Create: `engine/tests/test_source_analysis_models.py`

**Interfaces:**
- Consumes: `SourceDefinition`, `SourceSlice`, `SourceSliceRow`
- Produces: `SourceSchemaArtifact`, `SourceValueSummary`, and the response models used by the analysis routes

- [ ] **Step 1: Write the failing model test**

```python
def test_source_analysis_tables_persist_rows() -> None:
    Base.metadata.create_all(bind=_sqlite_engine)

    with SessionLocal() as db:
        project_id, source_definition_id = _seed_source_definition(db)
        schema_artifact = SourceSchemaArtifact(
            source_definition_id=source_definition_id,
            source_slice_version="v1",
            columns=[
                {"name": "CUST_ID", "inferred_type": "integer", "nullable": False, "max_length": 8},
                {"name": "SURNAME", "inferred_type": "text", "nullable": True, "max_length": 40},
            ],
        )
        summary = SourceValueSummary(
            source_definition_id=source_definition_id,
            source_slice_version="v1",
            field_name="SURNAME",
            value_counts={"Smith": 3, "Jones": 2},
        )
        db.add_all([schema_artifact, summary])
        db.commit()

        stored_schema = db.get(SourceSchemaArtifact, schema_artifact.schema_artifact_id)
        stored_summary = db.get(SourceValueSummary, summary.summary_id)

    assert stored_schema is not None
    assert stored_schema.source_definition_id == source_definition_id
    assert stored_schema.columns[0]["name"] == "CUST_ID"
    assert stored_summary is not None
    assert stored_summary.value_counts["Smith"] == 3
```

- [ ] **Step 2: Run the model test and confirm it fails before implementation**

Run:

```bash
cd engine && pytest tests/test_source_analysis_models.py -q
```

Expected:

- fails because `SourceSchemaArtifact` / `SourceValueSummary` are not defined yet, or the tables are missing

- [ ] **Step 3: Add the ORM models, response schemas, and migration**

```python
class SourceSchemaArtifact(Base):
    __tablename__ = "source_schema_artifacts"

    schema_artifact_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    source_definition_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("source_definitions.source_definition_id"), nullable=False
    )
    source_slice_version: Mapped[str] = mapped_column(String(64), nullable=False)
    columns: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class SourceValueSummary(Base):
    __tablename__ = "source_value_summaries"

    summary_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    source_definition_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("source_definitions.source_definition_id"), nullable=False
    )
    source_slice_version: Mapped[str] = mapped_column(String(64), nullable=False)
    field_name: Mapped[str] = mapped_column(String(255), nullable=False)
    value_counts: Mapped[dict[str, int]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
```

```python
class SourceAnalysisResponse(BaseModel):
    schema_artifact_id: str
    status: Literal["queued"] = "queued"


class SourceSchemaColumnResponse(BaseModel):
    name: str
    inferred_type: Literal["text", "integer", "decimal", "date", "boolean", "uuid"]
    nullable: bool
    max_length: int | None


class SourceSchemaArtifactResponse(BaseModel):
    schema_artifact_id: str
    source_definition_id: str
    source_slice_version: str
    columns: list[SourceSchemaColumnResponse]
    created_at: datetime


class SourceValueSummaryResponse(BaseModel):
    summary_id: str
    source_definition_id: str
    source_slice_version: str
    field_name: str
    value_counts: dict[str, int]
    created_at: datetime
```

- [ ] **Step 4: Run the migration check and the model test**

Run:

```bash
cd engine && python -m alembic upgrade head && pytest tests/test_source_analysis_models.py -q
```

Expected:

- Alembic applies `0011_source_analysis_artifacts.py` cleanly
- the model test passes

- [ ] **Step 5: Commit the data-model slice**

```bash
git add docs/domain/source-model.md engine/src/migrations_engine/db/models.py engine/src/migrations_engine/api/schemas.py engine/migrations/versions/0011_source_analysis_artifacts.py engine/tests/test_source_analysis_models.py
git commit -m "feat(source): add analysis artifacts schema"
```

### Task 2: Analysis service, routes, and API coverage

**Files:**
- Create: `engine/src/migrations_engine/management/source_analysis.py`
- Create: `engine/src/migrations_engine/routes/analysis.py`
- Modify: `engine/src/migrations_engine/app.py`
- Create: `engine/tests/test_source_analysis_service.py`
- Create: `engine/tests/test_source_analysis_api.py`

**Interfaces:**
- Consumes: `get_adapter("pii_review")`, `SourceSlice`, `SourceSliceRow`, `SourceSchemaArtifact`, `SourceValueSummary`
- Produces: `analyze_source_slice()`, `get_latest_source_schema_artifact()`, `list_source_value_summaries()`

- [ ] **Step 1: Write the failing service test**

```python
def test_analyze_source_slice_caps_sample_and_masks_pii(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_adapter = FakeAdapter(
        analysis_result=AnalysisResult(
            columns=[
                ColumnSchema(name="CUST_ID", inferred_type="integer", nullable=False, max_length=8),
                ColumnSchema(name="SURNAME", inferred_type="text", nullable=True, max_length=40),
            ]
        )
    )
    monkeypatch.setattr("migrations_engine.ai.factory.get_adapter", lambda task: fake_adapter)

    with SessionLocal() as db:
        project_id, source_definition_id = _seed_approved_slice(db, row_count=201)
        response = analyze_source_slice(
            db,
            actor=_central_team_user(db),
            project_id=project_id,
            source_definition_id=source_definition_id,
        )

        schemas = list(db.scalars(select(SourceSchemaArtifact).where(SourceSchemaArtifact.source_definition_id == source_definition_id)))
        summaries = list(db.scalars(select(SourceValueSummary).where(SourceValueSummary.source_definition_id == source_definition_id)))

    assert response.status == "queued"
    assert len(fake_adapter.calls) == 1
    assert len(fake_adapter.calls[0].user.splitlines()) == 201
    assert "***" in fake_adapter.calls[0].user
    assert len(schemas) == 1
    assert len(summaries) == 2
```

```python
def test_analyze_source_slice_caps_value_summary_distinct_values(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_adapter = FakeAdapter(
        analysis_result=AnalysisResult(
            columns=[
                ColumnSchema(name="CUST_ID", inferred_type="integer", nullable=False, max_length=8),
                ColumnSchema(name="SURNAME", inferred_type="text", nullable=True, max_length=40),
            ]
        )
    )
    monkeypatch.setattr("migrations_engine.ai.factory.get_adapter", lambda task: fake_adapter)

    with SessionLocal() as db:
        project_id, source_definition_id = _seed_approved_slice(db, row_count=600, unique_values=True)
        analyze_source_slice(
            db,
            actor=_central_team_user(db),
            project_id=project_id,
            source_definition_id=source_definition_id,
        )

        stored_summary = db.scalar(
            select(SourceValueSummary).where(
                SourceValueSummary.source_definition_id == source_definition_id,
                SourceValueSummary.field_name == "SURNAME",
            )
        )

    assert stored_summary is not None
    assert len(stored_summary.value_counts) == 500
```

- [ ] **Step 2: Run the service test and confirm it fails before implementation**

Run:

```bash
cd engine && pytest tests/test_source_analysis_service.py -q
```

Expected:

- fails because `management/source_analysis.py` does not exist yet, or the analysis function is missing

- [ ] **Step 3: Implement the analysis service and routes**

```python
def analyze_source_slice(
    db: Session,
    *,
    actor: User,
    project_id: str,
    source_definition_id: str,
) -> SourceAnalysisResponse:
    adapter = get_adapter("pii_review")
    source_slice = _latest_approved_slice(db, project_id=project_id, source_definition_id=source_definition_id)
    sample_text = _build_sample_text(db, source_slice=source_slice, limit=200)
    result = adapter.call(_SYSTEM_PROMPT, sample_text, AnalysisResult)
    schema_artifact = _persist_schema_artifact(db, source_slice=source_slice, result=result)
    _persist_value_summaries(db, source_slice=source_slice, result=result)
    db.commit()
    return SourceAnalysisResponse(schema_artifact_id=schema_artifact.schema_artifact_id, status="queued")
```

```python
@router.post("/{source_definition_id}/analyze", response_model=SourceAnalysisResponse, status_code=status.HTTP_202_ACCEPTED)
def post_source_analysis(
    project_id: str,
    source_definition_id: str,
    actor: User = Depends(get_central_team_user),
    db: Session = Depends(get_db),
) -> SourceAnalysisResponse:
    return analyze_source_slice(
        db,
        actor=actor,
        project_id=project_id,
        source_definition_id=source_definition_id,
    )
```

```python
app.include_router(analysis_router)
```

- [ ] **Step 4: Run the service and API tests**

Run:

```bash
cd engine && pytest tests/test_source_analysis_service.py tests/test_source_analysis_api.py -q
```

Expected:

- both tests pass
- the API returns the queued envelope for `POST /analyze`
- the `GET /schema` and `GET /value-summary` endpoints return the latest persisted artifacts

- [ ] **Step 5: Commit the service and route slice**

```bash
git add engine/src/migrations_engine/management/source_analysis.py engine/src/migrations_engine/routes/analysis.py engine/src/migrations_engine/app.py engine/tests/test_source_analysis_service.py engine/tests/test_source_analysis_api.py
git commit -m "feat(source): add source analysis api"
```
