# Impact Review Backend Flow Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the backend impact-review flow for runs, including the `impact_analysis` AI slot, a read-only impact report endpoint, and an acknowledge endpoint that advances the run state.

**Architecture:** Keep the feature narrow and service-oriented. The API layer should only enforce auth and route shaping, while `management/impact.py` encapsulates run lookup, rejection detection, replay-scope assembly, AI invocation, and acknowledge-state mutation. The implementation should reuse existing `RunRecord`, `MappingSnapshot`, and audit-recording patterns instead of introducing a new persistence model.

**Tech Stack:** Python 3.14, FastAPI, SQLAlchemy 2.x ORM, Pydantic, Pytest, existing migrations-engine AI adapter layer.

## Global Constraints

- Model slots live in YAML, not in the Pydantic `Settings` class.
- Provider API keys are referenced by environment-variable name in YAML and read at call time by the adapter implementation.
- Missing model-slot environment substitutions fail closed at load time.
- Missing provider keys fail closed when an adapter is called.
- Callers use `migrations_engine.ai.factory.get_adapter`; they do not talk to provider SDKs directly.
- Preserve project scoping in every impact-review endpoint.
- Do not touch frontend files.

---

### Task 1: AI slot regression and config wiring

**Files:**
- Modify: `engine/config/engine.yaml`
- Modify: `engine/src/migrations_engine/ai/config.py`
- Modify: `engine/src/migrations_engine/ai/factory.py`
- Create/Modify: `engine/tests/test_impact_review_config.py`

**Interfaces:**
- Consumes: `get_ai_config()`, `get_adapter()`, `ConfigurationError`
- Produces: a validated `impact_analysis` model slot available through the factory

- [ ] **Step 1: Keep the failing slot test in place**

The test must write a temporary `engine.yaml` with:

```yaml
models:
  planning: claude-3-haiku-20240307
  review: claude-3-haiku-20240307
  implementation: claude-3-haiku-20240307
migration:
  models:
    pii_review: claude-3-haiku-20240307
    field_mapping: claude-3-haiku-20240307
    script_generation: claude-3-haiku-20240307
    script_correction: claude-3-haiku-20240307
    impact_analysis: claude-3-haiku-20240307
providers:
  anthropic_api_key_env: ANTHROPIC_API_KEY
  openai_api_key_env: OPENAI_API_KEY
```

The assertions must prove that `get_adapter("impact_analysis")` does not fail
with `Unknown AI task`, while an arbitrary bogus slot still does.

- [ ] **Step 2: Run the slot test**

Run:

```bash
cd engine && python -m pytest tests/test_impact_review_config.py -v
```

Expected: slot lookup succeeds and the bogus slot still raises.

- [ ] **Step 3: Keep the config and factory mapping wired**

Ensure the YAML contains:

```yaml
    impact_analysis: ${MODEL_IMPACT_ANALYSIS}
```

Ensure `MigrationModelConfig` includes:

```python
impact_analysis: str
```

Ensure `_SLOT_MAP` includes:

```python
"impact_analysis": lambda config: config.migration_models.impact_analysis,
```

- [ ] **Step 4: Re-run the slot test**

Run:

```bash
cd engine && python -m pytest tests/test_impact_review_config.py -v
```

---

### Task 2: Impact review API contract

**Files:**
- Modify: `engine/src/migrations_engine/api/schemas.py`
- Create: `engine/src/migrations_engine/management/impact.py`
- Create: `engine/src/migrations_engine/routes/impact.py`
- Modify: `engine/src/migrations_engine/app.py`
- Create: `engine/tests/test_impact_review_api.py`

**Interfaces:**
- Consumes: `RunRecord`, `MappingSnapshot`, `record_management_audit`, `get_adapter`, `RunResponse`
- Produces: `ImpactReportResponse` for `GET /projects/{project_id}/runs/{run_id}/impact`
  and `RunResponse` for `POST /projects/{project_id}/runs/{run_id}/impact/acknowledge`

- [ ] **Step 1: Write the failing API tests**

Cover these behaviors:

- `GET /impact` returns `404 run_not_found` when the run is missing.
- `GET /impact` returns `404 gate_1_not_rejected` when the run has no
  `gate_1` rejection record.
- `GET /impact` returns the report payload when the run has a `gate_1`
  rejection, and the service uses the `impact_analysis` adapter slot.
- `POST /impact/acknowledge` returns an updated `RunResponse` and persists
  `run.status = "pending_gate_1"`.
- `POST /impact/acknowledge` returns `404 run_not_found` for a missing run.
- `POST /impact/acknowledge` returns `404 gate_1_not_rejected` when no
  rejection exists.
- Both endpoints enforce project access and central-team authorization where
  required.

- [ ] **Step 2: Run the API test file**

Run:

```bash
cd engine && python -m pytest tests/test_impact_review_api.py -v
```

Expected: import or missing-symbol failures before implementation.

- [ ] **Step 3: Implement the response schemas**

Add these models to `api/schemas.py`:

```python
class GateRejectionDetail(BaseModel):
    rejected_by: str | None
    rejected_at: datetime
    affected_objects: list[str]
    required_changes: str
    notes: str | None


class ImpactAIRecommendation(BaseModel):
    recommendation: str
    suggested_fix: str
    minimal_replay_scope: list[str]


class ImpactReportResponse(BaseModel):
    run_id: str
    gate_rejection: GateRejectionDetail
    replay_scope: list[str]
    ai_recommendation: ImpactAIRecommendation
```

- [ ] **Step 4: Implement the service**

Create `management/impact.py` with:

```python
def get_impact_report(db: Session, *, project_id: str, run_id: str) -> ImpactReportResponse: ...

def acknowledge_impact(
    db: Session,
    *,
    project_id: str,
    run_id: str,
    actor_user_id: str,
) -> RunResponse: ...
```

The service must:

- scope run lookup by `project_id`
- require a `gate_1` rejection record
- extract the rejected actor, timestamp, affected objects, required changes, and notes
- read field bindings from the run’s pinned mapping snapshot when available
- compute replay scope from other non-terminal runs in the same project that share an affected object
- call `get_adapter("impact_analysis")`
- set `run.status = "pending_gate_1"` on acknowledge
- record a management audit event

- [ ] **Step 5: Implement and register the router**

Create `routes/impact.py` with:

```python
@router.get("", response_model=ImpactReportResponse)
@router.post("/acknowledge", response_model=RunResponse)
```

Register the router in `app.py`.

- [ ] **Step 6: Re-run the API tests**

Run:

```bash
cd engine && python -m pytest tests/test_impact_review_api.py -v
```

Expected: all impact-review API tests pass.

---

### Task 3: Full backend verification

**Files:**
- All files touched above

**Interfaces:**
- Consumes: the full impact-review backend flow
- Produces: a verified backend implementation ready for summary and completion

- [ ] **Step 1: Run the focused impact review tests together**

Run:

```bash
cd engine && python -m pytest tests/test_impact_review_config.py tests/test_impact_review_api.py -v
```

- [ ] **Step 2: Run the related backend regression suite**

Run the nearby run and gate tests to ensure no collateral breakage:

```bash
cd engine && python -m pytest tests/test_runs_api.py tests/test_gates_api.py -q
```

- [ ] **Step 3: Write the task report**

Save the implementation report to:

```text
/Users/vjkotra/projects/katana/.superpowers/sdd/task-1-report.md
```

Include:

- what changed
- which tests were run
- any remaining concerns
