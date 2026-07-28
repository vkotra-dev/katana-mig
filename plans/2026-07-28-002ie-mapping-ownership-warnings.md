Task: tasks/002ie-mapping-ownership-warnings.md
Domain: docs/domain/api.md, docs/domain/source-model.md

## Current State

- `mapping_status` on `FeedResponse` (`api/schemas.py:273`) already exists, computed via
  `_compute_mapping_status`/`_batch_mapping_status`/`_dedup_snapshots`/
  `_compute_status_from_snapshots` (`management/feeds.py:474-551`). It reflects only THIS feed's
  own snapshot statuses — no cross-feed awareness.
- `review.py`'s `approve_mapping()` (task 002id, shipped) has a cross-feed conflict guard using:
  ```python
  outerjoin(Feed, Feed.source_definition_id == MappingSnapshot.source_definition_id)
  ...
  or_(
      MappingSnapshot.source_definition_id.is_(None),
      and_(
          MappingSnapshot.source_definition_id != source_definition_id,
          Feed.status != "discarded",
      ),
  )
  ```
  This is the exact pattern to reuse here, not reinvent.
- `proposal.py`'s `propose_mapping()` (task 002ic, shipped) attaches `per_table_ownership` to its
  409 detail — reactive only, no changes needed here.
- `Feed` model (`db/models.py:228-250`, table `source_definitions`): `source_definition_id` (str
  PK), `source_type` (str, not null), `destination_object_references` (JSON `list[str] | None` —
  the tables THIS feed maps, populated by `approve_mapping()`), `source_details` (JSON dict |
  None), `status` (str, `"discarded"` is a real value).
- `list_source_contracts()` (`feeds.py:64-99`) and `_source_contract_response()` (`feeds.py:554-
  581`) already load `Feed` ORM rows directly and access `.destination_object_references`/
  `.source_details`/`.source_type` with zero extra query.
- Feed page (`web/app/projects/[id]/feeds/[feedId]/page.tsx`): `feed` state (line 51) populated via
  `getFeedContract` in `loadAllData` (lines 99-108). Field Mappings section header at line 894,
  button row lines 897-905, table list starts line 909. `conflictOwnership` dead-code state at
  lines 63, 240, 246-271 — confirmed nothing renders it anywhere in the file.
- `web/lib/feeds-api.ts`: `FeedContractRecord` interface (~5-19), `mapFeedContractResponse` raw
  param type (~153-166) and mapper body (~178) — the `mapping_status` field previously missed the
  raw param type spot specifically, causing a `tsc` error; don't repeat that.
- `docs/domain/api.md` and `docs/domain/source-model.md` — currently have no mention of
  `mapping_ownership_warnings`/`MappingOwnership` (this task adds them). `api.md` was hand-edited
  during design exploration with a draft of the contract; it has one internal gap (see File
  Changes) that must be fixed as part of this task, not left as-is.

## Objective

Add `mapping_ownership_warnings` to `FeedResponse` — a persistent, load-time, per-table warning
when another feed (or a project-scoped snapshot) already holds an approved `MappingSnapshot` for a
table this feed also maps. Wire it into both the single-feed and list endpoints, render it in the
feed page's Field Mappings section, and remove the dead `conflictOwnership` reactive attempt.

## Out of Scope

- No changes to `_compute_mapping_status`/`_batch_mapping_status`/`_dedup_snapshots`/
  `_compute_status_from_snapshots` — new, additive functions only.
- No changes to `propose_mapping()`'s `per_table_ownership` 409 detail (002ic) or `approve_mapping()`'s
  guard (002id) — both stay exactly as shipped.
- No pagination on the warnings dict.

## Blast Radius

| File | Action | What changes |
|------|--------|---------------|
| `engine/src/migrations_engine/api/schemas.py` | modify | `MappingOwnership` model + field on `FeedResponse` |
| `engine/src/migrations_engine/management/feeds.py` | modify | `_compute_ownership_warnings()`, `_batch_ownership_warnings()`; wiring |
| `web/lib/feeds-api.ts` | modify | `mappingOwnershipWarnings` — raw param type, interface, mapper |
| `web/app/projects/[id]/feeds/[feedId]/page.tsx` | modify | Delete `conflictOwnership`; simplify conflict catch; render warning card |
| `docs/domain/api.md` | modify | `MappingOwnership` model, field docs, render contract, fix null-owner gap |
| `docs/domain/source-model.md` | modify | Note on persistent counterpart to 002id guard |
| `engine/tests/test_mapping_ownership_warnings.py` | new | See Tests |

## File Changes

### `engine/src/migrations_engine/api/schemas.py`

After `mapping_status` (line 273):
```python
class MappingOwnership(BaseModel):
    source_definition_id: str | None
    feed_label: str | None
    feed_source_type: str | None
    status: str
    destination_object_name: str
    mapping_snapshot_id: str
```
On `FeedResponse`:
```python
mapping_ownership_warnings: dict[str, MappingOwnership] | None = None
```

### `engine/src/migrations_engine/management/feeds.py`

Add near `_batch_mapping_status` (~line 551):

```python
def _compute_ownership_warnings(
    db: Session, project_id: str, feed_id: str, own_tables: list[str] | None,
) -> dict[str, dict[str, Any]] | None:
    if not own_tables:
        return None
    rows = db.execute(
        select(MappingSnapshot, Feed.source_details, Feed.source_type)
        .outerjoin(Feed, Feed.source_definition_id == MappingSnapshot.source_definition_id)
        .where(
            MappingSnapshot.project_id == project_id,
            MappingSnapshot.destination_object_name.in_(own_tables),
            MappingSnapshot.status == "approved",
            or_(
                MappingSnapshot.source_definition_id.is_(None),
                and_(
                    MappingSnapshot.source_definition_id != feed_id,
                    Feed.status != "discarded",
                ),
            ),
        )
        .order_by(MappingSnapshot.created_at.desc())
    ).all()
    warnings: dict[str, dict[str, Any]] = {}
    for snap, source_details, source_type in rows:
        tbl = snap.destination_object_name
        if tbl in warnings:
            continue  # first (most recent) match wins per table
        label = (source_details or {}).get("label") if snap.source_definition_id else None
        warnings[tbl] = {
            "source_definition_id": snap.source_definition_id,
            "feed_label": label or (snap.source_definition_id[:8] if snap.source_definition_id else None),
            "feed_source_type": source_type,  # None for project-scoped rows (no Feed match)
            "status": "approved",
            "destination_object_name": tbl,
            "mapping_snapshot_id": snap.mapping_snapshot_id,
        }
    return warnings or None


def _batch_ownership_warnings(
    db: Session, project_id: str, feed_tables: dict[str, list[str]],
) -> dict[str, dict[str, dict[str, Any]] | None]:
    all_tables = {t for tables in feed_tables.values() for t in tables}
    if not all_tables:
        return {fid: None for fid in feed_tables}
    rows = db.execute(
        select(MappingSnapshot, Feed.source_details, Feed.source_type)
        .outerjoin(Feed, Feed.source_definition_id == MappingSnapshot.source_definition_id)
        .where(
            MappingSnapshot.project_id == project_id,
            MappingSnapshot.destination_object_name.in_(all_tables),
            MappingSnapshot.status == "approved",
            or_(
                MappingSnapshot.source_definition_id.is_(None),
                Feed.status != "discarded",
            ),
        )
        .order_by(MappingSnapshot.created_at.desc())
    ).all()
    by_table: dict[str, list[tuple]] = {}
    for snap, source_details, source_type in rows:
        by_table.setdefault(snap.destination_object_name, []).append((snap, source_details, source_type))

    result: dict[str, dict[str, dict[str, Any]] | None] = {}
    for fid, tables in feed_tables.items():
        warnings: dict[str, dict[str, Any]] = {}
        for tbl in tables:
            other = next((c for c in by_table.get(tbl, []) if c[0].source_definition_id != fid), None)
            if other:
                snap, source_details, source_type = other
                label = (source_details or {}).get("label") if snap.source_definition_id else None
                warnings[tbl] = {
                    "source_definition_id": snap.source_definition_id,
                    "feed_label": label or (snap.source_definition_id[:8] if snap.source_definition_id else None),
                    "feed_source_type": source_type,
                    "status": "approved",
                    "destination_object_name": tbl,
                    "mapping_snapshot_id": snap.mapping_snapshot_id,
                }
        result[fid] = warnings or None
    return result
```

One query for the whole batch, not per feed. Check `and_`/`or_`/`Feed` imports at the top of
`feeds.py` before adding — `or_`/`Feed` were likely already imported for `_batch_mapping_status`;
`and_` may need adding.

**Wiring** — `_source_contract_response()` (~554-581): compute `own_tables =
source_definition.destination_object_references`, pass to `_compute_ownership_warnings`, set on
the returned `FeedResponse`. `list_source_contracts()` (~64-99): build `feed_tables =
{f.source_definition_id: (f.destination_object_references or []) for f in rows}`, call
`_batch_ownership_warnings` once, distribute per feed.

### `web/lib/feeds-api.ts`

Three spots:
1. Raw param type in `mapFeedContractResponse` (~153-166): add
   `mapping_ownership_warnings?: Record<string, { source_definition_id: string | null; feed_label: string | null; feed_source_type: string | null; status: string; destination_object_name: string; mapping_snapshot_id: string; }> | null;`
2. `FeedContractRecord` interface (~5-19): add a matching camelCase `MappingOwnership` TS interface
   and `mappingOwnershipWarnings: Record<string, MappingOwnership> | null;`.
3. Mapper body (~178): map field-by-field from snake_case to camelCase — do not cast.

### `web/app/projects/[id]/feeds/[feedId]/page.tsx`

- Delete `conflictOwnership` state (line 63) and its usages (line 240, lines 246-271).
- Simplify `handleAnalyzeWithAi`'s inner catch:
  ```ts
  try {
    await proposeMappingSnapshot(session.accessToken, projectId, feedId);
  } catch (err) {
    const status = (err as any).status || 0;
    const isConflict = err instanceof Error && (err.message.includes("conflict") || err.message.includes("409"));
    if (status !== 409 && !isConflict) throw err;
    // Table already owned elsewhere — no separate message here; loadAllData() below
    // refreshes mapping_ownership_warnings, the single canonical place this shows.
  }
  await loadAllData(session.accessToken);
  ```
- Insert an amber warning card between line 906 and line 909 in the Field Mappings section, reading
  `feed?.mappingOwnershipWarnings`: `<b>{table}</b> is already mapped on <link to
  /projects/{projectId}/feeds/{sourceDefinitionId} or "this project" if null> {(source_type) if
  non-null} →`. Render nothing if null/empty.

### `docs/domain/api.md`

Verify the pre-existing draft against what's implemented; fix the gap: after the `feed_source_type`
bullet, clarify both `feed_label`/`feed_source_type` are `null` for the project-scoped case, and
note in the render contract that the `(feed_source_type)` parenthetical is omitted (not shown as
"(null)") when project-scoped. Bump `timestamp`.

### `docs/domain/source-model.md`

Add one paragraph after the 002id guard description (~line 425-432) noting
`mapping_ownership_warnings` is the persistent, load-time counterpart to that guard. Bump
`timestamp`.

## Tests

- Feed B's `destination_object_references` includes `"Customer"`; Feed A has an approved
  `"Customer"` snapshot → Feed B's `mapping_ownership_warnings["Customer"]` shows Feed A's id/
  label/source_type.
- No conflict → field is `null`.
- Project-scoped (`NULL` `source_definition_id`) approved snapshot → warning shows with
  `source_definition_id: null`, `feed_label`/`feed_source_type` both `null`.
- Discarded owning feed → excluded.
- `list_source_contracts` batch path matches single-feed path for multiple feeds in one call.
- A feed's own approved table → no self-warning.

## Verification

```bash
.venv/bin/python -m pytest engine/tests/test_mapping_ownership_warnings.py -v
.venv/bin/python -m pytest engine/tests -q
.venv/bin/python scripts/validate_okf.py
cd web && npx tsc --noEmit
cd web && npm test
```

## Pitfalls

- Don't touch `_compute_mapping_status`/`_batch_mapping_status` — additive only.
- Don't repeat the raw-param-type gap that broke `mapping_status` in `feeds-api.ts` the first time.
- Never cast raw JSON to a camelCase type — map field-by-field (exact bug found in the removed
  `conflictOwnership` code).
- `_batch_ownership_warnings` must be one query for the whole batch, not per feed.
- Exclude discarded feeds; never warn a feed against its own approved row.

## Commit

```
feat(mapping): add persistent cross-feed table-ownership warning

Add mapping_ownership_warnings to FeedResponse - derived from DB state
on every feed load (not a one-shot reaction to a failed propose/approve
call like the existing 002ic/002id mechanisms). Reuses
Feed.destination_object_references and the established cross-feed
conflict-detection pattern from review.py's approve_mapping() guard.

Deletes the dead conflictOwnership state in the feed page (computed but
never rendered) and simplifies handleAnalyzeWithAi's conflict handling
to just reload feed data, avoiding a duplicate warning display.
```
