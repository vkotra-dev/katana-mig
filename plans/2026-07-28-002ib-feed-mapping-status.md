# Plan: 002ib — Feed mapping status + 409 error context

## Goal

1. Include existing snapshot context in 409 errors so the FE can show what happened
2. Add a `mapping_status` summary field to `FeedResponse` — quick-glance indicator (fiber list provides per-table detail)

## Design

### `mapping_status` semantics

Single value per feed, computed from `MappingSnapshot` records where `source_definition_id == feed_id`:
- `null` — no snapshots exist
- `"draft"` — all snapshots are `"draft"` or `"rejected"` (rejected = not yet resubmitted)
- `"approved"` — all snapshots are `"approved"`
- `"partial"` — mixed (e.g. some approved + some draft, or approved + rejected)

Rejected snapshots are included in the status set (not filtered out). A table with `"rejected"` status means it needs rework and should pull the summary toward `"partial"`. This is consistent with how dedup works: stale rejected rows are dropped by dedup (keep latest per table), but the current latest rejected row stays and is evaluated like any other non-approved state.

### Deduplication

Both `_compute_mapping_status` (single-feed) and `_batch_mapping_status` (batch) must dedup to latest snapshot per `destination_object_name`, following the established pattern in `review.py:189-196` and `sign_offs.py:185-191`: query ordered by `destination_object_name ASC, created_at DESC`, keep first-seen per table.

### Project-scoped snapshots (`source_definition_id IS NULL`)

Not included. These are project-level, not feed-level. Different lifecycle.

## Files Changed

### 1. `engine/src/migrations_engine/api/deps.py`

Add optional `detail` parameter to `AuthApiError`:

```python
from typing import Any

class AuthApiError(Exception):
    def __init__(self, code: str, message: str, status_code: int, detail: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.detail = detail
```

### 2. `engine/src/migrations_engine/app.py`

Include detail in error JSON:

```python
@app.exception_handler(AuthApiError)
async def auth_api_error_handler(request: Request, exc: AuthApiError) -> JSONResponse:
    content: dict = {"error": {"code": exc.code, "message": exc.message}}
    if exc.detail:
        content["error"]["detail"] = exc.detail
    return _cors_response(request, status_code=exc.status_code, content=content)
```

### 3. `engine/src/migrations_engine/api/schemas.py`

Add `mapping_status` to `FeedResponse`:

```python
class FeedResponse(BaseModel):
    # ... existing fields ...
    mapping_status: Literal["draft", "partial", "approved"] | None = None
```

### 4. `engine/src/migrations_engine/management/feeds.py`

Add helpers and update all callers of `_source_contract_response` to pass `db`:

**New helper — `_dedup_snapshots`:**

```python
def _dedup_snapshots(
    snapshots: list[MappingSnapshot],
) -> list[MappingSnapshot]:
    """Dedup to latest snapshot per (source_definition_id, destination_object_name).

    Caller must ORDER BY destination_object_name ASC, created_at DESC.
    Mirrors the pattern in review.py:189 and sign_offs.py:185.

    Keys on both source_definition_id and destination_object_name so it's safe
    to call with snapshots from multiple feeds at once (batch mode).
    """
    seen: set[tuple[str, str]] = set()
    unique: list[MappingSnapshot] = []
    for s in snapshots:
        key = (s.source_definition_id, s.destination_object_name)
        if key not in seen:
            seen.add(key)
            unique.append(s)
    return unique
```

**New helper — `_compute_status_from_snapshots`:**

```python
def _compute_status_from_snapshots(
    deduped: list[MappingSnapshot],
) -> Literal["draft", "partial", "approved"] | None:
    """Compute summary from deduped snapshots.

    "rejected" pulls toward "partial" — a rejected table needs rework and
    should not be silently ignored. Dedup already drops stale history,
    so this function only sees one row per table.
    """
    if not deduped:
        return None
    statuses: set[str] = {s.status for s in deduped}
    if statuses == {"approved"}:
        return "approved"
    if statuses == {"draft"}:
        return "draft"
    if statuses == {"rejected"}:
        return "draft"  # rejected = not yet resubmitted
    return "partial"
```

**New function — `_compute_mapping_status`:**

```python
def _compute_mapping_status(
    db: Session, project_id: str, feed_id: str
) -> Literal["draft", "partial", "approved"] | None:
    snapshots = db.scalars(
        select(MappingSnapshot)
        .where(
            MappingSnapshot.project_id == project_id,
            MappingSnapshot.source_definition_id == feed_id,
        )
        .order_by(MappingSnapshot.destination_object_name.asc(), MappingSnapshot.created_at.desc())
    ).all()
    deduped = _dedup_snapshots(snapshots)
    return _compute_status_from_snapshots(deduped)
```

**New function — `_batch_mapping_status`:**

```python
def _batch_mapping_status(
    db: Session, project_id: str, feed_ids: set[str]
) -> dict[str, Literal["draft", "partial", "approved"] | None]:
    if not feed_ids:
        return {}
    snapshots = db.scalars(
        select(MappingSnapshot)
        .where(
            MappingSnapshot.project_id == project_id,
            MappingSnapshot.source_definition_id.in_(feed_ids),
        )
        .order_by(MappingSnapshot.destination_object_name.asc(), MappingSnapshot.created_at.desc())
    ).all()
    deduped = _dedup_snapshots(snapshots)
    # Group by source_definition_id, then compute per-feed
    per_feed: dict[str, list[MappingSnapshot]] = {}
    for s in deduped:
        per_feed.setdefault(s.source_definition_id, []).append(s)
    result: dict[str, Literal["draft", "partial", "approved"] | None] = {}
    for fid, snaps in per_feed.items():
        result[fid] = _compute_status_from_snapshots(snaps)
    return result
```

**Update `_source_contract_response`** to accept optional `db` and populate `mapping_status`:

```python
def _source_contract_response(
    source_definition: Feed, db: Session | None = None
) -> FeedResponse:
    details = source_definition.source_details or {}
    label = cast(str, details.get("label", source_definition.source_type))
    encoding = cast(str, details.get("encoding", "utf-8"))
    mapping_status = None
    if db is not None:
        mapping_status = _compute_mapping_status(
            db,
            project_id=source_definition.project_id,
            feed_id=source_definition.source_definition_id,
        )
    return FeedResponse(
        source_definition_id=source_definition.source_definition_id,
        project_id=source_definition.project_id,
        source_type=source_definition.source_type,
        label=label,
        encoding=encoding,
        destination_object_references=source_definition.destination_object_references,
        layout_information=cast(list[dict[str, Any]] | None, source_definition.layout_information),
        copybook_text=source_definition.copybook_text,
        status=source_definition.status,
        created_at=source_definition.created_at,
        mapping_hints=source_definition.mapping_hints,
        transformation_instructions=source_definition.transformation_instructions,
        mapping_status=mapping_status,
    )
```

**Update callers:**
- `create_source_contract` — pass `db=db`
- `get_source_contract` — pass `db=db`
- `discard_feed` — pass `db=db`
- `list_source_contracts` — use `_batch_mapping_status` + build FeedResponse inline (no db param needed for list)

**`list_source_contracts` rewritten:**

```python
def list_source_contracts(
    db: Session,
    *,
    project_id: str,
    include_discarded: bool = False,
) -> list[FeedResponse]:
    stmt = select(Feed).where(Feed.project_id == project_id)
    if not include_discarded:
        stmt = stmt.where(Feed.status != "discarded")
    stmt = stmt.order_by(Feed.created_at.asc())
    rows = db.scalars(stmt).all()

    feed_ids = {f.source_definition_id for f in rows}
    status_map = _batch_mapping_status(db, project_id, feed_ids)

    result: list[FeedResponse] = []
    for feed in rows:
        details = feed.source_details or {}
        label = cast(str, details.get("label", feed.source_type))
        encoding = cast(str, details.get("encoding", "utf-8"))
        result.append(FeedResponse(
            source_definition_id=feed.source_definition_id,
            project_id=feed.project_id,
            source_type=feed.source_type,
            label=label,
            encoding=encoding,
            destination_object_references=feed.destination_object_references,
            layout_information=cast(list[dict[str, Any]] | None, feed.layout_information),
            copybook_text=feed.copybook_text,
            status=feed.status,
            created_at=feed.created_at,
            mapping_hints=feed.mapping_hints,
            transformation_instructions=feed.transformation_instructions,
            mapping_status=status_map.get(feed.source_definition_id),
        ))
    return result
```

### 5. `engine/src/migrations_engine/mapping/proposal.py`

**IntegrityError handler (line ~317):**

```python
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        existing = db.scalars(
            select(MappingSnapshot).where(
                MappingSnapshot.project_id == project_id,
                MappingSnapshot.source_definition_id == source_definition_id,
            ).order_by(MappingSnapshot.destination_object_name)
        ).all()
        per_table: dict[str, list[str]] = {}
        for s in existing:
            per_table.setdefault(s.destination_object_name, []).append(s.status)
        raise AuthApiError(
            "mapping_already_proposed",
            "Mapping has already been proposed for this feed.",
            409,
            {"per_table_status": {k: list(set(v)) for k, v in per_table.items()}},
        )
```

**"No snapshots" path (line ~332):**

```python
    if not snapshots:
        raise AuthApiError(
            "mapping_already_proposed",
            "All proposed tables already have approved mappings. No changes to apply.",
            409,
        )
```

### 6. Tests

Add `engine/tests/test_mapping_status.py`:
- `_dedup_snapshots` returns latest per table when duplicates exist
- `_compute_status_from_snapshots` returns `"draft"` when all are draft, `"approved"` when all approved, `"partial"` when mixed, `None` when empty
- `_compute_status_from_snapshots` ignores `"rejected"` snapshots (key test: rejected+draft → "draft", not "partial")
- `get_source_contract` returns `mapping_status` in response
- `list_source_contracts` returns `mapping_status` from batch query
- Proposing duplicate mapping returns 409 with `per_table_status` in detail

## Verification

1. All existing tests pass
2. New tests cover dedup logic, status computation, 409 error detail
3. Manual: propose → approve one table → re-propose another → check `"partial"` on feed
4. Manual: propose twice → check 409 has `per_table_status`
5. Manual: reject then re-propose → check `"draft"` (not `"partial"`)

## Pitfalls

- `_dedup_snapshots` requires ordering by `destination_object_name ASC, created_at DESC` — callers must enforce this
- `_compute_mapping_status` only queries `source_definition_id == feed_id`, not project-scoped. Deliberate scope boundary.
- `list_source_contracts` builds FeedResponse inline to avoid duplicating `_source_contract_response`'s field list and db dependency.

## Commit Message

```
feat(codegen): add mapping_status to feed response; improve 409 error context

- Add optional detail dict to AuthApiError for structured error context
- Include per_table_status in 409 when proposing duplicate mapping
- Add mapping_status field to FeedResponse (null/draft/partial/approved)
- Dedup snapshots to latest per table (follows review.py/sign_offs pattern)
- Exclude rejected snapshots from status computation
- Batch compute mapping_status in list endpoint via single query
- Improve "no snapshots" 409 message

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
```
