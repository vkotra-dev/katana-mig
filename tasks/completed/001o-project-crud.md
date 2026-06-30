# 001o-project-crud

**Plan:** `plans/2026-06-29-001o-project-crud.md`

## Domain

- [project.md](../docs/domain/project.md)
- [api.md](../docs/domain/api.md)
- [management.md](../docs/domain/management.md)
- [governance.md](../docs/domain/governance.md)

## Objective

Build the project lifecycle management backend as a complete vertical slice:
schemas, access guards, service layer, and routes for create, list, get, update,
and archive. Role and membership enforcement lives at the API layer only; service
functions contain pure business logic.

## Scope

- `ProjectStatus`, `ProjectResponse`, `ProjectCreateRequest`, `ProjectUpdateRequest` schemas
- `require_non_auditor` and `require_project_access` guards in `management/access.py`
- `get_project_initiation_user` dependency in `api/deps.py`
- `management/projects.py` service — create, list, get, update, archive
- `routes/projects.py` — wire deps to service; access guards called in route handlers
- Integration tests in `tests/test_project_crud_api.py`

## Schemas

`ProjectCreateRequest` accepts all initiation wizard fields written to `ProjectDefinition.domain_config`:

```python
class ProjectCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    goal: str | None = None
    stakeholder_email: str | None = None
    assignee_email: str | None = None
    lawful_basis: str | None = None
    # domain_config fields
    target_db_engine: Literal["mssql", "oracle", "postgresql", "mysql"] | None = None
    staging_schema: str | None = None
    dry_run: bool = False
    destination_schema_ddl: str | None = None
    environments: list[str] = Field(default_factory=list)
```

All `domain_config` fields are optional at create time — operators may submit them via
the wizard on creation or fill them in later via `PATCH /projects/{id}`.

`ProjectResponse` includes a `domain_config: dict | None` field exposing the full
stored config so the UI can round-trip it.

`ProjectUpdateRequest` accepts the same domain_config fields as `ProjectCreateRequest`
(all optional); update clones `ProjectDefinition` and writes the new values.

## Out of Scope

- Source contracts and intake (001q)
- Project CRUD UI (001p)
- Initial change request on project creation
- Portfolio operational fields (stage, days in stage, blocked indicator)

## Acceptance Criteria

- `POST /projects` — `central_team` or `project_stakeholder`; stakeholder auto-membered
- `POST /projects` stores all domain_config fields on `ProjectDefinition.domain_config`
- `GET /projects` — all authenticated; stakeholders see member projects only
- `GET /projects/{id}` — all authenticated; stakeholders blocked without membership
- `GET /projects/{id}` response includes `domain_config` with all stored fields
- `PATCH /projects/{id}` — `central_team` only; clones `ProjectDefinition`, never patches in place
- `PATCH /projects/{id}` with domain_config fields updates stored config on new definition
- `POST /projects/{id}/archive` — `central_team` only; sets `archived_at` and `status="archived"`
- `read_only_auditor` is rejected on all mutation routes
- Archived projects excluded from list by default; included with `?include_archived=true`

## Test Expectations

- Create with full domain_config → `GET /projects/{id}` returns matching `domain_config`
- Create with no domain_config fields → `domain_config` is null or empty in response
- `destination_schema_ddl` is stored verbatim (no parsing in this task)
- `environments` list is preserved in order
- List returns only member projects for stakeholder callers
- Get returns `403` for stakeholder without membership
- Update returns new definition with changed fields; old definition row preserved
- Update on archived project returns `409 project_archived`
- Archive sets `archived_at`; second archive returns `409 project_already_archived`
- All mutation routes return `403 forbidden` for `read_only_auditor`
- Create sets `status="active"` and records audit event
