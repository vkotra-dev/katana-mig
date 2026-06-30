# Governance

This page consolidates the repository operating rules that apply across the
whole project.

It is the repo-facing rulebook that tells you how to approach work, what order
to build in, which invariants are load-bearing, and what typing/testing
conventions the codebase expects.

`AGENTS.md` and `task-workflow.md` are legacy pointers into this bundle. The
numbered specs remain the historical source archive, but this page is the
working rulebook the repo should read from first.

## Purpose

Capture the repo-wide rules that govern:

- how to start work
- how to structure task traces
- how to order build and verification work
- which invariants cannot be weakened
- how typing, testing, and style are expected to look

## Repository operating rules

Before touching a component:

- read the relevant domain page first
- treat the domain page as the source of truth
- patch the domain page and the behavior together when behavior changes
- do not weaken a safety invariant to satisfy a test
- prefer one component per PR where possible
- respect the layer boundary between harness and migration domain

When working in this repo:

- keep changes narrow and component-scoped
- do not add migration-specific fields to harness types
- do not make harness logic migration-specific
- use protocols over concrete implementations
- keep business logic out of wiring and `__main__`
- raise only for unexpected failures; use dispositions for expected terminal states

### AI model policy and key management

AI-backed stages resolve their model assignments from `engine/config/engine.yaml`
through the `migrations_engine.ai` adapter layer.

Rules:

- model slots live in YAML, not in the Pydantic `Settings` class
- provider API keys are referenced by environment-variable name in YAML and
  read at call time by the adapter implementation
- missing model-slot environment substitutions fail closed at load time
- missing provider keys fail closed when an adapter is called
- callers use the factory in `migrations_engine.ai.factory`; they do not talk
  to provider SDKs directly

### DDL change rule

Every change to `engine/src/migrations_engine/db/models.py` that touches table
structure — adding a column, removing a column, creating a table, dropping a
table, or changing a column type — **must** ship with a hand-written Alembic
migration file in `engine/migrations/versions/`.

- Migration files follow the `NNNN_<description>.py` naming convention; inspect
  the current chain to get the next number before writing the file.
- The `down_revision` in the new file must match the `revision` of the latest
  existing migration — never guess the number; read it from the file.
- `alembic upgrade head` must run cleanly locally before the change is committed.
- The model edit and the migration file are staged and committed together in a
  single commit; a model change without a migration is a broken commit.
- Do **not** use `alembic revision --autogenerate` for production migrations;
  write the `upgrade()` / `downgrade()` by hand so the intent is explicit and
  reviewable.

## Repository map

```
AGENTS.md                        ← repository pointers into the bundle
BUILD.md                         ← build sequencing across 5 phases
HARD-PROBLEMS.md                 ← persistence, context management, conductor risks
pyproject.toml                   ← deps, mypy/ruff config

docs/domain/
  README.md                      ← bundle index + funnel map
  governance.md                  ← this page
  harness.md                     ← harness and platform execution contract
  security.md                    ← security boundaries
  auth.md                        ← identity and session contract
  management.md                  ← users, roles, memberships
  ui.md                          ← operator surface
  project.md                     ← project container contract
  runs.md                        ← migration-domain run contract
  source-model.md                ← source declaration and snapshot contract

specs/                           ← historical archive / derivation source
engine/                          ← Python package (migrations-engine)
  src/migrations_engine/
    app.py                       ← FastAPI lifespan + document catalog
    platform_api.py              ← REST: plans, runs, approvals, CR lifecycle
    composition/                 ← bootstrap_composition, platform + migration stages
    harness/
      run_manager.py             ← run loop and dispositions
      context_assembler.py      ← prompt/context assembly
      model_adapter.py           ← LLM adapter boundary
      tool_router.py             ← tool dispatch and array fan-out
      policy_gate.py            ← policy gating
      sandbox.py                ← sandboxed execution boundary
      verifier.py               ← final success authority
      audit_bus.py              ← append-only audit sink
      failure_taxonomy.py       ← retry/failure classification
      conductor.py              ← lifecycle baton transitions
      persistence.py            ← durable run/audit/lease state
    migration/
      source_adapter.py          ← source ingestion / physical modeling
      schema_discovery.py        ← structural analysis
      pii_classifier.py          ← sensitivity classification
      domain_object_analyser.py  ← domain object mapping
      lookup_value_mapper.py      ← lookup resolution and deltas
      rule_set_generator.py      ← transformation rules
      migration_code_generator.py← SQL/script generation and freeze
      reconciliation_engine.py   ← lineage and validation
      baton_registration.py      ← migration baton routing
    approval_service/            ← approval record validation and wake bridge
    infra/                       ← YamlInfraService
  tests/                         ← unit + integration

web/
  app/                           ← Next.js routes and screens
  lib/                           ← client helpers and auth/API utilities
tasks/                           ← task files, summaries, backlog, completed
plans/                           ← plan files
```

The layout above is the minimum structural map. When you touch a component,
read the page for that component and the surrounding bundle pages before editing.

## Task workflow and traceability

Use the task workflow whenever work needs planning, task files, plans, summaries,
or move-to-completed traceability.

Source of truth hierarchy:

- the working domain pages are the authoritative behavior docs
- `docs/intake.md` is only a front-door ledger when present
- `tasks/backlog/` is a queue and reminder surface only
- task files are execution artifacts, not specs
- if the domain page is thin or missing, patch the domain page first

Required lifecycle:

1. brainstorm
2. create task file(s)
3. create plan per task
4. execute
5. write summary
6. move task to `tasks/completed/`

Required markers in each plan:

- Task and Domain links at the top
- Current State
- Objective
- Out of Scope
- Blast Radius
- File Changes
- Tests
- Verification
- Pitfalls
- Commit

Traceability rules:

- task files are execution artifacts
- plans are synthesized from the working domain page
- backlog notes are reminders, not specs
- if the domain page is thin or missing, patch the domain page first
- every task should be recoverable from its slug across task, plan, summary, and
  completed artifact

Task mechanics:

- scan `tasks/` for the highest numbered `NNN` prefix when choosing the next task
  number, ignoring `TASK_INDEX.md` and any non-numbered files; if there are no
  numbered tasks, scan `tasks/completed/`
- task files live at `tasks/<slug>.md`
- plans live at `plans/YYYY-MM-DD-<slug>.md`
- summaries live at `tasks/summary/<slug>.md`
- completed tasks move to `tasks/completed/<slug>.md`
- the slug must remain identical across all four artifacts
- task files are created first, then plans, then execution, then summaries
- when a task uses a worktree, record the worktree branch/path in the task or
  plan, and treat cleanup as part of completion: merge or abandon the branch,
  remove the linked worktree, and prune stale metadata before closing the task
- when work is done, move the task with `git mv` so git history is preserved
- add the new task to `tasks/TASK_INDEX.md` when creating the task file
- do not execute a task without a corresponding plan file in `plans/`
- before writing a plan, read the current state of every file the task will touch
- if migrations are involved, inspect the current migration chain and schema state
  before drafting the plan
- plans written without reading current state are placeholders and cause agent
  divergence

## Build order

The repo has an explicit build order. Build from the bottom up so each layer is
testable against real lower layers.

### Harness core

1. `types`
2. `audit_bus`
3. `sandbox`
4. `verifier`
5. `tool_router`
6. `policy_gate`
7. `run_manager`
8. `context_assembler`

### Harness platform

9. `persistence`
10. `runtime_orchestrator`
11. `lifecycle_conductor`
12. `project_registry`
13. `change_requests` + `intake`
14. `planning_orchestrator` + `review_gate`

### Migration analysis pipeline

15. `source_adapter`
16. `schema_discovery`
17. `pii_classifier`
18. `domain_object_analyser`

### Migration mapping and generation

19. `lookup_value_mapper`
20. `rule_set_generator`
21. `migration_code_generator`
22. `reconciliation_engine`

### Human interface

23. `approval_service`
24. `ui`

## Rollout and rollback

Changes ship as versioned, reviewable bundles.

Rollout expectations:

- release changes are applied in the declared environment order
- each rollout step must preserve the documented invariants and observability
- behavior changes must be paired with the domain-page update that describes
  them
- launch-critical changes should be validated in the lowest-risk environment
  before promotion

Rollback expectations:

- rollback restores the previous known-good version of the affected frozen
  artifact, configuration bundle, or deployment release
- rollback does not rewrite historical artifacts in place
- if data correction is needed, it is handled by a new corrective artifact or
  run, not by mutating prior records
- rollback must preserve auditability and the ability to explain what changed
  and when

Any release that cannot state its forward path and rollback path explicitly is
not ready for promotion.

## Safety invariants

The invariants are repo-wide guardrails. Do not weaken them.

### Harness layer

- **I1** Verifier is the final authority on success.
- **I2** Approved actions are pinned.
- **I3** Every layer emits an audit event.
- **I4** Budget exhaustion stops gracefully; it never throws.
- **I5** Two independent retry counters.
- **I6** Tool calls are always an array.
- **I7** Nothing executes outside the sandbox.
- **I8** Audit-sink failure is converted to STOP_FATAL by the Run Manager.
- **I9** Batch fan-in is deterministic.
- **I10** Durable resume requires idempotency for side-effecting tools.
- **I11** Approved plans are immutable; divergence triggers re-planning.
- **I12** Canonical names downstream; aliases only in human input.
- **I13** World vs. work; intake describes the world, never the implementation.
- **I14** Stages communicate only by passing frozen batons.
- **I15** Project isolation; identity is `(project_id, cr_id)`.
- **I16** Lifecycle gates are mechanical-first.

### Migration domain

- **I17** Knowledge artifacts are version-immutable; executions declare their
  artifact versions; execution results never mutate knowledge artifacts directly.
- **I18** Every DDL change ships with a hand-written Alembic migration in the
  same commit; a model edit without a migration is a broken commit.

## Typing and code conventions

- Python 3.11+
- full type hints everywhere
- `mypy --strict` must stay clean
- `ruff` must stay clean
- no bare `Any` in committed code
- use `typing.Protocol` for collaborators
- prefer frozen dataclasses for artifacts and audit records
- keep audit append-only
- do not add business logic to wiring
- do not cross the harness / migration boundary in imports

## Verification expectations

Before claiming a change is complete:

- run the relevant targeted tests
- run the relevant type checks
- verify the behavior against the spec or bundle page
- confirm that any safety invariant affected by the change is still covered

When a change touches a task or plan:

- make the task traceable
- keep the summary in sync
- move the task to `tasks/completed/` only after the work is done

## Failure modes

| Situation | Handling |
|-----------|----------|
| Spec and implementation disagree | Spec wins until deliberately changed |
| Task lacks required markers | Task is not ready |
| Work starts without reading the relevant spec | Re-read before proceeding |
| A safety invariant would need to weaken to pass a test | Stop and raise it |
| Harness import reaches into migration code | Refactor; boundary violation |
| A behavior change lacks a spec change | Treat as a bug |

## Acceptance criteria

- [ ] Repo operating rules are readable in one place.
- [ ] Task workflow and traceability are explicit.
- [ ] Build order is clear and bottom-up.
- [ ] I1–I17 are visible as repo-wide guardrails.
- [ ] Typing and testing expectations are easy to find.
- [ ] The page is derived from the existing repo rules, not invented.

## Changelog

- 2026-06-29: Added DDL change rule and invariant I18 — every model.py table
  structure change must ship with a hand-written Alembic migration in the same commit.
- 2026-06-29: Added governance bundle page to consolidate repo operating rules,
  task workflow, build order, safety invariants, and typing/testing conventions.
