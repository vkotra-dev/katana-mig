---
type: Summary
task: 001ev-codegen-logging-prompt-extraction
date: 2026-07-23
outcome: completed
---

# Summary: 001ev — Extract codegen mig_upsert_log prompt instructions

## What was done

Extracted the `mig_upsert_log` audit-logging prompt instructions (rules 17–21) from each
platform block in `codegen_coding_standards.yaml` into a new standalone file
`codegen_logging_standards.yaml`. Updated the renderer to load and append both files.
No behavior change. 364/364 full-suite tests pass.

## File changes

| File | Change |
|------|--------|
| `engine/src/migrations_engine/ai/prompts/codegen_coding_standards.yaml` | Trimmed: rules 17–21 removed from all four platform blocks (postgresql, mssql, oracle, mysql). General blocks now end at rule 16 + its pattern example. Line count: 217 → 188. |
| `engine/src/migrations_engine/ai/prompts/codegen_logging_standards.yaml` | **New file.** Four platform keys (`postgresql`, `mssql`, `oracle`, `mysql`). Each contains rules 17–21 verbatim from the original, under a `## mig_upsert_log Audit Logging Pattern` header. 38 lines. |
| `engine/src/migrations_engine/codegen/coding_standards.py` | Added `_LOGGING_YAML_PATH` constant. `render_coding_standards_template` now loads both YAML files, applies the same `$stg/$dest/$engineName` Template substitution to the logging block, and appends it after the general block. Unknown engine → silent skip (no exception). |
| `engine/tests/test_codegen_coding_standards.py` | Added 6 new tests (11 → 17 total). |

## New tests

| Test | Guards |
|------|--------|
| `test_mssql_logging_block_comes_from_separate_file` | Both files assembled for mssql; general + logging + footer all present |
| `test_postgresql_logging_block_substitutes_schema_placeholders` | `$stg`/`$dest` substituted correctly in logging file for postgresql |
| `test_mssql_logging_block_substitutes_schema_placeholders` | Same for mssql |
| `test_oracle_logging_block_substitutes_schema_placeholders` | Same for oracle |
| `test_mysql_logging_block_substitutes_schema_placeholders` | Same for mysql |
| `test_unknown_engine_has_no_logging_block_and_does_not_error` | Missing key in logging file → silent skip, no mig_upsert_log in output |

## Notes

- `mig_upsert_log` still appears twice in `codegen_coding_standards.yaml` inside rule 4
  of the mssql and mysql blocks (incidental references in the `_row_num` staging-column
  description). These are not logging-pattern instructions and were intentionally left in place.
- Renderer output is byte-identical to the pre-refactor output for all four platforms.
- No API, DB, or UI changes.

## Verification

```
pytest engine/tests/test_codegen_coding_standards.py  → 17 passed
pytest engine/tests/                                   → 364 passed
```
