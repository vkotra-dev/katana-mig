import csv
from typing import Literal, Any
from pydantic import BaseModel, ConfigDict, field_validator

class ColumnSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    inferred_type: Literal["text", "integer", "decimal", "date", "boolean", "uuid"]
    nullable: bool
    max_length: int | None

    @field_validator("nullable", mode="before")
    @classmethod
    def _validate_nullable(cls, v: Any) -> bool | None:
        if v is not None and not isinstance(v, bool):
            raise ValueError("nullable must be a JSON boolean")
        return v

    @field_validator("max_length", mode="before")
    @classmethod
    def _validate_max_length(cls, v: Any) -> int | None:
        if v is not None and (not isinstance(v, int) or isinstance(v, bool) or v < 0):
            raise ValueError("max_length must be a non-negative integer or null")
        return v

class AnalysisResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    columns: list[ColumnSchema]
    re_use_score: int | None = None
    ddl: str = ""  # AI-generated CREATE TABLE DDL (default empty for backward compatibility)

class HeaderMismatch(Exception):
    pass

def parse_header(header_csv: str | None) -> list[str]:
    if not header_csv:
        return []
    try:
        return next(csv.reader([header_csv]))
    except StopIteration:
        return []

def validate_against_header(result: AnalysisResult, header_csv: str | None) -> None:
    if not header_csv:
        return
    expected = parse_header(header_csv)
    actual = [c.name for c in result.columns]
    if expected != actual:
        raise HeaderMismatch(f"AI generated column names do not match the header exactly. Expected: {expected}, got: {actual}")

def normalize_to_header(result: AnalysisResult, header_csv: str | None) -> None:
    if not header_csv:
        return
    expected = parse_header(header_csv)
    if len(expected) != len(result.columns):
        raise HeaderMismatch(f"Column count mismatch. Expected {len(expected)}, got {len(result.columns)}")
    for i, expected_name in enumerate(expected):
        result.columns[i].name = expected_name
