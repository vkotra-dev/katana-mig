# Plan: 001cb — Promote LookupValueMap to Project Scope

- **Task Link:** [tasks/001cb-lookup-value-map-project-scope.md](../tasks/001cb-lookup-value-map-project-scope.md)

## Current State

`LookupValueMap` is keyed by `(source_definition_id, lookup_name)`. The same destination lookup table (e.g. `GENDER_CODES`) gets a separate row per feed that references it. After 001ca, the fiber bridge writes one row per feed — creating duplicates. `LookupSnapshot` is already project-scoped (`project_id + lookup_name`); `LookupValueMap` should match.

Listing is currently done by passing `source_definition_id` directly. After promotion, listing for a feed is done by joining through `ProjectFiber` to find which `lookup_name` values belong to which feed.

## Blast Radius

| Layer | Files |
|---|---|
| Migration | new file under `engine/migrations/versions/` |
| DB model | `engine/src/migrations_engine/db/models.py` |
| Management | `engine/src/migrations_engine/management/lookup_mapping.py` |
| Management | `engine/src/migrations_engine/management/change_requests.py` |
| Management | `engine/src/migrations_engine/management/gates.py` |
| Routes | `engine/src/migrations_engine/routes/lookup.py` |
| 001ca bridge | `engine/src/migrations_engine/management/fibers.py` |
| Frontend client | `web/lib/lookup-api.ts` |
| Feed workspace | `web/app/projects/[id]/feeds/[feedId]/page.tsx` |
| Review page | `web/app/projects/[id]/feeds/[feedId]/review/page.tsx` |

## File Changes

### 1. Migration

New file `0027_lookup_value_map_project_scope.py` (or next revision number):

```python
def upgrade() -> None:
    # 1. Add project_id column (nullable initially for backfill)
    op.add_column("lookup_value_maps",
        sa.Column("project_id", sa.String(36), sa.ForeignKey("project_registry.project_id"), nullable=True)
    )

    # 2. Backfill from source_definitions
    op.execute("""
        UPDATE lookup_value_maps lvm
        JOIN source_definitions sd ON lvm.source_definition_id = sd.source_definition_id
        SET lvm.project_id = sd.project_id
    """)

    # 3. Dedup: for any (project_id, lookup_name) collision keep the newest row
    op.execute("""
        DELETE lvm1 FROM lookup_value_maps lvm1
        INNER JOIN lookup_value_maps lvm2
          ON lvm1.project_id = lvm2.project_id
          AND lvm1.lookup_name = lvm2.lookup_name
          AND lvm1.created_at < lvm2.created_at
    """)

    # 4. Make project_id NOT NULL
    op.alter_column("lookup_value_maps", "project_id", nullable=False)

    # 5. Drop old unique constraint and source_definition_id
    op.drop_constraint("uq_lookup_value_maps_source_name", "lookup_value_maps", type_="unique")
    op.drop_column("lookup_value_maps", "source_definition_id")

    # 6. Add new unique constraint
    op.create_unique_constraint(
        "uq_lookup_value_maps_project_name",
        "lookup_value_maps",
        ["project_id", "lookup_name"],
    )

def downgrade() -> None:
    # Reverse: re-add source_definition_id (cannot recover original values)
    op.drop_constraint("uq_lookup_value_maps_project_name", "lookup_value_maps", type_="unique")
    op.add_column("lookup_value_maps",
        sa.Column("source_definition_id", sa.String(36), nullable=True)
    )
    op.drop_column("lookup_value_maps", "project_id")
```

> Check the actual constraint name on `lookup_value_maps` before running — use `SHOW CREATE TABLE lookup_value_maps` or inspect the existing migration that created it.

### 2. DB Model — `engine/src/migrations_engine/db/models.py`

Replace on `LookupValueMap`:
```python
# Remove:
source_definition_id: Mapped[str] = mapped_column(
    String(36), ForeignKey("source_definitions.source_definition_id"), nullable=False
)

# Add:
project_id: Mapped[str] = mapped_column(
    String(36), ForeignKey("project_registry.project_id"), nullable=False, index=True
)
```

### 3. Management — `management/lookup_mapping.py`

**`create_lookup_value_map`**: remove `source_definition_id` param; remove `_get_source_definition` call; use `project_id`:

```python
def create_lookup_value_map(
    db: Session,
    *,
    actor: User,
    project_id: str,
    body: LookupValueMapCreateRequest,
) -> LookupValueMapResponse:
    lookup_name = body.lookup_name.strip()
    ...
    draft = LookupValueMap(
        project_id=project_id,
        lookup_name=lookup_name,
        ...
    )
```

**`list_lookup_value_maps`**: add optional `feed_id` param; when provided, resolve lookup names via `ProjectFiber`:

```python
def list_lookup_value_maps(
    db: Session,
    *,
    project_id: str,
    feed_id: str | None = None,
) -> list[LookupValueMapResponse]:
    stmt = select(LookupValueMap).where(LookupValueMap.project_id == project_id)

    if feed_id:
        fiber_keys = db.scalars(
            select(ProjectFiber.fiber_key).where(
                ProjectFiber.project_id == project_id,
                ProjectFiber.feed_id == feed_id,
                ProjectFiber.fiber_type == "lookup",
            )
        ).all()
        stmt = stmt.where(LookupValueMap.lookup_name.in_(fiber_keys))

    return [
        _lookup_value_map_response(row)
        for row in db.scalars(stmt.order_by(LookupValueMap.created_at.asc())).all()
    ]
```

**`_latest_lookup_value_map`**: change filter from `source_definition_id` to `project_id`:

```python
def _latest_lookup_value_map(db, *, project_id: str, lookup_name: str) -> LookupValueMap:
    row = db.scalar(
        select(LookupValueMap).where(
            LookupValueMap.project_id == project_id,
            LookupValueMap.lookup_name == lookup_name,
            LookupValueMap.status == "draft",
        ).order_by(LookupValueMap.created_at.desc())
    )
    if row is None:
        raise AuthApiError("lookup_map_not_found", "Lookup value map not found.", 404)
    return row
```

**`generate_lookup_snapshot`**: keep `source_definition_id` param for source analysis + mapping snapshot lookup; change `_latest_lookup_value_map` call to use `project_id`:

```python
lookup_map = _latest_lookup_value_map(db, project_id=project_id, lookup_name=lookup_name)
```

### 4. Management — `change_requests.py` and `gates.py`

Both already have `project_id` in scope. Change each `LookupValueMap.source_definition_id ==` filter to `LookupValueMap.project_id == project_id`.

### 5. Routes — `routes/lookup.py`

**lookup-maps POST**: remove `source_definition_id` from path and handler:
```python
@router.post("/projects/{project_id}/lookup-maps", ...)
def post_lookup_value_map(project_id: str, body: ..., ...):
    return create_lookup_value_map(db, actor=actor, project_id=project_id, body=body)
```

**lookup-maps GET**: remove `source_definition_id` from path; add optional `feed_id` query param:
```python
@router.get("/projects/{project_id}/lookup-maps", ...)
def get_lookup_value_maps(
    project_id: str,
    feed_id: str | None = Query(default=None),
    ...
):
    return list_lookup_value_maps(db, project_id=project_id, feed_id=feed_id)
```

**lookup-snapshots POST**: no URL change — stays at `/projects/{project_id}/sources/{source_definition_id}/lookup-snapshots`.

### 6. Fiber bridge — `management/fibers.py` (001ca)

In `_bridge_lookup_fiber_to_value_map`, two changes:

**FK change** — query and create use `project_id` instead of `source_definition_id`:
```python
existing = db.scalar(
    select(LookupValueMap).where(
        LookupValueMap.project_id == fiber.project_id,
        LookupValueMap.lookup_name == lookup_name,
        LookupValueMap.status == "draft",
    ).order_by(LookupValueMap.created_at.desc())
)
```

**Merge rule** — when `existing` is found, only add source values not already present. Values written by a previously approved fiber are never overwritten — first business-approved fiber wins per source value:
```python
if existing:
    for src, dest in source_value_map.items():
        if src not in existing.source_value_map:
            existing.source_value_map[src] = dest
    existing_dest_ids = {_extract_destination_id(r) for r in existing.destination_table}
    for row in dest_entries:
        if _extract_destination_id(row) not in existing_dest_ids:
            existing.destination_table = existing.destination_table + [row]
else:
    db.add(LookupValueMap(
        project_id=fiber.project_id,
        lookup_name=lookup_name,
        ...
    ))
```

### 7. Frontend — `web/lib/lookup-api.ts`

```ts
// listLookupValueMaps: URL changes, feedId becomes query param
export async function listLookupValueMaps(
  token: string,
  projectId: string,
  feedId?: string,
): Promise<LookupValueMapRecord[]> {
  const url = feedId
    ? `/projects/${projectId}/lookup-maps?feed_id=${feedId}`
    : `/projects/${projectId}/lookup-maps`;
  ...
}

// createLookupValueMap: remove sourceDefinitionId param
export async function createLookupValueMap(
  token: string,
  projectId: string,
  input: LookupValueMapInput,
): Promise<LookupValueMapRecord> {
  return jsonRequest(`/projects/${projectId}/lookup-maps`, { method: "POST", ... });
}
```

### 8. Frontend — Callers

**`web/app/projects/[id]/feeds/[feedId]/page.tsx`**:
```ts
// list: feedId still passed, just as optional arg (same call, different URL)
const mapsData = await listLookupValueMaps(token, projectId, feedId);

// create: remove feedId arg
await createLookupValueMap(session.accessToken, projectId, input);
```

**`web/app/projects/[id]/feeds/[feedId]/review/page.tsx`**:
```ts
// unchanged — feedId still passed
listLookupValueMaps(token, projectId, feedId)
```

### 9. Frontend — Pre-populate inherited mappings in lookup fiber workspace

When the lookup fiber card opens for Feed 2, `listLookupValueMaps(token, projectId, feedId)` may return a shared map already populated by another fiber. The workspace must surface these **before** the operator clicks "AI Analyze" so they know which values are already handled.

**On load** — after fetching the lookup map, if `lookupMap.sourceValueMap` is non-empty, render the existing entries in a read-only "Already mapped" section:

```tsx
{existingMap && Object.keys(existingMap.sourceValueMap).length > 0 && (
  <div className="rounded border border-emerald-200 bg-emerald-50 p-3 mb-4">
    <p className="text-xs font-semibold text-emerald-700 mb-2">
      Mapped in another feed — these values will not be re-analyzed
    </p>
    <table className="text-xs w-full">
      <tbody>
        {Object.entries(existingMap.sourceValueMap).map(([src, dest]) => (
          <tr key={src}>
            <td className="py-0.5 pr-4 font-mono text-slate-600">{src}</td>
            <td className="py-0.5 text-slate-500">→</td>
            <td className="py-0.5 pl-4 font-mono text-slate-700">{dest}</td>
          </tr>
        ))}
      </tbody>
    </table>
  </div>
)}
```

**AI Analyze button** — always enabled; the analysis discovers Feed 2's source values from its own slice data. After analysis, the proposed mappings panel shows only values that are NOT already in `existingMap.sourceValueMap`. Values already mapped are excluded from the AI proposal list.

**On approval bridge** — the merge rule (001ca) ensures already-mapped values are never overwritten. The pre-populated display is purely informational.

## Pitfalls

- Dedup step in migration is required — if any project has two feeds that both previously created a `LookupValueMap` for the same `lookup_name`, a unique constraint violation would occur without it. Keep the newest row.
- Verify the exact unique constraint name on `lookup_value_maps` before the migration — introspect the table or check the migration that originally created it.
- `generate_lookup_snapshot` still needs `source_definition_id` for source analysis validation — do not remove it from that function or route.
- `LookupValueMapResponse` schema in `api/schemas.py` currently includes `source_definition_id` — replace with `project_id`. Frontend `LookupValueMapRecord` interface should be updated to match.
- `ProjectFiber` import needed in `lookup_mapping.py` for the feed-filtered list query.

## Verification

1. Run migration — no constraint errors; all existing rows have `project_id` populated
2. Feed workspace lists lookup maps filtered to that feed's fiber keys
3. Two feeds with the same `lookup_name` share one `LookupValueMap` row — approving one feed's fiber populates it; the second feed's workspace shows the same shared map
4. `generate_lookup_snapshot` succeeds using project-scoped map
5. TypeScript compiles cleanly

## Commit

- `feat(001cb): promote LookupValueMap to project scope; list by feed via ProjectFiber`
