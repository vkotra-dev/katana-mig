from __future__ import annotations

from collections.abc import Iterable
import csv
import io

from sqlalchemy.orm import Session

from ..api.deps import AuthApiError
from ..db.models import SourceDefinition
from .cobol_parser import FieldDef, parse_copybook
from .csv_intake import IngestResult, _create_source_slice, _decode_upload, _store_upload_bytes
from .masking import mask_row


def ingest_fixed(
    db: Session,
    *,
    source_definition: SourceDefinition,
    raw_bytes: bytes,
    encoding_override: str | None = None,
    file_storage_path: str | None = None,
) -> IngestResult:
    layout_text = source_definition.copybook_text
    if not layout_text:
        raise AuthApiError("layout_not_ready", "Copybook must be uploaded before fixed-length data.", 409)

    if len(raw_bytes) > 50 * 1024 * 1024:
        raise AuthApiError("file_too_large", "Uploaded file exceeds 50 MB.", 413)

    encoding = encoding_override or _contract_encoding(source_definition)
    text = _decode_upload(raw_bytes, encoding=encoding)
    fields = parse_copybook(layout_text)
    header_values = [field.name for field in fields]
    row_warnings: list[str] = []
    storage_path = file_storage_path or _store_upload_bytes(raw_bytes, suffix=".dat")
    row_csv_rows: list[tuple[int, str]] = []

    for row_index, line in enumerate(_iter_non_empty_lines(text)):
        normalized_line = line.rstrip("\r\n")
        total_width = fields[-1].offset + fields[-1].width
        if len(normalized_line) != total_width:
            row_warnings.append(
                f"row {row_index + 1}: expected {total_width} characters, got {len(normalized_line)}"
            )
        padded_line = normalized_line[:total_width].ljust(total_width)
        values = [padded_line[field.offset : field.offset + field.width].strip() for field in fields]
        row_csv_rows.append((row_index, mask_row(header_values, values)))

    source_slice = _create_source_slice(
        db,
        source_definition=source_definition,
        header_csv=_dump_csv_row(header_values),
        file_storage_path=storage_path,
        parse_warnings=row_warnings,
        masked_fields=[field.name for field in fields if field.name.upper() in {"NAME", "SURNAME", "DOB"}],
        row_csv_rows=row_csv_rows,
    )
    return IngestResult(
        source_slice=source_slice,
        preview_rows=[row_csv for _index, row_csv in row_csv_rows[:10]],
        row_count=len(row_csv_rows),
    )


def _iter_non_empty_lines(text: str) -> Iterable[str]:
    for line in text.splitlines():
        if line.strip():
            yield line


def _dump_csv_row(values: list[str]) -> str:
    buffer = io.StringIO()
    csv.writer(buffer).writerow(values)
    return buffer.getvalue().rstrip("\r\n")


def _contract_encoding(source_definition: SourceDefinition) -> str:
    details = source_definition.source_details or {}
    encoding = details.get("encoding") if isinstance(details, dict) else None
    return str(encoding or "utf-8")
