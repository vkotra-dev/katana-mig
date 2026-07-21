---
type: Task Plan
title: Shared Prompt Class — Externalize System/User Prompts to YAML with Merge Fields
status: ready
---

# Task: 001ed-shared-prompt-template-class

## Context
Five AI call sites still have their system/user prompts hardcoded as Python string
literals/f-strings: `mapping/review.py::propose_mapping`,
`management/source_analysis.py::analyze_source_slice`, and three calls in
`management/fibers.py` (`analyze_feed`'s two AI calls, `submit_lookup_inputs`). This
session alone edited `propose_mapping`'s system prompt three times (001ea's initial
hardening plus two follow-up fixes) — every wording-only change required a full
Python edit/mypy/ruff/pytest/commit cycle. `codegen/service.py` already solved this
differently: its prompts live in Jinja2 template files
(`codegen/templates/system_prompt.txt.j2`, `user_prompt.txt.j2`), loaded and rendered
via small wrapper functions. This task builds a shared, reusable version of that idea
for the other five prompts — a generic `Prompt` class backed by YAML files with merge
fields — rather than duplicating codegen's bespoke Jinja setup five more times.

## Requirements

1. **Storage format**: one YAML file per prompt, two top-level string keys,
   `system:` and `user:`, using YAML block-scalar (`|`) style so multi-line prose
   (numbered rules, blank-line-separated sections) is written naturally with no
   escaping or continuation-line rules. Not a single combined file (keeps diffs/blame
   scoped to one prompt per change), not the database (a prompt's wording and its
   Pydantic response schema are tightly coupled — see 001ea/001eb — so a change to
   either needs the same PR review as code; `ai_call_log` already stores the
   *rendered* prompt per call, so DB storage of the *template* would be redundant for
   audit purposes).
2. **Merge-field syntax is `$name` / `${name}`** (Python stdlib `string.Template`),
   **not bare `{name}`**. At least one existing prompt
   (`review.py`'s current system prompt: `"...suggest a logical name for it (e.g.,
   '{source_field}_ref')."`) uses literal curly braces as an *example shown to the
   AI*, not a merge field — bare `{name}` substitution would corrupt it. Several
   prompts also show the AI literal JSON-shaped output examples, which are full of
   `{ }` — `$name` avoids all of that collision risk without needing to escape
   anything in the migrated content.
3. **One generic `Prompt` class**, not five subclasses:
   ```python
   prompt = Prompt("mapping")                     # loads ai/prompts/mapping.yaml
   prompt.set(ddl=ddl, source_columns=source_columns, mapping_hints_section=hints_text)
   system_text, user_text = prompt.get_prompt()
   ```
   `.set(**kwargs)` accumulates merge fields (can be called more than once before
   `get_prompt()`). `get_prompt()` substitutes every `$name` placeholder found in the
   template; a placeholder with no supplied value is replaced with `""` **and logs a
   warning** naming the prompt and the missing field — not a hard error, but not
   silent either.
4. **Convention for optional content**: call sites must explicitly `.set()` every
   merge field the template references, including intentionally-blank ones (e.g.
   `mapping_hints_section=""` when the feed has no mapping hints this call). The
   warn-and-drop path in requirement 3 is a safety net for a genuine wiring bug (the
   template references a field no code path ever supplies), not the mechanism for
   expressing "this section is sometimes absent" — that's an every-call warning for
   completely normal behavior otherwise, which defeats the point of making missing
   fields loud.
5. **Migrate the five prompts** into
   `engine/src/migrations_engine/ai/prompts/<name>.yaml`:
   - `mapping.yaml` — `review.py::propose_mapping`
   - `source_analysis.yaml` — `source_analysis.py::analyze_source_slice`
   - `feed_domain_object_analysis.yaml` — `fibers.py::analyze_feed`, first AI call
     (identifies destination tables, creates fibers)
   - `feed_field_mapping.yaml` — `fibers.py::analyze_feed`, second AI call (per-fiber
     field mapping into `fiber.field_bindings` — distinct prompt/schema from
     `mapping.yaml` despite the similar name, and both this and
     `feed_domain_object_analysis.yaml` log `call_type="feed_analysis"`, so name them
     by purpose, not call_type, to avoid collision)
   - `lookup_mapping.yaml` — `fibers.py::submit_lookup_inputs`. Its current
     "user prompt" is `json.dumps({...})` — structured data serialization, not
     authored prose. Only the `system` section needs real templating; keep the
     payload built in Python and pass it as a single `$payload` merge field for the
     `user` section, rather than forcing JSON construction into YAML/text.
6. **`Prompt` class lives in `engine/src/migrations_engine/ai/prompt.py`** — alongside
   `adapter.py`/`logging.py`/`factory.py`, since it's shared AI infrastructure, not
   specific to any one module.

## Out of Scope
- `codegen/service.py`'s existing Jinja2 template setup — already works, not
  migrated onto the new class in this task. Design `Prompt` so codegen *could* adopt
  it later without precluding that, but don't force it now.
- Per-project or per-environment prompt overrides, A/B testing, or any live-editing
  UI — none of that was asked for; file-based + PR review is the deliberate choice
  (see requirement 1).
- Any change to prompt *wording* itself — this is a pure mechanism migration; the
  text moving into the YAML files should be byte-for-byte what's in the Python
  strings today (aside from the `{source_field}_ref` brace note in requirement 2,
  which needs no escaping once `$name` syntax is adopted — the literal `{...}` just
  passes through untouched).
