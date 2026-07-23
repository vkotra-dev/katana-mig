---
type: Plan
task: 001ev-codegen-logging-prompt-extraction
date: 2026-07-23
---

# Plan: 001ev — Extract codegen mig_upsert_log prompt instructions

**Task:** [001ev-codegen-logging-prompt-extraction](../tasks/001ev-codegen-logging-prompt-extraction.md)  
**Domain:** [governance.md](../docs/domain/governance.md)

---

## Current State

### Files involved (read all of these before touching anything)

| File | Role |
|------|------|
| `engine/src/migrations_engine/ai/prompts/codegen_coding_standards.yaml` | 217-line YAML with four platform keys. Each key is a YAML block-scalar containing 21 numbered rules + shared header/footer keys. **Rules 17–21 in every platform block are the mig_upsert_log logging instructions.** |
| `engine/src/migrations_engine/codegen/coding_standards.py` | 35-line renderer. Loads the YAML, builds a `mapping` dict (`$stg`, `$dest`, `$engineName`), applies `string.Template.substitute()` to the platform block, then returns `header + specific + footer`. |
| `engine/tests/test_codegen_coding_standards.py` | 11 tests covering renderer output for each platform. Several tests (`test_postgresql_standards_include_migration_sp_requirements`, `test_mysql_standards_include_migration_sp_requirements`, `test_oracle_standards_include_migration_sp_requirements`) assert `mig_upsert_log` content is present in the rendered output. All must keep passing. |

### What "rules 17–21" contain per platform

**postgresql (lines 19–74 in YAML):**
- Rule 17: `WITH upserted AS (INSERT ... ON CONFLICT ... RETURNING) INSERT INTO $stg.mig_upsert_log ...`; xmax=0 idiom explained.
- Rule 18: Duplicate source-key check before upsert; RAISE EXCEPTION.
- Rule 19: Lookup seed idempotency — INSERT ON CONFLICT DO NOTHING.
- Rule 20: UNIQUE constraint on lookup code columns.
- Rule 21: FK pre-flight validation before upsert; RAISE EXCEPTION.

**mssql (lines 75–132):**
- Rule 17: OUTPUT clause logging to `[$stg].[mig_upsert_log]`; explicit column list required; result set with run_ref, rows_inserted, rows_updated after all MERGEs.
- Rule 18: Duplicate source-key check before MERGE; THROW.
- Rule 19: Lookup seed idempotency — IF NOT EXISTS / INSERT WHERE NOT EXISTS.
- Rule 20: UNIQUE constraint or index on lookup code columns.
- Rule 21: FK pre-flight validation before MERGE; THROW.

**oracle (lines 133–180):**
- Rule 17: RETURNING ... BULK COLLECT INTO v_dest_ids/v_source_rows; FORALL insert into `$stg.mig_upsert_log`; action known statically per UPDATE/INSERT statement.
- Rule 18: Duplicate source-key check before UPDATE/INSERT pair; RAISE_APPLICATION_ERROR.
- Rule 19: Lookup seed idempotency — INSERT INTO … SELECT … WHERE NOT EXISTS.
- Rule 20: UNIQUE constraint or index on lookup code columns.
- Rule 21: FK pre-flight validation; RAISE_APPLICATION_ERROR.

**mysql (lines 181–218):**
- Rule 17: Per-row logging via ROW_COUNT()/LAST_INSERT_ID(); cursor-based; batch-commit every 500 rows.
- Rule 18: Duplicate source-key check before cursor loop; SIGNAL SQLSTATE.
- Rule 19: Lookup seed idempotency — INSERT IGNORE or INSERT ON DUPLICATE KEY UPDATE.
- Rule 20: UNIQUE KEY on lookup code columns.
- Rule 21: Pre-flight SELECT COUNT(*) WHERE resolved_fk IS NULL; SIGNAL SQLSTATE.

### Renderer mechanics (coding_standards.py)

```python
mapping = {"dest": dest, "stg": stg, "engineName": engine_name}
header   = Template(data["shared_header"]).substitute(mapping).rstrip("\n")
footer   = data["shared_footer"].rstrip("\n")
specific_raw = data.get(engine_key, "")          # platform block, may contain $stg/$dest

if specific_raw:
    specific = Template(specific_raw).substitute(mapping)
    header = header + "\n" + specific.rstrip("\n")

return f"{header}\n\n{footer}"
```

The substitution variables used inside the platform blocks are: `$stg`, `$dest`, `$engineName`.
These same variables appear inside the logging rules (e.g. `$stg.mig_upsert_log`, `$dest.dest_table`).

---

## Objective

Extract rules 17–21 from each platform block in `codegen_coding_standards.yaml` into a new file
`codegen_logging_standards.yaml`. Update the renderer to load the new file and append the
matching logging block to the rendered output. No rule content changes. No behavior change.

---

## Out of Scope

- Content edits to any rule text
- `_mig_upsert_log_ddl` (Python DDL function) — untouched
- `_assemble_sql_bundle` — untouched
- API routes or response schemas — untouched
- No new platform support

---

## Blast Radius

| Layer | Impact |
|-------|--------|
| `codegen_coding_standards.yaml` | Remove rules 17–21 from each platform block |
| `codegen_logging_standards.yaml` | New file — created from scratch |
| `coding_standards.py` | Add second YAML load + append; signature unchanged |
| `test_codegen_coding_standards.py` | Existing tests unchanged; add ≥1 new test |
| DB / migrations | None |
| API contracts | None |
| UI | None |

---

## File Changes

### Step 1 — Create `codegen_logging_standards.yaml`

**Path:** `engine/src/migrations_engine/ai/prompts/codegen_logging_standards.yaml`

This file is new. Copy **verbatim** rules 17–21 (and only those) from each platform block into
the matching key in the new file.

Structure:

```yaml
postgresql: |2
       ## mig_upsert_log Audit Logging Pattern
         17. <exact text from codegen_coding_standards.yaml postgresql rule 17>
         18. <exact text from codegen_coding_standards.yaml postgresql rule 18>
         19. <exact text from codegen_coding_standards.yaml postgresql rule 19>
         20. <exact text from codegen_coding_standards.yaml postgresql rule 20>
         21. <exact text from codegen_coding_standards.yaml postgresql rule 21>

mssql: |2
       ## mig_upsert_log Audit Logging Pattern
         17. <exact text from codegen_coding_standards.yaml mssql rule 17>
         ...

oracle: |2
       ## mig_upsert_log Audit Logging Pattern
         17. <exact text from codegen_coding_standards.yaml oracle rule 17>
         ...

mysql: |2
       ## mig_upsert_log Audit Logging Pattern
         17. <exact text from codegen_coding_standards.yaml mysql rule 17>
         ...
```

**Copy rules 17–21 verbatim. Do not add, remove, or rephrase a single word.**

The `|2` block-scalar indicator and two-space indent used in `codegen_coding_standards.yaml`
must be preserved exactly so YAML parsing is consistent.

Rules 17–21 contain `$stg` and `$dest` variables — these must remain in the new file so
`string.Template.substitute()` expands them correctly at render time.

---

### Step 2 — Edit `codegen_coding_standards.yaml`

Remove rules 17–21 from each of the four platform blocks.

**For each platform block, the last retained content is:**
- The body of rule 16 (the CRITICAL lookup-tables rule) plus its accompanying pattern example
  (the `The correct pattern is:` block with the SQL sample).

Concretely, after editing:
- `postgresql` block ends after the rule-16 pattern example (the `Then reference resolved_fk1_id …` line).
- `mssql` block ends after `Then reference source.resolved_fk1_id and source.resolved_fk2_id …`.
- `oracle` block ends after `(and equivalently in the paired INSERT ... SELECT ... WHERE NOT EXISTS statement)`.
- `mysql` block ends after `WHERE s.pk_column IS NOT NULL;`.

**Do not touch `shared_header` or `shared_footer`.**

After removing rules 17–21, run a quick sanity check:
```bash
grep -c "mig_upsert_log" engine/src/migrations_engine/ai/prompts/codegen_coding_standards.yaml
# Expected output: 0
```

---

### Step 3 — Edit `coding_standards.py`

**Path:** `engine/src/migrations_engine/codegen/coding_standards.py`

Add a second YAML path constant and update `render_coding_standards_template` to:
1. Load `codegen_logging_standards.yaml` alongside the existing file.
2. Look up the platform-specific logging block using the same `engine_key`.
3. Apply `Template.substitute(mapping)` to the logging block (same mapping dict already built).
4. Append the logging block to the output, separated by a newline.

**Before (current `render_coding_standards_template`):**

```python
_YAML_PATH = Path(__file__).parent.parent / "ai" / "prompts" / "codegen_coding_standards.yaml"

def render_coding_standards_template(
    *,
    db_engine: str | None,
    staging_schema: str | None,
    destination_schema: str | None,
) -> str:
    data = yaml.safe_load(_YAML_PATH.read_text(encoding="utf-8"))

    engine_name = db_engine or "target database"
    stg = staging_schema or "staging"
    dest = destination_schema or "destination"
    lower_engine = (db_engine or "").lower()
    engine_key = "mssql" if lower_engine == "sqlserver" else lower_engine

    mapping = {"dest": dest, "stg": stg, "engineName": engine_name}
    header = Template(data["shared_header"]).substitute(mapping).rstrip("\n")
    footer = data["shared_footer"].rstrip("\n")
    specific_raw = data.get(engine_key, "")

    if specific_raw:
        specific = Template(specific_raw).substitute(mapping)
        header = header + "\n" + specific.rstrip("\n")

    return f"{header}\n\n{footer}"
```

**After:**

```python
_YAML_PATH = Path(__file__).parent.parent / "ai" / "prompts" / "codegen_coding_standards.yaml"
_LOGGING_YAML_PATH = Path(__file__).parent.parent / "ai" / "prompts" / "codegen_logging_standards.yaml"

def render_coding_standards_template(
    *,
    db_engine: str | None,
    staging_schema: str | None,
    destination_schema: str | None,
) -> str:
    data = yaml.safe_load(_YAML_PATH.read_text(encoding="utf-8"))
    logging_data = yaml.safe_load(_LOGGING_YAML_PATH.read_text(encoding="utf-8"))

    engine_name = db_engine or "target database"
    stg = staging_schema or "staging"
    dest = destination_schema or "destination"
    lower_engine = (db_engine or "").lower()
    engine_key = "mssql" if lower_engine == "sqlserver" else lower_engine

    mapping = {"dest": dest, "stg": stg, "engineName": engine_name}
    header = Template(data["shared_header"]).substitute(mapping).rstrip("\n")
    footer = data["shared_footer"].rstrip("\n")
    specific_raw = data.get(engine_key, "")
    logging_raw = logging_data.get(engine_key, "")

    if specific_raw:
        specific = Template(specific_raw).substitute(mapping)
        header = header + "\n" + specific.rstrip("\n")

    if logging_raw:
        logging_block = Template(logging_raw).substitute(mapping)
        header = header + "\n" + logging_block.rstrip("\n")

    return f"{header}\n\n{footer}"
```

**Key points:**
- `_LOGGING_YAML_PATH` mirrors the path pattern of `_YAML_PATH`.
- The same `mapping` dict is reused — no new variables.
- `logging_raw` is looked up with the same `engine_key` used for the general block.
- If `engine_key` has no entry in the logging file (e.g. unknown engine), `logging_raw` is `""` and the block is silently skipped — matching the existing fallback behavior.
- The function signature is unchanged; callers in `routes/projects.py` need no update.

---

### Step 4 — Update `test_codegen_coding_standards.py`

**Path:** `engine/tests/test_codegen_coding_standards.py`

#### Existing tests — do not touch, must all still pass

These 11 tests already exist and must remain green without modification.
The renderer change in Step 3 is additive — it appends logging content after the general block.
Existing assertions remain valid because the content they check is still in the rendered output.

Tests that explicitly check `mig_upsert_log` content and must keep passing:
- `test_postgresql_standards_include_migration_sp_requirements` — asserts `stg.mig_upsert_log`, `xmax = 0`, `gen_random_uuid()`
- `test_mysql_standards_include_migration_sp_requirements` — asserts `stg.mig_upsert_log`, `ROW_COUNT()`, `row-by-row`
- `test_oracle_standards_include_migration_sp_requirements` — asserts `stg.mig_upsert_log`, `BULK COLLECT INTO`, `RETURNING`, `does not support RETURNING`

#### New tests — append all of the following to the end of the file

Add exactly these six tests. Each one has a precise purpose stated in its docstring.

```python
# ── New tests for 001ev: codegen logging prompt extraction ──────────────────


def test_mssql_logging_block_comes_from_separate_file():
    """General block (from codegen_coding_standards.yaml) and logging block
    (from codegen_logging_standards.yaml) are both present in mssql output.
    mssql is the only platform NOT covered by the three existing mig_upsert_log
    assertions, so this is the primary regression guard for the split."""
    result = render_coding_standards_template(
        db_engine="mssql", staging_schema="stg", destination_schema="cxp"
    )
    # General block still present
    assert "SET XACT_ABORT ON immediately after SET NOCOUNT ON" in result
    # Logging block from new file is appended
    assert "stg.mig_upsert_log" in result
    assert "OUTPUT" in result
    # Shared footer still appended last
    assert "General Best Practices" in result


def test_postgresql_logging_block_substitutes_schema_placeholders():
    """$stg and $dest in the logging file are substituted correctly for postgresql."""
    result = render_coding_standards_template(
        db_engine="postgresql", staging_schema="my_stg", destination_schema="my_dest"
    )
    assert "my_stg.mig_upsert_log" in result
    assert "$stg" not in result
    assert "$dest" not in result


def test_mssql_logging_block_substitutes_schema_placeholders():
    """$stg and $dest in the logging file are substituted correctly for mssql."""
    result = render_coding_standards_template(
        db_engine="mssql", staging_schema="my_stg", destination_schema="my_dest"
    )
    assert "my_stg.mig_upsert_log" in result
    assert "$stg" not in result
    assert "$dest" not in result


def test_oracle_logging_block_substitutes_schema_placeholders():
    """$stg and $dest in the logging file are substituted correctly for oracle."""
    result = render_coding_standards_template(
        db_engine="oracle", staging_schema="my_stg", destination_schema="my_dest"
    )
    assert "my_stg.mig_upsert_log" in result
    assert "$stg" not in result
    assert "$dest" not in result


def test_mysql_logging_block_substitutes_schema_placeholders():
    """$stg and $dest in the logging file are substituted correctly for mysql."""
    result = render_coding_standards_template(
        db_engine="mysql", staging_schema="my_stg", destination_schema="my_dest"
    )
    assert "my_stg.mig_upsert_log" in result
    assert "$stg" not in result
    assert "$dest" not in result


def test_unknown_engine_has_no_logging_block_and_does_not_error():
    """An unrecognized engine key that has no entry in codegen_logging_standards.yaml
    must not raise; it silently omits the logging block."""
    result = render_coding_standards_template(
        db_engine="sqlite", staging_schema="stg", destination_schema="dest"
    )
    # Shared content still present
    assert "General Best Practices" in result
    # No mig_upsert_log injected for unknown engine
    assert "mig_upsert_log" not in result
```

**Total new tests: 6**

| Test name | What it guards |
|-----------|----------------|
| `test_mssql_logging_block_comes_from_separate_file` | Both files are loaded and assembled for mssql (the platform not covered by existing assertions) |
| `test_postgresql_logging_block_substitutes_schema_placeholders` | `$stg`/`$dest` Template substitution works inside the logging file for postgresql |
| `test_mssql_logging_block_substitutes_schema_placeholders` | Same, for mssql |
| `test_oracle_logging_block_substitutes_schema_placeholders` | Same, for oracle |
| `test_mysql_logging_block_substitutes_schema_placeholders` | Same, for mysql |
| `test_unknown_engine_has_no_logging_block_and_does_not_error` | Fallback: missing key in logging file → silent skip, no exception |

---

## Tests

Run only the affected test file after each step for fast feedback:

```bash
pytest engine/tests/test_codegen_coding_standards.py -v
```

Expected total after Step 4: **17 passed** (11 existing + 6 new).

Full suite before committing:

```bash
pytest engine/tests/ -q
```

If `mig_upsert_log` tests fail after Step 3, the renderer is not appending the logging block —
re-check that `logging_raw = logging_data.get(engine_key, "")` and the `if logging_raw:` block
are both present and not inside the `if specific_raw:` guard.

---

## Verification

After all steps:

```bash
# 1. No mig_upsert_log left in the general standards file
grep "mig_upsert_log" engine/src/migrations_engine/ai/prompts/codegen_coding_standards.yaml
# → no output

# 2. All four platform keys exist in the logging file
python3 -c "
import yaml
d = yaml.safe_load(open('engine/src/migrations_engine/ai/prompts/codegen_logging_standards.yaml').read())
assert set(d.keys()) == {'postgresql', 'mssql', 'oracle', 'mysql'}, d.keys()
print('OK:', list(d.keys()))
"

# 3. Renderer output still contains mig_upsert_log for all platforms
python3 -c "
from engine.src.migrations_engine.codegen.coding_standards import render_coding_standards_template as r
for engine in ['postgresql', 'mssql', 'oracle', 'mysql']:
    out = r(db_engine=engine, staging_schema='stg', destination_schema='dest')
    assert 'mig_upsert_log' in out, f'{engine}: mig_upsert_log missing'
    print(f'{engine}: OK')
"

# 4. Tests pass
pytest engine/tests/test_codegen_coding_standards.py -v
```

---

## Pitfalls

| Risk | Mitigation |
|------|------------|
| YAML indentation errors in the new file | Use the same `\|2` block-scalar indicator and two-space indent body as the source file. Validate with `python3 -c "import yaml; yaml.safe_load(open(...).read())"` after writing. |
| `$stg` / `$dest` variable references not substituted | Both files use `string.Template.substitute(mapping)` with the same `mapping` dict. If a `$` variable is forgotten in the logging file, the render will raise `KeyError`. Test immediately after Step 3. |
| Leaving a stray rule-17+ line in `codegen_coding_standards.yaml` | After Step 2, run `grep "mig_upsert_log" codegen_coding_standards.yaml` — must return empty. |
| Rules 18–21 are not purely about logging (they cover FK validation and seed idempotency) | Move them anyway as-is; the task scope is per the brainstorm decision. Do not rewrite rule text. |
| `string.Template` fails on `$$` (escaped dollar) in the mssql block | The mssql oracle blocks use `$$PLSQL_UNIT` — that is Oracle, not mssql. Check oracle block carefully. `$$` in `string.Template` renders as a literal `$`, so `$$PLSQL_UNIT` → `$PLSQL_UNIT`. This is correct existing behavior; do not change it. |

---

## Commit

Single commit after all steps pass:

```
refactor(codegen): extract mig_upsert_log prompt instructions to codegen_logging_standards.yaml

- Create engine/src/migrations_engine/ai/prompts/codegen_logging_standards.yaml
  with rules 17–21 from each platform block (postgresql, mssql, oracle, mysql).
- Remove rules 17–21 from codegen_coding_standards.yaml; general blocks now end at rule 16.
- Update render_coding_standards_template in coding_standards.py to load and append
  the logging block from the new file; same substitution mapping applied.
- Add regression test to verify both files are assembled in the rendered output.
- No behavior change; all existing tests pass.
```

Stage: both YAML files + `coding_standards.py` + `test_codegen_coding_standards.py`.
