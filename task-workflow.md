# Task Workflow — Planning & Traceability

Reusable across projects. Every piece of work follows this lifecycle. No step is skipped.

This document defines the planning and traceability process. The working repo
rulebook now lives in [`docs/domain/governance.md`](./docs/domain/governance.md).
This page is retained as a task-flow reference and should be kept aligned with
that bundle.

```
Brainstorm → Task file(s) → Plan (per task) → Execute → Summary → Move task to completed/
```

The **slug** is the common identifier across all artifacts for a given work item.

## Required Markers

Every task plan must make these markers obvious and complete:

- `Task` and `Domain` links at the top
- `Current State`
- `Objective`
- `Out of Scope`
- `Blast Radius`
- `File Changes`
- `Tests`
- `Verification`
- `Pitfalls`
- `Commit`

If any marker is missing or vague, the task is not ready to execute.

---

## Artifact Locations

| Artifact | Path | Example |
|----------|------|---------|
| Task | `tasks/<slug>.md` | `tasks/089c-rename-middleware.md` |
| Plan | `plans/YYYY-MM-DD-<slug>.md` | `plans/2026-06-10-089c-rename-middleware.md` |
| Summary | `tasks/summary/<slug>.md` | `tasks/summary/089c-rename-middleware.md` |
| Completed task | `tasks/completed/<slug>.md` | `tasks/completed/089c-rename-middleware.md` |

---

## Source of Truth Hierarchy

| Artifact | Role |
|----------|------|
| `docs/domain/` or the repo's equivalent working domain bundle | **Authoritative working docs.** Defines what the feature is, how it behaves, and what the data model looks like. Task files are derived from here. |
| `docs/intake.md` (if present) | **Front-door ledger.** Captures known missing work and prioritization only. Never the spec. |
| `tasks/backlog/` | **Queue / reminder only.** Records that work exists and its priority. Not a spec. Never the source of context for a task file. |
| Task file (`tasks/<slug>.md`) | **Execution artifact.** Synthesized from the authoritative working docs. If backlog text and domain docs disagree, follow the domain docs. |

**Rule:** Before creating any task file, verify the relevant spec section is complete. If it is missing or thin, write or patch the spec first — then derive the task from the spec, not from the intake or backlog item.

**Additional rule:** `docs/intake.md` is the formal entry point for new work when this repo uses one. Intake rows can identify missing docs and priority, but they must never serve as the implementation spec.

---

## Step 1 — Create Task(s) After Brainstorming

After brainstorming produces an approved design:

1. Determine size/complexity — single task or decomposed subtasks (`NNNa`, `NNNb`, `NNNc`...)
2. Assign next task number:
   - Scan `tasks/` for the highest NNN prefix in filenames (ignore `TASK_INDEX.md` and non-numbered files)
   - If `tasks/` has no numbered files, scan `tasks/completed/`
   - Use that number + 1 (or + next letter for subtasks)
3. Create `tasks/<slug>.md` using the Task Definition Template below
4. Add the new task(s) to `tasks/TASK_INDEX.md`

The task file is written first — **before invoking the writing-plans skill**. It has no forward references; it does not yet know its plan or summary paths. Once all task files are created, proceed immediately to Step 2. **No code is written until every task has a plan.**

---

## Step 2 — Create a Plan Per Task

**Gate: a task must not be executed without a corresponding plan file in `plans/`.**

For each task (or subtask), create `plans/YYYY-MM-DD-<slug>.md`.

**Before writing the plan, read the current state of every file the task will touch.** If
migrations are involved, inspect the current migration chain and schema state using the
repo's native inspection command or metadata source before drafting the plan. Plans written
without reading current state produce placeholders — placeholders cause agent divergence.

---

### Plan Template

Every plan must use this structure. No section is optional. Shallow plans are the leading
cause of agents diverging from intent (wrong import pattern, missing field copy, wrong
migration number, incomplete blast radius). The executor starts cold — assume they know
nothing about the current state of the codebase.

````markdown
Task: tasks/<slug>.md
Domain: docs/domain/<topic>.md   ← omit if no single owning page exists yet

## Current State

<!--
What exists RIGHT NOW before this plan is executed. Be explicit about:
- Which files already exist vs. need to be created
- Which migrations have been applied (include the number, e.g. "latest: 0018_...")
- Whether the model has been pre-edited without a migration (call this out explicitly)
- Which fields/constraints are present on the model vs. in the DB
- Any in-progress state that would surprise the executor

If any file is already in its final desired state (e.g., model edited ahead of migration),
say: "src/.../models/foo.py is already in its final form — do not modify it."
-->

## Objective

<!-- One paragraph. What this plan produces and why. Not a restatement of the current state. -->

## Out of Scope

<!--
Explicit list of things this plan does NOT touch, even if they seem related.
Write "Do NOT X" for anything an agent might plausibly wander into.
Examples:
- Do NOT modify adjacent data model files outside the scope of this task.
- Do NOT add tests for unrelated features that already have their own task.
- Do NOT auto-generate a migration when the plan calls for a hand-written migration.
- Do NOT patch ancillary UI/docs for unrelated screens in the same change.

If this plan's scope is narrow, write at least 2-3 entries so the agent knows
what to leave alone. "Everything not listed in Blast Radius" is not sufficient —
name the most tempting adjacent files explicitly.
-->

## Blast Radius

<!-- Table of every file that changes. One row per file. -->

| File | Action | What changes |
|------|--------|-------------|
| `src/.../models/foo.py` | modify | remove `bar` field, add `current_baz` property |
| `migrations/00NN_foo.py` | create | three-step migration |
| `src/.../foo_service.py` | modify | `_helper()` signature; `ingest()` defaults dict |
| `templates/.../foo.html` | modify | replace `foo.field` with `foo.current_term.field` |
| `tests/unit/test_00NN_foo.py` | create | 6 tests |

## File Changes

<!--
For EVERY file in the blast radius: write the exact change.
- New file: write the complete file content.
- Edit: write the exact old block (enough context to locate it) and the exact new block.
No descriptions. No "something like this". The executor must be able to copy-paste.
-->

### `src/.../models/foo.py`

**Remove** these lines:
```python
field_to_remove = models.CharField(...)
```

**Add** after `__str__`:
```python
@property
def current_baz(self):
    today = date.today()
    return self.children.filter(effective_date__lte=today, expiry_date__gte=today).first()
```

### `migrations/00NN_name.py` (create)

```python
# Full migration file — copy-pasteable. No placeholders.
from django.db import migrations, models
import django.db.models.deletion


def _backfill(apps, schema_editor):
    # RunPython functions are ALWAYS defined inline here.
    # NEVER import helper code if the migration must run from scratch.
    Foo = apps.get_model("myapp", "Foo")
    for foo in Foo.objects.all():
        ...


class Migration(migrations.Migration):
    dependencies = [
        ("myapp", "00NN_previous_migration"),   # ← actual number from migration inspection
    ]
    operations = [
        migrations.RunPython(_backfill, migrations.RunPython.noop),
    ]
```

## Tests

<!--
For every test file: write the complete class with every method.
Do NOT write "add tests for X". Write the class, the method names, and the assertions.
The executor types in what is written here — they must not design tests themselves.
-->

### `tests/unit/test_00NN_slug.py` (create)

```python
from tests.factories.myapp import FooFactory


class FooModelTest:

    def test_field_removed(self):
        foo = FooFactory()
        assert not hasattr(foo, "removed_field")

    def test_current_baz_returns_active_child(self):
        ...

    def test_current_baz_returns_none_when_no_children(self):
        ...
```

## Verification

<!-- Exact bash commands in execution order. Copy-pasteable. No paraphrasing. -->

```bash
# Confirm current migration state before writing the migration file
<repo-specific migration inspection command>

# Apply / validate the migration
<repo-specific migration apply command>

# Test the changed behavior
<repo-specific targeted test command>

# Regression check after model/service/migration changes
<repo-specific broader regression test command>
```

## Pitfalls

<!--
Explicit list of mistakes this type of task commonly produces.
Write "Do NOT X" for every known trap.
-->

- Do NOT put `RunPython` functions in importable helper modules if the migration must run
  from scratch.
- Do NOT edit `models.py` table structure without a matching migration file — a model
  change without a migration is a broken commit (invariant I18).
- Do NOT use `alembic revision --autogenerate` for production migrations — write
  `upgrade()` / `downgrade()` by hand so the intent is explicit and reviewable.
- Do NOT guess the `down_revision` value — read the `revision` string directly from the
  latest file in `engine/migrations/versions/` before writing the new migration.
- Do NOT skip migration verification when schema or model shape changes — the migration is
  part of the change, not an implementation detail.
- Do NOT ship a behavior change without updating the relevant tests and spec/doc patch when the
  public contract changes.
- Do NOT leave a docs/spec patch out of the blast radius if the task changes behavior,
  terminology, workflow, or review criteria.

## Commit

```
feat(myapp): <what this commit produces — one line, imperative>
```
````

---

### Plan Quality Checklist

Before handing a plan to an agent for execution, every item must be true:

- [ ] **Current state is written** — executor knows which files exist, which migration is latest, whether any file was pre-edited without a migration
- [ ] **No placeholders** — `00NN`, `<slug>`, `TODO`, `[list here]` are absent from the final plan
- [ ] **Migration written for every DDL change** — any plan that edits `models.py` table structure (add/remove column, create/drop table) includes a hand-written `engine/migrations/versions/NNNN_<description>.py`; the model edit and migration file are in the same commit
- [ ] **Migration number is real** — verified with the repo's migration inspection command, not guessed
- [ ] **Migration helpers are inline or embedded where required** — no import path from a mutable helper module if the migration must run from scratch
- [ ] **Out of scope is written** — at least 2-3 explicit "Do NOT touch X" entries name the most tempting adjacent files
- [ ] **Blast radius is complete** — every file that changes has an entry; nothing is implied
- [ ] **Every test method is named** — test class, method name, and key assertion written out; "add tests for X" is not acceptable
- [ ] **Pitfalls section is present** — at minimum covers the migration-specific traps for this task type
- [ ] **Verification commands are copy-pasteable** — no variable substitution, no paraphrasing required

---

## Step 3 — After Execution: Write Summary Then Move Task

After the task is executed and tests pass:

**3a — Write the summary**

Create `tasks/summary/<slug>.md`:

```markdown
Task: tasks/completed/<slug>.md
Plan: plans/YYYY-MM-DD-<slug>.md
Commits: <sha1>[, <sha2>]

## Changes Made
<!-- File-by-file record of what changed in the code.
     NOT a re-statement of the task or plan.
     Each entry: file path, then bullet points of what was added, removed, or renamed. -->

### `path/to/file.py`
- Added `FunctionName(param1, param2)` — one-line description
- Renamed `OldSymbol` → `NewSymbol`
- Removed `deprecated_method()`

## Deviations from Plan
<!-- If the deviation is cosmetic (variable name, minor restructure): document here, leave the plan as-is.
     If the deviation is structural (signature changed, layer skipped, scope reduced/expanded):
     update the plan to reflect what was actually built BEFORE writing this summary,
     then note here what changed and why. The plan must always reflect reality. -->

## Tests
`<repo-specific test command for the changed files>` — N passed, 0 failed
```

**3b — Update the task file, then move it**

Before moving the task, append these lines to `tasks/<slug>.md`:

```markdown
---
Plan: plans/YYYY-MM-DD-<slug>.md
Summary: tasks/summary/<slug>.md
```

Then move using `git mv tasks/<slug>.md tasks/completed/<slug>.md` to preserve git history.

---

## Full Traceability Chain

```
tasks/completed/<slug>.md          ← start here
  ├─ Plan →    plans/YYYY-MM-DD-<slug>.md
  └─ Summary → tasks/summary/<slug>.md

plans/YYYY-MM-DD-<slug>.md
  ├─ Task →    tasks/completed/<slug>.md
  └─ Domain →  docs/domain/<topic>.md

tasks/summary/<slug>.md
  ├─ Task →    tasks/completed/<slug>.md
  ├─ Plan →    plans/YYYY-MM-DD-<slug>.md
  └─ Commits → git log → actual code diff
```

Every artifact is reachable from every other artifact in at most two hops.

---

## What the Summary Records

`## Changes Made` is a **file-by-file record of changes** — code, tests, migrations, docs, and spec patches all count. Record what was added, removed, or renamed in each file. It is not a re-statement of the task requirements, an explanation of why the feature exists, or a conceptual description of the approach. A reviewer reading the summary should be able to identify exactly which files changed and what the change was, without opening git.
