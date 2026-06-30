from __future__ import annotations

from dataclasses import dataclass
import re


@dataclass(frozen=True, slots=True)
class FieldDef:
    name: str
    offset: int
    width: int
    picture: str
    type_hint: str


_LEVEL_RE = re.compile(r"^\s*(\d{2})\s+([A-Z0-9-]+)\b(.*)$", re.IGNORECASE)
_PIC_RE = re.compile(r"\bPIC\s+([A-Z0-9\(\)V\.\-]+)\.", re.IGNORECASE)
_OCCURS_RE = re.compile(r"\bOCCURS\s+(\d+)\s+TIMES\b", re.IGNORECASE)


def parse_copybook(text: str) -> list[FieldDef]:
    lines = [line.rstrip() for line in text.splitlines() if line.strip()]
    if not lines:
        raise ValueError("no fields found in copybook")

    fields: list[FieldDef] = []
    offset = 0
    in_record = False
    for line in lines:
        match = _LEVEL_RE.match(line)
        if match is None:
            continue
        level = int(match.group(1))
        name = match.group(2).replace("-", "_")
        tail = match.group(3)
        if level == 1:
            in_record = True
            continue
        if not in_record:
            continue
        if "REDEFINES" in tail.upper():
            continue

        picture_match = _PIC_RE.search(tail)
        if picture_match is None:
            continue
        picture = picture_match.group(1).upper()
        width = _picture_width(picture)
        type_hint = _picture_type_hint(picture)
        occurs_match = _OCCURS_RE.search(tail)
        repeats = int(occurs_match.group(1)) if occurs_match is not None else 1
        field_width = width * repeats
        if name.upper() != "FILLER":
            fields.append(
                FieldDef(
                    name=name,
                    offset=offset,
                    width=field_width,
                    picture=picture,
                    type_hint=type_hint,
                )
            )
        offset += field_width

    if not fields:
        raise ValueError("no fields found in copybook")
    return fields


def _picture_width(picture: str) -> int:
    total_width = 0
    parts = re.split(r"[V.]", picture)
    for part in parts:
        for token, repeat in re.findall(r"([X9A])(?:\((\d+)\))?", part):
            total_width += int(repeat) if repeat else 1
    if total_width == 0:
        raise ValueError(f"invalid picture clause: {picture}")
    return total_width


def _picture_type_hint(picture: str) -> str:
    if "V" in picture or "." in picture:
        return "decimal"
    if "9" in picture:
        return "integer"
    return "string"
