from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
import csv
import io
import tempfile

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..api.deps import AuthApiError
from ..db.models import Feed, FeedSlice, FeedSliceRow, new_id
from .masking import is_pii_field, mask_row


MAX_UPLOAD_BYTES = 50 * 1024 * 1024


@dataclass(frozen=True, slots=True)
class IngestResult:
    source_slice: FeedSlice
    preview_rows: list[str]
    row_count: int


def ingest_csv(
    db: Session,
    *,
    source_definition: Feed,
    raw_bytes: bytes,
    encoding_override: str | None = None,
    file_storage_path: str | None = None,
) -> IngestResult:
    if len(raw_bytes) > MAX_UPLOAD_BYTES:
        raise AuthApiError("file_too_large", "Uploaded file exceeds 50 MB.", 413)

    encoding = encoding_override or _contract_encoding(source_definition)
    text = _decode_upload(raw_bytes, encoding=encoding)
    reader = csv.reader(io.StringIO(text))
    try:
        headers = next(reader)
    except StopIteration as exc:
        raise AuthApiError("copybook_parse_error", "CSV header row is required.", 422) from exc

    if not headers:
        raise AuthApiError("copybook_parse_error", "CSV header row is required.", 422)

    storage_path = file_storage_path or _store_upload_bytes(raw_bytes, suffix=".csv")
    row_warnings: list[str] = []
    masked_fields = [header for header in headers if is_pii_field(header)]
    slice_rows: list[tuple[int, str]] = []

    for row_index, values in enumerate(reader):
        if len(values) != len(headers):
            row_warnings.append(f"row {row_index + 1}: expected {len(headers)} values, got {len(values)}")
        normalized_values = _normalize_values(values, width=len(headers))
        slice_rows.append((row_index, mask_row(headers, normalized_values)))

    source_slice = _create_source_slice(
        db,
        source_definition=source_definition,
        header_csv=_dump_csv_row(headers),
        file_storage_path=storage_path,
        parse_warnings=row_warnings,
        masked_fields=masked_fields,
        row_csv_rows=slice_rows,
    )
    return IngestResult(
        source_slice=source_slice,
        preview_rows=[row_csv for _index, row_csv in slice_rows[:10]],
        row_count=len(slice_rows),
    )


def _create_source_slice(
    db: Session,
    *,
    source_definition: Feed,
    header_csv: str,
    file_storage_path: str,
    parse_warnings: list[str],
    masked_fields: list[str],
    row_csv_rows: list[tuple[int, str]],
) -> FeedSlice:
    version_number = _next_slice_version(db, source_definition.source_definition_id)
    source_slice = FeedSlice(
        source_slice_id=new_id(),
        source_definition_id=source_definition.source_definition_id,
        source_contract_version=source_definition.source_contract_version,
        source_slice_version=f"v{version_number}",
        source_schema_artifact=source_definition.layout_information,
        masking_policy={"masked_fields": masked_fields},
        slice_payload={
            "masked_fields": masked_fields,
            "parse_warnings": parse_warnings,
            "row_count": len(row_csv_rows),
        },
        header_csv=header_csv,
        status="pending_approval",
        parse_warnings=parse_warnings,
        file_storage_path=file_storage_path,
        approved_at=None,
        approved_by_user_id=None,
    )
    db.add(source_slice)
    db.flush()
    for row_index, row_csv in row_csv_rows:
        db.add(
            FeedSliceRow(
                source_slice_id=source_slice.source_slice_id,
                row_index=row_index,
                row_csv=row_csv,
            )
        )
    return source_slice


def _next_slice_version(db: Session, source_definition_id: str) -> int:
    rows = db.scalars(
        select(FeedSlice.source_slice_version).where(
            FeedSlice.source_definition_id == source_definition_id
        )
    ).all()
    highest = 0
    for version in rows:
        if version.startswith("v") and version[1:].isdigit():
            highest = max(highest, int(version[1:]))
    return highest + 1


def _normalize_values(values: Iterable[str], *, width: int) -> list[str]:
    normalized = list(values)
    if len(normalized) < width:
        normalized.extend([""] * (width - len(normalized)))
    return normalized[:width]


def _dump_csv_row(values: list[str]) -> str:
    buffer = io.StringIO()
    csv.writer(buffer).writerow(values)
    return buffer.getvalue().rstrip("\r\n")


def _contract_encoding(source_definition: Feed) -> str:
    details = source_definition.source_details or {}
    encoding = details.get("encoding") if isinstance(details, dict) else None
    return str(encoding or "utf-8")


def _decode_upload(raw_bytes: bytes, *, encoding: str) -> str:
    for candidate in (encoding, "utf-8", "latin-1", "cp1252"):
        try:
            return raw_bytes.decode(candidate)
        except UnicodeDecodeError:
            continue
    raise AuthApiError("unsupported_encoding", "Uploaded file encoding is not supported.", 422)


def _store_upload_bytes(raw_bytes: bytes, *, suffix: str) -> str:
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix, mode="wb") as handle:
        handle.write(raw_bytes)
        return handle.name
