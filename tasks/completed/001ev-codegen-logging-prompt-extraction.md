---
type: Task
id: 001ev
slug: 001ev-codegen-logging-prompt-extraction
title: Extract codegen mig_upsert_log prompt instructions into a separate YAML file
status: ready
domain: docs/domain/governance.md
plan: plans/2026-07-23-001ev-codegen-logging-prompt-extraction.md
---

## Context

`engine/src/migrations_engine/ai/prompts/codegen_coding_standards.yaml` is a 217-line
prompt-content file. Each platform block (`postgresql`, `mssql`, `mysql`, `oracle`) contains
21 numbered migration SP requirements. Rules 17–21 in every platform block are specific to the
`mig_upsert_log` audit-logging contract — they describe the exact DML idiom (OUTPUT clause,
RETURNING + BULK COLLECT, ROW_COUNT/LAST_INSERT_ID, CTE+xmax, etc.) the LLM must use to write
to the runtime logging table injected by `_mig_upsert_log_ddl`.

These logging rules evolve at a different cadence from the general coding conventions (rules 1–16)
and are harder to find and edit when buried inside a large mixed file.

## Objective

Split the `mig_upsert_log`-specific prompt rules (17–21 in each platform) out of
`codegen_coding_standards.yaml` into a new standalone file
`engine/src/migrations_engine/ai/prompts/codegen_logging_standards.yaml`.

Update `render_coding_standards_template` in `coding_standards.py` to load and append the
matching platform block from the new file so the rendered output is identical to today's.

No behavior change. No API change. No DB change. Tests must stay green.

## Out of Scope

- Changing the content of any rule (copy exactly, do not rephrase)
- Changing `_mig_upsert_log_ddl` or the SQL bundle assembler
- Changing the codegen endpoint or its response schema
- Any new platform support

## Acceptance

- `codegen_logging_standards.yaml` exists with four keys: `postgresql`, `mssql`, `oracle`, `mysql`
- Each key contains exactly rules 17–21 from the corresponding platform block in the original YAML
  (and nothing else)
- Those rules are removed from `codegen_coding_standards.yaml`; the general blocks end at rule 16
  (and the rule-16 pattern example)
- `render_coding_standards_template` appends the logging block after the general block in its
  rendered output; the `$stg`/`$dest`/`$engineName` substitutions apply to the logging block too
- All existing tests in `test_codegen_coding_standards.py` pass without modification
  (assertions for `mig_upsert_log` content still hold because the renderer still includes it)
- `test_codegen_coding_standards.py` gains at least one new test that asserts the logging
  content is present even when the general block is verified, proving the two files are
  assembled correctly
