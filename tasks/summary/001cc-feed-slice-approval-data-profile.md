# Task Summary — 001cc (Feed Slice Approval Data Profile + PII Scan)

## Changes

1. **Imports & Helper Utilities**:
   - Added `approveFeedSlice` and `rejectFeedSlice` to imports in [page.tsx](file:///Users/vjkotra/projects/katana/web/app/projects/%5Bid%5D/feeds/%5BfeedId%5D/page.tsx).
   - Added `useMemo` to React imports.

2. **Client-side PII Scan & Helpers**:
   - Implemented regex patterns (`EMAIL_RE`, `SSN_RE`, `CARD_RE`, `PHONE_RE`, `DATE_RE`) to identify PII elements.
   - Built the `scanColumnPii` helper to identify high-probability and possible PII flags on column values.
   - Added `piiLabel` helper to visually tag column headers with red/amber/green badges.

3. **Approval Profile Derivation**:
   - Configured `approvalProfile` memo to compute total columns, total rows, blank columns (columns where every sample value is whitespace or empty), and column-wise PII scan results on sample records from `latestSlice`.

4. **Stakeholder Approval Workspace Card**:
   - Replaced the simple amber banner on the workspace page with a comprehensive review dashboard when the user is logged in as a `project_stakeholder` and status is `pending_approval`.
   - Included:
     - **Stats strip**: Visual cards for Column count, Total Rows, Preview Rows, and Blank Columns (with alert style when > 0).
     - **PII Scan**: List of scan indicators for each column.
     - **Sample Data**: An unmasked tabular view highlighting empty cells with amber background for easy discovery.
     - **Actions**: Approve and Reject actions, enforcing a non-empty string rationale for rejections.

5. **Access Gating**:
   - Gated the slice detail panel data preview so that data preview tables are only rendered if the slice status is `"approved"`.
   - Updated split functionality in all data tables to use `splitCsvRow` for correct parsing of quoted CSV values.

## Verification

- **Frontend tests**: All 268 Vitest tests passed cleanly.
- **Production Build**: Compiles successfully with Next.js without compilation or TypeScript errors.
