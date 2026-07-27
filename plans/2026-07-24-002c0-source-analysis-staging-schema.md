# Source Analysis: Inject staging_schema into prompt

**Task:** [002c0](../tasks/002c0-source-analysis-staging-schema-into-prompt.md)
**Domain:** source-model

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Inject both `staging_schema` and `target_db_engine` from `project_definition.domain_config` into the source analysis AI prompt so it generates schema-qualified, target-engine-appropriate `CREATE TABLE` DDL (e.g. `CREATE TABLE staging.my_table (policy_id VARCHAR(20) NOT NULL)` for PostgreSQL).

**Current gap:** The code reads `target_db_engine` from `domain_config` and passes it to the prompt, but ignores `staging_schema`. The AI therefore has no schema context — it generates bare `CREATE TABLE my_table (...)` without any schema qualification.

**Files touched:**
- `engine/src/migrations_engine/ai/prompts/source_analysis.yaml` — add `$staging_schema` placeholder
- `engine/src/migrations_engine/management/source_analysis.py` — extract and pass `staging_schema` to the prompt

**Tech Stack:** Python, string.Template substitution, FastAPI.

---

### Task: Add staging_schema to source analysis prompt

**Files:**
- `engine/src/migrations_engine/ai/prompts/source_analysis.yaml`
- `engine/src/migrations_engine/management/source_analysis.py`

**Interfaces:**
- Consumes: `project_definition.domain_config["staging_schema"]` (str | None)
- Already passes: `target_db_engine` from same `domain_config` — keep passing it
- Produces: Modified prompt template + analysis code that injects both `staging_schema` and `target_db_engine`

**[ ] Step 1: Update source_analysis.yaml prompt template**

Current `source_analysis.yaml` system section (lines 1-10):
```yaml
system: |
  You are a data analyst. Given CSV or fixed-length record samples, infer column schemas and generate a SQL DDL statement.
  CRITICAL RULES:
  1. Column Order & Names: ...
  5. SQL DDL Generation: Using the inferred columns and the target database engine '$target_db_engine', generate a valid CREATE TABLE SQL statement. ...
```

Add a new rule before the SQL DDL rule (after rule 4) and modify rule 5 to use `$staging_schema`:

Add after the existing rules, before rule 5:
```
  4. Schema Qualification: If a staging schema name is provided ('$staging_schema'), qualify ALL table names in the DDL with this schema (e.g. CREATE TABLE $staging_schema.my_table (...)). If no schema is provided ('$staging_schema' is empty), use bare table names.
```

Modify rule 5 to reference the schema-qualified table name:
```
  5. SQL DDL Generation: Using the inferred columns, the target database engine '$target_db_engine', and the schema name '$staging_schema', generate a valid CREATE TABLE SQL statement. ...
```

**[ ] Step 2: Update source_analysis.py to pass staging_schema**

In `engine/src/migrations_engine/management/source_analysis.py`, find lines 85-93:

Current code (line 85-93):
```python
target_db = project_definition.domain_config.get("target_db_engine", "postgresql") if project_definition.domain_config else "postgresql"

from ..ai.prompt import Prompt
prompt = Prompt("source_analysis")
prompt.set(
    source_type_section=source_type_section,
    sample_text=sample_text,
    target_db_engine=target_db,
)
```

Change to:
```python
target_db = project_definition.domain_config.get("target_db_engine", "postgresql") if project_definition.domain_config else "postgresql"
staging_schema = project_definition.domain_config.get("staging_schema") if project_definition.domain_config else None

from ..ai.prompt import Prompt
prompt = Prompt("source_analysis")
prompt.set(
    source_type_section=source_type_section,
    sample_text=sample_text,
    target_db_engine=target_db,
    staging_schema=staging_schema or "",
)
```

**[ ] Step 3: Verify syntax**

```bash
cd engine && .venv/bin/python -c "from migrations_engine.management.source_analysis import analyze_source_slice; print('OK')"
```

**[ ] Step 4: Test**

Run the existing source analysis tests to confirm no regressions:
```bash
cd engine && .venv/bin/pytest tests/test_source_analysis_api.py tests/test_source_analysis_service.py -v
```

Expected: all pass.

## Verification

After the change, a source analysis run with `staging_schema` set in the project config will produce DDL like:
```sql
CREATE TABLE staging.policy_claim (
  policy_id VARCHAR(20) NOT NULL,
  ...
);
```

Without `staging_schema` set, DDL is unchanged:
```sql
CREATE TABLE policy_claim (
  policy_id VARCHAR(20) NOT NULL,
  ...
);
```

## Pitfalls

1. **`$` in string.Template**: The `Prompt` class uses `string.Template`. Any literal `$` in the template that is NOT a placeholder must be escaped as `$$`. The `$staging_schema` and `$target_db_engine` references are valid placeholders — no escaping needed.

2. **Empty string handling**: When `staging_schema` is `None`, we pass `""` (empty string). The prompt template should handle this via the conditional wording in rule 4 ("If a staging schema name is provided...").

3. **Backwards compatibility**: `target_db_engine` already defaults to `"postgresql"` if absent. `staging_schema` is now also handled the same way. Existing `SourceSchemaArtifact` rows with bare table DDL are unaffected — only new analyses are affected.
