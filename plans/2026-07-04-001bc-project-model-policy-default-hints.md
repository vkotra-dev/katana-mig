# Project Model Policy Default Hints Implementation Plan

Task: [tasks/001bc-project-model-policy-default-hints.md](/Users/vjkotra/projects/katana/tasks/001bc-project-model-policy-default-hints.md)
Domain: [docs/domain/ui.md](/Users/vjkotra/projects/katana/docs/domain/ui.md)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expose the live `engine.yaml` model defaults to the UI and show the
effective model name plus source context on the project edit and detail
screens.

**Architecture:** Add a tiny authenticated config endpoint that reads the
resolved AI config already used by the adapter layer and returns only the model
names. Keep the frontend logic separate from project CRUD by introducing a
small shared model-policy catalog plus a dedicated defaults client helper. The
edit screen uses the helper to render the live global default beneath each
override input, while the detail screen renders a read-only model-policy block
with label, effective value, and source. The project save payload stays
unchanged.

**Tech Stack:** FastAPI, Pydantic, Next.js App Router, React, Vitest, Markdown
domain docs.

## Global Constraints

- AI-backed stages resolve their model assignments from `engine/config/engine.yaml`
  through the `migrations_engine.ai` adapter layer
- Model slots live in YAML, not in the Pydantic `Settings` class
- Provider API keys are referenced by environment-variable name in YAML and
  read at call time by the adapter implementation
- Missing model-slot environment substitutions fail closed at load time
- The project update payload shape must not change
- The UI must not hardcode model IDs

## Current State

- `ProjectEditForm` already renders the model policy override inputs, but the
  helper text is generic and does not show the live global model name.
- `ProjectDetailView` does not render any model policy section, so the read-only
  screen gives no clue which model is active for each task slot.
- The frontend has no helper for the resolved AI defaults, and the backend has
  no route that exposes them.
- `docs/domain/project.md`, `docs/domain/ui.md`, and `docs/domain/api.md` only
  describe the current override semantics in broad terms.

## Objective

Add an authenticated AI-config endpoint, wire the project edit/detail pages to
consume it, and render the default model names and source labels in the same
project surfaces operators already use.

## Out of Scope

- Changing model-selection rules in the adapter layer
- Adding provider secrets or env variable names to the client
- Altering project create/update payloads
- Changing the existing project navigation or shell

## Blast Radius

- `engine/src/migrations_engine/api/schemas.py`
- `engine/src/migrations_engine/routes/config.py` (new)
- `engine/src/migrations_engine/app.py`
- `engine/tests/test_config_api.py` (new)
- `web/lib/ai-model-defaults-api.ts` (new)
- `web/lib/ai-model-defaults-api.test.ts` (new)
- `web/components/projects/modelPolicyCatalog.ts` (new)
- `web/app/projects/[id]/edit/page.tsx`
- `web/app/projects/[id]/page.tsx`
- `web/components/projects/ProjectEditForm.tsx`
- `web/components/projects/ProjectDetailView.tsx`
- `web/components/projects/__tests__/ProjectEditForm.test.tsx`
- `web/components/projects/__tests__/ProjectDetailView.test.tsx`
- `web/app/projects/[id]/edit/page.test.tsx`
- `web/app/projects/[id]/page.test.tsx`
- `docs/domain/api.md`
- `docs/domain/project.md`
- `docs/domain/ui.md`

## File Changes

| Action | Path |
|--------|------|
| Create | `engine/src/migrations_engine/routes/config.py` |
| Modify | `engine/src/migrations_engine/api/schemas.py` |
| Modify | `engine/src/migrations_engine/app.py` |
| Create | `engine/tests/test_config_api.py` |
| Create | `web/lib/ai-model-defaults-api.ts` |
| Create | `web/lib/ai-model-defaults-api.test.ts` |
| Create | `web/components/projects/modelPolicyCatalog.ts` |
| Modify | `web/app/projects/[id]/edit/page.tsx` |
| Modify | `web/app/projects/[id]/page.tsx` |
| Modify | `web/components/projects/ProjectEditForm.tsx` |
| Modify | `web/components/projects/ProjectDetailView.tsx` |
| Modify | `web/components/projects/__tests__/ProjectEditForm.test.tsx` |
| Modify | `web/components/projects/__tests__/ProjectDetailView.test.tsx` |
| Modify | `web/app/projects/[id]/edit/page.test.tsx` |
| Modify | `web/app/projects/[id]/page.test.tsx` |
| Modify | `docs/domain/api.md` |
| Modify | `docs/domain/project.md` |
| Modify | `docs/domain/ui.md` |

## Tests

- `cd engine && PYTHONPATH=src pytest tests/test_config_api.py -q`
- `cd web && npm test -- lib/ai-model-defaults-api.test.ts components/projects/__tests__/ProjectEditForm.test.tsx components/projects/__tests__/ProjectDetailView.test.tsx 'app/projects/[id]/edit/page.test.tsx' 'app/projects/[id]/page.test.tsx'`

## Verification

- `rg -n "ai-model-defaults|model policy|engine.yaml|Global default" engine/src/migrations_engine web docs/domain`
- Confirm the edit screen still submits only the override payload
- Confirm the detail screen stays read-only and renders the effective model
  source for each slot

## Pitfalls

- Do not expose provider env names or API keys in the defaults response
- Keep the defaults fetch separate from project CRUD so a temporary config
  failure does not mutate project data
- Use one shared model-policy catalog for labels and ordering; do not duplicate
  the slot list in multiple components
- If the defaults endpoint is unavailable, render a non-destructive fallback in
  the UI rather than inventing model names

## Commit

- `feat(001bc): show global model defaults in project UI`

---

### Task 1: Add the authenticated AI defaults endpoint and client helper

**Files:**
- Create: `engine/src/migrations_engine/routes/config.py`
- Modify: `engine/src/migrations_engine/api/schemas.py`
- Modify: `engine/src/migrations_engine/app.py`
- Create: `engine/tests/test_config_api.py`
- Create: `web/lib/ai-model-defaults-api.ts`
- Create: `web/lib/ai-model-defaults-api.test.ts`
- Modify: `docs/domain/api.md`
- Modify: `docs/domain/project.md`

**Interfaces:**
- Consumes: `get_ai_config()` from `migrations_engine.ai.config`
- Produces: `GET /config/ai-model-defaults` plus `getAiModelDefaults(token)`
  on the client

- [ ] **Step 1: Write the failing backend and client tests**

Add a route test that proves the endpoint is auth-protected and returns the
resolved defaults without any provider config:

```python
from types import SimpleNamespace

from migrations_engine.routes import config as config_route_module

response = client.get("/config/ai-model-defaults")
assert response.status_code == 401

fake_config = SimpleNamespace(
    models=SimpleNamespace(
        planning="planning-model",
        review="review-model",
        implementation="implementation-model",
    ),
    migration_models=SimpleNamespace(
        pii_review="pii-model",
        field_mapping="field-model",
        lookup_mapping="lookup-model",
        script_generation="script-generation-model",
        script_correction="script-correction-model",
        schema_dependency="schema-dependency-model",
        impact_analysis="impact-model",
        feed_analysis="feed-analysis-model",
    ),
)
monkeypatch.setattr(config_route_module, "get_ai_config", lambda: fake_config)

response = client.get("/config/ai-model-defaults", headers={"Authorization": f"Bearer {token}"})
assert response.status_code == 200
assert response.json() == {
    "source": "engine.yaml",
    "platform_models": {
        "planning": "planning-model",
        "review": "review-model",
        "implementation": "implementation-model",
    },
    "migration_models": {
        "pii_review": "pii-model",
        "field_mapping": "field-model",
        "lookup_mapping": "lookup-model",
        "script_generation": "script-generation-model",
        "script_correction": "script-correction-model",
        "schema_dependency": "schema-dependency-model",
        "impact_analysis": "impact-model",
        "feed_analysis": "feed-analysis-model",
    },
}
```

Add a client test that asserts `getAiModelDefaults("token-1")` hits the new
route and maps the nested response into camelCase.

- [ ] **Step 2: Implement the endpoint and client helper**

Add a small route module that reads `get_ai_config()` and returns only the
resolved model names:

```python
@router.get("/ai-model-defaults", response_model=AIModelDefaultsResponse)
def get_ai_model_defaults(actor: User = Depends(get_current_user)) -> AIModelDefaultsResponse:
    config = get_ai_config()
    return AIModelDefaultsResponse(
        source="engine.yaml",
        platform_models=PlatformModelDefaults(
            planning=config.models.planning,
            review=config.models.review,
            implementation=config.models.implementation,
        ),
        migration_models=MigrationModelDefaults(
            pii_review=config.migration_models.pii_review,
            field_mapping=config.migration_models.field_mapping,
            lookup_mapping=config.migration_models.lookup_mapping,
            script_generation=config.migration_models.script_generation,
            script_correction=config.migration_models.script_correction,
            schema_dependency=config.migration_models.schema_dependency,
            impact_analysis=config.migration_models.impact_analysis,
            feed_analysis=config.migration_models.feed_analysis,
        ),
    )
```

Add `AIModelDefaultsResponse` schema types that contain only the model names and
the source label. Create `web/lib/ai-model-defaults-api.ts` with a typed fetch
helper that returns the same shape in camelCase.

Update `docs/domain/api.md` with a short `GET /config/ai-model-defaults`
section and update `docs/domain/project.md` so the model-policy section makes it
clear that project overrides fall back to the global `engine.yaml` values.

- [ ] **Step 3: Run the focused tests**

Run:

```bash
cd engine && PYTHONPATH=src pytest tests/test_config_api.py -q
cd web && npm test -- lib/ai-model-defaults-api.test.ts
```

Expected:

- the backend test proves the endpoint is authenticated and returns only model
  defaults
- the client test proves the new helper maps the nested response correctly

- [ ] **Step 4: Commit**

```bash
git add engine/src/migrations_engine/api/schemas.py \
  engine/src/migrations_engine/routes/config.py \
  engine/src/migrations_engine/app.py \
  engine/tests/test_config_api.py \
  web/lib/ai-model-defaults-api.ts \
  web/lib/ai-model-defaults-api.test.ts \
  docs/domain/api.md \
  docs/domain/project.md
git commit -m "feat(001bc): expose ai model defaults"
```

### Task 2: Show live defaults under the model override inputs in edit

**Files:**
- Create: `web/components/projects/modelPolicyCatalog.ts`
- Modify: `web/app/projects/[id]/edit/page.tsx`
- Modify: `web/components/projects/ProjectEditForm.tsx`
- Modify: `web/components/projects/__tests__/ProjectEditForm.test.tsx`
- Modify: `web/app/projects/[id]/edit/page.test.tsx`

**Interfaces:**
- Consumes: `getAiModelDefaults(token)` and a shared model-policy slot catalog
- Produces: helper text under each override input showing the current global
  default model name

- [ ] **Step 1: Write the failing edit-page and form tests**

Add a shared catalog file so the slot labels and order are defined once:

```ts
export const MODEL_POLICY_FIELDS = [
  { key: "fieldMapping", label: "Field mapping model" },
  { key: "scriptGeneration", label: "Script generation model" },
  { key: "scriptCorrection", label: "Script correction model" },
  { key: "lookupMapping", label: "Lookup mapping model" },
  { key: "piiReview", label: "PII review model" },
  { key: "impactAnalysis", label: "Impact analysis model" },
  { key: "schemaDependency", label: "Schema dependency model" },
  { key: "feedAnalysis", label: "Feed analysis model" },
  { key: "planning", label: "Planning model" },
  { key: "review", label: "Review model" },
  { key: "implementation", label: "Implementation model" },
] as const;
```

Update the edit-form test so it asserts each textbox still exists and now has a
helper line like:

```tsx
expect(screen.getByText("Global default: field-model")).toBeInTheDocument();
expect(screen.getByText("Global default: planning-model")).toBeInTheDocument();
```

Add an edit-page test that mocks `getAiModelDefaults` and verifies the page
passes the defaults into `ProjectEditForm`.

- [ ] **Step 2: Implement the defaults-aware edit flow**

Add a shared model-policy catalog and extend `ProjectEditForm` with a
`modelDefaults` prop. Render the current default name directly below each input
without changing the submit payload:

```tsx
<p className="text-xs text-slate-500">
  {defaultModel ? `Global default: ${defaultModel}` : "Global default unavailable"}
</p>
```

Fetch the defaults in `web/app/projects/[id]/edit/page.tsx` after the session is
available and pass them through to the form. Keep the project save path exactly
as it is today.

- [ ] **Step 3: Run the focused edit tests**

Run:

```bash
cd web && npm test -- components/projects/__tests__/ProjectEditForm.test.tsx 'app/projects/[id]/edit/page.test.tsx'
```

Expected:

- the model override fields still submit the same payload
- the helper text shows the live global default names

- [ ] **Step 4: Commit**

```bash
git add web/components/projects/modelPolicyCatalog.ts \
  'web/app/projects/[id]/edit/page.tsx' \
  web/components/projects/ProjectEditForm.tsx \
  web/components/projects/__tests__/ProjectEditForm.test.tsx \
  'web/app/projects/[id]/edit/page.test.tsx'
git commit -m "feat(001bc): show model defaults in project edit"
```

### Task 3: Render the effective model and source in project detail

**Files:**
- Modify: `web/app/projects/[id]/page.tsx`
- Modify: `web/components/projects/ProjectDetailView.tsx`
- Modify: `web/components/projects/__tests__/ProjectDetailView.test.tsx`
- Modify: `web/app/projects/[id]/page.test.tsx`
- Modify: `docs/domain/ui.md`

**Interfaces:**
- Consumes: the shared model-policy catalog and `getAiModelDefaults(token)`
- Produces: a read-only model-policy block that shows the effective model name
  and whether it came from a project override or from `engine.yaml`

- [ ] **Step 1: Write the failing detail-page and detail-view tests**

Update the detail-view test so it asserts the model-policy section is present
and that each slot shows the effective value plus source text:

```tsx
expect(screen.getByText("Model Policy")).toBeInTheDocument();
expect(screen.getByText("Field mapping model")).toBeInTheDocument();
expect(screen.getByText("field-model")).toBeInTheDocument();
expect(screen.getByText("planning-model")).toBeInTheDocument();
expect(screen.getByText("Source: project override")).toBeInTheDocument();
expect(screen.getByText("Source: engine.yaml")).toBeInTheDocument();
```

Add a detail-page test that mocks `getAiModelDefaults` and verifies the page
feeds the defaults into `ProjectDetailView`.

- [ ] **Step 2: Implement the read-only model-policy block**

Fetch the defaults in `web/app/projects/[id]/page.tsx` alongside the project
record, then pass them into `ProjectDetailView`. Render the model-policy cards
with a label, the effective model name, and a source line:

```tsx
<div className="space-y-1 rounded-xl border border-outline-variant bg-surface px-4 py-3">
  <div className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">
    {label}
  </div>
  <div className="text-sm text-slate-900">{effectiveModel}</div>
  <div className="text-xs text-slate-500">{sourceLabel}</div>
</div>
```

Use `project.modelPolicy?.[key] ?? defaults[key]` for the effective value so the
detail view shows the real runtime model, not just the override.

Update `docs/domain/ui.md` so the Project detail section mentions the model
policy block and the edit section explains that each override input shows the
current global default underneath it.

- [ ] **Step 3: Run the focused detail tests**

Run:

```bash
cd web && npm test -- components/projects/__tests__/ProjectDetailView.test.tsx 'app/projects/[id]/page.test.tsx'
```

Expected:

- the overview tab still renders
- the model-policy cards show the effective model and source

- [ ] **Step 4: Commit**

```bash
git add 'web/app/projects/[id]/page.tsx' \
  web/components/projects/ProjectDetailView.tsx \
  web/components/projects/__tests__/ProjectDetailView.test.tsx \
  'web/app/projects/[id]/page.test.tsx' \
  docs/domain/ui.md
git commit -m "feat(001bc): show model sources in project detail"
```
