# Summary: 002ih — Persist mapping_ownership_warnings and unblock codegen

## Status: Abandoned

The feeds.py logic to compute and populate `mapping_ownership_warnings` already exists in HEAD (in-memory). The task proposed persisting it via a new DB column on the `Feed` model. The persistence logic (which was in a separate stash) was lost; only the orphan DB column addition remained with nothing writing to it.

## Actions taken

- Removed the orphaned `mapping_ownership_warnings` column from `models.py` (no migration needed)
- Marked task as abandoned — the in-memory computation already serves the data via the API schema
