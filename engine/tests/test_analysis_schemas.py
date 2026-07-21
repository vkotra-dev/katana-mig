import pytest
from pydantic import ValidationError
from migrations_engine.management.analysis_schemas import (
    ColumnSchema,
    AnalysisResult,
    HeaderMismatch,
    parse_header,
    validate_against_header,
    normalize_to_header,
)

def test_column_schema_nullable() -> None:
    # nullable must be bool
    schema = ColumnSchema(name="foo", inferred_type="text", nullable=True, max_length=None)
    assert schema.nullable is True
    
    with pytest.raises(ValidationError):
        ColumnSchema(name="foo", inferred_type="text", nullable="yes", max_length=None)  # type: ignore

def test_column_schema_max_length() -> None:
    schema = ColumnSchema(name="foo", inferred_type="text", nullable=False, max_length=10)
    assert schema.max_length == 10
    
    with pytest.raises(ValidationError):
        ColumnSchema(name="foo", inferred_type="text", nullable=False, max_length=-1)
    
    with pytest.raises(ValidationError):
        ColumnSchema(name="foo", inferred_type="text", nullable=False, max_length=True)  # type: ignore

def test_parse_header() -> None:
    assert parse_header("a,b,c") == ["a", "b", "c"]
    assert parse_header("") == []

def test_validate_against_header_success() -> None:
    result = AnalysisResult(columns=[
        ColumnSchema(name="a", inferred_type="text", nullable=True, max_length=None),
        ColumnSchema(name="b", inferred_type="integer", nullable=False, max_length=None),
    ])
    validate_against_header(result, "a,b")

def test_validate_against_header_failure() -> None:
    result = AnalysisResult(columns=[
        ColumnSchema(name="A", inferred_type="text", nullable=True, max_length=None),
        ColumnSchema(name="b", inferred_type="integer", nullable=False, max_length=None),
    ])
    with pytest.raises(HeaderMismatch):
        validate_against_header(result, "a,b")

def test_normalize_to_header() -> None:
    result = AnalysisResult(columns=[
        ColumnSchema(name="A", inferred_type="text", nullable=True, max_length=None),
        ColumnSchema(name="b", inferred_type="integer", nullable=False, max_length=None),
    ])
    normalize_to_header(result, "a,b")
    assert result.columns[0].name == "a"
    assert result.columns[1].name == "b"

def test_normalize_to_header_count_mismatch() -> None:
    result = AnalysisResult(columns=[
        ColumnSchema(name="a", inferred_type="text", nullable=True, max_length=None),
    ])
    with pytest.raises(HeaderMismatch):
        normalize_to_header(result, "a,b")
