from __future__ import annotations

import pytest

from migrations_engine.intake.masking import is_pii_field, mask_row


@pytest.mark.parametrize(
    "name,expected",
    [
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
    ],
)
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
    assert result.startswith("1,***,")
    assert '"see, attached"' in result or "see, attached" in result


def test_mask_row_empty_values() -> None:
    headers = ["id", "email"]
    values = ["1", ""]
    result = mask_row(headers, values)
    assert result == "1,***"
