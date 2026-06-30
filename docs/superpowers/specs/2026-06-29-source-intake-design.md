# Source Intake and Storage — Design Spec

**Date:** 2026-06-29
**Status:** Approved for implementation

## Problem

The platform needs to accept source data files for migration projects, parse them into a governed, masked, versioned form, and store them so downstream analysis and AI steps can consume them.

Two file-based source types are in scope: **CSV** and **fixed-length record** files. Database sources are out of scope here (the engine downloads those independently). Source intake is a lifecycle distinct from project creation — sources are attached to an existing project, not declared at the time the project is created.

## Out of Scope

- Source intake during project creation — the project wizard captures name, goal, and governance metadata only; no source fields
- Database source download — handled separately by the engine
- Source analysis, domain object mapping, code generation — downstream of intake
- XLS/composite sources — future iteration
- PII masking policy configuration — masking is applied using a default field-name heuristic for now; policy configuration is a separate task
- Approval workflow for slices — slices are stored as `pending_approval`; the approval gate is a separate task

---

## Core Design Decisions

### 1. Sources are managed against a project, not declared at project creation

A project can own multiple source contracts added at any time after the project exists. The project detail page gains a **Sources tab** as the dedicated management surface. The project creation wizard has no source step.

### 2. All source types normalize to CSV at intake time

Regardless of whether the input is a CSV file or a fixed-length record file, the intake pipeline converts every record to a CSV row using the resolved column names as headers. This gives the rest of the system one uniform data shape to work with.

```
CSV file         → parse headers + rows → mask → store as CSV rows
Fixed-length     → parse COBOL copybook → derive headers
                 → slice each record by offset/width → mask → store as CSV rows
Unknown layout   → upload raw spec + data → AI derives layout → same CSV row path
```

### 3. COBOL copybook is the primary fixed-length layout format

A fixed-length source intake accepts two files: the data file and a COBOL copybook (`.cpy`). The copybook parser extracts field definitions (`name`, `offset`, `width`, `picture_clause`, `type_hint`). The parsed layout is stored as structured JSON on the source contract. The raw copybook text is stored verbatim alongside it so AI can re-read it for the unknown-layout fallback.

### 4. Storage: individual CSV rows, not a blob

Parsed masked rows are stored one-per-database-row in a new `source_slice_rows` table with a `row_csv` text field. This avoids a large JSON blob, supports row-level sampling, and makes AI consumption straightforward (iterate rows, reconstruct CSV on demand). At the expected scale of a few thousand records this is fast and compact.

### 5. Existing models are extended, not replaced

`SourceDefinition` and `SourceSlice` already exist in `models.py`. This design adds two columns and one new table rather than replacing the existing structure.

---

## Data Model

### Existing tables (no structural change, new columns only)

**`source_definitions`** — add:
```
copybook_text       Text | null    raw COBOL copybook stored verbatim (fixed-length only)
```
`layout_information` (JSON, already exists) holds the parsed field definitions:
```json
[
  {"name": "CUST-ID",  "offset": 0,  "width": 6,  "picture": "9(6)",  "type": "integer"},
  {"name": "SURNAME",  "offset": 6,  "width": 30, "picture": "X(30)", "type": "string"},
  {"name": "DOB",      "offset": 36, "width": 8,  "picture": "9(8)",  "type": "date"}
]
```

**`source_slices`** — add:
```
header_csv          Text | null    comma-separated column names: "CUST_ID,SURNAME,DOB,..."
```
`slice_payload` (JSON, already exists) holds slice-level summary metadata:
```json
{"row_count": 1842, "masked_fields": ["DOB", "SURNAME"], "parse_warnings": []}
```

### New table

**`source_slice_rows`**
```
id                  String(36)     PK, UUID
source_slice_id     String(36)     FK → source_slices.source_slice_id
row_index           Integer        0-based position in the original file
row_csv             Text           one masked CSV row: "100042,***,***,DATABASE,..."
created_at          DateTime
```

---

## Intake Pipeline

### CSV intake

```
1. POST /projects/{id}/source-contracts
   body: { "source_type": "csv", "encoding": "utf-8" }
   → creates SourceDefinition(source_type="csv", status="declared")

2. POST /projects/{id}/source-contracts/{contract_id}/slices
   multipart: file=data.csv
   → read header row → set header_csv on SourceSlice
   → for each data row:
       parse CSV → apply masking → store SourceSliceRow(row_csv=...)
   → SourceSlice(status="pending_approval", row_count=N)
```

### Fixed-length intake

```
1. POST /projects/{id}/source-contracts
   body: { "source_type": "fixed_length_file", "encoding": "cp1252" }
   → creates SourceDefinition(source_type="fixed_length_file", status="declared")

2. POST /projects/{id}/source-contracts/{contract_id}/copybook
   multipart: file=layout.cpy
   → store raw text in copybook_text
   → parse COBOL → populate layout_information JSON array
   → SourceDefinition(status="layout_ready")

3. POST /projects/{id}/source-contracts/{contract_id}/slices
   multipart: file=data.txt
   → use layout_information to slice each fixed-width record
   → convert to CSV row using field names as headers
   → set header_csv from field names
   → apply masking → store SourceSliceRow per record
   → SourceSlice(status="pending_approval", row_count=N)
```

### Unknown layout fallback

Same as fixed-length step 1, but step 2 uploads an arbitrary spec file. The raw spec is stored in `copybook_text`. Instead of the COBOL parser, the AI step derives `layout_information` from the spec + a sample of the raw data. Step 3 proceeds identically once `layout_information` is populated.

---

## API Surface

### Source contracts

| Method | Path | Role | Description |
|--------|------|------|-------------|
| `POST` | `/projects/{id}/source-contracts` | `central_team` | Declare a new source contract |
| `GET` | `/projects/{id}/source-contracts` | any authenticated | List source contracts for project |
| `GET` | `/projects/{id}/source-contracts/{contract_id}` | any authenticated | Get contract detail + layout |
| `POST` | `/projects/{id}/source-contracts/{contract_id}/copybook` | `central_team` | Upload COBOL copybook; parses into `layout_information` |

### Source slices

| Method | Path | Role | Description |
|--------|------|------|-------------|
| `POST` | `/projects/{id}/source-contracts/{contract_id}/slices` | `central_team` | Upload data file; triggers parse + mask + store |
| `GET` | `/projects/{id}/source-contracts/{contract_id}/slices` | any authenticated | List slices for a contract |
| `GET` | `/projects/{id}/source-contracts/{contract_id}/slices/{slice_id}` | any authenticated | Get slice detail + header + row preview |

### Request/response shapes

**`POST /projects/{id}/source-contracts`** request:
```json
{ "source_type": "csv", "encoding": "utf-8", "label": "Customer Master" }
```

**`SourceContractResponse`**:
```json
{
  "source_definition_id": "...",
  "project_id": "...",
  "source_type": "csv",
  "encoding": "utf-8",
  "label": "Customer Master",
  "layout_information": null,
  "status": "declared",
  "created_at": "..."
}
```

**`SourceSliceResponse`**:
```json
{
  "source_slice_id": "...",
  "source_definition_id": "...",
  "header_csv": "CUST_ID,SURNAME,DOB,ACCOUNT_TYPE",
  "row_count": 1842,
  "status": "pending_approval",
  "preview_rows": ["100042,***,***,DATABASE", "100043,***,***,SAVINGS"],
  "created_at": "..."
}
```

### Error codes

| Code | Status | When |
|------|--------|------|
| `source_contract_not_found` | 404 | Contract ID not found or not in this project |
| `source_slice_not_found` | 404 | Slice ID not found |
| `copybook_parse_error` | 422 | COBOL copybook cannot be parsed |
| `layout_not_ready` | 409 | Slice upload attempted before copybook parsed (fixed-length) |
| `file_too_large` | 413 | Upload exceeds size limit (default 50 MB) |
| `unsupported_encoding` | 422 | Encoding not supported |

---

## UI Surface

**Sources tab** is added to the project detail page (tab position 2, between Overview and Artifacts).

### Source list (default view)

```
Sources tab
├── Header: "Sources" + "Add Source" button (central_team only)
└── Table:
      columns: Type chip | Label | Status | Slice count | Last uploaded | →
      empty state: "No sources declared. Add a source to begin intake."
```

### Add Source dialog

Opened by the "Add Source" button. Two-step depending on source type:

**Step 1 — Declare contract:**
- Label (free text)
- Source Type: CSV | Fixed-Length Record
- Encoding (default utf-8)
- Submit → creates contract → advances to step 2

**Step 2a — CSV upload:**
- File picker (`.csv`)
- Upload → parse + mask + store
- Shows preview table of first 5 masked rows
- Close or "View Source" → navigates to source detail

**Step 2b — Fixed-length upload:**
- First: COBOL copybook upload (`.cpy`) → parse → show field table (name, offset, width, type)
- Then: data file upload (`.txt` / `.dat`) → parse using layout → show preview
- If copybook fails or is not COBOL format: "Use AI to interpret layout" option

### Source detail panel (click a row in the list)

```
Source detail
├── Contract card: type chip, label, encoding, status
├── Layout table (fixed-length only): field name | offset | width | picture
├── Copybook viewer (fixed-length only): collapsible raw text panel
└── Slices section:
      table: version | row count | status | uploaded at
      click row → slice detail: header_csv + masked row preview (first 10 rows)
```

---

## Masking Policy (default heuristic)

Until a configurable masking policy is built, fields are masked using a name-match list:

```python
PII_FIELD_NAMES = {
    "name", "surname", "firstname", "lastname", "dob", "dateofbirth",
    "ssn", "email", "phone", "address", "postcode", "zip", "nino",
    "nin", "passport", "driverslicense", "accountnumber", "iban",
}
```

A field whose normalized name (lowercase, no separators) appears in this set is replaced with `***` in the stored `row_csv`. The list of masked field names is recorded in `slice_payload.masked_fields`.

---

## Failure Modes

| Situation | Handling |
|-----------|----------|
| CSV header row missing | Reject with `copybook_parse_error`; require header row |
| Fixed-length upload before copybook | Reject with `layout_not_ready` |
| Copybook has no valid LEVEL 01 record | Reject with `copybook_parse_error` |
| Record length mismatch vs. layout total width | Warn in `slice_payload.parse_warnings`; continue |
| File exceeds 50 MB | Reject with `file_too_large` before parse |
| Encoding mismatch on read | Reject with `unsupported_encoding` |

---

## Testing Strategy

- **Unit**: COBOL copybook parser (field extraction, picture clause → type mapping)
- **Unit**: CSV row masker (replaces PII fields, leaves others intact)
- **Unit**: Fixed-length slicer (given layout + raw line → CSV row)
- **Integration (API)**: Full intake flows via FastAPI TestClient — declare contract, upload copybook, upload data file, assert rows stored correctly
- **Integration (API)**: Error paths — wrong order, bad copybook, oversized file
- **UI (Vitest)**: `SourceList` renders rows and CTA; `AddSourceDialog` steps 1→2a and 1→2b; field table renders layout
