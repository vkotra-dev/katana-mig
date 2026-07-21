# Plan: 001ed — Shared Prompt Class (YAML-backed, merge-field templating)

## Task and Domain links

- Task: `tasks/001ed-shared-prompt-template-class.md`
- Domain: none — internal AI-call infrastructure, no UI/API-surface change

## Current State

- Five prompts are hardcoded Python string literals/f-strings:
  - `mapping/review.py::propose_mapping`, system prompt at
    `review.py:345-364`, user prompt built at `review.py:367-379`
    (`f"Source columns:\n{source_columns!r}\n\nDestination DDL:\n{ddl}"`
    plus a conditional `extra_context` append for `feed.mapping_hints`
    and `project_definition.constraints`).
  - `management/source_analysis.py::analyze_source_slice`, `SYSTEM_PROMPT`
    constant plus `_build_system_prompt()` appending
    `source_type`/`layout_information` (hardened in 001eb).
  - `management/fibers.py::analyze_feed`, two AI calls:
    `_FEED_ANALYSIS_SYSTEM` (`fibers.py:102-114`) + user prompt at
    `fibers.py:631-636`; `_FIELD_MAPPING_SYSTEM` (`fibers.py:116-130`) +
    user prompt at `fibers.py:704-710`.
  - `management/fibers.py::submit_lookup_inputs`,
    `_LOOKUP_MAPPING_SYSTEM_PROMPT` (`fibers.py:132-141`) + user prompt at
    `fibers.py:849-856` (`json.dumps({...})` — structured payload, not
    prose).
- `codegen/service.py` already has a working, different mechanism:
  `jinja_env = Environment(loader=FileSystemLoader(TEMPLATES_DIR), ...)`,
  `.txt.j2` files, `_build_system_prompt`/`_build_user_prompt` wrapper
  functions calling `template.render(**kwargs)` (`codegen/service.py:37,
  487-582`). Not migrated by this task — left as a second, pre-existing
  mechanism, since it already works and this task's new `Prompt` class
  doesn't need to displace it to solve the actual pain (the other five
  prompts).
- Confirmed collision risk: `review.py:354`'s system prompt contains
  `'{source_field}_ref'` as a literal example shown to the AI, not a
  merge field — ruling out bare `{name}` substitution syntax.
- `string.Template` (stdlib) provides `$name`/`${name}` substitution.
  `.safe_substitute()` leaves an unmatched `$name` as literal text in the
  output (wrong for our "drop it" requirement); `.substitute(mapping)`
  calls `mapping[key]`, so a custom `dict` subclass overriding
  `__missing__` gives exactly "return `""` and log a warning for any key
  not supplied" — the mechanism this task needs, no extra library.

## Objective

1. `ai/prompt.py`: `Prompt` class — `Prompt(name)` loads
   `ai/prompts/<name>.yaml`; `.set(**kwargs)` accumulates merge fields;
   `.get_prompt() -> tuple[str, str]` substitutes `$name` fields in both
   `system`/`user` template strings via `string.Template.substitute()`
   with a warn-and-return-empty-string fallback for unsupplied fields.
2. `ai/prompts/*.yaml`: the five files listed in the task, content
   migrated verbatim from the current Python strings.
3. Update the five call sites to build a `Prompt`, `.set()` their merge
   fields (including empty-string for intentionally-absent optional
   sections), and use `.get_prompt()`'s output in place of the current
   inline string construction.

## Out of Scope

- Migrating `codegen/service.py` onto `Prompt` — not needed, not broken.
- Prompt-override storage (DB, per-project, live-editable) — deliberately
  file-based per the task's storage-strategy decision.
- Any wording change to the five prompts beyond the mechanical move —
  content should match today's Python strings exactly.

## Blast Radius

- `engine/src/migrations_engine/ai/prompt.py` (new)
- `engine/src/migrations_engine/ai/prompts/mapping.yaml` (new)
- `engine/src/migrations_engine/ai/prompts/source_analysis.yaml` (new)
- `engine/src/migrations_engine/ai/prompts/feed_domain_object_analysis.yaml` (new)
- `engine/src/migrations_engine/ai/prompts/feed_field_mapping.yaml` (new)
- `engine/src/migrations_engine/ai/prompts/lookup_mapping.yaml` (new)
- `engine/src/migrations_engine/mapping/review.py` (edited)
- `engine/src/migrations_engine/management/source_analysis.py` (edited)
- `engine/src/migrations_engine/management/fibers.py` (edited, 3 call
  sites)
- `engine/tests/test_prompt.py` (new)
- No DB migration, no API/schema change, no frontend change — the
  rendered prompt text sent to the AI should be unchanged; this only
  changes where the text is authored.

## File Changes

**`engine/src/migrations_engine/ai/prompt.py` (new)**
```python
from __future__ import annotations

import logging
from pathlib import Path
from string import Template

import yaml

logger = logging.getLogger(__name__)

_PROMPTS_DIR = Path(__file__).parent / "prompts"


class _WarnOnMissing(dict):
    def __init__(self, name: str, data: dict[str, str]) -> None:
        super().__init__(data)
        self._prompt_name = name

    def __missing__(self, key: str) -> str:
        logger.warning("Prompt '%s': merge field '%s' not supplied, dropping", self._prompt_name, key)
        return ""


class Prompt:
    def __init__(self, name: str) -> None:
        self._name = name
        path = _PROMPTS_DIR / f"{name}.yaml"
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        self._system = data["system"]
        self._user = data["user"]
        self._fields: dict[str, str] = {}

    def set(self, **kwargs: str) -> "Prompt":
        self._fields.update(kwargs)
        return self

    def get_prompt(self) -> tuple[str, str]:
        mapping = _WarnOnMissing(self._name, self._fields)
        system = Template(self._system).substitute(mapping)
        user = Template(self._user).substitute(mapping)
        return system, user
```
(`.set()` returns `self` for chaining; not required by the task, cheap
to include.)

**`engine/src/migrations_engine/ai/prompts/mapping.yaml` (new)**
```yaml
system: |
  You are a data migration specialist. Analyze the provided multi-table SQL DDL schema
  and the list of source CSV columns.
  1. Identify all destination tables that receive fields from this feed.
  2. Map the source fields to each identified table. A single source field MAY be mapped to multiple destination fields if it logically populates both.
  3. Classify each binding as 'direct', 'detail_fk', or 'lookup_fk'.
  4. A binding is 'detail_fk' when its destination column is a foreign key whose referenced table is also mapped in this response. It is 'lookup_fk' when it references a lookup table not mapped here.
  5. For any lookup_fk or detail_fk binding, always set reference_table_name to the name of the referenced table. If the referenced lookup table does not exist in the DDL, suggest a logical name for it (e.g., '{source_field}_ref').
  6. For every binding, set destination_data_type to the exact SQL type of the destination column as declared in the DDL (e.g. 'INT', 'NVARCHAR(255)', 'DATE', 'DECIMAL(18,2)'). Set to null only if the column is not found in the DDL.
  7. For every binding, set nullable to true if the destination column allows nulls, or false if it is explicitly NOT NULL.
  8. If the DDL is invalid or you cannot find any matching tables, set error_code and error_message.

  OUTPUT CONTRACT:
  Return strictly valid JSON with no markdown fences, no invented keys, and exact adherence to the schema.
  - Top-level keys: 'tables' (list), 'error_code' (string|null), 'error_message' (string|null)
  - Table keys: 'destination_table_name' (string), 'bindings' (list)
  - Binding keys: 'source_field' (string), 'destination_field' (string), 'binding_type' (string: 'direct', 'detail_fk', 'lookup_fk'), 'reference_table_name' (string|null), 'destination_data_type' (string|null), 'nullable' (boolean|null)
user: |
  Source columns:
  $source_columns

  Destination DDL:
  $ddl

  $mapping_hints_section
  $constraints_section
```
(the literal `{source_field}_ref` above is untouched — `$`-syntax
doesn't collide with it, confirming requirement 2's reasoning)

**`engine/src/migrations_engine/ai/prompts/source_analysis.yaml`,
`feed_domain_object_analysis.yaml`, `feed_field_mapping.yaml`,
`lookup_mapping.yaml` (new)**
- Same shape: `system` migrated verbatim from
  `SYSTEM_PROMPT`/`_FEED_ANALYSIS_SYSTEM`/`_FIELD_MAPPING_SYSTEM`/
  `_LOOKUP_MAPPING_SYSTEM_PROMPT`; `user` migrated from each site's
  f-string, with the interpolated Python expressions
  (`{source_columns!r}`, `{ddl}`, `{n_rows}`, `{sample_text}`, etc.)
  replaced by `$`-prefixed merge-field names.
- `source_analysis.yaml`'s `system` also needs the
  `source_type`/`layout_information` append from `_build_system_prompt`
  folded in as `$source_type_section` (built in Python, passed as one
  merge field, same pattern as `mapping.yaml`'s `$mapping_hints_section`).
- `lookup_mapping.yaml`'s `user` is just `$payload`; `submit_lookup_inputs`
  keeps building the JSON string in Python
  (`json.dumps({"source_values": ..., "destination_rows": ...})`) and
  passes it as `payload=...`.

**`mapping/review.py::propose_mapping`**
- Replace the inline `system_prompt = (...)` and `user_prompt = f"..."`
  + `extra_context` block with:
  ```python
  prompt = Prompt("mapping")
  prompt.set(
      source_columns=repr(source_columns),
      ddl=ddl,
      mapping_hints_section=f"Mapping hints (operator-supplied):\n{feed.mapping_hints}" if feed.mapping_hints else "",
      constraints_section=(
          "Project constraints:\n" + "\n".join(f"- {c}" for c in project_constraints)
          if project_constraints else ""
      ),
  )
  system_prompt, user_prompt = prompt.get_prompt()
  ```
- Everything downstream (`adapter.call(system_prompt, user_prompt, ...)`,
  `log_ai_call(..., system=system_prompt, user=user_prompt, ...)`) is
  unchanged — `system_prompt`/`user_prompt` are still plain strings.

**`management/source_analysis.py::analyze_source_slice`**
- Same substitution pattern; `_build_system_prompt`'s
  source_type/layout_information logic moves into building the
  `source_type_section` merge-field value, then `Prompt("source_analysis")`.

**`management/fibers.py::analyze_feed` (both calls),
`submit_lookup_inputs`**
- Same pattern, three separate `Prompt(...)` instances
  (`"feed_domain_object_analysis"`, `"feed_field_mapping"`,
  `"lookup_mapping"`).

## Tests

- `test_prompt.py`: `Prompt` loads a fixture YAML, `.set()` + `.get_prompt()`
  substitutes correctly; a template referencing an unset field returns
  `""` for that field and logs a warning (assert via `caplog`); a
  template with no merge fields at all round-trips unchanged; confirm
  `$name` next to a literal `{name}`-style brace passes through the brace
  untouched (regression test tied directly to the `{source_field}_ref`
  case in `mapping.yaml`).
- Per-call-site test: for each of the 5 updated functions, assert the
  final system/user prompt text sent to the (mocked) adapter is
  byte-for-byte identical to what it was before this migration, for at
  least one representative input (with and without optional sections
  present, e.g. a feed with and without `mapping_hints`).
- Rerun the full existing suite for `review.py`, `source_analysis.py`,
  `fibers.py` — none of their assertions should change, since the
  rendered prompt text isn't supposed to change, only where it's
  authored.

## Verification

- `mypy --strict` / `ruff` clean (note: `PyYAML`'s type stubs — confirm
  `types-PyYAML` is available/installed if `mypy --strict` flags
  `yaml.safe_load`'s return type).
- Manually trigger each of the 5 AI calls against a real or mocked
  adapter and diff the logged `ai_call_log.system_prompt`/`user_prompt`
  against pre-migration output — should be identical.
- Confirm a deliberately-misspelled `.set()` kwarg (e.g. `dll=ddl` typo)
  produces a logged warning and an empty substitution, not a crash and
  not a silently-wrong-but-unnoticed prompt.

## Pitfalls

- `string.Template.substitute()` (not `.safe_substitute()`) is required
  for the warn-and-drop behavior — `.safe_substitute()` would leave
  unmatched `$name` text literally in the prompt sent to the AI, which
  is worse than either failing loudly or dropping cleanly.
- Don't let `Prompt.get_prompt()` warn on every call for the routine
  case of an *intentionally* empty optional section — per the task's
  requirement 4, call sites must `.set(section="")` explicitly for those,
  not simply omit the key. Verify each of the 5 migrated call sites does
  this for every optional section rather than only setting the "on"
  case.
- `submit_lookup_inputs`'s `$payload` field contains a JSON string that
  itself is full of `{ }` characters — confirms the `$name` (not `{name}`)
  choice matters even more here; a bare-brace scheme would try to
  re-parse the JSON payload's own braces as further merge fields.
- YAML block-scalar (`|`) preserves a trailing newline by default — check
  whether the exact byte-for-byte match in the Tests section needs a
  `.rstrip()` somewhere to match the current f-string output, which
  generally doesn't end in a trailing newline.

## Commit

Own commit. No ordering dependency on 001dy/001dz — touches the same
three files 001ea/001eb/001ec already modified this session, so rebase
carefully if any of those are still in flight.
