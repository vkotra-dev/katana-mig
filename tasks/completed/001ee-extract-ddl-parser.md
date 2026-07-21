# Plan: 001ee — Extract DDL Parsing into mapping/ddl.py

## Task and Domain links

- Task: `tasks/001ee-extract-ddl-parser.md`
- Domain: none — internal module organization, no behavior change

## Current State

- `mapping/review.py:25-31`: `_TABLE_RE`, `_COLUMN_RE`, `_CONSTRAINT_PREFIXES`.
- `mapping/review.py:36-73`: `_parse_all_ddl_tables(ddl: str) -> dict[str, list[str]]`.
- `mapping/review.py:75-107`: `_parse_ddl(ddl: str) -> tuple[str, list[str]]`.
- Call sites, all inside `review.py` (confirmed via grep — zero external references):
  - `_parse_ddl` called once, at `review.py:128` inside `_get_project_destination_schema`.
  - `_parse_all_ddl_tables` called twice: `review.py:190` inside `derive_destination_fields`,
    and `review.py:292` inside `propose_mapping`.
- No test file imports or monkeypatches either function.

## Objective

1. New `mapping/ddl.py` holding the parsing code, functions renamed without the leading
   underscore.
2. `review.py` imports from it; its 3 internal call sites updated to the new names.

## Out of Scope

- `snapshots.py`/`proposal.py` extraction — 001ef/001eg.
- Any parsing-logic change.

## Blast Radius

- `engine/src/migrations_engine/mapping/ddl.py` (new)
- `engine/src/migrations_engine/mapping/review.py` (edited — ~85 lines removed, 1 import line
  added, 3 call sites renamed)
- `engine/tests/test_ddl.py` (new — see Tests)
- No route, API, or other-module changes.

## File Changes

**`engine/src/migrations_engine/mapping/ddl.py` (new)**
```python
from __future__ import annotations

import re

_TABLE_RE = re.compile(
    r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?(?:[\w$]+\.)?\"?(?P<table>[\w$]+)\"?",
    re.IGNORECASE,
)
_COLUMN_RE = re.compile(r'^\s*["`]?(?P<name>[A-Za-z_][\w$]*)["`]?\s+[A-Za-z]')
_CONSTRAINT_PREFIXES = ("CONSTRAINT", "PRIMARY", "UNIQUE", "FOREIGN", "CHECK")


def parse_all_ddl_tables(ddl: str) -> dict[str, list[str]]:
    ...  # body moved verbatim from _parse_all_ddl_tables


def parse_ddl(ddl: str) -> tuple[str, list[str]]:
    ...  # body moved verbatim from _parse_ddl
```
(bodies copied exactly as they exist today — no logic change)

**`engine/src/migrations_engine/mapping/review.py`**
- Delete lines 25-107 (the regexes + both functions).
- Add `from .ddl import parse_all_ddl_tables, parse_ddl` near the top, alongside the other
  intra-package imports.
- `review.py:128`: `table_name, columns = _parse_ddl(ddl)` → `parse_ddl(ddl)`.
- `review.py:190`: `ddl_tables = _parse_all_ddl_tables(ddl)` → `parse_all_ddl_tables(ddl)`.
- `review.py:292`: same rename.

## Tests

- New `engine/tests/test_ddl.py`: move (not duplicate) any existing DDL-parsing test coverage
  currently embedded in `test_mapping_review_api.py` if such tests exist there directly
  targeting `_parse_all_ddl_tables`/`_parse_ddl` (check before assuming none do); otherwise add
  basic coverage — multi-table DDL, quoted identifiers, constraint lines skipped — against the
  new `parse_all_ddl_tables`/`parse_ddl` names.
- Full `test_mapping_review_api.py` run — should pass unchanged, since these functions' behavior
  and all call sites within `review.py` are identical, just renamed/relocated.

## Verification

- `mypy --strict` / `ruff` clean on both files.
- `git diff --stat`: confirm this is a "boring" diff — content moved, 3 renames, nothing else
  changed.
- Full test suite green.

## Pitfalls

- Don't move `_CONSTRAINT_PREFIXES`/regexes without also moving the functions that use them in
  the same commit — a half-moved state won't import.
- Double-check no other in-flight branch also touches these exact lines before starting (none
  currently do per this session's task list).

## Commit

Own commit, first of three (001ee → 001ef → 001eg).
