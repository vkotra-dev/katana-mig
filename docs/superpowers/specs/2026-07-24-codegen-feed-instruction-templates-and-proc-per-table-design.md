# Codegen: Feed Instruction Templates & One-Proc-Per-Table Design

## Problem

Two issues in the codegen prompt system:

1. **Lookup tables omitted**: `_select_lookup_snapshot_version()` returns only the first lookup snapshot found (line 448 of `service.py`), so the AI only generates DDL/seed for one lookup table. When a feed uses multiple lookups (e.g., `claim_status` and `insurance_plan`), only the first one gets generated.

2. **Feed-specific instructions are raw text**: User-entered transformation instructions are dumped raw into the user prompt without consistent framing. Unlike coding standards (which go through `render_coding_standards_template()`), there is no YAML template to control prompt structure.

Additionally, all table mappings are generated in a single stored procedure. The requirement has shifted to one stored procedure per destination table, with lookup DDL and seed data delivered separately (before any procs).

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

**Current behavior:** `_build_lookup_tables()` returns a flat list of all lookup tables across the feed.

**New behavior:** `_build_lookup_tables()` returns lookup tables grouped by `destination_object_name`. The user prompt lists them per-table:

```
LOOKUP REFERENCE TABLES

Table: policy_claims
  Lookups:
  - claim_status_ref: source_val -> dest_val (5 sample mappings)
  
Table: policy_master
  Lookups:
  - insurance_plan_ref: source_val -> dest_val (5 sample mappings)
```

This requires grouping lookups by the destination tables that use them. The lookup name is derived from field bindings in the mapping snapshot.

**Implementation:** Extend `_build_lookup_tables()` to:
1. Group field bindings by `destination_object_name` (from mapping_snapshot)
2. For each destination table, collect its associated lookup names
3. For each lookup name, fetch the snapshot and build the lookup table dict
4. Return a list of dicts: `[{destination_object_name, lookups: [...]}, ...]`

### Section 7: Bundle Assembly Order

No code changes needed. `_assemble_sql_bundle()` already concatenates in the correct order:
1. Staging DDL
2. `lookup_ddl` array
3. `seed_data` array
4. `stored_procedures` array

The AI is instructed (via system prompt) to put lookup DDL in `lookup_ddl`, seed data in `seed_data`, and one CREATE PROCEDURE per table in `stored_procedures`.

## Files Changed

| File | Change |
|------|--------|
| `engine/src/migrations_engine/ai/prompts/feed_transformation_instructions.yaml` | **New** — YAML template for feed instruction formatting |
| `engine/src/migrations_engine/codegen/feed_instructions.py` | **New** — Renderer function |
| `engine/src/migrations_engine/codegen/service.py` | **Modified** — Bug fix, lookup grouping, service integration |
| `engine/src/migrations_engine/codegen/templates/user_prompt.txt.j2` | **Modified** — Replace raw injection with `feed_instructions` variable |
| `engine/src/migrations_engine/codegen/templates/system_prompt.txt.j2` | **Modified** — Add one-proc-per-table rules |

## Files Not Changed

| File | Reason |
|------|--------|
| `coding_standards.yaml` / `logging_standards.yaml` | Stored blob approach kept as-is |
| `project_definition.codegen_instructions` | Stored blob approach kept as-is |
| Frontend code | No UI changes needed — users still type free text into transformation instructions textarea |
| `feed_domain_object_analysis.yaml` / `feed_field_mapping.yaml` | Not affected by these changes |
