# Task 001t — Runs Backend (API + Execution Engine)

**Plan:** `plans/2026-06-29-001t-runs-api.md`

## Domain

- `docs/domain/runs.md` — run loop, baton handoff, checkpoint rule, LookupDeltaCR
- `docs/domain/source-model.md` — SourceSlice, CodeGenerationArtifact
- `docs/domain/governance.md` — approval, audit, I18

## Depends on

- 001q (source intake — SourceSlice must exist)
- 001ab (source slice approval — pin_snapshots requires status = "approved")
- 001r (CodeGenerationArtifact model + migration 0009)
- 001s (AI adapter — used by execution stages that call the LLM)

## Scope

Run record CRUD, run launch, execution engine (outer + inner loop), checkpoint
writes, LookupDeltaCR interrupt, and resume. `RunRecord` and `RunCheckpoint` ORM
models already exist (migration 0003). No new migration needed unless fields are
added.

## Existing models (migration 0003)

`RunRecord` and `RunCheckpoint` are already in `models.py`. Confirm field coverage
against the spec before adding columns. If fields are missing (e.g.
`codegen_artifact_id`, `destination_object_name`), add them via migration
`0010_run_record_fields.py` under I18.

## Schemas (`api/schemas.py` additions)

```python
class RunCreateRequest(BaseModel):
    destination_object_name: str
    source_definition_id: str
    environment: str | None = None

class RunResponse(BaseModel):
    run_id: str
    project_id: str
    destination_object_name: str
    environment: str | None
    status: str        # queued | running | paused | completed | failed | awaiting_approval
    current_stage: str | None
    source_slice_version: str | None
    mapping_snapshot_version: str | None
    lookup_snapshot_version: str | None
    codegen_artifact_id: str | None
    knowledge_freeze_version: str | None
    started_at: datetime | None
    last_checkpoint_at: datetime | None
    created_at: datetime

class RunCheckpointResponse(BaseModel):
    checkpoint_id: str
    run_id: str
    stage: str
    last_completed_row: int | None
    approved_snapshots: dict
    pause_reason: str | None
    created_at: datetime
```

## Routes (`routes/runs.py`)

```
POST   /projects/{project_id}/runs                     — create run record (status=queued)
GET    /projects/{project_id}/runs                     — list runs for project
GET    /projects/{project_id}/runs/{run_id}            — get run detail
POST   /projects/{project_id}/runs/{run_id}/launch     — transition queued → running; start execution
POST   /projects/{project_id}/runs/{run_id}/pause      — transition running → paused (manual)
POST   /projects/{project_id}/runs/{run_id}/resume     — resume from last checkpoint
GET    /projects/{project_id}/runs/{run_id}/checkpoints — list checkpoints
```

All mutation routes require `central_team`. GET routes respect project-access rule.

## Execution engine (`execution/run_engine.py`)

The engine runs synchronously in the first slice (no background queue yet — launch
blocks until the run pauses, errors, or completes). Background queue is YAGNI for
this task.

### Outer loop

```python
def execute_run(run_id: str, db: Session, adapter: AIAdapter) -> None:
    run = db.get(RunRecord, run_id)
    # pin source_slice_version from latest approved SourceSlice
    # pin mapping_snapshot_version from latest approved MappingSnapshot
    # pin lookup_snapshot_version from latest approved LookupSnapshot
    # write pinned versions onto RunRecord
    _inner_loop(run, db, adapter)
```

### Inner loop

```python
def _inner_loop(run: RunRecord, db: Session, adapter: AIAdapter) -> None:
    rows = db.query(SourceSliceRow).filter_by(source_slice_id=...).order_by(row_index)
    mapping = db.get(MappingSnapshot, run.mapping_snapshot_version)
    lookup = db.get(LookupSnapshot, run.lookup_snapshot_version)

    for row in rows:
        values = _apply_mapping(row, mapping.field_bindings)
        try:
            values = _apply_lookup(values, lookup.value_map)
        except UnmappedValueError as e:
            _write_checkpoint(run, row.row_index, db)
            _raise_lookup_delta_cr(run, e, db)
            return   # pause; operator resolves CR and resumes
        _write_mapped_row(run, values, db)
        if row.row_index % CHECKPOINT_INTERVAL == 0:
            _write_checkpoint(run, row.row_index, db)
```

`CHECKPOINT_INTERVAL = 500` (configurable via `domain_config`).

### LookupDeltaCR

When `UnmappedValueError` is raised:
1. Write `RunCheckpoint` at current row.
2. Insert `ChangeRequest(type="LookupDeltaCR", payload={lookup_field, source_value, run_id})`.
3. Set `RunRecord.status = "awaiting_approval"`, `pause_reason = "LookupDeltaCR"`.
4. Return — run is paused. Resume is triggered via `POST .../resume` after operator
   adds the missing mapping and a new `LookupSnapshot` is approved.

### Resume

On resume, reload `LookupSnapshot` (latest approved version for the project),
update `run.lookup_snapshot_version`, restore from last checkpoint row index,
continue the inner loop from that offset.

## Error codes

| Code | Status | When |
|---|---|---|
| `run_not_found` | 404 | Run not found or not in this project |
| `run_not_launchable` | 409 | Run not in `queued` status |
| `run_not_resumable` | 409 | Run not in `paused` or `awaiting_approval` status |
| `missing_source_slice` | 409 | No approved SourceSlice for this contract |
| `missing_mapping_snapshot` | 409 | No approved MappingSnapshot |
| `missing_lookup_snapshot` | 409 | No approved LookupSnapshot |

## Acceptance criteria

- [ ] `POST /projects/{id}/runs` creates a run in `queued` status
- [ ] `POST .../launch` transitions to `running` and executes the inner loop
- [ ] Checkpoint is written every 500 rows
- [ ] Unmapped lookup value pauses the run and creates a `ChangeRequest`
- [ ] Resume restarts from the last checkpoint row (not row 0)
- [ ] All run state transitions are recorded in `AuditEvent`
- [ ] Full test suite passes against real SQLite test DB

## Notes

- No background task queue in this slice — execution is synchronous on the launch request
- The AI adapter (001s) is used in later stages (mapping, codegen) but not in the raw
  row-mapping inner loop — that is deterministic given approved snapshots
- `RunRecord.codegen_artifact_id` links to the `CodeGenerationArtifact` produced or consumed
  by the code gen stage; it may be null for runs that haven't reached that stage
