# Plan: 001bt — Project Copy

- **Task Link:** [tasks/001bt-project-copy-prompt-config.md](../tasks/001bt-project-copy-prompt-config.md)
- **Domain Link:** [docs/domain/project.md](../docs/domain/project.md)

## Current State

No project copy operation exists. `management/projects.py` has `create_project`, `update_project`, and `archive_project` but no `copy_project`. The project list page has a "New Project" button that navigates to a blank creation form.

`ProjectMembership` only holds `project_stakeholder` entries — `central_team` users have global project access by role and are never in the membership table.

## Objective

Single `POST /projects/{id}/copy` endpoint that atomically creates a new project pre-loaded with all configuration from the source project, with feeds in the empty upload-required state. Frontend replaces the "New Project" button with a dropdown and a two-step copy modal.

## Blast Radius

| Layer | Files |
|---|---|
| API schema | `engine/src/migrations_engine/api/schemas.py` |
| Management | `engine/src/migrations_engine/management/projects.py` |
| Route | `engine/src/migrations_engine/routes/projects.py` |
| Frontend API client | `web/lib/projects-api.ts` |
| Project list page | `web/app/projects/page.tsx` |

## File Changes

### 1. API Schema — `engine/src/migrations_engine/api/schemas.py`

```python
class ProjectCopyRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    stakeholder_user_ids: list[str] = Field(default_factory=list)
```

### 2. Management — `engine/src/migrations_engine/management/projects.py`

Add `copy_project` after `archive_project`:

```python
def copy_project(
    db: Session,
    *,
    actor: User,
    source_project_id: str,
    body: ProjectCopyRequest,
) -> ProjectResponse:
    source_registry, source_definition = _get_project_rows(db, source_project_id)

    if source_registry.status == "archived":
        raise AuthApiError("project_archived", "Cannot copy an archived project.", 422)

    new_project_id = new_id()
    new_definition_id = new_id()

    new_definition = ProjectDefinition(
        definition_id=new_definition_id,
        project_id=new_project_id,
        name=body.name,
        goal=source_definition.goal,
        repos=source_definition.repos,
        workspace=source_definition.workspace,
        project_resources=source_definition.project_resources,
        execution_environments=source_definition.execution_environments,
        model_policy=source_definition.model_policy,
        canonical_terms=source_definition.canonical_terms,
        constraints=source_definition.constraints,
        unresolved_questions=source_definition.unresolved_questions,
        assumptions=source_definition.assumptions,
        domain_config=source_definition.domain_config,
        status="active",
    )
    db.add(new_definition)

    new_registry = ProjectRegistry(
        project_id=new_project_id,
        name=body.name,
        definition_id=new_definition_id,
        lexicon_scope=source_registry.lexicon_scope,
        status="active",
    )
    db.add(new_registry)

    # Copy feeds (no slices)
    source_feeds = db.scalars(
        select(Feed).where(Feed.project_id == source_project_id)
    ).all()
    for feed in source_feeds:
        db.add(Feed(
            project_id=new_project_id,
            source_type=feed.source_type,
            source_contract_version=feed.source_contract_version,
            access_reference=feed.access_reference,
            selection_information=feed.selection_information,
            layout_information=feed.layout_information,
            destination_object_references=feed.destination_object_references,
            sample_policy=feed.sample_policy,
            source_details=feed.source_details,
            copybook_text=feed.copybook_text,
            mapping_hints=feed.mapping_hints,
            status="active",
        ))

    # Assign stakeholders (blank by default — source stakeholders are NOT copied)
    for user_id in body.stakeholder_user_ids:
        user = db.get(User, user_id)
        if user is None:
            raise AuthApiError("user_not_found", f"User {user_id} not found.", 404)
        db.add(ProjectMembership(
            project_id=new_project_id,
            user_id=user_id,
            role=PROJECT_STAKEHOLDER_ROLE,
        ))

    db.commit()
    return _project_response(db, new_project_id, actor)
```

> `_get_project_rows`, `_project_response`, `PROJECT_STAKEHOLDER_ROLE`, `Feed`, `ProjectDefinition`, `ProjectRegistry`, `ProjectMembership` are all already imported in `projects.py`.

### 3. Route — `engine/src/migrations_engine/routes/projects.py`

```python
@router.post("/{project_id}/copy", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
def post_project_copy(
    project_id: str,
    body: ProjectCopyRequest,
    actor: User = Depends(get_central_team_user),
    db: Session = Depends(get_db),
) -> ProjectResponse:
    return copy_project(db, actor=actor, source_project_id=project_id, body=body)
```

Add `ProjectCopyRequest` to existing imports from `..api.schemas` and `copy_project` to imports from `..management.projects`.

### 4. Frontend API Client — `web/lib/projects-api.ts`

Add interface and function:

```ts
export interface ProjectCopyInput {
  name: string;
  stakeholderUserIds: string[];
}

export async function copyProject(
  token: string,
  sourceProjectId: string,
  input: ProjectCopyInput,
): Promise<ProjectRecord> {
  const response = await requestJson<Parameters<typeof mapProjectRecord>[0]>(
    `/projects/${sourceProjectId}/copy`,
    {
      method: "POST",
      token,
      body: JSON.stringify({
        name: input.name,
        stakeholder_user_ids: input.stakeholderUserIds,
      }),
    },
  );
  return mapProjectRecord(response);
}
```

### 5. Project List Page — `web/app/projects/page.tsx`

**Step 1 — Replace "New Project" button with a dropdown button**

```tsx
{/* Dropdown trigger */}
<div className="relative">
  <button
    onClick={() => setDropdownOpen((o) => !o)}
    className="inline-flex items-center gap-1.5 rounded-lg bg-indigo-600 px-3 py-2 text-sm font-semibold text-white hover:bg-indigo-700"
  >
    New Project
    <ChevronDownIcon className="h-4 w-4" />
  </button>
  {dropdownOpen && (
    <div className="absolute right-0 mt-1 w-44 rounded-lg border border-outline-variant bg-white shadow-lg z-10">
      <button
        onClick={() => { setDropdownOpen(false); router.push("/projects/new"); }}
        className="block w-full px-4 py-2 text-left text-sm text-slate-700 hover:bg-slate-50"
      >
        New Project
      </button>
      <button
        onClick={() => { setDropdownOpen(false); setCopyModalStep(1); }}
        className="block w-full px-4 py-2 text-left text-sm text-slate-700 hover:bg-slate-50"
      >
        Copy from…
      </button>
    </div>
  )}
</div>
```

State additions:
```ts
const [dropdownOpen, setDropdownOpen] = useState(false);
const [copyModalStep, setCopyModalStep] = useState<0 | 1 | 2>(0); // 0 = closed
const [copySourceProject, setCopySourceProject] = useState<ProjectRecord | null>(null);
const [copyName, setCopyName] = useState("");
const [copySearch, setCopySearch] = useState("");
const [copySubmitting, setCopySubmitting] = useState(false);
```

**Step 2 — Copy modal**

```tsx
{copyModalStep > 0 && (
  <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
    <div className="w-full max-w-md rounded-2xl bg-white p-6 shadow-xl space-y-4">

      {copyModalStep === 1 && (
        <>
          <h2 className="text-base font-bold text-slate-900">Copy from project</h2>
          <input
            type="search"
            placeholder="Search projects…"
            value={copySearch}
            onChange={(e) => setCopySearch(e.target.value)}
            className="w-full rounded-lg border px-3 py-2 text-sm"
          />
          <ul className="max-h-60 overflow-y-auto divide-y divide-outline-variant">
            {projects
              .filter(
                (p) =>
                  p.status !== "archived" &&
                  p.name.toLowerCase().includes(copySearch.toLowerCase()),
              )
              .map((p) => (
                <li key={p.projectId}>
                  <button
                    onClick={() => {
                      setCopySourceProject(p);
                      setCopyName(`Copy of ${p.name}`);
                      setCopyModalStep(2);
                    }}
                    className="w-full px-3 py-2.5 text-left text-sm text-slate-700 hover:bg-slate-50"
                  >
                    {p.name}
                  </button>
                </li>
              ))}
          </ul>
          <button
            onClick={() => setCopyModalStep(0)}
            className="text-sm text-slate-500 hover:underline"
          >
            Cancel
          </button>
        </>
      )}

      {copyModalStep === 2 && copySourceProject && (
        <>
          <h2 className="text-base font-bold text-slate-900">
            Copy "{copySourceProject.name}"
          </h2>
          <div>
            <label className="text-xs font-medium text-slate-600">New project name</label>
            <input
              type="text"
              value={copyName}
              onChange={(e) => setCopyName(e.target.value)}
              className="mt-1 w-full rounded-lg border px-3 py-2 text-sm"
            />
          </div>
          <p className="text-xs text-slate-500">
            Stakeholders are not carried over — assign them after the project is created.
          </p>
          <div className="flex justify-end gap-2">
            <button
              onClick={() => setCopyModalStep(1)}
              className="rounded-lg border px-3 py-2 text-sm text-slate-600 hover:bg-slate-50"
            >
              Back
            </button>
            <button
              disabled={!copyName.trim() || copySubmitting}
              onClick={handleCopyProject}
              className="rounded-lg bg-indigo-600 px-3 py-2 text-sm font-semibold text-white disabled:opacity-40 hover:bg-indigo-700"
            >
              {copySubmitting ? "Copying…" : "Copy project"}
            </button>
          </div>
        </>
      )}

    </div>
  </div>
)}
```

**Step 3 — `handleCopyProject` handler**

```ts
async function handleCopyProject() {
  if (!copySourceProject || !copyName.trim() || !session?.accessToken) return;
  setCopySubmitting(true);
  try {
    const newProject = await copyProject(session.accessToken, copySourceProject.projectId, {
      name: copyName.trim(),
      stakeholderUserIds: [],
    });
    setCopyModalStep(0);
    router.push(`/projects/${newProject.projectId}`);
  } catch {
    setError("Failed to copy project.");
    setCopySubmitting(false);
  }
}
```

Add `copyProject` to imports from `@/lib/projects-api`.

## Pitfalls

- Close the dropdown when clicking outside — add a `useEffect` with a `mousedown` listener on `document`, or use a `blur` / `focusout` approach. Simplest: wrap the dropdown in a `<div onBlur>` with `tabIndex={-1}`.
- `_project_response` fetches the latest run summaries as part of building the response — since the new project has no runs, this is a no-op and safe.
- `feed.label` is not a column on `Feed` — check `FeedResponse.label` mapping in `schemas.py` to confirm where the label comes from (it may be in `source_details` or `selection_information`). Copy the same source field, not a derived label.
- The step-2 modal notes "Stakeholders are not carried over." If the product evolves to pre-populate them, the `stakeholder_user_ids` field on `ProjectCopyRequest` already supports it — no schema change needed.
- Dismiss the dropdown on `Escape` key and on outside click for good UX.

## Tests

- Backend: integration test on `POST /projects/{id}/copy` — assert new project has same constraints and feed count, feeds have no slices, mapping_hints match source, source stakeholders not copied.
- Frontend: no automated tests for the modal flow; manual verification only.

## Verification

1. Click the "New Project" dropdown → two options appear: "New Project" and "Copy from…"
2. "New Project" → existing creation flow unchanged
3. "Copy from…" → step 1 modal shows active projects, search filters correctly
4. Select a source project → step 2 shows pre-filled name, operator note, confirm button
5. Confirm → new project created, redirect lands on new project detail page
6. New project has all config (constraints, feed definitions with mapping_hints, destination DDL)
7. All feeds show "No slices uploaded yet" — no slices copied
8. Source project's stakeholders are NOT on the new project

## Commit

- `feat(001bt): add project copy with config and mapping hints carry-forward`
