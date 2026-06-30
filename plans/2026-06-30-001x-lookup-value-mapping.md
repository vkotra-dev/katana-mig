# Lookup Value Mapping Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add operator-managed lookup tables, generate approved lookup snapshots from source value summaries, and expose a lookup entry screen for each lookup field.

**Architecture:** Keep the pre-run lookup flow separate from runtime `LookupDeltaCR`. Store the operator-provided destination table as a versioned draft artifact, derive a `LookupSnapshot` only when the mapping is complete, and reuse `SourceValueSummary` to drive the source-side list. The backend lives in a dedicated management module plus routes; the UI page renders one lookup tab at a time and posts the draft table back through the new API.

**Tech Stack:** FastAPI, SQLAlchemy 2.x ORM, Pydantic v2, Alembic, Next.js App Router, React 19, Vitest, Testing Library.

## Global Constraints

- Source contracts are declared, not inferred from runtime connection strings.
- Source-type-specific structure must be preserved.
- A source slice is approved, immutable, and versioned before downstream use.
- Source analysis must mask raw PII before any AI-facing step.
- `mypy --strict` must stay clean.
- `ruff` must stay clean.
- Every DDL change ships with a hand-written Alembic migration in the same commit.
- Migration `0012` must run cleanly after `0011`.
- Lookup entry is a pre-run mapping flow; runtime `LookupDeltaCR` remains a separate path.

## Current State

- `docs/domain/source-model.md` describes lookup mapping only as a downstream concept; it does not yet spell out the operator-managed lookup table or snapshot creation flow.
- `engine/src/migrations_engine/db/models.py` has `LookupSnapshot`, `MappingSnapshot`, `SourceDefinition`, `SourceSlice`, and `SourceValueSummary`, but no `LookupValueMap`.
- `engine/src/migrations_engine/mapping/snapshots.py` already creates approved `LookupSnapshot` rows for runtime tests, but it does not accept operator-provided table drafts.
- `engine/src/migrations_engine/routes/` has no lookup route module yet.
- The project detail page already has a Sources tab, but there is no lookup page under `web/app/projects/[id]/sources/[sourceId]/lookup/`.

## Objective

- Persist operator-provided lookup tables as draft `LookupValueMap` records.
- Generate a `LookupSnapshot` from an approved `LookupValueMap` plus the latest `SourceValueSummary` rows for the relevant lookup field.
- Reject snapshot generation when any source values are unmapped and report those values explicitly.
- Approve a generated lookup snapshot and emit audit evidence.
- Add a lookup entry UI page with lookup tabs, source values, destination mappings, draft upload/paste support, and a two-step generate/approve flow.

## Out of Scope

- Runtime `LookupDeltaCR` handling in the execution engine.
- Mapping-snapshot creation.
- Code generation.
- Reworking the project detail Sources tab.
- Changing the `LookupSnapshot` runtime contract beyond what this task needs to persist and approve snapshots.

## Blast Radius

- `docs/domain/source-model.md`
- `engine/src/migrations_engine/db/models.py`
- `engine/migrations/versions/0012_lookup_value_maps.py`
- `engine/src/migrations_engine/api/schemas.py`
- `engine/src/migrations_engine/management/lookup_mapping.py`
- `engine/src/migrations_engine/routes/lookup.py`
- `engine/src/migrations_engine/app.py`
- `engine/tests/test_lookup_mapping_models.py`
- `engine/tests/test_lookup_mapping_service.py`
- `engine/tests/test_lookup_mapping_api.py`
- `web/lib/lookup-api.ts`
- `web/lib/lookup-api.test.ts`
- `web/app/projects/[id]/sources/[sourceId]/lookup/page.tsx`
- `web/app/projects/[id]/sources/[sourceId]/lookup/page.test.tsx`

## File Changes

| File | Change |
|---|---|
| `docs/domain/source-model.md` | Add a lookup-mapping section that defines lookup table drafts, snapshot generation, unmapped-value rejection, and approval. |
| `engine/src/migrations_engine/db/models.py` | Add `LookupValueMap` ORM model and any uniqueness constraints needed for `(source_definition_id, lookup_name, status)`. |
| `engine/migrations/versions/0012_lookup_value_maps.py` | Create the `lookup_value_maps` table. |
| `engine/src/migrations_engine/api/schemas.py` | Add request/response models for lookup table drafts, snapshot generation, and approval. |
| `engine/src/migrations_engine/management/lookup_mapping.py` | Implement draft persistence, snapshot generation, unmapped-value detection, and approval. |
| `engine/src/migrations_engine/routes/lookup.py` | Add the four lookup mapping endpoints. |
| `engine/src/migrations_engine/app.py` | Register the new lookup router. |
| `web/lib/lookup-api.ts` | Add API helpers for drafts, snapshots, and approval. |
| `web/app/projects/[id]/sources/[sourceId]/lookup/page.tsx` | Add the lookup entry screen. |
| `engine/tests/test_lookup_mapping_models.py` | Verify the draft table persists and uniqueness behaves as expected. |
| `engine/tests/test_lookup_mapping_service.py` | Verify snapshot generation, unmapped-value rejection, and approval behavior. |
| `engine/tests/test_lookup_mapping_api.py` | Verify auth gating and the lookup API contract. |
| `web/lib/lookup-api.test.ts` | Verify the client helpers serialize and map correctly. |
| `web/app/projects/[id]/sources/[sourceId]/lookup/page.test.tsx` | Verify the UI tabs, draft entry, and two-step snapshot flow. |

## Tests

- Model / migration check:
  - `cd engine && PYTHONPATH=src pytest tests/test_lookup_mapping_models.py -q`
  - `cd engine && source ../.venv/bin/activate && PYTHONPATH=src python -m alembic upgrade head --sql >/tmp/katana_001x_migration.sql`
- Service check:
  - `cd engine && PYTHONPATH=src pytest tests/test_lookup_mapping_service.py -q`
- API check:
  - `cd engine && PYTHONPATH=src pytest tests/test_lookup_mapping_api.py -q`
- UI check:
  - `cd web && npm test -- lib/lookup-api.test.ts app/projects/[id]/sources/[sourceId]/lookup/page.test.tsx`

## Verification

- Confirm `POST /projects/{project_id}/sources/{source_definition_id}/lookup-maps` stores the destination table draft for the named lookup.
- Confirm `POST /projects/{project_id}/sources/{source_definition_id}/lookup-snapshots` creates a `LookupSnapshot` with a fully populated `value_map`.
- Confirm unmapped source values cause a 409 or 422 response that lists the exact unmapped values.
- Confirm `POST /projects/{project_id}/sources/{source_definition_id}/lookup-snapshots/{lookup_snapshot_id}/approve` marks the lookup snapshot approved and records an audit event.
- Confirm the lookup UI shows source values from `SourceValueSummary` and the draft destination mapping controls.

## Pitfalls

- Do not conflate this pre-run lookup entry flow with runtime `LookupDeltaCR`.
- Do not build lookup snapshots from unmapped source values without surfacing the gap.
- Do not fetch source values from `SourceSliceRow`; use `SourceValueSummary`.
- Do not add a new AI dependency; this flow is deterministic and operator-driven.
- Do not widen the project shell unless the lookup page needs it.

## Commit

- `feat(lookup): add lookup value mapping and snapshot approval`

### Task 1: Lookup mapping model, service, routes, and API coverage

**Files:**
- Modify: `docs/domain/source-model.md`
- Modify: `engine/src/migrations_engine/db/models.py`
- Modify: `engine/src/migrations_engine/api/schemas.py`
- Create: `engine/migrations/versions/0012_lookup_value_maps.py`
- Create: `engine/src/migrations_engine/management/lookup_mapping.py`
- Create: `engine/src/migrations_engine/routes/lookup.py`
- Modify: `engine/src/migrations_engine/app.py`
- Create: `engine/tests/test_lookup_mapping_models.py`
- Create: `engine/tests/test_lookup_mapping_service.py`
- Create: `engine/tests/test_lookup_mapping_api.py`

**Interfaces:**
- Consumes: `SourceValueSummary`, `LookupSnapshot`, `SourceDefinition`, `User`
- Produces: `LookupValueMap`, `LookupSnapshot`, `create_lookup_value_map()`, `generate_lookup_snapshot()`, `approve_lookup_snapshot()`

- [ ] **Step 1: Write the failing model test**

```python
def test_lookup_value_map_persists_and_limits_one_draft_per_lookup() -> None:
    Base.metadata.create_all(bind=TEST_ENGINE)

    with SessionLocal() as db:
        project_id, source_definition_id = _seed_source_definition(db)
        draft = LookupValueMap(
            source_definition_id=source_definition_id,
            lookup_name="status_code",
            destination_table=[
                {"id": "ACTIVE", "label": "Active"},
                {"id": "BLOCKED", "label": "Blocked"},
            ],
            status="draft",
        )
        db.add(draft)
        db.commit()

        stored = db.get(LookupValueMap, draft.lookup_value_map_id)

    assert stored is not None
    assert stored.lookup_name == "status_code"
    assert stored.destination_table[0]["id"] == "ACTIVE"
```

- [ ] **Step 2: Run the model test and confirm it fails before implementation**

Run:

```bash
cd engine && PYTHONPATH=src pytest tests/test_lookup_mapping_models.py -q
```

Expected:

- fails because `LookupValueMap` is not defined yet, or the table is missing

- [ ] **Step 3: Add the ORM model, response schemas, and migration**

```python
class LookupValueMap(Base):
    __tablename__ = "lookup_value_maps"
    __table_args__ = (
        UniqueConstraint(
            "source_definition_id",
            "lookup_name",
            "status",
            name="uq_lookup_value_maps_definition_lookup_status",
        ),
    )

    lookup_value_map_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    source_definition_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("source_definitions.source_definition_id"), nullable=False
    )
    lookup_name: Mapped[str] = mapped_column(String(128), nullable=False)
    destination_table: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="draft")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
```

```python
class LookupValueMapCreateRequest(BaseModel):
    lookup_name: str = Field(min_length=1, max_length=128)
    destination_table: list[dict[str, Any]]


class LookupValueMapResponse(BaseModel):
    lookup_value_map_id: str
    source_definition_id: str
    lookup_name: str
    destination_table: list[dict[str, Any]]
    status: Literal["draft", "approved"]
    created_at: datetime


class LookupSnapshotGenerateRequest(BaseModel):
    lookup_name: str = Field(min_length=1, max_length=128)


class LookupSnapshotResponse(BaseModel):
    lookup_snapshot_id: str
    project_id: str
    source_definition_id: str
    lookup_name: str
    lookup_snapshot_version: str
    value_map: dict[str, str]
    status: Literal["draft", "approved"]
    created_at: datetime
```

- [ ] **Step 4: Run the migration check and the model test**

Run:

```bash
cd engine && source ../.venv/bin/activate && PYTHONPATH=src python -m alembic upgrade head --sql >/tmp/katana_001x_migration.sql && PYTHONPATH=src pytest tests/test_lookup_mapping_models.py -q
```

Expected:

- Alembic renders the full chain through `0012_lookup_value_maps.py`
- the model test passes

- [ ] **Step 5: Implement the service and route layer**

```python
def create_lookup_value_map(
    db: Session,
    *,
    actor: User,
    project_id: str,
    source_definition_id: str,
    body: LookupValueMapCreateRequest,
) -> LookupValueMapResponse:
    lookup_value_map = LookupValueMap(
        source_definition_id=source_definition_id,
        lookup_name=body.lookup_name.strip(),
        destination_table=body.destination_table,
        status="draft",
    )
    db.add(lookup_value_map)
    db.commit()
    db.refresh(lookup_value_map)
    return LookupValueMapResponse(
        lookup_value_map_id=lookup_value_map.lookup_value_map_id,
        source_definition_id=lookup_value_map.source_definition_id,
        lookup_name=lookup_value_map.lookup_name,
        destination_table=lookup_value_map.destination_table,
        status=lookup_value_map.status,
        created_at=lookup_value_map.created_at,
    )


def generate_lookup_snapshot(
    db: Session,
    *,
    actor: User,
    project_id: str,
    source_definition_id: str,
    body: LookupSnapshotGenerateRequest,
) -> LookupSnapshotResponse:
    lookup_value_map = _require_draft_lookup_value_map(
        db,
        project_id=project_id,
        source_definition_id=source_definition_id,
        lookup_name=body.lookup_name,
    )
    source_values = _load_source_values(db, source_definition_id=source_definition_id, lookup_name=body.lookup_name)
    destination_ids = {str(row.get("id")): row for row in lookup_value_map.destination_table}
    value_map: dict[str, str] = {}
    unmapped_values: list[str] = []
    for source_value in source_values:
        destination_row = destination_ids.get(source_value)
        if destination_row is None:
            unmapped_values.append(source_value)
            continue
        value_map[source_value] = str(destination_row["id"])
    if unmapped_values:
        raise ValueError(f"Unmapped source values: {', '.join(unmapped_values)}")
    snapshot = LookupSnapshot(
        project_id=project_id,
        lookup_name=body.lookup_name,
        lookup_snapshot_version=_next_lookup_snapshot_version(db, project_id=project_id, lookup_name=body.lookup_name),
        value_map=value_map,
        status="draft",
    )
    db.add(snapshot)
    db.commit()
    db.refresh(snapshot)
    return LookupSnapshotResponse(
        lookup_snapshot_id=snapshot.lookup_snapshot_id,
        project_id=snapshot.project_id,
        source_definition_id=source_definition_id,
        lookup_name=snapshot.lookup_name,
        lookup_snapshot_version=snapshot.lookup_snapshot_version,
        value_map=snapshot.value_map,
        status=snapshot.status,
        created_at=snapshot.created_at,
    )


@router.post("/{source_definition_id}/lookup-maps", response_model=LookupValueMapResponse, status_code=status.HTTP_201_CREATED)
def post_lookup_value_map(
    project_id: str,
    source_definition_id: str,
    body: LookupValueMapCreateRequest,
    actor: User = Depends(get_central_team_user),
    db: Session = Depends(get_db),
) -> LookupValueMapResponse:
    return create_lookup_value_map(
        db,
        actor=actor,
        project_id=project_id,
        source_definition_id=source_definition_id,
        body=body,
    )
```

- [ ] **Step 6: Run the service and API tests**

Run:

```bash
cd engine && PYTHONPATH=src pytest tests/test_lookup_mapping_service.py tests/test_lookup_mapping_api.py -q
```

Expected:

- the draft persistence test passes
- the unmapped-value rejection test passes
- the approval test passes
- the API returns the expected error codes and payloads

- [ ] **Step 7: Commit the backend slice**

```bash
git add docs/domain/source-model.md engine/src/migrations_engine/db/models.py engine/src/migrations_engine/api/schemas.py engine/migrations/versions/0012_lookup_value_maps.py engine/src/migrations_engine/management/lookup_mapping.py engine/src/migrations_engine/routes/lookup.py engine/src/migrations_engine/app.py engine/tests/test_lookup_mapping_models.py engine/tests/test_lookup_mapping_service.py engine/tests/test_lookup_mapping_api.py
git commit -m "feat(lookup): add value mapping backend"
```

### Task 2: Lookup entry screen and client helpers

**Files:**
- Create: `web/lib/lookup-api.ts`
- Create: `web/lib/lookup-api.test.ts`
- Create: `web/app/projects/[id]/sources/[sourceId]/lookup/page.tsx`
- Create: `web/app/projects/[id]/sources/[sourceId]/lookup/page.test.tsx`

**Interfaces:**
- Consumes: `listSourceContracts`, `listSourceSlices`, `SourceValueSummary`, `LookupValueMapResponse`
- Produces: `listLookupValueMaps()`, `createLookupValueMap()`, `generateLookupSnapshot()`, `approveLookupSnapshot()`, and the lookup page UI

- [ ] **Step 1: Write the failing client test**

```tsx
it("posts a lookup draft and maps the response", async () => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
    ok: true,
    status: 201,
    json: async () => ({
      lookup_value_map_id: "map-1",
      source_definition_id: "source-1",
      lookup_name: "status_code",
      destination_table: [{ id: "ACTIVE", label: "Active" }],
      status: "draft",
      created_at: "2026-06-30T00:00:00Z",
    }),
  }));

  const result = await createLookupValueMap("token-1", "project-1", "source-1", {
    lookupName: "status_code",
    destinationTable: [{ id: "ACTIVE", label: "Active" }],
  });

  expect(result.status).toBe("draft");
  expect(fetch).toHaveBeenCalledWith(
    expect.stringContaining("/lookup-maps"),
    expect.objectContaining({ method: "POST" }),
  );
});
```

- [ ] **Step 2: Run the client test and confirm it fails before implementation**

Run:

```bash
cd web && npm test -- lib/lookup-api.test.ts
```

Expected:

- fails because `lookup-api.ts` does not exist yet

- [ ] **Step 3: Implement the lookup API client and page**

```tsx
export function LookupPage({ params }: { params: Promise<{ id: string; sourceId: string }> }) {
  const { id: projectId, sourceId } = use(params);
  const [session, setSession] = useState<UiSession | null>(null);
  const [lookupNames, setLookupNames] = useState<string[]>([]);
  const [activeLookup, setActiveLookup] = useState<string | null>(null);
  const [sourceValues, setSourceValues] = useState<SourceValueSummaryRecord[]>([]);
  const [draftRows, setDraftRows] = useState<LookupDraftRow[]>([]);

  useEffect(() => {
    setSession(loadUiSession());
  }, []);

  useEffect(() => {
    if (!session) {
      return;
    }
    void loadLookupData(session.accessToken, projectId, sourceId).then(({ names, values }) => {
      setLookupNames(names);
      setActiveLookup(names[0] ?? null);
      setSourceValues(values);
    });
  }, [projectId, session, sourceId]);

  return (
    <main className="flex min-h-screen flex-col bg-surface text-slate-800">
      <Topbar role={role} />
      <section className="mx-auto flex w-full max-w-[1600px] flex-1 flex-col gap-4 px-6 py-6">
        <LookupTabs lookupNames={lookupNames} activeLookup={activeLookup} onSelect={setActiveLookup} />
        <LookupValueTable sourceValues={sourceValues} activeLookup={activeLookup} />
        <LookupDraftEditor draftRows={draftRows} onChange={setDraftRows} />
      </section>
    </main>
  );
}
```

- [ ] **Step 4: Run the UI tests**

Run:

```bash
cd web && npm test -- lib/lookup-api.test.ts app/projects/[id]/sources/[sourceId]/lookup/page.test.tsx
```

Expected:

- the client helper test passes
- the lookup page test passes

- [ ] **Step 5: Commit the UI slice**

```bash
git add web/lib/lookup-api.ts web/lib/lookup-api.test.ts web/app/projects/[id]/sources/[sourceId]/lookup/page.tsx web/app/projects/[id]/sources/[sourceId]/lookup/page.test.tsx
git commit -m "feat(lookup): add lookup entry screen"
```
