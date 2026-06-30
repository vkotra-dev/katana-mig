# Runs and Analysis Review Hardening Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add regression coverage for the remaining run and source-analysis review concerns without changing the already-correct core behavior.

**Architecture:** Keep the fix narrow: the execution engine already scopes by project and preserves lookup snapshot versions, so the task is to prove that behavior with tests. The source-analysis service already uses the correct adapter slot and synchronous response shape; add a regression test so the contract stays pinned.

**Tech Stack:** Python 3.14, FastAPI, SQLAlchemy 2.x ORM, Pytest, SQLite test fixtures.

## Global Constraints

- Preserve project scoping in the run execution path.
- Preserve the full lookup snapshot version map for multi-lookup runs.
- Keep source analysis synchronous and governed by the `field_mapping` slot.
- Do not widen the review slice beyond the tests needed to pin the contract.

---

### Task 1: Run API scoping regression

**Files:**
- Modify: `engine/tests/test_runs_api.py`

**Interfaces:**
- Consumes: run launch/resume routes, `execute_run()` project guard
- Produces: a regression test proving foreign-project launch/resume requests fail closed

- [ ] **Step 1: Add the failing regression test**

Create a test that:

- seeds two projects
- creates a run in project A
- calls `/projects/{project_b}/runs/{run_id}/launch`
- calls `/projects/{project_b}/runs/{run_id}/resume`
- asserts both return `404 run_not_found`

- [ ] **Step 2: Run the test**

Run:

```bash
cd engine && PYTHONPATH=src pytest tests/test_runs_api.py -q
```

- [ ] **Step 3: Commit**

```bash
git add engine/tests/test_runs_api.py
git commit -m "test(review): lock down run project scoping"
```

### Task 2: Source analysis adapter-slot regression

**Files:**
- Modify: `engine/tests/test_source_analysis_service.py`

**Interfaces:**
- Consumes: `analyze_source_slice()`
- Produces: a regression test proving the `field_mapping` slot is used

- [ ] **Step 1: Add the failing regression test**

Create a test that monkeypatches `get_adapter` to capture the requested slot and
asserts it is `field_mapping`.

- [ ] **Step 2: Run the test**

Run:

```bash
cd engine && PYTHONPATH=src pytest tests/test_source_analysis_service.py -q
```

- [ ] **Step 3: Commit**

```bash
git add engine/tests/test_source_analysis_service.py
git commit -m "test(review): pin source analysis adapter slot"
```
