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


def test_parse_simple_copybook_fields() -> None:
    fields = parse_copybook(SIMPLE_COPYBOOK)
    names = [field.name for field in fields]
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
    names = [field.name for field in fields]
    assert "FILLER" not in names


def test_filler_offset_still_counted() -> None:
    fields = parse_copybook(FILLER_COPYBOOK)
    amount = next(field for field in fields if field.name == "AMOUNT")
    assert amount.offset == 10


def test_picture_9_type_hint() -> None:
    fields = parse_copybook(SIMPLE_COPYBOOK)
    cust_id = next(field for field in fields if field.name == "CUST_ID")
    assert cust_id.type_hint == "integer"


def test_picture_x_type_hint() -> None:
    fields = parse_copybook(SIMPLE_COPYBOOK)
    surname = next(field for field in fields if field.name == "SURNAME")
    assert surname.type_hint == "string"


def test_picture_v_type_hint() -> None:
    fields = parse_copybook(FILLER_COPYBOOK)
    amount = next(field for field in fields if field.name == "AMOUNT")
    assert amount.type_hint == "decimal"
    assert amount.width == 12


def test_empty_copybook_raises() -> None:
    with pytest.raises(ValueError, match="no fields"):
        parse_copybook("   ")


def test_hyphen_to_underscore_in_name() -> None:
    fields = parse_copybook(SIMPLE_COPYBOOK)
    assert all("-" not in field.name for field in fields)
