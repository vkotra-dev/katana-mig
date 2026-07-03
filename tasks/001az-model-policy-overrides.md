# Task 001az — Per-Project Model Policy Overrides

**Plan:** `plans/2026-07-03-001az-model-policy-overrides.md`

## Domain

- [project.md](/Users/vjkotra/projects/katana/docs/domain/project.md)
- [api.md](/Users/vjkotra/projects/katana/docs/domain/api.md)

## Current State

- `project_records.model_policy` is a JSON column storing `dict[str, Any] | None`.
- The global AI model config (`engine.yaml`) assigns one model name per AI task
  via env-var substitution. All projects use the same models.
- The engine never reads `model_policy` from the project — it always uses the
  global config regardless of what is stored.
- The project edit form does not expose `model_policy` at all.

## Objective

Define a structured `ModelPolicy` Pydantic model that allows individual projects
to override the model used for any specific AI task. Any field left null falls
back to the global `engine.yaml` value. Wire a `resolve_model` helper into the
AI config layer so running tasks consult the project policy first.

Expose the policy as a "Model Policy" section in the project edit form with one
text input per AI task and placeholder text showing the current global default.

## Scope

- Define `ModelPolicy` as a typed Pydantic model with optional fields mirroring
  `MigrationModelConfig` and `PlatformModelConfig`
- Add `resolve_model(task: str, project_policy: ModelPolicy | None, global_config: AIConfig) -> str`
  helper in the AI config layer
- Thread `project_policy` into the AI adapter call sites so they call
  `resolve_model` instead of reading `global_config` directly
- Update `ProjectCreateRequest` / `ProjectUpdateRequest` / `ProjectResponse`
  to use `ModelPolicy` instead of `dict[str, Any]`
- Add a "Model Policy" section to `ProjectEditForm` with 11 text inputs
  (3-column grid) and placeholder showing the live global default

## AI Task Fields

All fields are `str | None = None` — null means use global default:

| Field | Maps to global |
|---|---|
| `pii_review` | `migration_models.pii_review` |
| `field_mapping` | `migration_models.field_mapping` |
| `lookup_mapping` | `migration_models.lookup_mapping` |
| `script_generation` | `migration_models.script_generation` |
| `script_correction` | `migration_models.script_correction` |
| `schema_dependency` | `migration_models.schema_dependency` |
| `impact_analysis` | `migration_models.impact_analysis` |
| `feed_analysis` | `migration_models.feed_analysis` |
| `planning` | `models.planning` |
| `review` | `models.review` |
| `implementation` | `models.implementation` |

## Out of Scope

- Changing the `model_policy` column type — it remains a JSON column (the
  structured Pydantic model serialises cleanly to JSON)
- Provider selection (Anthropic vs OpenAI) — not part of this task
- Temperature or token limit overrides

## Acceptance Criteria

- `ModelPolicy` Pydantic model validates and rejects unknown model names that
  don't match a known task field
- `resolve_model("field_mapping", policy, config)` returns the project override
  when set, otherwise the global config value
- All AI adapter call sites use `resolve_model` — no direct reads of
  `global_config.migration_models.*`
- Project edit form shows a "Model Policy" section with inputs prefilled from
  the project's current overrides and placeholder text showing the global default
- Clearing an input removes the override; saving with an empty field sends `null`

## Test Expectations

- `resolve_model` returns project value when field is set
- `resolve_model` returns global value when project field is null
- `resolve_model` returns global value when project policy is null entirely
- Edit form renders 11 model override inputs in the Model Policy section
- Submit payload includes `modelPolicy` with only non-empty fields set

## Pitfalls

- The JSON column stores the dict as-is; Pydantic serialisation must use
  `model_dump(exclude_none=True)` or similar so null fields don't clutter storage
- AI adapter call sites must not hardcode `get_ai_config()` reads after this
  task — all model resolution must go through `resolve_model`

## Commit

- `feat(001az): add per-project model policy overrides with global fallback`
