from __future__ import annotations

import csv
import io

PII_FIELD_NAMES: frozenset[str] = frozenset(
    {
        "name",
        "surname",
        "firstname",
        "lastname",
        "fullname",
        "dob",
        "dateofbirth",
        "birthdate",
        "ssn",
        "socialsecuritynumber",
        "email",
        "emailaddress",
        "phone",
        "phonenumber",
        "mobile",
        "telephone",
        "address",
        "streetaddress",
        "postcode",
        "zipcode",
        "zip",
        "nino",
        "nin",
        "passport",
        "passportnumber",
        "driverslicense",
        "drivinglicense",
        "accountnumber",
        "bankaccount",
        "iban",
        "sortcode",
    }
)


def is_pii_field(name: str) -> bool:
    normalized = name.lower().replace(" ", "").replace("_", "").replace("-", "")
    return normalized in PII_FIELD_NAMES


def mask_row(headers: list[str], values: list[str]) -> str:
    masked = ["***" if is_pii_field(header) else value for header, value in zip(headers, values, strict=False)]
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(masked)
    return buffer.getvalue().rstrip("\r\n")
