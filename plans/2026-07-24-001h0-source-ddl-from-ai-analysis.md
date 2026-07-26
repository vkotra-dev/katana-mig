Task: tasks/001h0-source-ddl-from-ai-analysis.md
Domain: docs/domain/source-model.md, docs/domain/api.md

## Current State

- `SourceSchemaArtifact` stores source schema analysis results with columns (name, inferred_type, nullable, max_length) and a `created_at` timestamp.
- The `source_analysis.yaml` prompt asks the AI to infer column schemas from CSV/fixed-length samples. It returns JSON matching `AnalysisResult(columns: list[ColumnSchema], re_use_score: int | None)`.
- The analyze endpoint (`analyze_source_slice`) calls the AI, saves the artifact, and returns `{ schema_artifact_id, status }`.
- The feed page shows an "Analyze with AI" button. After analysis, the field mapping table is populated.
- There is no DDL generation from source analysis. The project-level `destination_schema_ddl` is a free-text field in `project_definition.domain_config`.

## Objective

Extend source analysis to also produce a SQL DDL statement (CREATE TABLE) from the inferred columns, using the target database engine. Store the DDL and display it on the feed page with a copy button.

## Out of Scope

- Do NOT auto-apply the DDL to the project's `destination_schema_ddl`
- Do NOT generate DDL for multiple tables
- Do NOT modify the existing column analysis flow

## Blast Radius

| File | Action | What changes |
|------|--------|-------------|
| `engine/tests/test_source_analysis_models.py` | modify | Update 1 existing, add 1 new test |
| `engine/tests/test_source_analysis_service.py` | modify | Add 1 new test (existing covered by default) |
| `engine/tests/test_source_analysis_api.py` | modify | Update 1 existing, add 1 new test |
| `engine/src/migrations_engine/ai/prompts/source_analysis.yaml` | modify | Add `target_db_engine` + DDL instructions |
| `engine/src/migrations_engine/management/analysis_schemas.py` | modify | Add `ddl: str` to `AnalysisResult` |
| `engine/src/migrations_engine/db/models.py` | modify | Add `destination_ddl` column |
| `engine/migrations/versions/0042_...` | create | Migration for new column |
| `engine/src/migrations_engine/management/source_analysis.py` | modify | Pass `target_db_engine`, save DDL |
| `engine/src/migrations_engine/api/schemas.py` | modify | Add `destination_ddl` field |
| `web/lib/feeds-api.ts` | modify | Add `destinationDDL` type |
| `web/lib/feeds-api.ts` | add | New `getSourceSchemaArtifact()` API call |
| `web/app/projects/[id]/feeds/[feedId]/page.tsx` | modify | Add `sourceDDL` state, wire into `loadAllData` and `handleAnalyzeWithAi`, add collapsible DDL section |
| `docs/domain/source-model.md` | modify | Document new field |
| `docs/domain/api.md` | modify | Document response change |

## File Changes

### 1. `engine/src/migrations_engine/ai/prompts/source_analysis.yaml`

Add `target_db_engine` to system prompt and instruct AI to include a `ddl` field:

```yaml
system: |
  You are a data analyst. Given CSV or fixed-length record samples, infer column schemas.
  CRITICAL RULES:
  1. Column Order & Names: You MUST preserve the exact column order. If a header is provided, copy every column name VERBATIM, character-for-character. Do NOT change casing or fix typos in column names.
  2. Type Inference: Infer types (text, integer, decimal, date, boolean, uuid) based on sample rows. Ignore masked or redacted values (e.g. 'MASKED', '****') when inferring types.
  3. Nullability: Set 'nullable' to true if any sample row has an empty/null value for the column.
  4. Max Length: For text columns, provide 'max_length' as the maximum character count found. For other types, set max_length to null.
  5. SQL DDL Generation: Using the inferred columns and the target database engine '$target_db_engine', generate a valid CREATE TABLE SQL statement. The table name should be derived from the source file context. Use appropriate SQL data types for the target engine (e.g. VARCHAR for text, INT for integer, DECIMAL(p,s) for decimal, DATE for date, BOOLEAN for boolean, CHAR(36) for uuid). Include NOT NULL constraints for non-nullable columns. Return the DDL as a single string.
  Return a JSON object with exactly these fields:
  - "columns": list of column objects (see schema)
  - "ddl": a single SQL CREATE TABLE string
  - "re_use_score": (optional) int or null

  $source_type_section

user: |
  $sample_text
```

Note: `$target_db_engine` will be substituted via `prompt.set(target_db_engine=...)`.

### 2. `engine/src/migrations_engine/management/analysis_schemas.py`

Add `ddl: str` field to `AnalysisResult`:

```python
class AnalysisResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    columns: list[ColumnSchema]
    re_use_score: int | None = None
    ddl: str = ""  # NEW: generated DDL from AI (default empty so existing tests don't break)
```

### 3. `engine/src/migrations_engine/db/models.py`

Add `destination_ddl` column to `SourceSchemaArtifact` **after `created_at` (line 337)**:

```python
destination_ddl: Mapped[str | None] = mapped_column(Text, nullable=True)
```

Note: NOT at line 334 — the `columns` field is at line 334. The new column goes after `created_at` at line 337.

### 4. Migration: `engine/migrations/versions/0042_add_source_ddl_to_source_schema_artifact.py`

```python
"""add destination_ddl to source_schema_artifact

Revision ID: 0042
Revises: 0041
"""
from alembic import op
import sqlalchemy as sa

revision = "0042"
down_revision = "0041"

def upgrade() -> None:
    op.add_column("source_schema_artifacts",
                    sa.Column("destination_ddl", sa.Text(), nullable=True))

def downgrade() -> None:
    op.drop_column("source_schema_artifacts", "destination_ddl")
```

### 5. `engine/src/migrations_engine/management/source_analysis.py`

Modify the prompt call to pass `target_db_engine` (line ~86-90):

```python
target_db = project_definition.domain_config.get("target_db_engine", "postgresql") if project_definition.domain_config else "postgresql"

prompt = Prompt("source_analysis")
prompt.set(
    source_type_section=source_type_section,
    sample_text=sample_text,
    target_db_engine=target_db,
)
```

Save the DDL to the artifact (line ~159-163):

```python
schema_artifact = SourceSchemaArtifact(
    source_definition_id=source_definition_id,
    source_slice_version=source_slice.source_slice_version,
    columns=[column.model_dump(mode="python") for column in analysis_result.columns],
    destination_ddl=getattr(analysis_result, "ddl", "") or None,
)
```

Also in this file: update `_schema_artifact_response` (line ~329) to include `destination_ddl=artifact.destination_ddl`.

### 6. `engine/src/migrations_engine/api/schemas.py`

Add `destination_ddl` to `SourceAnalysisResponse` (line ~404-408):

```python
class SourceAnalysisResponse(BaseModel):
    schema_artifact_id: str
    status: Literal["completed"] = "completed"
    ai_reuse_score: int | None = None
    destination_ddl: str | None = None  # NEW
```

Add `destination_ddl` to `SourceSchemaArtifactResponse` (line ~417-422):

```python
class SourceSchemaArtifactResponse(BaseModel):
    schema_artifact_id: str
    source_definition_id: str
    source_slice_version: str
    columns: list[SourceSchemaColumnResponse]
    created_at: datetime
    destination_ddl: str | None = None  # NEW
```

### 7. `engine/src/migrations_engine/routes/analysis.py`

Add a new GET route for the full artifact (line ~52, after value-summary route):

```python
# Add SourceSchemaArtifactResponse to the import in routes/analysis.py

@router.get("/{source_definition_id}/schema-artifact", response_model=SourceSchemaArtifactResponse)
def get_source_schema_artifact(
    project_id: str,
    source_definition_id: str,
    actor: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SourceSchemaArtifactResponse:
    require_project_access(db, user=actor, project_id=project_id)
    return get_latest_source_schema_artifact(
        db,
        project_id=project_id,
        source_definition_id=source_definition_id,
    )
```

### 8. `web/lib/feeds-api.ts`

Add `getSourceSchemaArtifact` function:

```typescript
export async function getSourceSchemaArtifact(
  token: string,
  projectId: string,
  sourceDefinitionId: string,
): Promise<{ schemaArtifactId: string; destinationDDL: string | null }> {
  const response = await requestJson<{
    schema_artifact_id: string;
    destination_ddl: string | null;
  }>(`/projects/${projectId}/sources/${sourceDefinitionId}/schema-artifact`, {
    method: "GET",
    token,
  });
  return {
    schemaArtifactId: response.schema_artifact_id,
    destinationDDL: response.destination_ddl ?? null,
  };
}
```

Update `analyzeFeedSource` return type to include `destinationDDL`:

```typescript
export async function analyzeFeedSource(
  token: string,
  projectId: string,
  sourceDefinitionId: string,
): Promise<{ status: string; schemaArtifactId: string; destinationDDL: string | null }> {
  const response = await requestJson<{ status: string; schema_artifact_id: string; destination_ddl: string | null }>(
    `/projects/${projectId}/sources/${sourceDefinitionId}/analyze`,
    { method: "POST", token },
  );
  return {
    status: response.status,
    schemaArtifactId: response.schema_artifact_id,
    destinationDDL: response.destination_ddl ?? null,
  };
}
```

### 9. `web/app/projects/[id]/feeds/[feedId]/page.tsx`

**State**: Add `sourceDDL` state:

```tsx
const [sourceDDL, setSourceDDL] = useState<string | null>(null);
```

**loadAllData**: After fetching schema, also fetch the artifact to persist DDL across reloads:

```tsx
let sourceDDLValue: string | null = null;
try {
  const artifact = await getSourceSchemaArtifact(token, projectId, feedId);
  sourceDDLValue = artifact.destinationDDL;
} catch { /* No artifact yet — DDL stays null */ }
```

Then pass it to state update:

```tsx
setFeedSchema(schemaData);
setSourceDDL(sourceDDLValue);
```

**handleAnalyzeWithAi**: Capture DDL from the analyze response and update state:

```tsx
const result = await analyzeFeedSource(session.accessToken, projectId, feedId);
setSourceDDL(result.destinationDDL ?? null);
await loadAllData(session.accessToken);
```

**Render**: Add collapsible DDL section after the mapping table:

```tsx
{sourceDDL && (
  <div className="pt-4 border-t border-slate-100">
    <div className="flex items-center justify-between mb-2">
      <h4 className="text-sm font-semibold text-slate-700">Source DDL</h4>
      <button
        type="button"
        onClick={() => {
          navigator.clipboard.writeText(sourceDDL);
          setNotice("DDL copied to clipboard.");
        }}
        className="text-xs text-primary hover:text-primary-hover font-medium"
      >
        Copy to clipboard
      </button>
    </div>
    <pre className="text-xs bg-slate-950 text-slate-100 rounded-lg p-3 font-mono whitespace-pre-wrap">
      {sourceDDL}
    </pre>
  </div>
)}
```

**Import**: Add `getSourceSchemaArtifact` to the import from `feeds-api`.

## Tests

### Schema default for backward compatibility

`AnalysisResult.ddl` must have a default value (`ddl: str = ""`) so existing tests that don't specify it don't break. The AI prompt will always supply it in production.

### File-by-file test changes

**`test_source_analysis_models.py` — 1 existing + 1 new:**

1. `test_source_analysis_tables_persist_rows` — update: add `destination_ddl=None` to the `SourceSchemaArtifact` constructor since the new column exists but old test data won't have it.
2. **New: `test_source_schema_artifact_persists_destination_ddl`** — create an artifact with `destination_ddl="CREATE TABLE ..."`, read it back, assert round-trip.

**`test_source_analysis_service.py` — 5 existing + 1 new:**

All 5 existing tests create `AnalysisResult(columns=[...])` without `ddl`. Since `ddl: str = ""` has a default, they won't break — no changes needed to existing test bodies.

3. **New: `test_analyze_source_slice_saves_ddl`** — full integration test:
   - `FakeAdapter` returns `AnalysisResult(columns=[...], ddl="CREATE TABLE customer_extract (CUST_ID INTEGER NOT NULL, SURNAME TEXT);")`
   - Call `analyze_source_slice(db, actor, project_id, source_definition_id)`
   - Query DB for the `SourceSchemaArtifact`
   - Assert `artifact.destination_ddl == "CREATE TABLE customer_extract ..."`

**`test_source_analysis_api.py` — 1 existing + 1 new:**

4. `test_source_analysis_returns_schema_and_value_summary` — update: the `AnalysisResult` in this test won't break (default `ddl=""`). After the existing assertions, assert `response.json()["destination_ddl"] is None` (since empty string `""` is falsy and should be stored as `None` in the model, or `""` if stored as-is — adjust assertion accordingly).

5. **New: `test_source_analysis_api_returns_destination_ddl`** — end-to-end API test:
   - POST to `/projects/{id}/sources/{id}/analyze` with mocked adapter returning a DDL
   - GET the response JSON
   - Assert `response.json()["destination_ddl"] == "CREATE TABLE ..."`

### Test summary

| File | Existing updated | New |
|------|-----------------|-----|
| `test_source_analysis_models.py` | 1 (`test_source_analysis_tables_persist_rows`) | 1 (`test_source_schema_artifact_persists_destination_ddl`) |
| `test_source_analysis_service.py` | 0 (default handles it) | 1 (`test_analyze_source_slice_saves_ddl`) |
| `test_source_analysis_api.py` | 1 (`test_source_analysis_returns_schema_and_value_summary`) | 1 (`test_source_analysis_api_returns_destination_ddl`) |

## Verification

```bash
# Backend: run all tests
.venv/bin/python -m pytest engine/tests -q

# Frontend: verify no type errors
cd web && npx tsc --noEmit 2>&1 | head -20
```

## Pitfalls

- The AI prompt must be explicit about returning `ddl` in the JSON response — without this the pydantic validation will fail
- The `target_db_engine` may be null in the project config — default to "postgresql"
- The Alembic migration `down_revision` must point to `0041` (the current head)
- The `destination_ddl` field must be nullable in both the model and migration (in case old artifacts don't have it)
- **Page reload gap**: The DDL must survive page reloads. `loadAllData()` must fetch the schema artifact via `getSourceSchemaArtifact()` and populate `sourceDDL` state. The DDL from the one-shot analyze response is also cached in state, but on subsequent mounts only `loadAllData` runs.
- Model column goes after `created_at` (line 337), not at line 334.

## Commit

```
feat(source-analysis): generate DDL from AI and persist on feed page
```
