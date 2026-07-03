# Per-Project Model Policy Overrides Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the freeform `model_policy` JSON blob with a typed `ModelPolicy` Pydantic model, add a `resolve_model` helper that prefers project overrides over the global config, thread it through all AI adapter call sites, and expose the fields in the project edit form.

**Architecture:** `ModelPolicy` mirrors the field names from `MigrationModelConfig` and `PlatformModelConfig` but makes every field optional (null = use global). A `resolve_model(task, policy, config)` pure function in `ai/config.py` centralises fallback logic. AI adapters receive the resolved model name rather than reading global config directly. The `model_policy` JSON column is unchanged — Pydantic serialises the model cleanly into it.

**Tech Stack:** Pydantic v2, Python, FastAPI, Next.js / TypeScript, Vitest

## Global Constraints

- `model_policy` column type stays JSON — no Alembic migration needed
- `resolve_model` must be a pure function (no side effects, no global state)
- Null field in `ModelPolicy` always falls back to global — never to empty string
- The edit form sends only explicitly set fields; unset fields are omitted from the payload

---

## File Changes

| Action | Path |
|--------|------|
| Modify | `engine/src/migrations_engine/api/schemas.py` |
| Modify | `engine/src/migrations_engine/ai/config.py` |
| Modify | `engine/src/migrations_engine/ai/openai_adapter.py` |
| Modify | `engine/src/migrations_engine/ai/anthropic_adapter.py` |
| Modify | `engine/tests/test_project_crud_api.py` |
| Create | `engine/tests/test_model_policy.py` |
| Modify | `web/lib/projects-api.ts` |
| Modify | `web/components/projects/ProjectEditForm.tsx` |
| Modify | `web/components/projects/__tests__/ProjectEditForm.test.tsx` |

---

### Task 1: Define ModelPolicy and resolve_model

**Files:**
- Modify: `engine/src/migrations_engine/api/schemas.py`
- Modify: `engine/src/migrations_engine/ai/config.py`
- Create: `engine/tests/test_model_policy.py`

**Interfaces:**
- Produces:
  ```python
  class ModelPolicy(BaseModel):
      pii_review: str | None = None
      field_mapping: str | None = None
      lookup_mapping: str | None = None
      script_generation: str | None = None
      script_correction: str | None = None
      schema_dependency: str | None = None
      impact_analysis: str | None = None
      feed_analysis: str | None = None
      planning: str | None = None
      review: str | None = None
      implementation: str | None = None

  def resolve_model(task: str, policy: ModelPolicy | None, config: AIConfig) -> str
  ```

- [ ] **Step 1: Write the failing tests**

Create `engine/tests/test_model_policy.py`:

```python
import pytest
from migrations_engine.api.schemas import ModelPolicy
from migrations_engine.ai.config import AIConfig, MigrationModelConfig, PlatformModelConfig, ProviderConfig, resolve_model

_GLOBAL = AIConfig(
    models=PlatformModelConfig(planning="global-plan", review="global-review", implementation="global-impl"),
    migration_models=MigrationModelConfig(
        pii_review="global-pii",
        field_mapping="global-fm",
        lookup_mapping="global-lm",
        script_generation="global-sg",
        script_correction="global-sc",
        schema_dependency="global-sd",
        impact_analysis="global-ia",
        feed_analysis="global-fa",
    ),
    providers=ProviderConfig(anthropic_api_key_env="ANTHROPIC_API_KEY", openai_api_key_env="OPENAI_API_KEY"),
)


def test_resolve_uses_global_when_policy_is_none():
    assert resolve_model("field_mapping", None, _GLOBAL) == "global-fm"


def test_resolve_uses_global_when_field_is_none():
    policy = ModelPolicy(field_mapping=None)
    assert resolve_model("field_mapping", policy, _GLOBAL) == "global-fm"


def test_resolve_uses_project_override():
    policy = ModelPolicy(field_mapping="project-fm")
    assert resolve_model("field_mapping", policy, _GLOBAL) == "project-fm"


def test_resolve_platform_task():
    assert resolve_model("planning", None, _GLOBAL) == "global-plan"
    policy = ModelPolicy(planning="project-plan")
    assert resolve_model("planning", policy, _GLOBAL) == "project-plan"


def test_resolve_unknown_task_raises():
    with pytest.raises(ValueError, match="unknown model task"):
        resolve_model("nonexistent", None, _GLOBAL)
```

- [ ] **Step 2: Run the tests and confirm they fail**

Run: `cd engine && python -m pytest tests/test_model_policy.py -v`
Expected: `ModelPolicy` not found; `resolve_model` not found.

- [ ] **Step 3: Add ModelPolicy to schemas**

In `engine/src/migrations_engine/api/schemas.py`, after `SamplePolicy`:

```python
class ModelPolicy(BaseModel):
    pii_review: str | None = None
    field_mapping: str | None = None
    lookup_mapping: str | None = None
    script_generation: str | None = None
    script_correction: str | None = None
    schema_dependency: str | None = None
    impact_analysis: str | None = None
    feed_analysis: str | None = None
    planning: str | None = None
    review: str | None = None
    implementation: str | None = None
```

Update `ProjectResponse`, `ProjectCreateRequest`, `ProjectUpdateRequest`:

```python
# Replace:
model_policy: dict[str, Any] | None
model_policy: dict[str, Any] | None = None

# With:
model_policy: ModelPolicy | None
model_policy: ModelPolicy | None = None
```

- [ ] **Step 4: Add resolve_model to ai/config.py**

In `engine/src/migrations_engine/ai/config.py`, add after `get_ai_config`:

```python
from ..api.schemas import ModelPolicy


_MIGRATION_TASKS = {
    "pii_review", "field_mapping", "lookup_mapping", "script_generation",
    "script_correction", "schema_dependency", "impact_analysis", "feed_analysis",
}
_PLATFORM_TASKS = {"planning", "review", "implementation"}


def resolve_model(task: str, policy: "ModelPolicy | None", config: AIConfig) -> str:
    if task in _MIGRATION_TASKS:
        global_value = getattr(config.migration_models, task)
    elif task in _PLATFORM_TASKS:
        global_value = getattr(config.models, task)
    else:
        raise ValueError(f"unknown model task: {task!r}")

    if policy is not None:
        override = getattr(policy, task, None)
        if override:
            return override

    return global_value
```

- [ ] **Step 5: Re-run the tests and confirm they pass**

Run: `cd engine && python -m pytest tests/test_model_policy.py -v`
Expected: all 5 tests pass.

- [ ] **Step 6: Commit**

```bash
git add engine/src/migrations_engine/api/schemas.py \
        engine/src/migrations_engine/ai/config.py \
        engine/tests/test_model_policy.py
git commit -m "feat(001az): add ModelPolicy schema and resolve_model helper"
```

---

### Task 2: Thread resolve_model through AI adapter call sites

**Files:**
- Modify: `engine/src/migrations_engine/ai/openai_adapter.py`
- Modify: `engine/src/migrations_engine/ai/anthropic_adapter.py`

**Interfaces:**
- Consumes: `resolve_model(task, policy, config)` from Task 1
- Produces: adapter methods accept `model_policy: ModelPolicy | None = None` and resolve the model name via `resolve_model` before calling the provider

- [ ] **Step 1: Read both adapter files**

Read `engine/src/migrations_engine/ai/openai_adapter.py` and `engine/src/migrations_engine/ai/anthropic_adapter.py` to find every place that reads a model name directly from `AIConfig` (e.g. `config.migration_models.field_mapping`).

- [ ] **Step 2: Write the failing tests**

In `engine/tests/test_model_policy.py`, add integration tests verifying adapters use the project override:

```python
from unittest.mock import MagicMock, patch
from migrations_engine.ai.anthropic_adapter import AnthropicAdapter
from migrations_engine.api.schemas import ModelPolicy


def test_anthropic_adapter_uses_project_model_override():
    policy = ModelPolicy(field_mapping="claude-opus-4-8")
    adapter = AnthropicAdapter(api_key="test", config=_GLOBAL, model_policy=policy)
    # The adapter should resolve "field_mapping" to "claude-opus-4-8"
    assert adapter.resolved_model("field_mapping") == "claude-opus-4-8"


def test_anthropic_adapter_falls_back_to_global():
    adapter = AnthropicAdapter(api_key="test", config=_GLOBAL, model_policy=None)
    assert adapter.resolved_model("field_mapping") == "global-fm"
```

- [ ] **Step 3: Update adapters to accept and use model_policy**

In each adapter's `__init__`, add `model_policy: ModelPolicy | None = None` and store it. Add a `resolved_model(task: str) -> str` method that calls `resolve_model(task, self._model_policy, self._config)`. Replace every direct `self._config.migration_models.<task>` or `self._config.models.<task>` read with `self.resolved_model("<task>")`.

- [ ] **Step 4: Re-run the tests and confirm they pass**

Run: `cd engine && python -m pytest tests/test_model_policy.py -v`
Expected: all tests pass including the new adapter tests.

- [ ] **Step 5: Commit**

```bash
git add engine/src/migrations_engine/ai/openai_adapter.py \
        engine/src/migrations_engine/ai/anthropic_adapter.py \
        engine/tests/test_model_policy.py
git commit -m "feat(001az): thread resolve_model through ai adapter call sites"
```

---

### Task 3: Model Policy section in the project edit form

**Files:**
- Modify: `web/lib/projects-api.ts`
- Modify: `web/components/projects/ProjectEditForm.tsx`
- Modify: `web/components/projects/__tests__/ProjectEditForm.test.tsx`

**Interfaces:**
- Consumes: `ModelPolicy` type from Task 1 (via API response)
- Produces: "Model Policy" section in the edit form with 11 text inputs, 3-column grid, empty = use global default

- [ ] **Step 1: Write the failing tests**

In `web/components/projects/__tests__/ProjectEditForm.test.tsx`:

```tsx
it("renders the Model Policy section with task inputs", () => {
  render(<ProjectEditForm project={project} onSubmit={vi.fn()} />);
  expect(screen.getByText("Model Policy")).toBeInTheDocument();
  expect(screen.getByRole("textbox", { name: "Field mapping model" })).toBeInTheDocument();
  expect(screen.getByRole("textbox", { name: "Script generation model" })).toBeInTheDocument();
});

it("includes modelPolicy overrides in submit payload", async () => {
  const onSubmit = vi.fn().mockResolvedValue(undefined);
  render(<ProjectEditForm project={project} onSubmit={onSubmit} />);

  fireEvent.change(screen.getByRole("textbox", { name: "Field mapping model" }), {
    target: { value: "claude-opus-4-8" },
  });
  fireEvent.submit(screen.getByRole("button", { name: "Save changes" }).closest("form") as HTMLFormElement);

  await waitFor(() =>
    expect(onSubmit).toHaveBeenCalledWith(
      expect.objectContaining({
        modelPolicy: expect.objectContaining({ fieldMapping: "claude-opus-4-8" }),
      })
    )
  );
});
```

- [ ] **Step 2: Run the tests and confirm they fail**

Run: `cd web && npm test -- components/projects/__tests__/ProjectEditForm.test.tsx`
Expected: Model Policy section not present.

- [ ] **Step 3: Update frontend types**

In `web/lib/projects-api.ts`, add:

```ts
export interface ModelPolicy {
  piiReview?: string | null;
  fieldMapping?: string | null;
  lookupMapping?: string | null;
  scriptGeneration?: string | null;
  scriptCorrection?: string | null;
  schemaDependency?: string | null;
  impactAnalysis?: string | null;
  feedAnalysis?: string | null;
  planning?: string | null;
  review?: string | null;
  implementation?: string | null;
}
```

Update `ProjectRecord.modelPolicy` and `ProjectCreateInput.modelPolicy` to use `ModelPolicy | null` instead of `Record<string, unknown> | null`.

Update `mapProjectRecord` to map `model_policy` snake_case fields to camelCase. Update `toProjectPayload` to convert `modelPolicy` back to snake_case.

- [ ] **Step 4: Add Model Policy section to ProjectEditForm**

Add state for each policy field, initialised from `project.modelPolicy`. Add a section after the Sample Policy section:

```tsx
{/* Model Policy section divider */}
<div className="col-span-3 border-t border-outline-variant pt-4">
  <h3 className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">
    Model Policy
  </h3>
  <p className="mt-1 text-xs text-slate-400">
    Override the AI model used for specific tasks on this project. Leave blank to use the global default.
  </p>
</div>

{/* Migration task overrides — 3 per row */}
<div className="space-y-2">
  <label ...>Field mapping model</label>
  <input aria-label="Field mapping model" type="text" placeholder="Global default" value={mpFieldMapping} onChange={...} />
</div>
<div className="space-y-2">
  <label ...>Script generation model</label>
  <input aria-label="Script generation model" type="text" placeholder="Global default" value={mpScriptGeneration} onChange={...} />
</div>
<div className="space-y-2">
  <label ...>Script correction model</label>
  <input aria-label="Script correction model" type="text" placeholder="Global default" value={mpScriptCorrection} onChange={...} />
</div>
<div className="space-y-2">
  <label ...>Lookup mapping model</label>
  <input aria-label="Lookup mapping model" type="text" placeholder="Global default" value={mpLookupMapping} onChange={...} />
</div>
<div className="space-y-2">
  <label ...>PII review model</label>
  <input aria-label="PII review model" type="text" placeholder="Global default" value={mpPiiReview} onChange={...} />
</div>
<div className="space-y-2">
  <label ...>Impact analysis model</label>
  <input aria-label="Impact analysis model" type="text" placeholder="Global default" value={mpImpactAnalysis} onChange={...} />
</div>
<div className="space-y-2">
  <label ...>Schema dependency model</label>
  <input aria-label="Schema dependency model" type="text" placeholder="Global default" value={mpSchemaDependency} onChange={...} />
</div>
<div className="space-y-2">
  <label ...>Feed analysis model</label>
  <input aria-label="Feed analysis model" type="text" placeholder="Global default" value={mpFeedAnalysis} onChange={...} />
</div>
<div className="space-y-2">
  <label ...>Planning model</label>
  <input aria-label="Planning model" type="text" placeholder="Global default" value={mpPlanning} onChange={...} />
</div>
<div className="space-y-2">
  <label ...>Review model</label>
  <input aria-label="Review model" type="text" placeholder="Global default" value={mpReview} onChange={...} />
</div>
<div className="space-y-2">
  <label ...>Implementation model</label>
  <input aria-label="Implementation model" type="text" placeholder="Global default" value={mpImplementation} onChange={...} />
</div>
```

In the submit payload, build `modelPolicy` by omitting null/empty fields:

```ts
modelPolicy: [
  ["fieldMapping", mpFieldMapping],
  ["scriptGeneration", mpScriptGeneration],
  ["scriptCorrection", mpScriptCorrection],
  ["lookupMapping", mpLookupMapping],
  ["piiReview", mpPiiReview],
  ["impactAnalysis", mpImpactAnalysis],
  ["schemaDependency", mpSchemaDependency],
  ["feedAnalysis", mpFeedAnalysis],
  ["planning", mpPlanning],
  ["review", mpReview],
  ["implementation", mpImplementation],
].reduce<ModelPolicy>((acc, [key, val]) => {
  if (val.trim()) acc[key as keyof ModelPolicy] = val.trim();
  return acc;
}, {}) || null,
```

- [ ] **Step 5: Re-run the tests and confirm they pass**

Run: `cd web && npm test -- components/projects/__tests__/ProjectEditForm.test.tsx`
Expected: all tests pass including new Model Policy tests.

- [ ] **Step 6: Commit**

```bash
git add web/lib/projects-api.ts web/components/projects/ProjectEditForm.tsx \
        web/components/projects/__tests__/ProjectEditForm.test.tsx
git commit -m "feat(001az): add model policy section to project edit form"
```

---

## Verification

1. Policy schema tests: `cd engine && python -m pytest tests/test_model_policy.py -v`
2. Full engine suite: `cd engine && python -m pytest -v`
3. Frontend suite: `cd web && npm test`
4. Browser smoke check: open project edit, fill a Model Policy field, save, reload — override persists; clear field, save — falls back to global

## Commit Summary

```
feat(001az): add ModelPolicy schema and resolve_model helper
feat(001az): thread resolve_model through ai adapter call sites
feat(001az): add model policy section to project edit form
```
