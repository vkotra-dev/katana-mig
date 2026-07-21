# Task: 001df — AI Re-analysis and Sign-off Preservation

## Status
Ready

## Problem
Currently, the AI Analyze buttons across the Feed Detail page either refuse to run if data already exists (early-exit caching) or destructively overwrite existing data. The user has requested that:
1. Pressing the "AI Analyze" button should **always** force a fresh AI analysis (re-run every step).
2. The results of the fresh analysis must **never** overwrite fields/mappings that have already been signed off or approved by a human.

## Solution

### Part 1: Source Analysis (`source_analysis.py`)
Source analysis extracts schema and value summaries. 
- Remove the early-exit check (`if existing_artifact is not None: return`).
- When a new analysis completes, delete the old `SourceSchemaArtifact` for that slice version so the new one can be saved cleanly.

### Part 2: Field Mapping (`mapping/review.py`)
- Remove any early exits.
- When generating the `MappingSnapshotRow`s from the AI's result, query the `MappingSignOff` table for this feed. 
- **Upsert Logic**: If a destination column has an active sign-off, **skip** creating a snapshot row for it. Only propose snapshot rows for unapproved fields.

### Part 3: Lookup Fiber Mapping (`management/fibers.py`)
- Remove the early exit that blocks re-analysis if a `LookupSignOff` exists.
- **Upsert Logic**: Instead of unconditionally deleting everything:
  1. Retrieve all existing `LookupMapping` rows for the fiber.
  2. Identify which rows are `"approved"`.
  3. Delete only the `LookupMapping` and `LookupSourceEntry` rows that are NOT approved.
  4. When the AI returns new mapping pairs, **insert/update (upsert)** mappings ONLY for source values that do not have an `"approved"` status.
  5. Merge the new destination feeds/entries carefully without dropping the ones currently referenced by approved mappings.
