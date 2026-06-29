from __future__ import annotations

from dataclasses import dataclass

from ..db.models import LookupSnapshot
from .exceptions import UnmappedLookupValueError


@dataclass(frozen=True)
class MappedRow:
    source_field: str
    source_value: str
    destination_field: str
    destination_value: str


def apply_lookup_value(snapshot: LookupSnapshot, source_value: str) -> str:
    mapped = snapshot.value_map.get(source_value)
    if mapped is None:
        raise UnmappedLookupValueError(
            unmapped_value=source_value,
            lookup_name=snapshot.lookup_name,
        )
    return mapped
