---
type: Task
status: Completed
created_at: 2026-07-19
title: Add MS SQL Migration SP Requirements to Codegen Standards Template
---

# Add MS SQL Migration SP Requirements to Codegen Standards Template

**Problem:**
When generating code for MS SQL Server, the current "Suggest Standards" template is too brief. It lacks critical best practices for transaction safety, robust error handling, and robust MERGE output tracking.

**Requirements:**
The user requested the following specific instructions to be added to the MS SQL branch of the `generateCodingStandardsTemplate` function in the frontend:
- SET XACT_ABORT ON immediately after SET NOCOUNT ON
- Validate source table is non-empty before MERGE; THROW if empty (not RAISERROR)
- Check for duplicate PKs in source before MERGE; THROW if duplicates found (not RAISERROR)
- Use THROW not RAISERROR for all error raising (SQL Server 2012+)
- Return a result set after completion: run_ref, rows_inserted, rows_updated, completed_at
- Use CAST(COALESCE(inserted.[pk], deleted.[pk]) AS NVARCHAR(255)) in OUTPUT for future-safe action logging
- NULL values in source columns flow through unchanged unless destination is NOT NULL
- Note index requirements on MERGE join key columns in comments

**Scope:**
Update `web/app/projects/[id]/codegen/page.tsx` to inject these instructions into the `specificStandards` block when `dbEngine` is `mssql` or `sqlserver`.
