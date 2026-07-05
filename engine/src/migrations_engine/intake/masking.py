from __future__ import annotations

import csv
import io

from ..ai.config import get_ai_config


def _pii_config():
    return get_ai_config().pii


def is_pii_field(name: str) -> bool:
    normalized = name.lower().replace(" ", "").replace("_", "").replace("-", "")
    return normalized in _pii_config().field_names


def _matches_pii_pattern(value: str) -> bool:
    v = value.strip()
    if not v:
        return False
    return any(pattern.match(v) for pattern in _pii_config().patterns)


def mask_row(headers: list[str], values: list[str]) -> str:
    masked = [
        "***"
        if is_pii_field(header) or _matches_pii_pattern(value)
        else value
        for header, value in zip(headers, values, strict=False)
    ]
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(masked)
    return buffer.getvalue().rstrip("\r\n")
