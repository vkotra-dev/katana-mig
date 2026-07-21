# Summary: 001ed — Shared Prompt Class (YAML-backed, merge-field templating)

## What was built
The five hardcoded system/user prompts (`review.py::propose_mapping`,
`source_analysis.py::analyze_source_slice`, and three in `fibers.py`) now live in YAML template
files with a reusable `Prompt` class, instead of being edited as Python string literals every
time the wording needs to change.

### Key changes
- **`ai/prompt.py`**: generic `Prompt(name)` class — `.set(**kwargs)` accumulates merge fields,
  `.get_prompt()` returns `(system, user)` via `string.Template.substitute()` with a
  `_WarnOnMissing(dict)` fallback (`__missing__` logs a warning and returns `""` for any
  unsupplied field) rather than raising or leaving raw `$name` text behind.
- **`ai/prompts/*.yaml`** (5 new files): `mapping.yaml`, `source_analysis.yaml`,
  `feed_domain_object_analysis.yaml`, `feed_field_mapping.yaml`, `lookup_mapping.yaml` — each
  with `system:`/`user:` block-scalar keys, content migrated verbatim from the Python strings.
- **`$name` merge-field syntax** (not bare `{name}`): required because the mapping prompt already
  contains a literal `{source_field}_ref` example shown to the AI, which bare-brace substitution
  would have corrupted.
- **Call sites updated**: all five now build a `Prompt`, `.set()` their merge fields (including
  explicit `""` for intentionally-absent optional sections, e.g. missing mapping hints), and use
  `.get_prompt()`'s output — codegen's separate, pre-existing Jinja2 template mechanism was left
  untouched since it already worked.
- **Optional-section spacing fix**: `mapping.yaml` originally had two separate optional-section
  placeholders in sequence, which produced an extra blank line when only one was populated (a
  `.strip()`-uncatchable mid-string gap). Fixed by moving the join logic back into Python
  (`extra_context = "\n\n" + "\n\n".join(...)  if ... else ""`) so the template just does
  `$ddl$extra_context`, matching the original code's exact spacing in every combination.

## Verification
`test_prompt.py` covers the `Prompt` class mechanics (missing-field warning, literal-brace
pass-through). `test_prompt_backward_compatibility.py` asserts byte-for-byte parity against the
original hardcoded prompt strings for `source_analysis` and `mapping`, including all three
combinations of the mapping prompt's optional sections (both present, constraints-only, neither).
