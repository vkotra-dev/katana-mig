from __future__ import annotations

import csv
import json
from collections import Counter
from typing import Literal

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..api.deps import AuthApiError
from ..api.schemas import (
    SourceAnalysisResponse,
    SourceSchemaArtifactResponse,
    SourceSchemaColumnResponse,
    SourceValueSummaryResponse,
)
from ..db.models import (
    SourceDefinition,
    SourceSchemaArtifact,
    SourceSlice,
    SourceSliceRow,
    SourceValueSummary,
    User,
)
from ..management.platform import record_management_audit

try:
    from ..ai.factory import get_adapter
except ModuleNotFoundError:  # pragma: no cover - optional SDK dependency may be absent in tests
    get_adapter = None  # type: ignore[assignment]


SYSTEM_PROMPT = (
    "You are a data analyst. Given CSV or fixed-length record samples, "
    "infer column schemas. Return a JSON object matching the schema below."
)


class ColumnSchema(BaseModel):
    name: str
    inferred_type: Literal["text", "integer", "decimal", "date", "boolean", "uuid"]
    nullable: bool
    max_length: int | None


class AnalysisResult(BaseModel):
    columns: list[ColumnSchema]


def analyze_source_slice(
    db: Session,
    *,
    actor: User,
    project_id: str,
    source_definition_id: str,
) -> SourceAnalysisResponse:
    source_definition = _get_source_definition(db, project_id=project_id, source_definition_id=source_definition_id)
    source_slice = _latest_approved_source_slice(db, source_definition_id=source_definition_id)
    existing_artifact = db.scalar(
        select(SourceSchemaArtifact).where(
            SourceSchemaArtifact.source_definition_id == source_definition_id,
            SourceSchemaArtifact.source_slice_version == source_slice.source_slice_version,
        )
    )
    if existing_artifact is not None:
        return SourceAnalysisResponse(schema_artifact_id=existing_artifact.schema_artifact_id)

    sample_rows = _load_slice_rows(db, source_slice_id=source_slice.source_slice_id, limit=200)
    sample_text = _build_sample_text(header_csv=source_slice.header_csv, rows=sample_rows)
    system_prompt = _build_system_prompt(source_definition)

    if get_adapter is None:
        raise AuthApiError("ai_adapter_unavailable", "AI adapter dependency is unavailable.", 503)
    adapter = get_adapter("field_mapping")
    analysis_result = adapter.call(system_prompt, sample_text, AnalysisResult)

    schema_artifact = SourceSchemaArtifact(
        source_definition_id=source_definition_id,
        source_slice_version=source_slice.source_slice_version,
        columns=[column.model_dump(mode="python") for column in analysis_result.columns],
    )
    db.add(schema_artifact)
    db.flush()

    value_summaries = _build_value_summaries(db, source_slice=source_slice)
    db.add_all(value_summaries)
    db.flush()

    record_management_audit(
        db,
        project_id=project_id,
        actor_user_id=actor.user_id,
        event_type="source_analysis_completed",
        payload={
            "source_definition_id": source_definition_id,
            "source_slice_id": source_slice.source_slice_id,
            "source_slice_version": source_slice.source_slice_version,
            "schema_artifact_id": schema_artifact.schema_artifact_id,
            "sample_row_count": len(sample_rows),
            "value_summary_count": len(value_summaries),
        },
    )
    db.commit()
    db.refresh(schema_artifact)

    return SourceAnalysisResponse(schema_artifact_id=schema_artifact.schema_artifact_id)


def get_latest_source_schema_artifact(
    db: Session,
    *,
    project_id: str,
    source_definition_id: str,
) -> SourceSchemaArtifactResponse:
    _get_source_definition(db, project_id=project_id, source_definition_id=source_definition_id)
    artifact = db.scalar(
        select(SourceSchemaArtifact)
        .where(SourceSchemaArtifact.source_definition_id == source_definition_id)
        .order_by(SourceSchemaArtifact.created_at.desc(), SourceSchemaArtifact.schema_artifact_id.desc())
    )
    if artifact is None:
        raise AuthApiError("source_analysis_not_found", "Source analysis has not been run.", 404)
    return _schema_artifact_response(artifact)


def list_source_value_summaries(
    db: Session,
    *,
    project_id: str,
    source_definition_id: str,
    field_name: str | None = None,
) -> list[SourceValueSummaryResponse]:
    _get_source_definition(db, project_id=project_id, source_definition_id=source_definition_id)
    source_slice_version = _latest_source_slice_version(db, source_definition_id=source_definition_id)
    if source_slice_version is None:
        raise AuthApiError("source_analysis_not_found", "Source analysis has not been run.", 404)

    stmt = select(SourceValueSummary).where(
        SourceValueSummary.source_definition_id == source_definition_id,
        SourceValueSummary.source_slice_version == source_slice_version,
    )
    if field_name:
        stmt = stmt.where(SourceValueSummary.field_name == field_name)
    rows = db.scalars(stmt.order_by(SourceValueSummary.field_name.asc())).all()
    return [_value_summary_response(row) for row in rows]


def _get_source_definition(db: Session, *, project_id: str, source_definition_id: str) -> SourceDefinition:
    source_definition = db.get(SourceDefinition, source_definition_id)
    if source_definition is None or source_definition.project_id != project_id:
        raise AuthApiError("source_not_found", "Source contract not found.", 404)
    return source_definition


def _latest_approved_source_slice(db: Session, *, source_definition_id: str) -> SourceSlice:
    source_slice = db.scalar(
        select(SourceSlice)
        .where(
            SourceSlice.source_definition_id == source_definition_id,
            SourceSlice.status == "approved",
        )
        .order_by(SourceSlice.approved_at.desc().nullslast(), SourceSlice.created_at.desc())
    )
    if source_slice is None:
        raise AuthApiError("source_analysis_not_ready", "An approved source slice is required.", 409)
    return source_slice


def _latest_source_slice_version(db: Session, *, source_definition_id: str) -> str | None:
    source_slice = db.scalar(
        select(SourceSlice.source_slice_version)
        .where(
            SourceSlice.source_definition_id == source_definition_id,
            SourceSlice.status == "approved",
        )
        .order_by(SourceSlice.approved_at.desc().nullslast(), SourceSlice.created_at.desc())
    )
    return source_slice


def _load_slice_rows(db: Session, *, source_slice_id: str, limit: int | None = None) -> list[str]:
    stmt = (
        select(SourceSliceRow.row_csv)
        .where(SourceSliceRow.source_slice_id == source_slice_id)
        .order_by(SourceSliceRow.row_index.asc())
    )
    if limit is not None:
        stmt = stmt.limit(limit)
    return list(db.scalars(stmt))


def _build_sample_text(*, header_csv: str | None, rows: list[str]) -> str:
    parts: list[str] = []
    if header_csv:
        parts.append(header_csv)
    parts.extend(rows)
    return "\n".join(parts)


def _build_system_prompt(source_definition: SourceDefinition) -> str:
    layout_information = json.dumps(source_definition.layout_information or [], ensure_ascii=False)
    if source_definition.source_type == "fixed_length_file":
        return f"{SYSTEM_PROMPT}\nSource type: fixed_length_file\nLayout information: {layout_information}"
    return f"{SYSTEM_PROMPT}\nSource type: {source_definition.source_type}"


def _build_value_summaries(db: Session, *, source_slice: SourceSlice) -> list[SourceValueSummary]:
    headers = _parse_csv_row(source_slice.header_csv)
    counts_by_field: dict[str, Counter[str]] = {header: Counter() for header in headers}
    rows = _load_slice_rows(db, source_slice_id=source_slice.source_slice_id)

    for row_csv in rows:
        values = _parse_csv_row(row_csv)
        normalized_values = _normalize_values(values, width=len(headers))
        for header, value in zip(headers, normalized_values, strict=False):
            counter = counts_by_field[header]
            if value not in counter and len(counter) >= 500:
                continue
            counter[value] += 1

    return [
        SourceValueSummary(
            source_definition_id=source_slice.source_definition_id,
            source_slice_version=source_slice.source_slice_version,
            field_name=field_name,
            value_counts=dict(counter),
        )
        for field_name, counter in counts_by_field.items()
    ]


def _parse_csv_row(value: str | None) -> list[str]:
    if not value:
        return []
    return next(csv.reader([value]))


def _normalize_values(values: list[str], *, width: int) -> list[str]:
    normalized = list(values)
    if len(normalized) < width:
        normalized.extend([""] * (width - len(normalized)))
    return normalized[:width]


def _schema_artifact_response(artifact: SourceSchemaArtifact) -> SourceSchemaArtifactResponse:
    return SourceSchemaArtifactResponse(
        schema_artifact_id=artifact.schema_artifact_id,
        source_definition_id=artifact.source_definition_id,
        source_slice_version=artifact.source_slice_version,
        columns=[SourceSchemaColumnResponse.model_validate(column) for column in artifact.columns],
        created_at=artifact.created_at,
    )


def _value_summary_response(summary: SourceValueSummary) -> SourceValueSummaryResponse:
    return SourceValueSummaryResponse(
        summary_id=summary.summary_id,
        source_definition_id=summary.source_definition_id,
        source_slice_version=summary.source_slice_version,
        field_name=summary.field_name,
        value_counts=summary.value_counts,
        created_at=summary.created_at,
    )
