# Summary: Data-Driven Feed Analysis Prompts + AI Log Viewer

## Task Overview
This task implements data-driven feed analysis by including sample CSV data in AI prompts, tightening Pydantic schemas, and adding AI log viewer functionality.

## Implementation Details

### 1. Key Requirements
- Include sample CSV rows in all AI prompts (up to sample_policy.max_rows)
- Rewrite system prompts with explicit, rule-driven instructions
- Tighten Pydantic output schemas with additional fields
- Tag feed analysis logs with artifact_id for queryability
- Add AI log viewer to feed page

### 2. Files Modified

#### engine/src/migrations/management/fibers.py
- Modified AI prompt generation to include sample data from source rows
- Updated system prompts to prevent zombie tables and spurious bindings
- Tightened Pydantic schemas to include:
  - `unmatched_columns`
  - `unmatched_source_fields` 
  - `unmatched_source_values`
  - `sample_values`
  - `binding_type`
  - `reference_table_name`

### 3. API Changes
#### web/lib/feeds-api.ts
- Added `listAiCallLogs` client function
- Added `artifactId` tagging to all AI analysis log entries

### 4. UI Changes
#### web/app/projects/[id]/feeds/[feedId]/page.tsx
- Added collapsible AI log viewer panel
- Implemented system prompt display
- Added user prompt display with sample data
- Added raw response viewer
- Added artifact ID tagging in AI analysis

## Implementation Status
✅ All requirements from task 001cx have been implemented in the codebase