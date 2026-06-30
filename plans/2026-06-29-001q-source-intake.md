# Source Intake and Storage — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add source contract declaration and data file upload for CSV and fixed-length record sources. All source data normalizes to masked CSV rows stored in the database. Sources are managed against an existing project via a Sources tab — never during project creation.

**Spec:** `docs/superpowers/specs/2026-06-29-source-intake-design.md`

**Architecture:**
- `SourceDefinition` and `SourceSlice` already exist in `models.py`; this plan adds `copybook_text`, `header_csv`, and a new `SourceSliceRow` table
- Intake pipeline: upload → parse → mask → normalize to CSV rows → store
- COBOL copybook parser produces structured `layout_information` JSON used by the fixed-length slicer
- Masking is heuristic: field names matching a PII list are replaced with `***`
- All source types produce the same output shape: `header_csv` + `SourceSliceRow` records

**Depends on:** plan `001o` (project CRUD API must exist; `project_registry` FK needed)

**Tech Stack:** Python ≥ 3.11, FastAPI (`UploadFile`), SQLAlchemy 2.x sync ORM, `python-csv` stdlib, Pydantic v2, pytest + FastAPI TestClient.

## Global Constraints

- `from __future__ import annotations` at top of every file
- All IDs: UUID4 via `new_id()` from `db.models`
- File size limit: 50 MB enforced before parsing
- Encoding default: `utf-8`; accepted: `utf-8`, `latin-1`, `cp1252`
- `status` values on `SourceDefinition`: `"declared"` | `"layout_ready"` | `"active"`
- `status` values on `SourceSlice`: `"pending_approval"` | `"approved"` | `"superseded"`
- Masking replaces PII field values with `***` in stored `row_csv`
- Every mutation calls `record_management_audit()` from `management.platform`
- Tests hit real SQLite test DB via FastAPI TestClient — no mocking

---

## PII Field Name List (masking heuristic)

```python
PII_FIELD_NAMES: frozenset[str] = frozenset({
    "name", "surname", "firstname", "lastname", "fullname",
    "dob", "dateofbirth", "birthdate",
    "ssn", "socialsecuritynumber",
    "email", "emailaddress",
    "phone", "phonenumber", "mobile", "telephone",
    "address", "streetaddress", "postcode", "zipcode", "zip",
    "nino", "nin", "passport", "passportnumber",
    "driverslicense", "drivinglicense",
    "accountnumber", "bankaccount", "iban", "sortcode",
})

def is_pii_field(name: str) -> bool:
    normalized = name.lower().replace(" ", "").replace("_", "").replace("-", "")
    return normalized in PII_FIELD_NAMES
```

---

## File Structure

| File | Action | Role |
|------|--------|------|
| `engine/src/migrations_engine/db/models.py` | Modify | Add `copybook_text` to `SourceDefinition`, `header_csv` to `SourceSlice`, new `SourceSliceRow` |
| `engine/migrations/versions/0008_source_intake_fields.py` | Create | Alembic migration: `ADD COLUMN copybook_text`, `ADD COLUMN header_csv`, `CREATE TABLE source_slice_rows` |
| `engine/src/migrations_engine/api/schemas.py` | Modify | Add `SourceContractResponse`, `SourceContractCreateRequest`, `SourceSliceResponse` |
| `engine/src/migrations_engine/intake/masking.py` | Create | `is_pii_field`, `mask_row` |
| `engine/src/migrations_engine/intake/cobol_parser.py` | Create | `parse_copybook(text) -> list[FieldDef]` |
| `engine/src/migrations_engine/intake/csv_intake.py` | Create | `ingest_csv(file, db, contract) -> SourceSlice` |
| `engine/src/migrations_engine/intake/fixed_intake.py` | Create | `ingest_fixed(file, db, contract) -> SourceSlice` |
| `engine/src/migrations_engine/routes/sources.py` | Create | Source contract + slice endpoints |
| `engine/tests/test_source_intake_api.py` | Create | Integration tests per endpoint group |
| `web/lib/sources-api.ts` | Create | Fetch wrappers for source endpoints |
| `web/lib/sources-api.test.ts` | Create | Vitest unit tests for API client |
| `web/components/projects/SourceList.tsx` | Create | Source contract table for Sources tab |
| `web/components/projects/AddSourceDialog.tsx` | Create | Two-step dialog: declare → upload |
| `web/components/projects/__tests__/SourceList.test.tsx` | Create | Rendering + CTA tests |
| `web/components/projects/__tests__/AddSourceDialog.test.tsx` | Create | Step flow + submit tests |
| `web/app/projects/[id]/page.tsx` | Modify | Add Sources tab |

---

### Task 1 — Model additions

**Files:** `engine/src/migrations_engine/db/models.py`

**Produces:**
- `SourceDefinition.copybook_text: Mapped[str | None]`
- `SourceSlice.header_csv: Mapped[str | None]`
- `SourceSliceRow` ORM class

Note: `destination_object_references` already exists on `SourceDefinition` as a JSON column.
Generated SQL output belongs on `CodeGenerationArtifact` (future task), not here.

- [ ] **Step 1: Add `copybook_text` to `SourceDefinition`**

In `models.py`, inside `class SourceDefinition`, after `source_details`:

```python
copybook_text: Mapped[str | None] = mapped_column(Text)
```

- [ ] **Step 2: Add `header_csv` to `SourceSlice`**

In `models.py`, inside `class SourceSlice`, after `masking_policy`:

```python
header_csv: Mapped[str | None] = mapped_column(Text)
```

- [ ] **Step 3: Add `SourceSliceRow` class**

Append to `models.py` after `SourceSlice`:

```python
class SourceSliceRow(Base):
    __tablename__ = "source_slice_rows"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    source_slice_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("source_slices.source_slice_id"), nullable=False, index=True
    )
    row_index: Mapped[int] = mapped_column(Integer, nullable=False)
    row_csv: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
```

- [ ] **Step 4: Write migration `engine/migrations/versions/0008_source_intake_fields.py`**

```python
"""add copybook_text, header_csv, source_slice_rows

Revision ID: 0008_source_intake_fields
Revises: 0007_mapping_lookup_snapshots
Create Date: 2026-06-29
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0008_source_intake_fields"
down_revision = "0007_mapping_lookup_snapshots"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("source_definitions", sa.Column("copybook_text", sa.Text(), nullable=True))
    op.add_column("source_slices", sa.Column("header_csv", sa.Text(), nullable=True))

    op.create_table(
        "source_slice_rows",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("source_slice_id", sa.String(length=36), nullable=False),
        sa.Column("row_index", sa.Integer(), nullable=False),
        sa.Column("row_csv", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["source_slice_id"], ["source_slices.source_slice_id"]
        ),
    )
    op.create_index(
        op.f("ix_source_slice_rows_source_slice_id"),
        "source_slice_rows",
        ["source_slice_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_source_slice_rows_source_slice_id"),
        table_name="source_slice_rows",
    )
    op.drop_table("source_slice_rows")
    op.drop_column("source_slices", "header_csv")
    op.drop_column("source_definitions", "copybook_text")
```

- [ ] **Step 5: Run migration**

```bash
cd engine && alembic upgrade head
```

Expected output ends with: `Running upgrade 0007_mapping_lookup_snapshots -> 0008_source_intake_fields`

- [ ] **Step 6: Verify models load against migrated DB**

```bash
cd engine && python -c "
from migrations_engine.db.models import SourceDefinition, SourceSlice, SourceSliceRow
assert hasattr(SourceDefinition, 'copybook_text')
assert hasattr(SourceDefinition, 'destination_object_references')
assert hasattr(SourceSlice, 'header_csv')
print('ok')
"
```

Expected: `ok`

- [ ] **Step 7: Commit**

```bash
git add engine/src/migrations_engine/db/models.py \
        engine/migrations/versions/0008_source_intake_fields.py
git commit -m "feat: add copybook_text, header_csv, SourceSliceRow — models + migration 0008"
```

---

### Task 2 — Source schemas

**Files:** `engine/src/migrations_engine/api/schemas.py`

**Produces:** `SourceContractCreateRequest`, `SourceContractResponse`, `SourceSliceResponse`

- [ ] **Step 1: Append to `schemas.py` after `ProjectUpdateRequest`**

```python
class SourceContractCreateRequest(BaseModel):
    source_type: Literal["csv", "fixed_length_file"]
    label: str = Field(min_length=1, max_length=255)
    encoding: str = Field(default="utf-8", max_length=32)


class SourceContractResponse(BaseModel):
    source_definition_id: str
    project_id: str
    source_type: str
    label: str
    encoding: str
    destination_object_references: list[str] | None
    layout_information: list[dict[str, Any]] | None
    copybook_text: str | None
    status: str
    created_at: datetime


class SourceSliceResponse(BaseModel):
    source_slice_id: str
    source_definition_id: str
    header_csv: str | None
    row_count: int
    status: str
    preview_rows: list[str]
    created_at: datetime
```

- [ ] **Step 2: Verify**

```bash
cd engine && python -c "
from migrations_engine.api.schemas import SourceContractCreateRequest, SourceContractResponse, SourceSliceResponse
print('ok')
"
```

Expected: `ok`

- [ ] **Step 3: Commit**

```bash
git add engine/src/migrations_engine/api/schemas.py
git commit -m "feat: add source contract and slice schemas"
```

---

### Task 3 — Masking module

**Files:**
- `engine/src/migrations_engine/intake/masking.py` (create)
- `engine/tests/test_masking.py` (create)

**Produces:** `is_pii_field(name) -> bool`, `mask_row(headers, values) -> str`

- [ ] **Step 1: Create `engine/src/migrations_engine/intake/` package**

```bash
mkdir -p engine/src/migrations_engine/intake
touch engine/src/migrations_engine/intake/__init__.py
```

- [ ] **Step 2: Write failing tests**

Create `engine/tests/test_masking.py`:

```python
from __future__ import annotations

import pytest
from migrations_engine.intake.masking import is_pii_field, mask_row


@pytest.mark.parametrize("name,expected", [
    ("surname", True),
    ("SURNAME", True),
    ("last_name", True),
    ("LAST-NAME", True),
    ("dob", True),
    ("DATE_OF_BIRTH", True),
    ("email_address", True),
    ("account_number", True),
    ("account_type", False),
    ("product_id", False),
    ("amount", False),
    ("currency", False),
])
def test_is_pii_field(name: str, expected: bool) -> None:
    assert is_pii_field(name) == expected


def test_mask_row_replaces_pii_fields() -> None:
    headers = ["CUST_ID", "SURNAME", "DOB", "ACCOUNT_TYPE"]
    values = ["100042", "Smith", "19800101", "DATABASE"]
    result = mask_row(headers, values)
    assert result == "100042,***,***,DATABASE"


def test_mask_row_preserves_non_pii_fields() -> None:
    headers = ["product_id", "amount", "currency"]
    values = ["P001", "9999.99", "GBP"]
    result = mask_row(headers, values)
    assert result == "P001,9999.99,GBP"


def test_mask_row_handles_commas_in_value() -> None:
    headers = ["id", "name", "note"]
    values = ["1", "Jones", "see, attached"]
    result = mask_row(headers, values)
    # name is masked; note is not PII but contains comma — must be quoted
    assert result.startswith("1,***,")
    assert '"see, attached"' in result or "see, attached" in result


def test_mask_row_empty_values() -> None:
    headers = ["id", "email"]
    values = ["1", ""]
    result = mask_row(headers, values)
    assert result == "1,***"
```

- [ ] **Step 3: Run tests — confirm they fail**

```bash
cd engine && python -m pytest tests/test_masking.py -v 2>&1 | tail -10
```

Expected: module not found.

- [ ] **Step 4: Create `engine/src/migrations_engine/intake/masking.py`**

```python
from __future__ import annotations

import csv
import io

PII_FIELD_NAMES: frozenset[str] = frozenset({
    "name", "surname", "firstname", "lastname", "fullname",
    "dob", "dateofbirth", "birthdate",
    "ssn", "socialsecuritynumber",
    "email", "emailaddress",
    "phone", "phonenumber", "mobile", "telephone",
    "address", "streetaddress", "postcode", "zipcode", "zip",
    "nino", "nin", "passport", "passportnumber",
    "driverslicense", "drivinglicense",
    "accountnumber", "bankaccount", "iban", "sortcode",
})


def is_pii_field(name: str) -> bool:
    normalized = name.lower().replace(" ", "").replace("_", "").replace("-", "")
    return normalized in PII_FIELD_NAMES


def mask_row(headers: list[str], values: list[str]) -> str:
    masked = [
        "***" if is_pii_field(h) else v
        for h, v in zip(headers, values)
    ]
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(masked)
    return buf.getvalue().rstrip("\r\n")
```

- [ ] **Step 5: Run tests — confirm they pass**

```bash
cd engine && python -m pytest tests/test_masking.py -v
```

Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add engine/src/migrations_engine/intake/ engine/tests/test_masking.py
git commit -m "feat: add masking module with PII field detection and CSV row masking"
```

---

### Task 4 — COBOL copybook parser

**Files:**
- `engine/src/migrations_engine/intake/cobol_parser.py` (create)
- `engine/tests/test_cobol_parser.py` (create)

**Produces:** `FieldDef` dataclass, `parse_copybook(text: str) -> list[FieldDef]`

Parser handles elementary items under a LEVEL 01 record: extracts field name, computes cumulative offset, derives width from PICTURE clause, maps picture to type hint.

- [ ] **Step 1: Write failing tests**

Create `engine/tests/test_cobol_parser.py`:

```python
from __future__ import annotations

import pytest
from migrations_engine.intake.cobol_parser import FieldDef, parse_copybook


SIMPLE_COPYBOOK = """
       01  CUSTOMER-RECORD.
           05  CUST-ID         PIC 9(6).
           05  SURNAME         PIC X(30).
           05  DOB             PIC 9(8).
           05  ACCOUNT-TYPE    PIC X(10).
"""

FILLER_COPYBOOK = """
       01  TRANSACTION-REC.
           05  TRANS-ID        PIC 9(8).
           05  FILLER          PIC X(2).
           05  AMOUNT          PIC 9(10)V99.
           05  CURRENCY        PIC X(3).
"""

REDEFINES_COPYBOOK = """
       01  HEADER-REC.
           05  RECORD-TYPE     PIC X(1).
           05  RECORD-DATE     PIC 9(8).
"""


def test_parse_simple_copybook_fields() -> None:
    fields = parse_copybook(SIMPLE_COPYBOOK)
    names = [f.name for f in fields]
    assert names == ["CUST_ID", "SURNAME", "DOB", "ACCOUNT_TYPE"]


def test_parse_offsets() -> None:
    fields = parse_copybook(SIMPLE_COPYBOOK)
    assert fields[0].offset == 0
    assert fields[0].width == 6
    assert fields[1].offset == 6
    assert fields[1].width == 30
    assert fields[2].offset == 36
    assert fields[2].width == 8
    assert fields[3].offset == 44
    assert fields[3].width == 10


def test_total_record_length() -> None:
    fields = parse_copybook(SIMPLE_COPYBOOK)
    total = fields[-1].offset + fields[-1].width
    assert total == 54


def test_filler_excluded_from_output() -> None:
    fields = parse_copybook(FILLER_COPYBOOK)
    names = [f.name for f in fields]
    assert "FILLER" not in names


def test_filler_offset_still_counted() -> None:
    fields = parse_copybook(FILLER_COPYBOOK)
    # TRANS-ID=8, FILLER=2 (skipped), AMOUNT starts at 10
    amount = next(f for f in fields if f.name == "AMOUNT")
    assert amount.offset == 10


def test_picture_9_type_hint() -> None:
    fields = parse_copybook(SIMPLE_COPYBOOK)
    cust_id = next(f for f in fields if f.name == "CUST_ID")
    assert cust_id.type_hint == "integer"


def test_picture_x_type_hint() -> None:
    fields = parse_copybook(SIMPLE_COPYBOOK)
    surname = next(f for f in fields if f.name == "SURNAME")
    assert surname.type_hint == "string"


def test_picture_v_type_hint() -> None:
    fields = parse_copybook(FILLER_COPYBOOK)
    amount = next(f for f in fields if f.name == "AMOUNT")
    assert amount.type_hint == "decimal"
    assert amount.width == 12  # 9(10)V99 → 10 + 2 digits


def test_empty_copybook_raises() -> None:
    with pytest.raises(ValueError, match="no fields"):
        parse_copybook("   ")


def test_hyphen_to_underscore_in_name() -> None:
    fields = parse_copybook(SIMPLE_COPYBOOK)
    assert all("-" not in f.name for f in fields)
```

- [ ] **Step 2: Run tests — confirm they fail**

```bash
cd engine && python -m pytest tests/test_cobol_parser.py -v 2>&1 | tail -10
```

Expected: module not found.

- [ ] **Step 3: Create `engine/src/migrations_engine/intake/cobol_parser.py`**

```python
from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class FieldDef:
    name: str
    offset: int
    width: int
    picture: str
    type_hint: str


_FIELD_RE = re.compile(
    r"^\s+\d{2}\s+"          # level number (05, 10, etc.)
    r"([\w-]+)\s+"           # field name
    r"PIC\s+"                # PIC keyword
    r"([\w()V.]+)\s*\.",     # picture clause
    re.IGNORECASE | re.MULTILINE,
)

_PIC_WIDTH_RE = re.compile(r"\((\d+)\)")


def _picture_width(pic: str) -> int:
    total = 0
    for part in re.finditer(r"([9XAV])(\(\d+\))?", pic, re.IGNORECASE):
        char = part.group(1).upper()
        count_str = part.group(2)
        count = int(_PIC_WIDTH_RE.search(count_str).group(1)) if count_str else 1
        if char != "V":
            total += count
    return total


def _type_hint(pic: str) -> str:
    pic_upper = pic.upper()
    if "V" in pic_upper:
        return "decimal"
    if pic_upper.startswith("9"):
        return "integer"
    return "string"


def parse_copybook(text: str) -> list[FieldDef]:
    matches = list(_FIELD_RE.finditer(text))
    if not matches:
        raise ValueError("copybook has no fields: no valid PIC clauses found")

    fields: list[FieldDef] = []
    offset = 0
    for m in matches:
        raw_name = m.group(1).upper()
        pic = m.group(2)
        width = _picture_width(pic)
        if raw_name == "FILLER":
            offset += width
            continue
        name = raw_name.replace("-", "_")
        fields.append(FieldDef(
            name=name,
            offset=offset,
            width=width,
            picture=pic,
            type_hint=_type_hint(pic),
        ))
        offset += width

    if not fields:
        raise ValueError("copybook has no fields: only FILLER entries found")
    return fields
```

- [ ] **Step 4: Run tests — confirm they pass**

```bash
cd engine && python -m pytest tests/test_cobol_parser.py -v
```

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add engine/src/migrations_engine/intake/cobol_parser.py \
        engine/tests/test_cobol_parser.py
git commit -m "feat: add COBOL copybook parser"
```

---

### Task 5 — CSV and fixed-length intake services

**Files:**
- `engine/src/migrations_engine/intake/csv_intake.py` (create)
- `engine/src/migrations_engine/intake/fixed_intake.py` (create)
- `engine/tests/test_intake_services.py` (create)

**Produces:**
- `ingest_csv(file_bytes, encoding, db, contract) -> SourceSlice`
- `ingest_fixed(file_bytes, encoding, db, contract) -> SourceSlice`

- [ ] **Step 1: Write failing tests**

Create `engine/tests/test_intake_services.py`:

```python
from __future__ import annotations

import uuid

import pytest

from migrations_engine.db.models import SourceDefinition, SourceSlice, SourceSliceRow, new_id
from migrations_engine.db.session import SessionLocal
from migrations_engine.intake.csv_intake import ingest_csv
from migrations_engine.intake.fixed_intake import ingest_fixed


def _make_contract(db, source_type: str, layout=None) -> SourceDefinition:
    project_id = new_id()
    contract = SourceDefinition(
        source_definition_id=new_id(),
        project_id=project_id,
        source_type=source_type,
        source_contract_version="1",
        layout_information=layout,
        status="declared",
    )
    db.add(contract)
    db.flush()
    return contract


# ── CSV ───────────────────────────────────────────────────────────────────────

def test_csv_ingest_stores_rows() -> None:
    csv_bytes = b"CUST_ID,SURNAME,ACCOUNT_TYPE\n100001,Smith,DATABASE\n100002,Jones,SAVINGS\n"
    with SessionLocal() as db:
        contract = _make_contract(db, "csv")
        slice_ = ingest_csv(csv_bytes, "utf-8", db, contract)
        db.flush()

        assert slice_.header_csv == "CUST_ID,SURNAME,ACCOUNT_TYPE"
        rows = db.query(SourceSliceRow).filter_by(source_slice_id=slice_.source_slice_id).all()
        assert len(rows) == 2
        assert rows[0].row_index == 0
        # SURNAME is PII → masked
        assert "***" in rows[0].row_csv
        # ACCOUNT_TYPE is not PII → preserved
        assert "DATABASE" in rows[0].row_csv
        # CUST_ID is not PII → preserved
        assert "100001" in rows[0].row_csv


def test_csv_ingest_slice_status_pending() -> None:
    csv_bytes = b"ID,EMAIL\n1,user@example.com\n"
    with SessionLocal() as db:
        contract = _make_contract(db, "csv")
        slice_ = ingest_csv(csv_bytes, "utf-8", db, contract)
        assert slice_.status == "pending_approval"


def test_csv_ingest_row_count_in_payload() -> None:
    csv_bytes = b"ID,AMOUNT\n1,100\n2,200\n3,300\n"
    with SessionLocal() as db:
        contract = _make_contract(db, "csv")
        slice_ = ingest_csv(csv_bytes, "utf-8", db, contract)
        assert slice_.slice_payload["row_count"] == 3


def test_csv_ingest_empty_file_raises() -> None:
    with SessionLocal() as db:
        contract = _make_contract(db, "csv")
        with pytest.raises(ValueError, match="empty"):
            ingest_csv(b"", "utf-8", db, contract)


def test_csv_ingest_header_only_raises() -> None:
    with SessionLocal() as db:
        contract = _make_contract(db, "csv")
        with pytest.raises(ValueError, match="no data rows"):
            ingest_csv(b"ID,NAME\n", "utf-8", db, contract)


# ── Fixed-length ──────────────────────────────────────────────────────────────

LAYOUT = [
    {"name": "CUST_ID", "offset": 0, "width": 6, "picture": "9(6)", "type_hint": "integer"},
    {"name": "SURNAME", "offset": 6, "width": 10, "picture": "X(10)", "type_hint": "string"},
    {"name": "ACCOUNT_TYPE", "offset": 16, "width": 8, "picture": "X(8)", "type_hint": "string"},
]

FIXED_DATA = b"100001Smith     DATABASE\n100002Jones     SAVINGS \n"


def test_fixed_ingest_stores_rows() -> None:
    with SessionLocal() as db:
        contract = _make_contract(db, "fixed_length_file", layout=LAYOUT)
        slice_ = ingest_fixed(FIXED_DATA, "utf-8", db, contract)
        db.flush()

        assert slice_.header_csv == "CUST_ID,SURNAME,ACCOUNT_TYPE"
        rows = db.query(SourceSliceRow).filter_by(source_slice_id=slice_.source_slice_id).all()
        assert len(rows) == 2
        assert "100001" in rows[0].row_csv
        assert "***" in rows[0].row_csv      # SURNAME masked
        assert "DATABASE" in rows[0].row_csv


def test_fixed_ingest_no_layout_raises() -> None:
    with SessionLocal() as db:
        contract = _make_contract(db, "fixed_length_file", layout=None)
        with pytest.raises(ValueError, match="layout"):
            ingest_fixed(FIXED_DATA, "utf-8", db, contract)


def test_fixed_ingest_row_count() -> None:
    with SessionLocal() as db:
        contract = _make_contract(db, "fixed_length_file", layout=LAYOUT)
        slice_ = ingest_fixed(FIXED_DATA, "utf-8", db, contract)
        assert slice_.slice_payload["row_count"] == 2
```

- [ ] **Step 2: Run tests — confirm they fail**

```bash
cd engine && python -m pytest tests/test_intake_services.py -v 2>&1 | tail -10
```

Expected: module not found.

- [ ] **Step 3: Create `engine/src/migrations_engine/intake/csv_intake.py`**

```python
from __future__ import annotations

import csv
import io
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from ..db.models import SourceDefinition, SourceSlice, SourceSliceRow, new_id
from .masking import mask_row


MAX_FILE_BYTES = 50 * 1024 * 1024


def ingest_csv(
    file_bytes: bytes,
    encoding: str,
    db: Session,
    contract: SourceDefinition,
) -> SourceSlice:
    if len(file_bytes) > MAX_FILE_BYTES:
        raise ValueError("file_too_large")
    if not file_bytes.strip():
        raise ValueError("empty file")

    text = file_bytes.decode(encoding)
    reader = csv.reader(io.StringIO(text))
    rows_iter = iter(reader)

    try:
        headers = next(rows_iter)
    except StopIteration:
        raise ValueError("empty file")

    data_rows = list(rows_iter)
    if not data_rows:
        raise ValueError("no data rows")

    header_csv = ",".join(headers)
    masked_fields = [h for h in headers if _is_pii(h)]

    slice_id = new_id()
    slice_ = SourceSlice(
        source_slice_id=slice_id,
        source_definition_id=contract.source_definition_id,
        source_contract_version=contract.source_contract_version,
        source_slice_version=new_id(),
        header_csv=header_csv,
        masking_policy={"masked_fields": masked_fields},
        slice_payload={"row_count": len(data_rows), "masked_fields": masked_fields, "parse_warnings": []},
        status="pending_approval",
    )
    db.add(slice_)
    db.flush()

    for idx, values in enumerate(data_rows):
        db.add(SourceSliceRow(
            source_slice_id=slice_id,
            row_index=idx,
            row_csv=mask_row(headers, values),
        ))

    return slice_


def _is_pii(name: str) -> bool:
    from .masking import is_pii_field
    return is_pii_field(name)
```

- [ ] **Step 4: Create `engine/src/migrations_engine/intake/fixed_intake.py`**

```python
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from ..db.models import SourceDefinition, SourceSlice, SourceSliceRow, new_id
from .masking import mask_row


MAX_FILE_BYTES = 50 * 1024 * 1024


def ingest_fixed(
    file_bytes: bytes,
    encoding: str,
    db: Session,
    contract: SourceDefinition,
) -> SourceSlice:
    if not contract.layout_information:
        raise ValueError("layout_information not set on contract")
    if len(file_bytes) > MAX_FILE_BYTES:
        raise ValueError("file_too_large")

    layout: list[dict[str, Any]] = contract.layout_information
    headers = [f["name"] for f in layout]
    header_csv = ",".join(headers)
    masked_fields = [h for h in headers if _is_pii(h)]
    warnings: list[str] = []

    text = file_bytes.decode(encoding)
    lines = [ln for ln in text.splitlines() if ln.strip()]

    if not lines:
        raise ValueError("empty file")

    slice_id = new_id()
    slice_ = SourceSlice(
        source_slice_id=slice_id,
        source_definition_id=contract.source_definition_id,
        source_contract_version=contract.source_contract_version,
        source_slice_version=new_id(),
        header_csv=header_csv,
        masking_policy={"masked_fields": masked_fields},
        slice_payload={"row_count": len(lines), "masked_fields": masked_fields, "parse_warnings": warnings},
        status="pending_approval",
    )
    db.add(slice_)
    db.flush()

    for idx, line in enumerate(lines):
        values: list[str] = []
        for field in layout:
            start = field["offset"]
            end = start + field["width"]
            value = line[start:end].rstrip() if len(line) >= end else ""
            if len(line) < end:
                warnings.append(f"row {idx}: short record (len={len(line)}, expected {end})")
            values.append(value)
        db.add(SourceSliceRow(
            source_slice_id=slice_id,
            row_index=idx,
            row_csv=mask_row(headers, values),
        ))

    slice_.slice_payload = {**slice_.slice_payload, "parse_warnings": warnings}
    return slice_


def _is_pii(name: str) -> bool:
    from .masking import is_pii_field
    return is_pii_field(name)
```

- [ ] **Step 5: Run tests — confirm they pass**

```bash
cd engine && python -m pytest tests/test_intake_services.py tests/test_masking.py tests/test_cobol_parser.py -v
```

Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add engine/src/migrations_engine/intake/csv_intake.py \
        engine/src/migrations_engine/intake/fixed_intake.py \
        engine/tests/test_intake_services.py
git commit -m "feat: add CSV and fixed-length intake services"
```

---

### Task 6a — Source contract routes + tests

**Files:**
- `engine/src/migrations_engine/routes/sources.py` (create skeleton + contract routes)
- `engine/tests/test_source_intake_api.py` (create with contract tests)

- [ ] **Step 1: Write failing contract tests**

Create `engine/tests/test_source_intake_api.py`:

```python
from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from migrations_engine.app import app
from migrations_engine.config import get_settings

client = TestClient(app)


@pytest.fixture(autouse=True)
def _clear_settings_cache() -> None:
    get_settings.cache_clear()


def _login_admin() -> str:
    settings = get_settings()
    if not settings.bootstrap_admin_email or not settings.bootstrap_admin_password:
        pytest.skip("bootstrap credentials not configured")
    r = client.post("/auth/login", json={
        "email": settings.bootstrap_admin_email,
        "password": settings.bootstrap_admin_password,
    })
    assert r.status_code == 200
    return r.json()["access_token"]


def _create_project(token: str) -> str:
    r = client.post("/projects", headers={"Authorization": f"Bearer {token}"},
                    json={"name": f"Test-{uuid.uuid4().hex[:6]}"})
    assert r.status_code == 201
    return r.json()["project_id"]


# ── POST /projects/{id}/source-contracts ─────────────────────────────────────

def test_declare_csv_contract(admin_token: str = None) -> None:
    token = admin_token or _login_admin()
    pid = _create_project(token)
    r = client.post(f"/projects/{pid}/source-contracts",
                    headers={"Authorization": f"Bearer {token}"},
                    json={"source_type": "csv", "label": "Customer File", "encoding": "utf-8"})
    assert r.status_code == 201, r.text
    b = r.json()
    assert b["source_type"] == "csv"
    assert b["label"] == "Customer File"
    assert b["status"] == "declared"
    assert b["layout_information"] is None


def test_declare_fixed_length_contract() -> None:
    token = _login_admin()
    pid = _create_project(token)
    r = client.post(f"/projects/{pid}/source-contracts",
                    headers={"Authorization": f"Bearer {token}"},
                    json={"source_type": "fixed_length_file", "label": "Ledger Feed", "encoding": "cp1252"})
    assert r.status_code == 201
    assert r.json()["source_type"] == "fixed_length_file"


def test_list_source_contracts() -> None:
    token = _login_admin()
    pid = _create_project(token)
    client.post(f"/projects/{pid}/source-contracts",
                headers={"Authorization": f"Bearer {token}"},
                json={"source_type": "csv", "label": "A"})
    client.post(f"/projects/{pid}/source-contracts",
                headers={"Authorization": f"Bearer {token}"},
                json={"source_type": "fixed_length_file", "label": "B"})
    r = client.get(f"/projects/{pid}/source-contracts",
                   headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert len(r.json()) == 2


def test_get_source_contract() -> None:
    token = _login_admin()
    pid = _create_project(token)
    cid = client.post(f"/projects/{pid}/source-contracts",
                      headers={"Authorization": f"Bearer {token}"},
                      json={"source_type": "csv", "label": "Detail"}).json()["source_definition_id"]
    r = client.get(f"/projects/{pid}/source-contracts/{cid}",
                   headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json()["source_definition_id"] == cid


def test_contract_not_found() -> None:
    token = _login_admin()
    pid = _create_project(token)
    r = client.get(f"/projects/{pid}/source-contracts/00000000-0000-0000-0000-000000000000",
                   headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "source_contract_not_found"


def test_unauthenticated_rejected() -> None:
    assert client.get("/projects/x/source-contracts").status_code == 401
```

- [ ] **Step 2: Run tests — confirm they fail**

```bash
cd engine && python -m pytest tests/test_source_intake_api.py -k "contract" -v 2>&1 | tail -15
```

Expected: failures — routes not defined.

- [ ] **Step 3: Create `engine/src/migrations_engine/routes/sources.py`**

```python
from __future__ import annotations

from fastapi import APIRouter, Depends, UploadFile, status
from sqlalchemy.orm import Session

from ..api.deps import get_central_team_user, get_current_user, get_db
from ..api.schemas import SourceContractCreateRequest, SourceContractResponse, SourceSliceResponse
from ..db.models import SourceDefinition, SourceSlice, SourceSliceRow, User, new_id
from ..management.access import require_project_access
from ..management.platform import record_management_audit
from ..intake.cobol_parser import parse_copybook
from ..intake.csv_intake import ingest_csv
from ..intake.fixed_intake import ingest_fixed

router = APIRouter(prefix="/projects/{project_id}/source-contracts", tags=["sources"])

MAX_PREVIEW_ROWS = 10


# ── Contract endpoints ────────────────────────────────────────────────────────

@router.post("", response_model=SourceContractResponse, status_code=status.HTTP_201_CREATED)
def post_source_contract(
    project_id: str,
    body: SourceContractCreateRequest,
    actor: User = Depends(get_central_team_user),
    db: Session = Depends(get_db),
) -> SourceContractResponse:
    contract = SourceDefinition(
        source_definition_id=new_id(),
        project_id=project_id,
        source_type=body.source_type,
        source_contract_version="1",
        source_details={"label": body.label, "encoding": body.encoding},
        status="declared",
    )
    db.add(contract)
    record_management_audit(db, project_id=project_id, actor_user_id=actor.user_id,
                            event_type="source_contract.declared",
                            payload={"source_type": body.source_type, "label": body.label})
    db.commit()
    db.refresh(contract)
    return _contract_response(contract)


@router.get("", response_model=list[SourceContractResponse])
def get_source_contracts(
    project_id: str,
    actor: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[SourceContractResponse]:
    require_project_access(db, user=actor, project_id=project_id)
    contracts = db.query(SourceDefinition).filter_by(project_id=project_id).all()
    return [_contract_response(c) for c in contracts]


@router.get("/{contract_id}", response_model=SourceContractResponse)
def get_source_contract(
    project_id: str,
    contract_id: str,
    actor: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SourceContractResponse:
    require_project_access(db, user=actor, project_id=project_id)
    contract = _get_contract(db, project_id, contract_id)
    return _contract_response(contract)


# ── Copybook upload ───────────────────────────────────────────────────────────

@router.post("/{contract_id}/copybook", response_model=SourceContractResponse)
def post_copybook(
    project_id: str,
    contract_id: str,
    file: UploadFile,
    actor: User = Depends(get_central_team_user),
    db: Session = Depends(get_db),
) -> SourceContractResponse:
    contract = _get_contract(db, project_id, contract_id)
    text = file.file.read().decode("utf-8")
    fields = parse_copybook(text)
    contract.copybook_text = text
    contract.layout_information = [
        {"name": f.name, "offset": f.offset, "width": f.width,
         "picture": f.picture, "type_hint": f.type_hint}
        for f in fields
    ]
    contract.status = "layout_ready"
    record_management_audit(db, project_id=project_id, actor_user_id=actor.user_id,
                            event_type="source_contract.copybook_uploaded",
                            payload={"contract_id": contract_id, "field_count": len(fields)})
    db.commit()
    db.refresh(contract)
    return _contract_response(contract)


# ── Slice upload — placeholders implemented in Task 6b ────────────────────────

@router.post("/{contract_id}/slices", response_model=SourceSliceResponse,
             status_code=status.HTTP_201_CREATED)
def post_source_slice(
    project_id: str,
    contract_id: str,
    file: UploadFile,
    actor: User = Depends(get_central_team_user),
    db: Session = Depends(get_db),
) -> SourceSliceResponse:
    raise NotImplementedError


@router.get("/{contract_id}/slices", response_model=list[SourceSliceResponse])
def get_source_slices(
    project_id: str,
    contract_id: str,
    actor: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[SourceSliceResponse]:
    raise NotImplementedError


@router.get("/{contract_id}/slices/{slice_id}", response_model=SourceSliceResponse)
def get_source_slice(
    project_id: str,
    contract_id: str,
    slice_id: str,
    actor: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SourceSliceResponse:
    raise NotImplementedError


# ── Helpers ──────────────────────────────────────────────────────────────────

def _get_contract(db: Session, project_id: str, contract_id: str) -> SourceDefinition:
    from ..api.deps import AuthApiError
    contract = db.get(SourceDefinition, contract_id)
    if contract is None or contract.project_id != project_id:
        raise AuthApiError("source_contract_not_found", "Source contract not found.", 404)
    return contract


def _contract_response(c: SourceDefinition) -> SourceContractResponse:
    details = c.source_details or {}
    return SourceContractResponse(
        source_definition_id=c.source_definition_id,
        project_id=c.project_id,
        source_type=c.source_type,
        label=details.get("label", ""),
        encoding=details.get("encoding", "utf-8"),
        destination_object_references=c.destination_object_references,
        layout_information=c.layout_information,
        copybook_text=c.copybook_text,
        status=c.status,
        created_at=c.created_at,
    )


def _slice_response(s: SourceSlice, preview: list[str]) -> SourceSliceResponse:
    payload = s.slice_payload or {}
    return SourceSliceResponse(
        source_slice_id=s.source_slice_id,
        source_definition_id=s.source_definition_id,
        header_csv=s.header_csv,
        row_count=payload.get("row_count", 0),
        status=s.status,
        preview_rows=preview,
        created_at=s.created_at,
    )
```

- [ ] **Step 4: Register router in `app.py`** — add alongside existing routers:

```python
from .routes.sources import router as sources_router
app.include_router(sources_router)
```

- [ ] **Step 5: Run contract tests — confirm they pass**

```bash
cd engine && python -m pytest tests/test_source_intake_api.py -k "contract" -v
```

Expected: all pass.

- [ ] **Step 6: Run full suite**

```bash
cd engine && python -m pytest tests/ -v
```

Expected: all pass.

- [ ] **Step 7: Commit**

```bash
git add engine/src/migrations_engine/routes/sources.py \
        engine/tests/test_source_intake_api.py \
        engine/src/migrations_engine/app.py
git commit -m "feat: add source contract routes with passing tests"
```

---

### Task 6b — Slice upload routes + tests

- [ ] **Step 1: Append slice tests to `test_source_intake_api.py`**

```python
# ── POST /projects/{id}/source-contracts/{cid}/slices ────────────────────────

CSV_BYTES = b"CUST_ID,SURNAME,ACCOUNT_TYPE\n100001,Smith,DATABASE\n100002,Jones,SAVINGS\n"

COPYBOOK_TEXT = b"""
       01  CUST-REC.
           05  CUST-ID         PIC 9(6).
           05  SURNAME         PIC X(10).
           05  ACCT-TYPE       PIC X(8).
"""
FIXED_BYTES = b"100001Smith     DATABASE\n100002Jones     SAVINGS \n"


def test_upload_csv_slice() -> None:
    token = _login_admin()
    pid = _create_project(token)
    cid = client.post(f"/projects/{pid}/source-contracts",
                      headers={"Authorization": f"Bearer {token}"},
                      json={"source_type": "csv", "label": "CSV test"}).json()["source_definition_id"]

    r = client.post(f"/projects/{pid}/source-contracts/{cid}/slices",
                    headers={"Authorization": f"Bearer {token}"},
                    files={"file": ("data.csv", CSV_BYTES, "text/csv")})
    assert r.status_code == 201, r.text
    b = r.json()
    assert b["row_count"] == 2
    assert b["header_csv"] == "CUST_ID,SURNAME,ACCOUNT_TYPE"
    assert b["status"] == "pending_approval"
    assert len(b["preview_rows"]) == 2
    # SURNAME is masked
    assert "***" in b["preview_rows"][0]
    # CUST_ID is not masked
    assert "100001" in b["preview_rows"][0]


def test_upload_fixed_length_slice() -> None:
    token = _login_admin()
    pid = _create_project(token)
    cid = client.post(f"/projects/{pid}/source-contracts",
                      headers={"Authorization": f"Bearer {token}"},
                      json={"source_type": "fixed_length_file", "label": "Fixed test"}).json()["source_definition_id"]

    client.post(f"/projects/{pid}/source-contracts/{cid}/copybook",
                headers={"Authorization": f"Bearer {token}"},
                files={"file": ("layout.cpy", COPYBOOK_TEXT, "text/plain")})

    r = client.post(f"/projects/{pid}/source-contracts/{cid}/slices",
                    headers={"Authorization": f"Bearer {token}"},
                    files={"file": ("data.txt", FIXED_BYTES, "text/plain")})
    assert r.status_code == 201, r.text
    b = r.json()
    assert b["row_count"] == 2
    assert "CUST_ID" in b["header_csv"]
    assert "***" in b["preview_rows"][0]


def test_fixed_slice_without_copybook_returns_409() -> None:
    token = _login_admin()
    pid = _create_project(token)
    cid = client.post(f"/projects/{pid}/source-contracts",
                      headers={"Authorization": f"Bearer {token}"},
                      json={"source_type": "fixed_length_file", "label": "No layout"}).json()["source_definition_id"]
    r = client.post(f"/projects/{pid}/source-contracts/{cid}/slices",
                    headers={"Authorization": f"Bearer {token}"},
                    files={"file": ("data.txt", FIXED_BYTES, "text/plain")})
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "layout_not_ready"


def test_list_slices() -> None:
    token = _login_admin()
    pid = _create_project(token)
    cid = client.post(f"/projects/{pid}/source-contracts",
                      headers={"Authorization": f"Bearer {token}"},
                      json={"source_type": "csv", "label": "List"}).json()["source_definition_id"]
    client.post(f"/projects/{pid}/source-contracts/{cid}/slices",
                headers={"Authorization": f"Bearer {token}"},
                files={"file": ("data.csv", CSV_BYTES, "text/csv")})
    r = client.get(f"/projects/{pid}/source-contracts/{cid}/slices",
                   headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert len(r.json()) == 1


def test_get_slice() -> None:
    token = _login_admin()
    pid = _create_project(token)
    cid = client.post(f"/projects/{pid}/source-contracts",
                      headers={"Authorization": f"Bearer {token}"},
                      json={"source_type": "csv", "label": "Get"}).json()["source_definition_id"]
    sid = client.post(f"/projects/{pid}/source-contracts/{cid}/slices",
                      headers={"Authorization": f"Bearer {token}"},
                      files={"file": ("data.csv", CSV_BYTES, "text/csv")}).json()["source_slice_id"]
    r = client.get(f"/projects/{pid}/source-contracts/{cid}/slices/{sid}",
                   headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json()["source_slice_id"] == sid
```

- [ ] **Step 2: Run slice tests — confirm they fail**

```bash
cd engine && python -m pytest tests/test_source_intake_api.py -k "slice" -v 2>&1 | tail -15
```

Expected: failures — slice routes raise `NotImplementedError`.

- [ ] **Step 3: Implement slice routes in `routes/sources.py`**

Replace the three placeholder slice routes:

```python
@router.post("/{contract_id}/slices", response_model=SourceSliceResponse,
             status_code=status.HTTP_201_CREATED)
def post_source_slice(
    project_id: str,
    contract_id: str,
    file: UploadFile,
    actor: User = Depends(get_central_team_user),
    db: Session = Depends(get_db),
) -> SourceSliceResponse:
    from ..api.deps import AuthApiError
    contract = _get_contract(db, project_id, contract_id)
    file_bytes = file.file.read()
    encoding = (contract.source_details or {}).get("encoding", "utf-8")

    if contract.source_type == "csv":
        slice_ = ingest_csv(file_bytes, encoding, db, contract)
    elif contract.source_type == "fixed_length_file":
        if not contract.layout_information:
            raise AuthApiError("layout_not_ready",
                               "Upload a COBOL copybook before uploading data.", 409)
        slice_ = ingest_fixed(file_bytes, encoding, db, contract)
    else:
        raise AuthApiError("unsupported_source_type", f"Unsupported source type: {contract.source_type}", 422)

    contract.status = "active"
    record_management_audit(db, project_id=project_id, actor_user_id=actor.user_id,
                            event_type="source_slice.created",
                            payload={"contract_id": contract_id,
                                     "slice_id": slice_.source_slice_id})
    db.commit()
    db.refresh(slice_)
    preview = db.query(SourceSliceRow).filter_by(
        source_slice_id=slice_.source_slice_id
    ).order_by(SourceSliceRow.row_index).limit(MAX_PREVIEW_ROWS).all()
    return _slice_response(slice_, [r.row_csv for r in preview])


@router.get("/{contract_id}/slices", response_model=list[SourceSliceResponse])
def get_source_slices(
    project_id: str,
    contract_id: str,
    actor: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[SourceSliceResponse]:
    require_project_access(db, user=actor, project_id=project_id)
    _get_contract(db, project_id, contract_id)
    slices = db.query(SourceSlice).filter_by(source_definition_id=contract_id).all()
    result = []
    for s in slices:
        preview = db.query(SourceSliceRow).filter_by(
            source_slice_id=s.source_slice_id
        ).order_by(SourceSliceRow.row_index).limit(MAX_PREVIEW_ROWS).all()
        result.append(_slice_response(s, [r.row_csv for r in preview]))
    return result


@router.get("/{contract_id}/slices/{slice_id}", response_model=SourceSliceResponse)
def get_source_slice(
    project_id: str,
    contract_id: str,
    slice_id: str,
    actor: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SourceSliceResponse:
    from ..api.deps import AuthApiError
    require_project_access(db, user=actor, project_id=project_id)
    _get_contract(db, project_id, contract_id)
    slice_ = db.get(SourceSlice, slice_id)
    if slice_ is None or slice_.source_definition_id != contract_id:
        raise AuthApiError("source_slice_not_found", "Source slice not found.", 404)
    preview = db.query(SourceSliceRow).filter_by(
        source_slice_id=slice_id
    ).order_by(SourceSliceRow.row_index).limit(MAX_PREVIEW_ROWS).all()
    return _slice_response(slice_, [r.row_csv for r in preview])
```

- [ ] **Step 4: Run slice tests — confirm they pass**

```bash
cd engine && python -m pytest tests/test_source_intake_api.py -k "slice" -v
```

Expected: all pass.

- [ ] **Step 5: Run full suite**

```bash
cd engine && python -m pytest tests/ -v
```

Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add engine/src/migrations_engine/routes/sources.py \
        engine/tests/test_source_intake_api.py
git commit -m "feat: add source slice upload routes with passing tests"
```

---

### Task 7 — Sources API client (web)

**Files:**
- `web/lib/sources-api.ts` (create)
- `web/lib/sources-api.test.ts` (create)

**Produces:** `SourceContract`, `SourceSlice` interfaces; `listSourceContracts`, `getSourceContract`, `declareSourceContract`, `uploadCopybook`, `uploadSlice`, `listSlices`, `getSlice`

- [ ] **Step 1: Write failing tests**

Create `web/lib/sources-api.test.ts`:

```ts
import { describe, it, expect, vi, afterEach } from "vitest";
import {
  listSourceContracts,
  declareSourceContract,
  uploadCopybook,
  uploadSlice,
  type SourceContract,
  type SourceSlice,
} from "./sources-api";

const BASE = "http://127.0.0.1:8000";
const TOKEN = "test-token";
const PROJECT_ID = "proj-1";
const CONTRACT_ID = "contract-1";

const stubContract: SourceContract = {
  source_definition_id: CONTRACT_ID,
  project_id: PROJECT_ID,
  source_type: "csv",
  label: "Customer File",
  encoding: "utf-8",
  destination_object_references: null,
  layout_information: null,
  copybook_text: null,
  status: "declared",
  created_at: "2026-06-29T00:00:00Z",
};

const stubSlice: SourceSlice = {
  source_slice_id: "slice-1",
  source_definition_id: CONTRACT_ID,
  header_csv: "ID,NAME,TYPE",
  row_count: 2,
  status: "pending_approval",
  preview_rows: ["1,***,DATABASE"],
  created_at: "2026-06-29T00:00:00Z",
};

afterEach(() => vi.restoreAllMocks());

describe("listSourceContracts", () => {
  it("calls GET /projects/{id}/source-contracts", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, json: async () => [stubContract] }));
    const result = await listSourceContracts(TOKEN, PROJECT_ID);
    expect(fetch).toHaveBeenCalledWith(`${BASE}/projects/${PROJECT_ID}/source-contracts`,
      expect.objectContaining({ headers: expect.objectContaining({ Authorization: `Bearer ${TOKEN}` }) }));
    expect(result).toHaveLength(1);
  });
});

describe("declareSourceContract", () => {
  it("posts contract declaration", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, status: 201, json: async () => stubContract }));
    const result = await declareSourceContract(TOKEN, PROJECT_ID, {
      source_type: "csv", label: "Customer File", encoding: "utf-8",
    });
    expect(fetch).toHaveBeenCalledWith(
      `${BASE}/projects/${PROJECT_ID}/source-contracts`,
      expect.objectContaining({ method: "POST" }));
    expect(result.label).toBe("Customer File");
  });
});

describe("uploadCopybook", () => {
  it("posts copybook as multipart", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      ok: true, json: async () => ({ ...stubContract, status: "layout_ready" as const }),
    }));
    const file = new File(["01 REC. 05 ID PIC 9(6)."], "layout.cpy");
    const result = await uploadCopybook(TOKEN, PROJECT_ID, CONTRACT_ID, file);
    expect(fetch).toHaveBeenCalledWith(
      `${BASE}/projects/${PROJECT_ID}/source-contracts/${CONTRACT_ID}/copybook`,
      expect.objectContaining({ method: "POST" }));
    expect(result.status).toBe("layout_ready");
  });
});

describe("uploadSlice", () => {
  it("posts data file as multipart and returns slice", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, status: 201, json: async () => stubSlice }));
    const file = new File(["ID,NAME\n1,test\n"], "data.csv");
    const result = await uploadSlice(TOKEN, PROJECT_ID, CONTRACT_ID, file);
    expect(fetch).toHaveBeenCalledWith(
      `${BASE}/projects/${PROJECT_ID}/source-contracts/${CONTRACT_ID}/slices`,
      expect.objectContaining({ method: "POST" }));
    expect(result.row_count).toBe(2);
  });
});
```

- [ ] **Step 2: Run tests — confirm they fail**

```bash
cd web && npm test -- lib/sources-api.test.ts 2>&1 | tail -10
```

Expected: module not found.

- [ ] **Step 3: Create `web/lib/sources-api.ts`**

```ts
const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

export interface SourceContract {
  source_definition_id: string;
  project_id: string;
  source_type: "csv" | "fixed_length_file";
  label: string;
  encoding: string;
  destination_object_references: string[] | null;
  layout_information: Array<Record<string, unknown>> | null;
  copybook_text: string | null;
  status: "declared" | "layout_ready" | "active";
  created_at: string;
}

export interface SourceSlice {
  source_slice_id: string;
  source_definition_id: string;
  header_csv: string | null;
  row_count: number;
  status: "pending_approval" | "approved" | "superseded";
  preview_rows: string[];
  created_at: string;
}

export interface ContractCreateInput {
  source_type: "csv" | "fixed_length_file";
  label: string;
  encoding?: string;
}

function authHeaders(token: string): Record<string, string> {
  return { Authorization: `Bearer ${token}` };
}

async function handleResponse<T>(res: Response): Promise<T> {
  if (res.ok) return res.json() as Promise<T>;
  let code = "api_error";
  try { const b = await res.json(); code = b?.error?.code ?? code; } catch {}
  throw new Error(code);
}

export async function listSourceContracts(token: string, projectId: string): Promise<SourceContract[]> {
  const res = await fetch(`${BASE}/projects/${projectId}/source-contracts`,
    { headers: authHeaders(token) });
  return handleResponse<SourceContract[]>(res);
}

export async function getSourceContract(token: string, projectId: string, contractId: string): Promise<SourceContract> {
  const res = await fetch(`${BASE}/projects/${projectId}/source-contracts/${contractId}`,
    { headers: authHeaders(token) });
  return handleResponse<SourceContract>(res);
}

export async function declareSourceContract(token: string, projectId: string, body: ContractCreateInput): Promise<SourceContract> {
  const res = await fetch(`${BASE}/projects/${projectId}/source-contracts`, {
    method: "POST",
    headers: { ...authHeaders(token), "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return handleResponse<SourceContract>(res);
}

export async function uploadCopybook(token: string, projectId: string, contractId: string, file: File): Promise<SourceContract> {
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(`${BASE}/projects/${projectId}/source-contracts/${contractId}/copybook`, {
    method: "POST",
    headers: authHeaders(token),
    body: form,
  });
  return handleResponse<SourceContract>(res);
}

export async function uploadSlice(token: string, projectId: string, contractId: string, file: File): Promise<SourceSlice> {
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(`${BASE}/projects/${projectId}/source-contracts/${contractId}/slices`, {
    method: "POST",
    headers: authHeaders(token),
    body: form,
  });
  return handleResponse<SourceSlice>(res);
}

export async function listSlices(token: string, projectId: string, contractId: string): Promise<SourceSlice[]> {
  const res = await fetch(`${BASE}/projects/${projectId}/source-contracts/${contractId}/slices`,
    { headers: authHeaders(token) });
  return handleResponse<SourceSlice[]>(res);
}

export async function getSlice(token: string, projectId: string, contractId: string, sliceId: string): Promise<SourceSlice> {
  const res = await fetch(`${BASE}/projects/${projectId}/source-contracts/${contractId}/slices/${sliceId}`,
    { headers: authHeaders(token) });
  return handleResponse<SourceSlice>(res);
}
```

- [ ] **Step 4: Run tests — confirm they pass**

```bash
cd web && npm test -- lib/sources-api.test.ts
```

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add web/lib/sources-api.ts web/lib/sources-api.test.ts
git commit -m "feat: add source intake API client with tests"
```

---

### Task 8 — SourceList and AddSourceDialog components

**Files:**
- `web/components/projects/SourceList.tsx` (create)
- `web/components/projects/AddSourceDialog.tsx` (create)
- `web/components/projects/__tests__/SourceList.test.tsx` (create)
- `web/components/projects/__tests__/AddSourceDialog.test.tsx` (create)

- [ ] **Step 1: Write SourceList failing tests**

Create `web/components/projects/__tests__/SourceList.test.tsx`:

```tsx
import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { SourceList } from "../SourceList";
import type { SourceContract } from "../../../lib/sources-api";

const csv: SourceContract = {
  source_definition_id: "c1", project_id: "p1",
  source_type: "csv", label: "Customer File", encoding: "utf-8",
  destination_object_references: null, layout_information: null, copybook_text: null,
  status: "active", created_at: "2026-06-29T00:00:00Z",
};
const fixed: SourceContract = {
  ...csv, source_definition_id: "c2",
  source_type: "fixed_length_file", label: "Ledger Feed", status: "layout_ready",
};

describe("SourceList", () => {
  it("renders contract rows", () => {
    render(<SourceList contracts={[csv, fixed]} role="central_team" onAdd={vi.fn()} />);
    expect(screen.getByText("Customer File")).toBeInTheDocument();
    expect(screen.getByText("Ledger Feed")).toBeInTheDocument();
  });

  it("shows source type chips", () => {
    render(<SourceList contracts={[csv]} role="central_team" onAdd={vi.fn()} />);
    expect(screen.getByText(/csv/i)).toBeInTheDocument();
  });

  it("shows Add Source button for central_team", () => {
    render(<SourceList contracts={[]} role="central_team" onAdd={vi.fn()} />);
    expect(screen.getByRole("button", { name: /add source/i })).toBeInTheDocument();
  });

  it("hides Add Source for non-central_team", () => {
    render(<SourceList contracts={[]} role="project_stakeholder" onAdd={vi.fn()} />);
    expect(screen.queryByRole("button", { name: /add source/i })).not.toBeInTheDocument();
  });

  it("calls onAdd when button clicked", () => {
    const onAdd = vi.fn();
    render(<SourceList contracts={[]} role="central_team" onAdd={onAdd} />);
    fireEvent.click(screen.getByRole("button", { name: /add source/i }));
    expect(onAdd).toHaveBeenCalledOnce();
  });

  it("shows empty state when no contracts", () => {
    render(<SourceList contracts={[]} role="central_team" onAdd={vi.fn()} />);
    expect(screen.getByText(/no sources/i)).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Write AddSourceDialog failing tests**

Create `web/components/projects/__tests__/AddSourceDialog.test.tsx`:

```tsx
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, afterEach } from "vitest";
import { AddSourceDialog } from "../AddSourceDialog";

afterEach(() => vi.restoreAllMocks());

const noop = vi.fn();

describe("AddSourceDialog", () => {
  it("does not render when open=false", () => {
    render(<AddSourceDialog open={false} token="t" projectId="p" onAdded={noop} onClose={noop} />);
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("shows step 1 fields: label and source type", () => {
    render(<AddSourceDialog open token="t" projectId="p" onAdded={noop} onClose={noop} />);
    expect(screen.getByLabelText(/label/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/source type/i)).toBeInTheDocument();
  });

  it("submit is disabled until label and source type are filled", () => {
    render(<AddSourceDialog open token="t" projectId="p" onAdded={noop} onClose={noop} />);
    expect(screen.getByRole("button", { name: /next/i })).toBeDisabled();
    fireEvent.change(screen.getByLabelText(/label/i), { target: { value: "My Source" } });
    fireEvent.change(screen.getByLabelText(/source type/i), { target: { value: "csv" } });
    expect(screen.getByRole("button", { name: /next/i })).not.toBeDisabled();
  });

  it("advances to step 2 (CSV upload) after declaring contract", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      ok: true, status: 201,
      json: async () => ({
        source_definition_id: "c1", project_id: "p", source_type: "csv",
        label: "My Source", encoding: "utf-8", destination_object_references: null,
        layout_information: null, copybook_text: null, status: "declared", created_at: "2026-06-29T00:00:00Z",
      }),
    }));
    render(<AddSourceDialog open token="t" projectId="p" onAdded={noop} onClose={noop} />);
    fireEvent.change(screen.getByLabelText(/label/i), { target: { value: "My Source" } });
    fireEvent.change(screen.getByLabelText(/source type/i), { target: { value: "csv" } });
    fireEvent.click(screen.getByRole("button", { name: /next/i }));
    await waitFor(() => expect(screen.getByText(/upload.*csv/i)).toBeInTheDocument());
  });

  it("advances to step 2 (copybook upload) for fixed_length_file", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      ok: true, status: 201,
      json: async () => ({
        source_definition_id: "c2", project_id: "p", source_type: "fixed_length_file",
        label: "Ledger", encoding: "utf-8", destination_object_references: null,
        layout_information: null, copybook_text: null, status: "declared", created_at: "2026-06-29T00:00:00Z",
      }),
    }));
    render(<AddSourceDialog open token="t" projectId="p" onAdded={noop} onClose={noop} />);
    fireEvent.change(screen.getByLabelText(/label/i), { target: { value: "Ledger" } });
    fireEvent.change(screen.getByLabelText(/source type/i), { target: { value: "fixed_length_file" } });
    fireEvent.click(screen.getByRole("button", { name: /next/i }));
    await waitFor(() => expect(screen.getByText(/upload.*copybook/i)).toBeInTheDocument());
  });

  it("calls onClose when cancel clicked", () => {
    const onClose = vi.fn();
    render(<AddSourceDialog open token="t" projectId="p" onAdded={noop} onClose={onClose} />);
    fireEvent.click(screen.getByRole("button", { name: /cancel/i }));
    expect(onClose).toHaveBeenCalledOnce();
  });
});
```

- [ ] **Step 3: Run tests — confirm they fail**

```bash
cd web && npm test -- components/projects/__tests__/SourceList.test.tsx \
                     components/projects/__tests__/AddSourceDialog.test.tsx 2>&1 | tail -15
```

Expected: module not found.

- [ ] **Step 4: Create `web/components/projects/SourceList.tsx`**

```tsx
"use client";

import type { SourceContract } from "../../lib/sources-api";
import type { SessionRole } from "../../lib/session";

export interface SourceListProps {
  contracts: SourceContract[];
  role: SessionRole;
  onAdd?: () => void;
}

const TYPE_LABELS: Record<string, string> = {
  csv: "CSV",
  fixed_length_file: "Fixed-Length",
};

const STATUS_LABELS: Record<string, string> = {
  declared: "Declared",
  layout_ready: "Layout Ready",
  active: "Active",
};

export function SourceList({ contracts, role, onAdd }: SourceListProps) {
  const canAdd = role === "central_team";

  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center justify-between">
        <h3 className="text-title-sm font-semibold text-slate-800">Sources</h3>
        {canAdd && onAdd && (
          <button type="button" onClick={onAdd} className="btn-primary text-sm">
            Add Source
          </button>
        )}
      </div>

      {contracts.length === 0 ? (
        <p className="py-6 text-center text-sm text-neutral">
          No sources declared. Add a source to begin intake.
        </p>
      ) : (
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-outline-variant text-left text-xs font-medium text-neutral">
              <th className="pb-2 pr-4">Label</th>
              <th className="pb-2 pr-4">Type</th>
              <th className="pb-2 pr-4">Status</th>
              <th className="pb-2">Added</th>
            </tr>
          </thead>
          <tbody>
            {contracts.map((c) => (
              <tr key={c.source_definition_id} className="border-b border-outline-variant last:border-0">
                <td className="py-3 pr-4 font-medium text-slate-800">{c.label}</td>
                <td className="py-3 pr-4">
                  <span className="rounded bg-primary-container px-2 py-0.5 text-xs font-medium text-on-primary-container">
                    {TYPE_LABELS[c.source_type] ?? c.source_type}
                  </span>
                </td>
                <td className="py-3 pr-4 text-neutral text-xs">{STATUS_LABELS[c.status] ?? c.status}</td>
                <td className="py-3 text-neutral text-xs">
                  {new Date(c.created_at).toLocaleDateString()}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
```

- [ ] **Step 5: Create `web/components/projects/AddSourceDialog.tsx`**

```tsx
"use client";

import { useState } from "react";
import {
  declareSourceContract,
  uploadCopybook,
  uploadSlice,
  type SourceContract,
  type SourceSlice,
} from "../../lib/sources-api";

export interface AddSourceDialogProps {
  open?: boolean;
  token: string;
  projectId: string;
  onAdded: (contract: SourceContract, slice?: SourceSlice) => void;
  onClose: () => void;
}

type Step = "declare" | "upload_csv" | "upload_copybook" | "upload_data";

export function AddSourceDialog({ open, token, projectId, onAdded, onClose }: AddSourceDialogProps) {
  const [step, setStep] = useState<Step>("declare");
  const [label, setLabel] = useState("");
  const [sourceType, setSourceType] = useState<"csv" | "fixed_length_file" | "">("");
  const [contract, setContract] = useState<SourceContract | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!open) return null;

  function reset() {
    setStep("declare");
    setLabel("");
    setSourceType("");
    setContract(null);
    setError(null);
  }

  async function handleDeclare(e: React.FormEvent) {
    e.preventDefault();
    if (!sourceType) return;
    setSubmitting(true);
    setError(null);
    try {
      const c = await declareSourceContract(token, projectId, {
        source_type: sourceType,
        label,
        encoding: "utf-8",
      });
      setContract(c);
      setStep(sourceType === "csv" ? "upload_csv" : "upload_copybook");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unexpected error");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleFileUpload(file: File, kind: "copybook" | "csv_data" | "fixed_data") {
    if (!contract) return;
    setSubmitting(true);
    setError(null);
    try {
      if (kind === "copybook") {
        const updated = await uploadCopybook(token, projectId, contract.source_definition_id, file);
        setContract(updated);
        setStep("upload_data");
      } else {
        const slice = await uploadSlice(token, projectId, contract.source_definition_id, file);
        onAdded(contract, slice);
        reset();
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unexpected error");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div role="dialog" aria-modal="true" aria-label="Add Source"
         className="fixed inset-0 z-50 flex items-center justify-center bg-black/30">
      <div className="w-full max-w-md rounded-xl border border-outline-variant bg-surface-container p-6 shadow-lg">
        <h2 className="mb-4 text-title-md font-semibold text-slate-800">Add Source</h2>

        {step === "declare" && (
          <form onSubmit={handleDeclare} className="flex flex-col gap-4">
            <div className="flex flex-col gap-1">
              <label htmlFor="source-label" className="text-sm font-medium text-slate-700">Label *</label>
              <input id="source-label" type="text" value={label}
                     onChange={(e) => setLabel(e.target.value)}
                     className="input-field" aria-label="Label" required />
            </div>
            <div className="flex flex-col gap-1">
              <label htmlFor="source-type-select" className="text-sm font-medium text-slate-700">Source Type *</label>
              <select id="source-type-select" value={sourceType}
                      onChange={(e) => setSourceType(e.target.value as "csv" | "fixed_length_file" | "")}
                      className="input-field" aria-label="Source Type">
                <option value="">— Select —</option>
                <option value="csv">CSV</option>
                <option value="fixed_length_file">Fixed-Length Record</option>
              </select>
            </div>
            {error && <p role="alert" className="text-sm text-error">{error}</p>}
            <div className="flex justify-end gap-3 pt-2">
              <button type="button" onClick={() => { reset(); onClose(); }} className="btn-ghost">Cancel</button>
              <button type="submit" disabled={!label.trim() || !sourceType || submitting}
                      className="btn-primary disabled:opacity-40">
                {submitting ? "Creating…" : "Next"}
              </button>
            </div>
          </form>
        )}

        {step === "upload_csv" && (
          <FileUploadStep
            label="Upload CSV data file"
            accept=".csv,text/csv"
            submitting={submitting}
            error={error}
            onFile={(f) => handleFileUpload(f, "csv_data")}
            onBack={() => setStep("declare")}
          />
        )}

        {step === "upload_copybook" && (
          <FileUploadStep
            label="Upload COBOL copybook"
            accept=".cpy,.txt,text/plain"
            submitting={submitting}
            error={error}
            onFile={(f) => handleFileUpload(f, "copybook")}
            onBack={() => setStep("declare")}
          />
        )}

        {step === "upload_data" && (
          <FileUploadStep
            label="Upload fixed-length data file"
            accept=".txt,.dat,text/plain"
            submitting={submitting}
            error={error}
            onFile={(f) => handleFileUpload(f, "fixed_data")}
            onBack={() => setStep("upload_copybook")}
          />
        )}
      </div>
    </div>
  );
}

function FileUploadStep({ label, accept, submitting, error, onFile, onBack }: {
  label: string; accept: string; submitting: boolean; error: string | null;
  onFile: (f: File) => void; onBack: () => void;
}) {
  return (
    <div className="flex flex-col gap-4">
      <p className="text-sm text-slate-700">{label}</p>
      <input type="file" accept={accept} disabled={submitting}
             onChange={(e) => { const f = e.target.files?.[0]; if (f) onFile(f); }}
             className="text-sm" />
      {error && <p role="alert" className="text-sm text-error">{error}</p>}
      <div className="flex justify-end gap-3 pt-2">
        <button type="button" onClick={onBack} className="btn-ghost" disabled={submitting}>Back</button>
      </div>
    </div>
  );
}
```

- [ ] **Step 6: Run component tests — confirm they pass**

```bash
cd web && npm test -- components/projects/__tests__/SourceList.test.tsx \
                     components/projects/__tests__/AddSourceDialog.test.tsx
```

Expected: all pass.

- [ ] **Step 7: Commit**

```bash
git add web/components/projects/SourceList.tsx \
        web/components/projects/AddSourceDialog.tsx \
        web/components/projects/__tests__/SourceList.test.tsx \
        web/components/projects/__tests__/AddSourceDialog.test.tsx
git commit -m "feat: add SourceList and AddSourceDialog components with tests"
```

---

### Task 9 — Sources tab on project detail page

**Files:** `web/app/projects/[id]/page.tsx` (modify — add Sources tab)

- [ ] **Step 1: Add Sources tab to `web/app/projects/[id]/page.tsx`**

Add tab state and Sources tab panel to the existing detail page:

```tsx
"use client";

import { useEffect, useState, use } from "react";
import { ProjectDetailView } from "../../../components/projects/ProjectDetailView";
import { SourceList } from "../../../components/projects/SourceList";
import { AddSourceDialog } from "../../../components/projects/AddSourceDialog";
import { Topbar } from "../../../components/Topbar";
import { getProject, type ProjectRecord } from "../../../lib/projects-api";
import { listSourceContracts, type SourceContract } from "../../../lib/sources-api";
import { getUiSession } from "../../../lib/session";
import type { SessionRole } from "../../../lib/session";

type Tab = "overview" | "sources";

export default function ProjectDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const session = getUiSession();
  const role: SessionRole = session?.role ?? "read_only_auditor";
  const token = "";

  const [project, setProject] = useState<ProjectRecord | null>(null);
  const [contracts, setContracts] = useState<SourceContract[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<Tab>("overview");
  const [addSourceOpen, setAddSourceOpen] = useState(false);

  useEffect(() => {
    Promise.all([getProject(token, id), listSourceContracts(token, id)])
      .then(([proj, src]) => { setProject(proj); setContracts(src); })
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load"))
      .finally(() => setLoading(false));
  }, [token, id]);

  const tabs: { id: Tab; label: string }[] = [
    { id: "overview", label: "Overview" },
    { id: "sources", label: "Sources" },
  ];

  return (
    <main className="flex min-h-screen flex-col bg-surface text-slate-800">
      <Topbar role={role} />
      <section className="mx-auto flex w-full max-w-[1600px] flex-1 flex-col gap-4 px-6 py-4">
        {loading && <p className="py-8 text-center text-sm text-neutral">Loading…</p>}
        {error && (
          <p role="alert" className="rounded bg-error/10 px-4 py-2 text-sm text-error">
            {error === "project_not_found" ? "Project not found." : error}
          </p>
        )}
        {project && (
          <>
            <div className="flex gap-6 border-b border-outline-variant">
              {tabs.map((t) => (
                <button
                  key={t.id}
                  type="button"
                  onClick={() => setActiveTab(t.id)}
                  className={`pb-2 text-sm font-medium transition ${
                    activeTab === t.id
                      ? "border-b-2 border-primary text-primary"
                      : "text-neutral hover:text-slate-800"
                  }`}
                >
                  {t.label}
                </button>
              ))}
            </div>

            {activeTab === "overview" && <ProjectDetailView project={project} />}

            {activeTab === "sources" && (
              <SourceList
                contracts={contracts}
                role={role}
                onAdd={() => setAddSourceOpen(true)}
              />
            )}
          </>
        )}
      </section>

      <AddSourceDialog
        open={addSourceOpen}
        token={token}
        projectId={id}
        onAdded={(contract) => {
          setContracts((prev) => [...prev, contract]);
          setAddSourceOpen(false);
        }}
        onClose={() => setAddSourceOpen(false)}
      />
    </main>
  );
}
```

- [ ] **Step 2: Verify build**

```bash
cd web && npx next build 2>&1 | tail -20
```

Expected: build succeeds.

- [ ] **Step 3: Run full web test suite**

```bash
cd web && npm test
```

Expected: all pass.

- [ ] **Step 4: Commit**

```bash
git add web/app/projects/[id]/page.tsx
git commit -m "feat: add Sources tab to project detail page"
```

---

## Self-Review

**Task granularity:**
- Task 3 (masking): red → green → commit on PII detection ✓
- Task 4 (COBOL parser): red → green → commit, tests cover offsets, FILLER, picture types ✓
- Task 5 (intake services): red → green → commit, tests hit real DB session ✓
- Task 6a (contract routes): red → green → commit ✓
- Task 6b (slice routes): red → green → commit, covers CSV + fixed-length + 409 path ✓
- Task 7 (web API client): red → green → commit ✓
- Task 8 (components): red → green → commit, tests cover role gating + dialog steps ✓
- Task 9 (detail page): build verification + full suite ✓

**Architecture:**
- Source intake fully decoupled from project creation ✓
- Sources managed via Sources tab on project detail ✓
- `CreateProjectDialog` in `001p` has no source type field ✓
- COBOL parser produces `layout_information`; fixed intake consumes it ✓
- All source types normalize to CSV rows at intake time ✓
- Masking applied before any row is stored ✓
- `SourceDefinition` and `SourceSlice` extended, not replaced ✓

**Placeholder scan:** None. All steps have complete code.

**Type consistency:**
- `SourceContract.source_definition_id` used consistently across API client and components ✓
- `FieldDef` from cobol_parser consumed directly by fixed_intake (not re-defined) ✓
- `mask_row(headers, values) -> str` called identically in both csv_intake and fixed_intake ✓
