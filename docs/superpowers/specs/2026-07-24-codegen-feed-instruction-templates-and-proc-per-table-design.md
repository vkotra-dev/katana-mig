# Codegen: Multi-Table Artifact Generation, Feed Instructions & One-Proc-Per-Table Design

## Problem

Three issues in the codegen system:

1. **Root issue — only first table codegen'd**: `_primary_destination_object_name()` (service.py:369) returns `references[0]` only. `generate_codegen_artifact()` is called once from the route (routes/codegen.py:33), processing only one table. If a feed maps to multiple destination tables, only the first table gets a codegen artifact. `build_delivery_bundle_text` already handles multiple artifacts but no second artifact is ever created.

2. **Lookup tables omitted**: `_select_lookup_snapshot_version()` (service.py:426-449) returns on the first lookup snapshot found, silently dropping all others. The AI only generates DDL/seed for one lookup table per artifact.

3. **Feed-specific instructions are raw text**: User-entered transformation instructions are dumped raw into the user prompt (`user_prompt.txt.j2` line 24-27) without consistent framing. Unlike coding standards (which go through `render_coding_standards_template()`), there is no YAML template to control prompt structure.

## Prerequisite Task: Multi-Table Codegen Artifact Generation

**Everything else in this spec (Sections 2-10) depends on this prerequisite being in place first.**

**File:** `engine/src/migrations_engine/codegen/service.py`

**Current behavior:** `generate_codegen_artifact()` calls `_primary_destination_object_name()` which returns only `references[0]`. One AI call, one artifact.

**New behavior:** `generate_codegen_artifact()` iterates over ALL `destination_object_references`, creating one artifact (and one AI call) per table:

```python
def generate_codegen_artifact(db, *, actor, project_id, source_definition_id) -> list[CodegenTriggerResponse]:
    source_definition = _get_source_definition(db, project_id=project_id, source_definition_id=source_definition_id)
    dest_tables = [str(r).strip() for r in (source_definition.destination_object_references or []) if r]
    
    results = []
    for dest_table in dest_tables:
        # ... existing artifact generation logic per table ...
        results.append(trigger_response)
    
    return results
```

**Route handler change:** Return type changes from `CodegenTriggerResponse` to `list[CodegenTriggerResponse]`.

**`_select_latest_approved_mapping_snapshot` impact:** Already queries by `destination_object_name` — no change needed. Each call fetches the correct snapshot for the target table.

**Artifact naming:** Each artifact is stored with its `destination_object_name`. `build_delivery_bundle_text` already groups artifacts by `destination_object_name` and handles `0000_` lookup artifacts. No changes needed to `build_delivery_bundle_text`.

## Design

### Section 1: Bug Fix — Collect All Lookup Snapshots

**File:** `engine/src/migrations_engine/codegen/service.py`

**Current behavior:** `_select_lookup_snapshot_version()` iterates through lookup names and returns on the first successful snapshot lookup:

```python
for lookup_name in lookup_names:
    try:
        snapshot = select_latest_approved_lookup_snapshot(...)
    except SnapshotNotFoundError:
        continue
    return snapshot.lookup_snapshot_version  # Returns first match only
```

**Change:** Collect all snapshot versions into a list and return them. Update the user prompt to pass `lookup_snapshots` (a list of dicts with `name` and `snapshot_version`) instead of a single `lookup_snapshot_version` string.

**New implementation:**
```python
def _select_lookup_snapshot_version(
    db: Session, *, project_id: str, mapping_snapshot: MappingSnapshot
) -> list[dict[str, str]]:
    lookup_names = sorted({
        str(binding.get("lookup_name"))
        for binding in mapping_snapshot.field_bindings
        if binding.get("lookup_name") and not binding.get("dropped")
    })
    results = []
    for lookup_name in lookup_names:
        try:
            snapshot = select_latest_approved_lookup_snapshot(db, project_id, lookup_name)
            results.append({"lookup_name": lookup_name, "snapshot_version": snapshot.lookup_snapshot_version})
        except SnapshotNotFoundError:
            continue
    return results
```

The user prompt template (`user_prompt.txt.j2`) is updated to iterate over the list of lookup snapshots, displaying each lookup name and its snapshot version.

### Section 2: YAML Template for Feed Transformation Instructions

**New file:** `engine/src/migrations_engine/ai/prompts/feed_transformation_instructions.yaml`

```yaml
system: |
  (empty — user-prompt data only)

user: |
  FEED-SPECIFIC TRANSFORMATION RULES
  The following instructions are specific to this feed.
  Apply ALL rules below when generating the stored procedure.
  Do not skip or reinterpret any rule.
  
  $payload
```

This follows the same pattern as `lookup_mapping.yaml` — a YAML file that takes `$payload` as input. The payload is the user's free-text transformation instructions, wrapped with consistent AI-facing context.

### Section 3: Python Renderer

**New file:** `engine/src/migrations_engine/codegen/feed_instructions.py`

```python
from __future__ import annotations
from pathlib import Path
from string import Template
import yaml

_PROMPTS_DIR = Path(__file__).parent.parent / "ai" / "prompts"

def render_feed_instructions_template(user_text: str | None) -> str:
    data = yaml.safe_load(_PROMPTS_DIR / "feed_transformation_instructions.yaml")
    return Template(data["user"]).substitute(payload=user_text or "(none)").strip()
```

Mirrors the `render_coding_standards_template()` pattern — reads a YAML template, substitutes the payload, returns the formatted string.

### Section 4: Service Integration

**File:** `engine/src/migrations_engine/codegen/service.py`

**4a. Import the renderer:**
```python
from .feed_instructions import render_feed_instructions_template
```

**4b. Update `_build_user_prompt()` to use the renderer:**
Replace the raw text injection of `source_definition.transformation_instructions` with the rendered template output. The Jinja2 template (`user_prompt.txt.j2`) changes from:

```jinja2
{% if source_definition.transformation_instructions %}
FEED-SPECIFIC TRANSFORMATION INSTRUCTIONS
{{ source_definition.transformation_instructions.strip() }}
{% endif %}
```

To a variable injection:
```jinja2
{% if feed_instructions %}
{{ feed_instructions }}
{% endif %}
```

Where `feed_instructions = render_feed_instructions_template(source_definition.transformation_instructions)` is passed into the template context.

### Section 5: One Proc Per Destination Table

**File:** `engine/src/migrations_engine/codegen/service.py`

**Current behavior:** One stored procedure containing all MERGE/UPsert statements for all destination tables, with all lookup DDL and seed data in that single procedure.

**New behavior:** One stored procedure per `destination_object_name`. Each procedure handles only:
- Its own lookup DDL (if it uses lookups)
- Its own MERGE/UPsert statement
- Its own seed data (if applicable)

The system prompt (`system_prompt.txt.j2`) is updated with explicit rules:

```
GENERATE ONE PROCEDURE PER DESTINATION TABLE:
- For each destination table in field_bindings, generate a SEPARATE stored procedure
- Each procedure handles ONLY its own lookup DDL, seed data, and one MERGE/UPsert
- NEVER combine multiple table mappings in a single procedure
- Lookups used by multiple tables: create the lookup DDL/seed once in the first procedure that references it

EXECUTION ORDER (the SQL bundle enforces this):
1. Lookup DDL is created first (lookup_ddl array)
2. Lookup seed data is inserted (seed_data array)
3. Stored procedures are generated (stored_procedures array)

Cross-table references:
- If a downstream table needs data from an upstream destination table, JOIN $dest.<upstream_table> directly
- The $dest schema is assumed to contain data populated by earlier procs
- The $dest schema is populated in destination_object_sequence order
```

The `GeneratedSQL` model (which already has `stored_procedures: list[str]`) is unchanged — it naturally supports multiple procedure entries.

### Section 6: Lookup Tables Grouped by Destination Table

**File:** `engine/src/migrations_engine/codegen/service.py`

**Current behavior:** `_build_lookup_tables()` returns a flat list of all lookup tables, passing only 5 sample mappings per lookup. The AI cannot reliably write JOIN queries or seed data from samples alone.

**New behavior:** `_build_lookup_tables()` returns lookup tables grouped by `destination_object_name`, and passes the **full approved value_map** (not just 5 samples). The user prompt lists them per-table:

```
LOOKUP REFERENCE TABLES

Table: policy_claims
  Lookups:
  - claim_status_ref (12 mappings):
    source_val -> dest_val
    APPROVED -> APPROVED
    PENDING -> PENDING
    REJECTED -> REJECTED
    ... (all 12 mappings)
  
Table: policy_master
  Lookups:
  - insurance_plan_ref (87 mappings):
    source_val -> dest_val
    PL -> PLAN_A
    PN -> PLAN_B
    ... (all 87 mappings)
```

**Why full data is required:** The AI needs the complete `source_val -> dest_val` mapping to:
1. Generate correct `INSERT` seed data statements (one per mapping)
2. Write reliable `LEFT JOIN` conditions that resolve every source value to its destination FK
3. Ensure no unmapped values cause join failures at runtime

Without all mappings, the AI writes JOIN queries based on samples, and any unmapped source value silently produces NULL — causing missing FK values in the destination table.

**Implementation:** Extend `_build_lookup_tables()` to:
1. Group field bindings by `destination_object_name` (from mapping_snapshot)
2. For each destination table, collect its associated lookup names
3. For each lookup name, fetch the snapshot and build the lookup table dict
4. Pass the **full** `value_map` (all key-value pairs, no cap) to the prompt
5. Return a list of dicts: `[{destination_object_name, lookups: [..., with full value_map]}, ...]`

### Section 7: Bundle Assembly Order

No code changes needed. `_assemble_sql_bundle()` already concatenates in the correct order:
1. Staging DDL
2. `lookup_ddl` array
3. `seed_data` array
4. `stored_procedures` array

The AI is instructed (via system prompt) to put lookup DDL in `lookup_ddl`, seed data in `seed_data`, and one CREATE PROCEDURE per table in `stored_procedures`.

### Section 8: Cross-Proc FK Resolution via Global Migration Log

**Current behavior:** Each proc has its own `run_ref` (auto-generated per-proc). `mig_upsert_log` entries are scoped to that `run_ref`. Detail procs cannot access master proc's log entries because they run separately with their own `run_ref`.

**New behavior:** `mig_upsert_log` is a **global shared table** across all procs. `source_row_num` stores a **business key** (not the staging `_row_num`) that is meaningful across source tables. This enables detail procs to look up master FKs at runtime.

**How it works:**

1. **Master proc** logs entries with business key:
   ```sql
   INSERT INTO $stg.mig_upsert_log (dest_table, source_row_num, dest_row_id, action)
   VALUES ('policy_master', s.source_policy_number, @new_policy_id, 'INSERT');
   ```

2. **Detail proc** queries the log to resolve master FK:
   ```sql
   SELECT l.dest_row_id
   FROM $stg.mig_upsert_log l
   WHERE l.dest_table = 'policy_master'
     AND l.source_row_num = s.source_policy_number
   ```

3. **Detail proc** uses resolved `dest_row_id` in its upsert to `claim_detail`.

**Logging standard update:** `codegen_logging_standards.yaml` is updated to specify:
- `source_row_num` stores a **business key** meaningful across source tables (not staging `_row_num`)
- Detail procs can query `mig_upsert_log` to resolve FKs to previously-populated destination tables
- `run_ref` is still generated per-proc (for audit), but the log table itself is shared
- Procs must be executed in `destination_object_sequence` order (master before detail)

**System prompt rule:** When a field binding references a lookup that maps to another destination table (i.e., a foreign key to a master table), the detail proc must resolve the FK by querying `mig_upsert_log`:
```
If a destination table has a FK to another destination table:
1. Query $stg.mig_upsert_log WHERE dest_table = '<master_table_name>' AND source_row_num = s.<source_field_matching_master>
2. Use the returned dest_row_id as the resolved FK value
3. This works because procs execute in destination_object_sequence order
```

**`source_row_num` semantics change:** Currently stores the staging `_row_num` (per-table unique). After this change, for FK resolution purposes, `source_row_num` stores a business key that is stable and meaningful across source tables. This enables cross-proc FK resolution without shared state.

## Files Changed

| File | Change |
|------|--------|
| `engine/src/migrations_engine/ai/prompts/feed_transformation_instructions.yaml` | **New** — YAML template for feed instruction formatting |
| `engine/src/migrations_engine/codegen/feed_instructions.py` | **New** — Renderer function |
| `engine/src/migrations_engine/codegen/service.py` | **Modified** — Multi-table loop, bug fix, lookup grouping, service integration |
| `engine/src/migrations_engine/codegen/templates/user_prompt.txt.j2` | **Modified** — Replace raw injection with `feed_instructions` variable |
| `engine/src/migrations_engine/codegen/templates/system_prompt.txt.j2` | **Modified** — Add one-proc-per-table rules and cross-proc FK resolution rules |
| `engine/src/migrations_engine/ai/prompts/codegen_logging_standards.yaml` | **Modified** — Add cross-proc FK resolution via mig_upsert_log |
| `engine/src/migrations_engine/routes/codegen.py` | **Modified** — Return type changes to list, handles multi-table response |

## Files Not Changed

| File | Reason |
|------|--------|
| `coding_standards.yaml` | Stored blob approach kept as-is |
| `project_definition.codegen_instructions` | Stored blob approach kept as-is |
| Frontend code | No UI changes needed — users still type free text into transformation instructions textarea |
| `feed_domain_object_analysis.yaml` / `feed_field_mapping.yaml` | Not affected by these changes |
