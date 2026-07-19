# Summary: Add MS SQL Migration SP Requirements to Codegen Standards Template

## Task Overview
Implemented MS SQL Server specific coding standards and requirements for the codegen template as requested in task 001ct-codegen-mssql-standards.

## Changes Made

1. **Modified `generateCodingStandardsTemplate` function in `/Users/vjkotra/projects/katana/web/app/projects/[id]/codegen/page.tsx`**

2. **Added specific MS SQL Server requirements**:
   - SET XACT_ABORT ON immediately after SET NOCOUNT ON
   - Validate source table is non-empty before MERGE; THROW if empty
   - Check for duplicate PKs in source before MERGE; THROW if duplicates found
   - Use THROW not RAISERROR for all error handling (SQL Server 2012+)
   - Return result set after completion with: run_ref, rows_inserted, rows_updated, completed_at
   - Use CAST(COALESCE(inserted.[pk], deleted.[pk]) AS NVARCHAR(255)) for action logging
   - NULL values in source columns flow through unchanged unless destination is NOT NULL
   - Note index requirements on MERGE join key columns in comments

3. **Updated the specific standards section for MS SQL Server**:
   - Added all required MS SQL Server specific rules and best practices
   - Maintained consistency with the existing code structure and patterns
   - Ensured proper error handling conventions for SQL Server

## Implementation Details

The implementation follows the exact requirements specified in the task:
- Updated the MS SQL Server section of the generateCodingStandardsTemplate function
- Added detailed guidelines for MERGE operations with proper error handling and validation
- Included both the standard SQL Server coding conventions as well as the specific requirements for stored procedures

This ensures that when code is generated for SQL Server, developers will automatically get the enhanced standards for better transaction safety, error handling, and MERGE operation best practices.