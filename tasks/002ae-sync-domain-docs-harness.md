---
id: 002ae
title: Sync docs/domain/harness.md against actual codebase
status: completed
created: 2026-07-24
priority: medium
domain: docs
depends-on: []
---

# Sync docs/domain/harness.md

## Objective

Update `docs/domain/harness.md` to accurately reflect the current harness execution engine. Last updated 2026-07-16.

## Scope

- `docs/domain/harness.md` only

## What to verify

1. **Core harness components** — Verify each component exists at the listed path:
   - `run_manager.py` → `engine/src/migrations_engine/harness/run_manager.py`
   - `context_assembler.py` → `engine/src/migrations_engine/harness/context_assembler.py`
   - `model_adapter.py` → `engine/src/migrations_engine/harness/model_adapter.py`
   - `tool_router.py` → `engine/src/migrations_engine/harness/tool_router.py`
   - `policy_gate.py` → `engine/src/migrations_engine/harness/policy_gate.py`
   - `sandbox.py` → `engine/src/migrations_engine/harness/sandbox.py`
   - `verifier.py` → `engine/src/migrations_engine/harness/verifier.py`
   - `audit_bus.py` → `engine/src/migrations_engine/harness/audit_bus.py`
   - `failure_taxonomy.py` → `engine/src/migrations_engine/harness/failure_taxonomy.py`

2. **Platform harness components** — Verify each exists:
   - `conductor.py`, `persistence.py`, `runtime_orchestrator.py`, `lifecycle_conductor.py`
   - `project_registry.py`, `change_requests.py`, `intake.py`, `planning_orchestrator.py`
   - `review_gate.py`, `model_router.py`, `ingestion_trigger.py`, `notification_handler.py`

3. **Run loop order** — Verify the 7 steps match actual `run_manager.py` loop

4. **Disposition types** — Verify all 7 disposition types match actual failure taxonomy

5. **Lifecycle stages** — Verify: ingestion, intake, planning, approval, implementation, verification, review, delivery

6. **Sandbox boundary** — Verify all listed execution types go through sandbox

7. **Persistence fields** — Verify durable state list matches actual `persistence.py`

8. **Observability** — Verify the minimum observability requirements match actual structured logging/metrics setup

## Out of scope

- Any other domain doc files
- Backend implementation changes

## Acceptance criteria

- [ ] All core harness component files exist at listed paths
- [ ] All platform harness component files exist at listed paths
- [ ] Run loop order matches actual code
- [ ] Disposition types match actual failure taxonomy
- [ ] Lifecycle stages match actual conductor
- [ ] Changelog updated
- [ ] timestamp updated
