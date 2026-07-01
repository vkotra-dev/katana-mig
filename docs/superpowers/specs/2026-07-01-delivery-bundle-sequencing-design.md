# AI-Assisted Delivery Bundle Sequencing — Design Spec

**Status:** Approved  
**Date:** 2026-07-01

## Problem

The delivery bundle (`GET /projects/{project_id}/delivery-bundle`) concatenates SQL artifacts in alphabetical order. When handed to ops, there is no indication of the correct execution sequence. If destination objects have FK dependencies (e.g. `customers` must exist before `orders`), running scripts out of order will fail.

## Solution

Use AI to analyse the project's `destination_schema_ddl` once, extract all destination objects and their FK/REFERENCES relationships, and produce a topologically-sorted execution sequence. Store this analysis on the project. Use it to order the delivery bundle and prefix each SQL block with a sequence number. Surface a summary report showing how many objects were identified vs how many have been processed (have active artifacts).

## Trigger

When the **first source** is added to a project, if no schema analysis exists yet, the Sources tab shows a prompt banner:

> "Analyze your destination schema to enable dependency-ordered SQL delivery."  → **Analyze DDL** button

Clicking the button runs the AI analysis. The banner disappears once analysis exists. If `destination_schema_ddl` is not set on the project, the button is disabled with a tooltip: "Set a destination schema DDL on the project first."

Re-analysis: a secondary "Re-analyze" button appears on the codegen page once analysis exists, for when the DDL is updated.

---

## Backend

### New AI task slot: `schema_dependency`

**`engine/config/engine.yaml`** — add under `migration.models`:
```yaml
schema_dependency: ${MODEL_SCHEMA_DEPENDENCY}
```

**`engine/src/migrations_engine/ai/config.py`** — add field to `MigrationModelConfig`:
```python
schema_dependency: str
```
Add parse line in `_parse_config`:
```python
schema_dependency=_require_str(migration_models, "schema_dependency", "migration.models.schema_dependency"),
```

**`engine/src/migrations_engine/ai/factory.py`** — add to `_SLOT_MAP`:
```python
"schema_dependency": lambda config: config.migration_models.schema_dependency,
```

---

### New DB model: `ProjectSchemaAnalysis`

**`engine/src/migrations_engine/db/models.py`**:

```python
class ProjectSchemaAnalysis(Base):
    __tablename__ = "project_schema_analyses"

    analysis_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("project_definitions.project_id"), nullable=False, unique=True)
    destination_object_sequence: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    identified_count: Mapped[int] = mapped_column(Integer, nullable=False)
    analyzed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
```

`unique=True` on `project_id` — one analysis record per project; re-analysis overwrites.

---

### New migration: `0016_project_schema_analysis`

**`engine/migrations/versions/0016_project_schema_analysis.py`**:

```python
revision = "0016_project_schema_analysis"
down_revision = "0015_reconciliation_tables"

def upgrade() -> None:
    op.create_table(
        "project_schema_analyses",
        sa.Column("analysis_id", sa.String(36), primary_key=True),
        sa.Column("project_id", sa.String(36), sa.ForeignKey("project_definitions.project_id"), nullable=False, unique=True),
        sa.Column("destination_object_sequence", sa.JSON(), nullable=False),
        sa.Column("identified_count", sa.Integer(), nullable=False),
        sa.Column("analyzed_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_project_schema_analyses_project_id", "project_schema_analyses", ["project_id"])

def downgrade() -> None:
    op.drop_index("ix_project_schema_analyses_project_id", table_name="project_schema_analyses")
    op.drop_table("project_schema_analyses")
```

---

### New service: `codegen/schema_analysis.py`

**AI prompt:**

```
System: You are a SQL DDL analyst. Given a multi-table DDL script, identify all destination objects (tables/views) and their dependency relationships based on FOREIGN KEY / REFERENCES clauses. Return a JSON object matching the schema below.

User: <destination_schema_ddl>
```

**Response model:**

```python
class _ObjectDependency(BaseModel):
    name: str            # destination object name
    depends_on: list[str]  # names of objects this one references

class _DDLAnalysisResult(BaseModel):
    objects: list[_ObjectDependency]
```

**Topological sort:** Standard Kahn's algorithm over the dependency graph. Cycles are broken by falling back to alphabetical insertion of remaining nodes (with a warning recorded in `analyzed_at` metadata — no hard failure).

**Service function:**

```python
def run_schema_analysis(
    db: Session,
    *,
    project_id: str,
) -> ProjectSchemaAnalysisResponse:
    project = db.get(ProjectDefinition, project_id)
    if project is None:
        raise AuthApiError("not_found", "Project not found.", 404)

    ddl = (project.domain_config or {}).get("destination_schema_ddl")
    if not ddl:
        raise AuthApiError("missing_ddl", "Project has no destination_schema_ddl.", 422)

    adapter = get_adapter("schema_dependency")
    result = adapter.call(SYSTEM_PROMPT, ddl, _DDLAnalysisResult)

    sequence = _topological_sort(result.objects)   # list[str], ordered

    existing = db.scalars(
        select(ProjectSchemaAnalysis).where(ProjectSchemaAnalysis.project_id == project_id)
    ).first()

    if existing:
        existing.destination_object_sequence = sequence
        existing.identified_count = len(sequence)
        existing.analyzed_at = datetime.now(UTC)
        db.flush()
        record = existing
    else:
        record = ProjectSchemaAnalysis(
            project_id=project_id,
            destination_object_sequence=sequence,
            identified_count=len(sequence),
            analyzed_at=datetime.now(UTC),
        )
        db.add(record)
        db.flush()

    db.commit()
    db.refresh(record)
    return _to_response(db, record, project_id)


def get_schema_analysis(
    db: Session,
    *,
    project_id: str,
) -> ProjectSchemaAnalysisResponse | None:
    record = db.scalars(
        select(ProjectSchemaAnalysis).where(ProjectSchemaAnalysis.project_id == project_id)
    ).first()
    if record is None:
        return None
    return _to_response(db, record, project_id)
```

**`_to_response`** computes `processed_count` dynamically: count how many names in `destination_object_sequence` have at least one `active` `CodeGenerationArtifact` with a matching `destination_object_name`.

---

### API schemas

```python
class ProjectSchemaAnalysisResponse(BaseModel):
    analysis_id: str
    project_id: str
    destination_object_sequence: list[str]
    identified_count: int
    processed_count: int    # computed dynamically
    analyzed_at: str        # ISO datetime
```

---

### New routes (added to `codegen.py` router)

```python
@router.post("/projects/{project_id}/schema-analysis", response_model=ProjectSchemaAnalysisResponse)
def trigger_schema_analysis(
    project_id: str,
    actor: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ProjectSchemaAnalysisResponse:
    require_project_access(db, user=actor, project_id=project_id)
    return run_schema_analysis(db, project_id=project_id)


@router.get("/projects/{project_id}/schema-analysis", response_model=ProjectSchemaAnalysisResponse | None)
def get_schema_analysis_route(
    project_id: str,
    actor: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ProjectSchemaAnalysisResponse | None:
    require_project_access(db, user=actor, project_id=project_id)
    return get_schema_analysis(db, project_id=project_id)
```

Both routes: any authenticated user with project access (read or write).

---

### Updated `build_delivery_bundle_text`

When `ProjectSchemaAnalysis` exists for the project, sort artifacts by position in `destination_object_sequence` and prefix each block with a zero-padded sequence number:

```python
def build_delivery_bundle_text(db: Session, *, project_id: str) -> DeliveryBundleResponse:
    analysis = get_schema_analysis(db, project_id=project_id)
    sequence = analysis.destination_object_sequence if analysis else None

    artifacts = db.scalars(
        select(CodeGenerationArtifact)
        .where(
            CodeGenerationArtifact.project_id == project_id,
            CodeGenerationArtifact.status == "active",
        )
        .order_by(CodeGenerationArtifact.destination_object_name.asc(), CodeGenerationArtifact.created_at.desc())
    ).all()

    if sequence:
        position = {name: i for i, name in enumerate(sequence)}
        artifacts = sorted(artifacts, key=lambda a: position.get(a.destination_object_name, len(sequence)))

    bundle_parts: list[str] = []
    for idx, artifact in enumerate(artifacts, start=1):
        if sequence:
            prefix = f"-- [{idx:02d}] {artifact.destination_object_name}"
        else:
            prefix = f"-- {artifact.destination_object_name}"
        bundle_parts.append(prefix)
        if artifact.sql_bundle:
            bundle_parts.append(artifact.sql_bundle.strip())

    return DeliveryBundleResponse(
        sql_bundle="\n\n".join(bundle_parts).strip(),
        artifact_count=len(artifacts),
    )
```

Artifacts whose `destination_object_name` is not in the sequence sort to the end (position = `len(sequence)`).

---

## Frontend

### New API helper: `codegen-api.ts`

```typescript
export interface SchemaAnalysisRecord {
  analysisId: string;
  projectId: string;
  destinationObjectSequence: string[];
  identifiedCount: number;
  processedCount: number;
  analyzedAt: string;
}

export async function getSchemaAnalysis(
  token: string,
  projectId: string,
): Promise<SchemaAnalysisRecord | null> { ... }   // GET, returns null on 404

export async function triggerSchemaAnalysis(
  token: string,
  projectId: string,
): Promise<SchemaAnalysisRecord> { ... }   // POST
```

---

### SourceList: analysis prompt banner

After the first source loads (i.e. `sources.length > 0`), fetch `GET /projects/{project_id}/schema-analysis`. If the result is `null`, show a banner above the source table:

```
┌─────────────────────────────────────────────────────────────────────┐
│  Analyze your destination schema to enable dependency-ordered SQL   │
│  delivery.                                          [Analyze DDL]   │
└─────────────────────────────────────────────────────────────────────┘
```

- Banner styled: `rounded-xl border border-primary/30 bg-primary/5 px-4 py-3`
- "Analyze DDL" button: `bg-primary text-white` pill; disabled + tooltip "Set destination_schema_ddl on the project first" if `project.domainConfig?.destinationSchemaDdl` is absent
- On click: POST to trigger analysis; on success banner disappears, codegen page report updates on next visit

Banner is not shown if analysis already exists.

---

### Codegen page: schema analysis report panel

Add a new panel below the "Delivery bundle" sidebar panel (already exists). Shows when `SchemaAnalysisRecord` is loaded:

```
Schema dependency analysis
──────────────────────────
  Identified    12 objects
  Processed      7 objects   ← have active artifact
  Pending        5 objects   ← no active artifact yet

  [Re-analyze DDL]   (triggers POST, refreshes)

  Analyzed: 2026-07-01 14:22
```

If no analysis exists, shows:
```
  No schema analysis yet. Add a source and click "Analyze DDL" to begin.
```

Panel is always visible on the codegen page (shows empty state if no analysis).

---

## Error handling

| Condition | Behaviour |
|---|---|
| `destination_schema_ddl` not set | POST returns `422 missing_ddl`; UI shows inline error under button |
| AI call fails | `AICallError` bubbles to `500`; UI shows "Analysis failed, try again" |
| DDL has no FK relationships | AI returns all objects with empty `depends_on`; sequence is alphabetical; no error |
| Cycle detected in FK graph | Cycle nodes appended alphabetically after acyclic nodes; no error; analysis completes |

---

## Tests

**Service (`tests/codegen/test_schema_analysis.py`)**
- `run_schema_analysis` with valid DDL produces ordered sequence and correct `identified_count`
- Re-running overwrites existing record (not creates a second)
- Missing DDL raises `AuthApiError("missing_ddl", ..., 422)`
- `get_schema_analysis` returns `None` when no record exists
- `_to_response` computes `processed_count` from active artifacts correctly
- `build_delivery_bundle_text` prefixes with `[01]` when analysis present; falls back to plain heading when absent
- Artifacts not in sequence sort to end of bundle

**Route (`tests/routes/test_schema_analysis_routes.py`)**
- `POST /projects/{id}/schema-analysis` — `central_team` succeeds, unauthenticated 401
- `GET /projects/{id}/schema-analysis` — returns null when no analysis; returns record when present

**UI (`SourceList.test.tsx`)**
- Banner appears when sources exist and analysis is null
- Banner hidden when analysis exists
- "Analyze DDL" disabled when no `destinationSchemaDdl`
- Clicking "Analyze DDL" calls `triggerSchemaAnalysis` and hides banner on success

**UI (`CodegenPage.test.tsx`)**
- Report panel shows identified/processed/pending counts
- "Re-analyze DDL" calls `triggerSchemaAnalysis` and refreshes counts
