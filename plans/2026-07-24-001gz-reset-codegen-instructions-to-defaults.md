Task: tasks/001gz-reset-codegen-instructions-to-defaults.md
Domain: docs/domain/api.md, docs/domain/project.md

## Current State

- `project_definition.codegen_instructions` stores the global codegen instructions text, saved per project.
- `render_coding_standards_template()` in `engine/src/migrations_engine/codegen/coding_standards.py` reads both `codegen_coding_standards.yaml` and `codegen_logging_standards.yaml` and merges them into one text blob with `$stg`/`$dest`/`$engineName` substitutions.
- On first load, the codegen page pre-populates the textarea from `getCodegenCodingStandardsTemplate()` which calls `render_coding_standards_template()`.
- The existing "Suggest Standards" button (in `web/app/projects/[id]/codegen/page.tsx`, line 567) calls `getCodegenCodingStandardsTemplate()` and only sets local textarea state — it does NOT save to the project.
- Users can edit the textarea and click "Save" which calls `saveCodegenInstructions()` (PATCH `/projects/{project_id}/codegen-instructions`) to persist their custom text.
- The codegen pipeline reads `project_definition.codegen_instructions` and injects it into `system_prompt.txt.j2` at the `GLOBAL CODING STANDARDS` section (line 60-63).
- There is no way to reset the saved value back to the YAML template defaults.

## Objective

Replace the "Suggest Standards" button with a "Reset to defaults" button that, when clicked with confirmation, calls a new backend endpoint to render the YAML template and overwrite the project's saved `codegen_instructions` with the merged template.

## Out of Scope

- Do NOT change the existing PATCH `codegen-instructions` endpoint (it handles normal save operations)
- Do NOT delete or modify the GET `codegen-coding-standards-template` endpoint (it may be used by other consumers)
- Do NOT add per-feed-level reset — only global project-level
- Do NOT change how the YAML files themselves are structured or read
- Do NOT modify the Jinja system_prompt.txt.j2 template

## Blast Radius

| File | Action | What changes |
|------|--------|-------------|
| `engine/src/migrations_engine/routes/projects.py` | modify | Add `reset_codegen_instructions` POST endpoint after existing `patch_codegen_instructions` |
| `web/lib/projects-api.ts` | modify | Add `resetCodegenInstructions()` function |
| `web/app/projects/[id]/codegen/page.tsx` | modify | Replace "Suggest Standards" with "Reset to defaults" button at bottom-left of textarea; update handler |
| `engine/tests/test_codegen_system_prompt.py` | modify | Add test for reset endpoint |
| `docs/domain/api.md` | modify | Document new POST endpoint |
| `tasks/TASK_INDEX.md` | modify | Add entry for 001gz (already done) |

## File Changes

### `engine/src/migrations_engine/routes/projects.py`

Add the new endpoint right after the existing `patch_codegen_instructions` endpoint (after line 149, before the GET template endpoint):

```python
@router.post("/{project_id}/codegen-instructions/reset", response_model=ProjectResponse)
def reset_codegen_instructions(
    project_id: str,
    actor: User = Depends(get_central_team_user),
    db: Session = Depends(get_db),
) -> ProjectResponse:
    require_project_access(db, user=actor, project_id=project_id)
    project = get_project(db, project_id=project_id)
    config = project.domain_config
    template = render_coding_standards_template(
        db_engine=config.target_db_engine if config else None,
        staging_schema=config.staging_schema if config else None,
        destination_schema=config.destination_schema if config else None,
    )
    return update_project(
        db,
        actor=actor,
        project_id=project_id,
        body=ProjectUpdateRequest(codegen_instructions=template),
    )
```

This follows the exact same pattern as `patch_codegen_instructions` (lines 136-149): require central_team, require project access, call `render_coding_standards_template()`, save via `update_project()`.

### `web/lib/projects-api.ts`

Add `resetCodegenInstructions()` function right after the existing `saveCodegenInstructions()` function (after line 564):

```typescript
export async function resetCodegenInstructions(
  token: string,
  projectId: string,
): Promise<ProjectRecord> {
  const data = await requestJson<Parameters<typeof mapProjectRecord>[0]>(
    `/projects/${projectId}/codegen-instructions/reset`,
    {
      method: "POST",
      token,
    },
  );
  return mapProjectRecord(data);
}
```

This calls POST to the new reset endpoint (no request body needed — the server renders the template server-side).

### `web/app/projects/[id]/codegen/page.tsx`

**1. Rename handler** (line 387):
```diff
-  const handleSuggestGlobalInstructions = async (): Promise<void> => {
+  const handleResetGlobalInstructions = async (): Promise<void> => {
     if (
       globalInstructions.trim() &&
```

**2. Replace the handler body** — the entire handler function (lines 387-402) becomes:

```typescript
  const handleResetGlobalInstructions = async (): Promise<void> => {
    if (!session || !routeParams) return;
    if (
      !window.confirm("This will overwrite your saved global instructions with the YAML template defaults. Are you sure?")
    ) {
      return;
    }

    setPageError(null);
    setStatusMessage(null);
    setActionLoading("reset");
    try {
      const updated = await resetCodegenInstructions(session.accessToken, routeParams.id);
      setProject(updated);
      setGlobalInstructions(updated.codegenInstructions ?? "");
      setStatusMessage("Global instructions reset to defaults.");
    } catch (error) {
      setPageError(error instanceof Error ? error.message : "Unable to reset global instructions.");
    } finally {
      setActionLoading(null);
    }
  };
```

Note: `actionLoading` is already declared as state (line 214). The reset button sets a loading indicator during the API call.

**3. Replace the button** (lines 563-571):
```diff
-                {(role === "central_team" || role === "admin") && (
-                  <button
-                    type="button"
-                    className="rounded-lg border border-outline-variant bg-surface px-3.5 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-50 hover:text-slate-900 transition-colors focus:outline-none focus:ring-2 focus:ring-primary/20"
-                    onClick={() => void handleSuggestGlobalInstructions()}
-                  >
-                    Suggest Standards
-                  </button>
-                )}
+                {(role === "central_team" || role === "admin") && (
+                  <button
+                    type="button"
+                    className="rounded-lg border border-amber-300 bg-amber-50 px-3.5 py-2 text-xs font-semibold text-amber-700 hover:bg-amber-100 hover:text-amber-900 transition-colors focus:outline-none focus:ring-2 focus:ring-amber-200"
+                    onClick={() => void handleResetGlobalInstructions()}
+                    disabled={actionLoading === "reset"}
+                  >
+                    {actionLoading === "reset" ? "Resetting..." : "Reset to defaults"}
+                  </button>
+                )}
```

**4. Add "Reset to defaults" button at bottom-left of textarea** — move from top-right section to the save button area. Replace the existing save button section (lines 582-593):

```diff
-                {(role === "central_team" || role === "admin") && (
-                  <div className="flex justify-end">
-                    <button
-                      className="rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-white hover:bg-primary-hover disabled:bg-slate-200 disabled:text-slate-400"
-                      onClick={handleSaveGlobalInstructions}
-                      disabled={saveLoading}
-                    >
-                      {saveLoading ? "Saving..." : "Save"}
-                    </button>
-                  </div>
-                )}
+                {(role === "central_team" || role === "admin") && (
+                  <div className="flex justify-between items-center">
+                    <button
+                      type="button"
+                      className="rounded-lg border border-amber-300 bg-amber-50 px-3 py-1.5 text-xs font-semibold text-amber-700 hover:bg-amber-100 hover:text-amber-900 transition-colors focus:outline-none focus:ring-2 focus:ring-amber-200"
+                      onClick={() => void handleResetGlobalInstructions()}
+                      disabled={actionLoading === "reset"}
+                    >
+                      {actionLoading === "reset" ? "Resetting..." : "Reset to defaults"}
+                    </button>
+                    <button
+                      className="rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-white hover:bg-primary-hover disabled:bg-slate-200 disabled:text-slate-400"
+                      onClick={handleSaveGlobalInstructions}
+                      disabled={saveLoading}
+                    >
+                      {saveLoading ? "Saving..." : "Save"}
+                    </button>
+                  </div>
+                )}
```

This moves the reset button to the bottom-left of the textarea (left side of the flex row), with the Save button on the right. The reset button uses amber styling to visually indicate it's a destructive action.

### `engine/tests/test_codegen_system_prompt.py`

Add a test right after `test_build_system_prompt_no_longer_appends_run_logging_requirements()` (after line 27):

```python
def test_reset_codegen_instructions_overwrites_with_yaml_template(monkeypatch: pytest.MonkeyPatch) -> None:
    """POST /projects/{id}/codegen-instructions/reset resets codegen_instructions to the YAML template."""
    from migrations_engine.routes.projects import reset_codegen_instructions

    project_definition = ProjectDefinition(
        definition_id="def-1",
        project_id="proj-1",
        name="Test",
        status="active",
        codegen_instructions="Custom text that should be replaced.",
    )

    config = MagicMock()
    config.target_db_engine = "postgresql"
    config.staging_schema = "staging"
    config.destination_schema = "destination"

    project_mock = MagicMock()
    project_mock.domain_config = config

    db_mock = MagicMock()
    db_mock.scalar.return_value = None

    updated_instructions: list[str] = []

    def mock_update_project(db, *, actor, project_id, body):
        updated_instructions.append(body.codegen_instructions)
        # Simulate returning the project with updated instructions
        project_mock.codegen_instructions = body.codegen_instructions
        return project_mock

    monkeypatch.setattr(
        "migrations_engine.routes.projects.get_project",
        lambda db, *, project_id: project_mock,
    )
    monkeypatch.setattr(
        "migrations_engine.routes.projects.update_project",
        mock_update_project,
    )

    # Create a mock user with CENTRAL_TEAM role
    mock_user = MagicMock()
    mock_user.role = "central_team"

    with patch("migrations_engine.routes.projects.require_project_access", return_value=None):
        result = reset_codegen_instructions(
            project_id="proj-1",
            actor=mock_user,
            db=db_mock,
        )

    assert result.codegen_instructions == "Custom text that should be replaced."
    assert len(updated_instructions) == 1
    # The saved value should be the rendered template, NOT the old custom text
    assert updated_instructions[0] != "Custom text that should be replaced."
    # The template should contain the coding standards header
    assert "Coding Standards and Guidelines" in updated_instructions[0]
    # The template should include logging standards (both YAMLs merged)
    assert "mig_upsert_log" in updated_instructions[0]
```

### `docs/domain/api.md`

After the existing `PATCH /projects/{project_id}/codegen-instructions` section (after line 1161), add:

```markdown
### `POST /projects/{project_id}/codegen-instructions/reset`

Reset project-wide codegen instructions to the YAML template defaults. Renders `codegen_coding_standards.yaml` + `codegen_logging_standards.yaml` via `render_coding_standards_template()` and saves the merged result. Requires `central_team`.

Response `200`: `ProjectResponse` with `codegen_instructions` set to the rendered template.

No request body.
```

## Tests

- New test in `engine/tests/test_codegen_system_prompt.py`: verifies the reset endpoint overwrites custom text with the rendered YAML template and that both coding standards and logging standards are present in the result.
- No frontend tests needed — the button is a simple action button with a confirm dialog; behavior is visually verified.

## Verification

```bash
# Backend: run the new test
.venv/bin/python -m pytest engine/tests/test_codegen_system_prompt.py -q

# Backend: full suite
.venv/bin/python -m pytest engine/tests -q

# Frontend: verify no type errors
cd web && npx tsc --noEmit 2>&1 | head -20
```

Expected after changes: all backend tests pass (no regression), no frontend type errors.

## Pitfalls

- The new POST endpoint must be placed BEFORE the GET template endpoint in the router file — FastAPI matches routes in definition order, and a less-specific route could shadow a more-specific one. The POST path `/codegen-instructions/reset` is distinct enough that it won't conflict, but placement matters for readability.
- The `actionLoading` state variable is already declared (line 214) as `useState<string | null>(null)`. Use a specific key like `"reset"` to distinguish from the feed-level `actionLoading` states.
- The reset endpoint uses `get_central_team_user` guard — same as the existing PATCH endpoint. Do not change the access model.
- Do NOT remove the existing GET `codegen-coding-standards-template` endpoint — the codegen page no longer calls it (it now calls the reset endpoint directly), but it may be used by other consumers.

## Commit

```
feat(codegen): add "Reset to defaults" button to overwrite codegen instructions with YAML template
```
