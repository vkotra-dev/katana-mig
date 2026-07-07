# Plan: 001bw — Dashboard Health View

- **Task Link:** [tasks/001bw-dashboard-health-view.md](../tasks/001bw-dashboard-health-view.md)
- **Domain Link:** [docs/domain/project.md](../docs/domain/project.md)

## Current State

The dashboard contains a `SummaryStrip` showing three metrics (Total Projects, Active Migrations, and Completed Migrations) and a `PortfolioTable` listing active projects with details about the project name, goals, and latest run. However, there are no visual indicators showing the progress or health of the underlying source feeds, mapping snaplots, or lookup value mappings. 

## Objective

1. Add database health analysis helpers to load project health summaries in batch.
2. Extend `ProjectResponse` and frontend interfaces to carry project health indicators.
3. Update `<SummaryStrip>` on the dashboard to a 5-column layout with "Needs Attention" and "Pending Review" status aggregates.
4. Render Feed / Mapping / Lookup status badges in the `<PortfolioTable>` on the dashboard.

## Blast Radius

| Layer | Files |
|---|---|
| API schema | `engine/src/migrations_engine/api/schemas.py` |
| Management | `engine/src/migrations_engine/management/projects.py` |
| Frontend API client | `web/lib/projects-api.ts` |
| Portfolio UI component | `web/components/portfolio/PortfolioTable.tsx` |
| Summary strip UI | `web/components/portfolio/SummaryStrip.tsx` |
| Dashboard page | `web/app/dashboard/page.tsx` |

## File Changes

### 1. API Schema — `engine/src/migrations_engine/api/schemas.py`

Add `HealthStatus` and `ProjectHealthSummary` schemas:

```python
HealthStatus = Literal["healthy", "pending_review", "needs_attention"]


class ProjectHealthSummary(BaseModel):
    feed_status: HealthStatus
    mapping_status: HealthStatus
    lookup_status: HealthStatus
```

And update `ProjectResponse` to include the `health` field:

```python
class ProjectResponse(BaseModel):
    # ... existing fields
    latest_run_summary: LatestRunSummary | None = None
    health: ProjectHealthSummary | None = None
```

---

### 2. Management — `engine/src/migrations_engine/management/projects.py`

Add `_load_project_health_summaries` function and update `list_projects` and `_project_response`.

```python
def _load_project_health_summaries(
    db: Session,
    project_ids: list[str],
) -> dict[str, ProjectHealthSummary]:
    if not project_ids:
        return {}

    # Initialize results
    health_by_project: dict[str, dict[str, str]] = {
        pid: {"feed": "healthy", "mapping": "healthy", "lookup": "healthy"}
        for pid in project_ids
    }

    # 1. Feed Status
    latest_slice_subquery = (
        select(
            FeedSlice.source_definition_id,
            func.max(FeedSlice.created_at).label("max_created_at")
        )
        .group_by(FeedSlice.source_definition_id)
        .subquery()
    )

    feed_slices_stmt = (
        select(
            Feed.project_id,
            Feed.source_definition_id,
            FeedSlice.status.label("slice_status")
        )
        .outerjoin(
            latest_slice_subquery,
            Feed.source_definition_id == latest_slice_subquery.c.source_definition_id
        )
        .outerjoin(
            FeedSlice,
            (FeedSlice.source_definition_id == latest_slice_subquery.c.source_definition_id)
            & (FeedSlice.created_at == latest_slice_subquery.c.max_created_at)
        )
        .where(Feed.project_id.in_(project_ids))
    )

    # Temporary groupings to roll up feed status
    project_feed_statuses: dict[str, list[str]] = {pid: [] for pid in project_ids}
    for project_id, _, slice_status in db.execute(feed_slices_stmt).all():
        if slice_status is None:
            status = "needs_attention"
        elif slice_status == "rejected":
            status = "needs_attention"
        elif slice_status == "pending_approval":
            status = "pending_review"
        else:
            status = "healthy"
        project_feed_statuses[project_id].append(status)

    for pid, statuses in project_feed_statuses.items():
        if not statuses:
            health_by_project[pid]["feed"] = "healthy"
        elif "needs_attention" in statuses:
            health_by_project[pid]["feed"] = "needs_attention"
        elif "pending_review" in statuses:
            health_by_project[pid]["feed"] = "pending_review"
        else:
            health_by_project[pid]["feed"] = "healthy"

    # 2. Mapping Status
    mapping_stmt = (
        select(
            Feed.project_id,
            Feed.source_definition_id,
            MappingSnapshot.status.label("snapshot_status")
        )
        .outerjoin(
            MappingSnapshot,
            Feed.source_definition_id == MappingSnapshot.source_definition_id
        )
        .where(Feed.project_id.in_(project_ids))
    )

    project_mapping_statuses: dict[str, list[str]] = {pid: [] for pid in project_ids}
    for project_id, _, snapshot_status in db.execute(mapping_stmt).all():
        if snapshot_status is None:
            status = "needs_attention"
        elif snapshot_status == "rejected":
            status = "needs_attention"
        elif snapshot_status == "draft":
            status = "pending_review"
        else:
            status = "healthy"
        project_mapping_statuses[project_id].append(status)

    for pid, statuses in project_mapping_statuses.items():
        if not statuses:
            health_by_project[pid]["mapping"] = "healthy"
        elif "needs_attention" in statuses:
            health_by_project[pid]["mapping"] = "needs_attention"
        elif "pending_review" in statuses:
            health_by_project[pid]["mapping"] = "pending_review"
        else:
            health_by_project[pid]["mapping"] = "healthy"

    # 3. Lookup Status
    lookup_stmt = (
        select(
            ProjectFiber.project_id,
            ProjectFiber.fiber_id,
            LookupMapping.status.label("mapping_status")
        )
        .outerjoin(
            LookupMapping,
            ProjectFiber.fiber_id == LookupMapping.fiber_id
        )
        .where(
            ProjectFiber.project_id.in_(project_ids),
            ProjectFiber.fiber_type == "lookup"
        )
    )

    # Track by project: fiber_id -> list of mapping statuses
    project_lookup_data: dict[str, dict[str, list[str]]] = {pid: {} for pid in project_ids}
    for project_id, fiber_id, mapping_status in db.execute(lookup_stmt).all():
        if fiber_id not in project_lookup_data[project_id]:
            project_lookup_data[project_id][fiber_id] = []
        if mapping_status:
            project_lookup_data[project_id][fiber_id].append(mapping_status)

    for pid, fibers_data in project_lookup_data.items():
        if not fibers_data:
            health_by_project[pid]["lookup"] = "healthy"
            continue

        fiber_statuses = []
        for fiber_id, statuses in fibers_data.items():
            if not statuses:
                # Fiber exists but has zero mappings
                fiber_statuses.append("needs_attention")
            elif any(s == "rejected" for s in statuses):
                fiber_statuses.append("needs_attention")
            elif any(s in ("proposed", "pending", "draft") for s in statuses):
                fiber_statuses.append("pending_review")
            else:
                fiber_statuses.append("healthy")

        if "needs_attention" in fiber_statuses:
            health_by_project[pid]["lookup"] = "needs_attention"
        elif "pending_review" in fiber_statuses:
            health_by_project[pid]["lookup"] = "pending_review"
        else:
            health_by_project[pid]["lookup"] = "healthy"

    # Convert to response schemas
    return {
        pid: ProjectHealthSummary(
            feed_status=states["feed"],
            mapping_status=states["mapping"],
            lookup_status=states["lookup"],
        )
        for pid, states in health_by_project.items()
    }
```

Update `list_projects`:
```python
    latest_run_summary_by_project = _load_latest_run_summaries(db, [registry.project_id for registry, _ in rows])
    health_by_project = _load_project_health_summaries(db, [registry.project_id for registry, _ in rows])

    return [
        _project_response(
            registry,
            definition,
            latest_run_summary=latest_run_summary_by_project.get(registry.project_id),
            health=health_by_project.get(registry.project_id),
        )
        for registry, definition in rows
    ]
```

And update `_project_response` to accept `health` and set it:
```python
def _project_response(
    registry: ProjectRegistry,
    definition: ProjectDefinition,
    latest_run_summary: LatestRunSummary | None = None,
    health: ProjectHealthSummary | None = None,
) -> ProjectResponse:
    return ProjectResponse(
        # ... existing fields
        latest_run_summary=latest_run_summary,
        health=health,
    )
```

---

### 3. Frontend API Client — `web/lib/projects-api.ts`

Add interfaces:

```typescript
export type HealthStatus = "healthy" | "pending_review" | "needs_attention";

export interface ProjectHealthSummary {
  feedStatus: HealthStatus;
  mappingStatus: HealthStatus;
  lookupStatus: HealthStatus;
}
```

Add optional `health?: ProjectHealthSummary` to `ProjectRecord`.

Update `mapProjectRecord` translation logic:

```typescript
    health: backend.health
      ? {
          feedStatus: backend.health.feed_status,
          mappingStatus: backend.health.mapping_status,
          lookupStatus: backend.health.lookup_status,
        }
      : undefined,
```

---

### 4. Summary Strip component — `web/components/portfolio/SummaryStrip.tsx`

Extend the card indicators layout to 5 grid columns, adding "Needs Attention" and "Pending Review" metrics:

```typescript
interface SummaryStripProps {
  total: number;
  active: number;
  needsAttention: number;
  pendingReview: number;
  completed: number;
}
```

Render red-themed border/background cards for "Needs Attention" and amber/blue for "Pending Review".

---

### 5. Dashboard View — `web/app/dashboard/page.tsx`

Calculate counts using the health summary states:
- `needsAttention` = projects where `health.feedStatus === "needs_attention" || health.mappingStatus === "needs_attention" || health.lookupStatus === "needs_attention"`.
- `pendingReview` = projects where any status is `"pending_review"` and none are `"needs_attention"`.

---

### 6. Portfolio Table — `web/components/portfolio/PortfolioTable.tsx`

Render status chips for **Feeds**, **Mappings**, and **Lookups** instead of a single static project status block.

## Key Decisions & Invariants

- Batch queries for health summaries are written with clean joins using raw SQLAlchemy queries to prevent execution overhead (N+1 queries).
- Feed slice lookup joins on `Feed.project_id` due to `FeedSlice` lack of direct project membership relation.
