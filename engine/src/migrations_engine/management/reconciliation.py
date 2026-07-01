from __future__ import annotations

import csv
from datetime import UTC, datetime
from io import StringIO
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..api.deps import AuthApiError
from ..api.schemas import (
    LineageResponse,
    LineageRowResponse,
    ReconciliationCheckResult,
    ReconciliationExportResponse,
    ReconciliationReportResponse,
    RowCountSummary,
)
from ..db.models import (
    MappingArtifact,
    MappingSnapshot,
    ReconciliationLineageRow,
    ReconciliationReport,
    RunRecord,
    SourceDefinition,
    SourceSlice,
    SourceSliceRow,
)


def _get_run_or_404(db: Session, *, project_id: str, run_id: str) -> RunRecord:
    run = db.scalar(select(RunRecord).where(RunRecord.run_id == run_id, RunRecord.project_id == project_id))
    if run is None:
        raise AuthApiError("run_not_found", "Run not found.", 404)
    return run


def _get_source_slice_or_404(db: Session, *, project_id: str, source_definition_id: str, source_slice_version: str) -> SourceSlice:
    source_slice = db.scalar(
        select(SourceSlice)
        .join(SourceDefinition, SourceDefinition.source_definition_id == SourceSlice.source_definition_id)
        .where(
            SourceDefinition.project_id == project_id,
            SourceSlice.source_definition_id == source_definition_id,
            SourceSlice.source_slice_version == source_slice_version,
        )
        .order_by(SourceSlice.created_at.desc())
    )
    if source_slice is None:
        raise AuthApiError("source_slice_not_found", "Source slice not found.", 404)
    return source_slice


def _get_mapping_snapshot_or_404(
    db: Session,
    *,
    project_id: str,
    destination_object_name: str,
    mapping_snapshot_version: str,
) -> MappingSnapshot:
    mapping_snapshot = db.scalar(
        select(MappingSnapshot).where(
            MappingSnapshot.project_id == project_id,
            MappingSnapshot.destination_object_name == destination_object_name,
            MappingSnapshot.mapping_snapshot_version == mapping_snapshot_version,
        )
    )
    if mapping_snapshot is None:
        raise AuthApiError("mapping_snapshot_not_found", "Mapping snapshot not found.", 404)
    return mapping_snapshot


def _get_mapping_artifact_or_404(db: Session, *, project_id: str, run_id: str) -> MappingArtifact:
    mapping_artifact = db.scalar(
        select(MappingArtifact).where(
            MappingArtifact.project_id == project_id,
            MappingArtifact.run_id == run_id,
        )
    )
    if mapping_artifact is None:
        raise AuthApiError("mapping_artifact_not_found", "Mapping artifact not found.", 404)
    return mapping_artifact


def _gate_is_approved(run: RunRecord, gate: str) -> bool:
    for record in run.approvals or []:
        if record.get("gate") == gate and record.get("decision") == "approved":
            return True
    return False


def _parse_first_csv_field(row_csv: str) -> str | None:
    reader = csv.reader(StringIO(row_csv))
    row = next(reader, None)
    if not row:
        return None
    return row[0] if row[0] != "" else None


def _binding_rules(field_bindings: list[dict[str, Any]]) -> list[str]:
    return [f"{binding['source_field']} → {binding['destination_field']}" for binding in field_bindings]


def _destination_field(field_bindings: list[dict[str, Any]]) -> str | None:
    if not field_bindings:
        return None
    first = field_bindings[0]
    destination_field = first.get("destination_field")
    return str(destination_field) if destination_field else None


def _source_rows_for_report(db: Session, *, source_slice_id: str) -> list[SourceSliceRow]:
    return list(
        db.scalars(
            select(SourceSliceRow)
            .where(SourceSliceRow.source_slice_id == source_slice_id)
            .order_by(SourceSliceRow.row_index.asc())
        )
    )


def _to_check(name: str, status: str, detail: str) -> ReconciliationCheckResult:
    return ReconciliationCheckResult(check_name=name, status=status, detail=detail)


def _build_lineage_rows(
    db: Session,
    *,
    run: RunRecord,
    report: ReconciliationReport,
    source_rows: list[SourceSliceRow],
    mapped_rows: list[dict[str, Any]],
    field_bindings: list[dict[str, Any]],
) -> list[ReconciliationCheckResult]:
    checks: list[ReconciliationCheckResult] = []
    rules_applied = _binding_rules(field_bindings)
    destination_field = _destination_field(field_bindings)

    sorted_source_rows = sorted(source_rows, key=lambda row: row.row_index)
    for index, source_row in enumerate(sorted_source_rows):
        if source_row.row_index != index:
            raise ValueError("source row index gap detected — lineage cannot be reconstructed")

    if len(source_rows) > len(mapped_rows):
        checks.append(
            _to_check(
                "source_row_gap",
                "fail",
                "source row count is greater than mapped row count; lineage cannot be reconstructed completely.",
            )
        )

    seen_destination_ids: set[str] = set()
    for index, source_row in enumerate(sorted_source_rows):
        mapped_row = mapped_rows[index] if index < len(mapped_rows) else None
        source_row_key = _parse_first_csv_field(source_row.row_csv)
        destination_row_id = None
        outcome = "rejected"
        outcome_detail = None

        if mapped_row is not None:
            if destination_field is not None:
                value = mapped_row.get(destination_field)
                destination_row_id = value if value not in {"", None} else None

            if mapped_row.get("destination_row_id") not in {None, ""} and destination_row_id is None:
                destination_row_id = str(mapped_row["destination_row_id"])

            if any(
                mapped_row.get(binding["destination_field"]) in {None, ""}
                for binding in field_bindings
                if binding.get("destination_field")
            ):
                outcome = "partially_mapped"
                outcome_detail = "one or more mapped destination fields are null."
            elif destination_row_id is None:
                outcome = "rejected"
                outcome_detail = "no destination row produced."
            elif destination_row_id in seen_destination_ids:
                outcome = "duplicated"
                outcome_detail = f"duplicate destination row id {destination_row_id}."
            else:
                outcome = "confirmed"
                seen_destination_ids.add(destination_row_id)

        db.add(
            ReconciliationLineageRow(
                report_id=report.report_id,
                run_id=run.run_id,
                source_row_index=source_row.row_index,
                source_row_key=source_row_key,
                destination_row_id=destination_row_id,
                mapping_rules_applied=rules_applied,
                outcome=outcome,
                outcome_detail=outcome_detail,
            )
        )

    if len(mapped_rows) > len(source_rows):
        orphan_count = len(mapped_rows) - len(source_rows)
        for index in range(orphan_count):
            mapped_row = mapped_rows[len(source_rows) + index]
            destination_row_id = None
            if destination_field is not None:
                value = mapped_row.get(destination_field)
                destination_row_id = value if value not in {None, ""} else None
            if destination_row_id is None and mapped_row.get("destination_row_id") not in {None, ""}:
                destination_row_id = str(mapped_row["destination_row_id"])
            db.add(
                ReconciliationLineageRow(
                    report_id=report.report_id,
                    run_id=run.run_id,
                    source_row_index=None,
                    source_row_key=None,
                    destination_row_id=destination_row_id,
                    mapping_rules_applied=rules_applied,
                    outcome="rejected",
                    outcome_detail="orphaned mapped row — no source row at this index",
                )
            )
        checks.append(
            _to_check(
                "orphaned_mapped_rows",
                "fail",
                "mapped row count is greater than source row count; surplus mapped rows were recorded as orphaned lineage rows.",
            )
        )

    return checks


def _count_lineages(db: Session, *, report_id: str) -> dict[str, int]:
    rows = list(
        db.scalars(
            select(ReconciliationLineageRow).where(ReconciliationLineageRow.report_id == report_id)
        )
    )
    return {
        "source_rows": len(rows),
        "destination_rows": len(rows),
        "rejected": sum(1 for row in rows if row.outcome == "rejected"),
        "duplicated": sum(1 for row in rows if row.outcome == "duplicated"),
        "partially_mapped": sum(1 for row in rows if row.outcome == "partially_mapped"),
    }


def _compute_row_count_summary(
    *,
    source_rows: list[SourceSliceRow],
    mapped_rows: list[dict[str, Any]],
    lineage_counts: dict[str, int],
) -> RowCountSummary:
    return RowCountSummary(
        source_rows=len(source_rows),
        destination_rows=len(mapped_rows),
        rejected=lineage_counts["rejected"],
        duplicated=lineage_counts["duplicated"],
        partially_mapped=lineage_counts["partially_mapped"],
    )


def _evaluate_row_count_check(summary: RowCountSummary) -> ReconciliationCheckResult:
    if summary.source_rows == summary.destination_rows:
        return _to_check("row_count", "pass", "source row count matches destination row count.")
    return _to_check(
        "row_count",
        "fail",
        f"source row count {summary.source_rows} does not match destination row count {summary.destination_rows}.",
    )


def _evaluate_key_integrity_check(
    *,
    source_rows: list[SourceSliceRow],
    report_id: str,
    db: Session,
) -> ReconciliationCheckResult:
    sampled_rows = source_rows[:50]
    lineage_rows = list(
        db.scalars(
            select(ReconciliationLineageRow).where(ReconciliationLineageRow.report_id == report_id)
        )
    )
    index_to_lineage = {row.source_row_index: row for row in lineage_rows if row.source_row_index is not None}
    missing: list[str] = []
    for source_row in sampled_rows:
        source_key = _parse_first_csv_field(source_row.row_csv)
        lineage_row = index_to_lineage.get(source_row.row_index)
        if lineage_row is None or lineage_row.outcome == "rejected":
            missing.append(source_key or f"row-{source_row.row_index}")
    if missing:
        return _to_check("key_integrity", "fail", f"missing or rejected lineage rows for: {', '.join(missing)}.")
    return _to_check("key_integrity", "pass", "all sampled source keys were represented in lineage.")


def _evaluate_null_rate_check(*, mapped_rows: list[dict[str, Any]], field_bindings: list[dict[str, Any]]) -> ReconciliationCheckResult:
    destination_fields = [binding["destination_field"] for binding in field_bindings if binding.get("destination_field")]
    if not destination_fields:
        return _to_check("null_rate", "pass", "no destination fields were available for null-rate analysis.")
    failed_fields: list[str] = []
    for field_name in destination_fields:
        total = len(mapped_rows)
        null_count = sum(1 for row in mapped_rows if row.get(field_name) in {None, ""})
        if total and null_count / total >= 0.05:
            failed_fields.append(field_name)
    if failed_fields:
        return _to_check("null_rate", "fail", f"null rate exceeds threshold for: {', '.join(failed_fields)}.")
    return _to_check("null_rate", "pass", "all destination fields remain below the null-rate threshold.")


def _evaluate_lookup_coverage_check(*, mapped_rows: list[dict[str, Any]], field_bindings: list[dict[str, Any]]) -> ReconciliationCheckResult:
    lookup_fields = [binding for binding in field_bindings if binding.get("lookup_name")]
    if not lookup_fields:
        return _to_check("lookup_coverage", "pass", "no lookup-translated fields were present.")
    missing: list[str] = []
    for binding in lookup_fields:
        destination_field = str(binding["destination_field"])
        if any(row.get(destination_field) in {None, ""} for row in mapped_rows):
            missing.append(destination_field)
    if missing:
        return _to_check("lookup_coverage", "fail", f"lookup coverage is missing for: {', '.join(sorted(set(missing)))}.")
    return _to_check("lookup_coverage", "pass", "all lookup-translated fields are populated.")


def _load_context(
    db: Session,
    *,
    project_id: str,
    run_id: str,
) -> tuple[RunRecord, SourceSlice, MappingSnapshot, MappingArtifact, list[SourceSliceRow]]:
    run = _get_run_or_404(db, project_id=project_id, run_id=run_id)
    if run.source_definition_reference is None or run.source_slice_version is None or run.mapping_snapshot_version is None:
        raise AuthApiError("reconciliation_not_ready", "Run does not have pinned reconciliation artifacts.", 409)

    source_slice = _get_source_slice_or_404(
        db,
        project_id=project_id,
        source_definition_id=run.source_definition_reference,
        source_slice_version=run.source_slice_version,
    )
    mapping_snapshot = _get_mapping_snapshot_or_404(
        db,
        project_id=project_id,
        destination_object_name=run.destination_object_name,
        mapping_snapshot_version=run.mapping_snapshot_version,
    )
    mapping_artifact = _get_mapping_artifact_or_404(db, project_id=project_id, run_id=run_id)
    source_rows = _source_rows_for_report(db, source_slice_id=source_slice.source_slice_id)
    return run, source_slice, mapping_snapshot, mapping_artifact, source_rows


def trigger_reconciliation(
    db: Session,
    *,
    project_id: str,
    run_id: str,
) -> ReconciliationReportResponse:
    run = _get_run_or_404(db, project_id=project_id, run_id=run_id)
    if run.status != "completed":
        raise AuthApiError("reconciliation_not_ready", "Run must be completed before reconciliation can run.", 409)
    if not _gate_is_approved(run, "gate_2"):
        raise AuthApiError("gate_2_not_approved", "Gate 2 must be approved before reconciliation can run.", 422)
    existing_in_progress = db.scalar(
        select(ReconciliationReport).where(
            ReconciliationReport.run_id == run_id,
            ReconciliationReport.overall_status == "in_progress",
        )
    )
    if existing_in_progress is not None:
        raise AuthApiError("reconciliation_in_progress", "Reconciliation is already in progress.", 409)

    run, source_slice, mapping_snapshot, mapping_artifact, source_rows = _load_context(
        db, project_id=project_id, run_id=run_id
    )

    report = ReconciliationReport(
        run_id=run_id,
        checks=[],
        overall_status="in_progress",
        row_count_summary=None,
    )
    db.add(report)
    db.flush()

    try:
        gap_checks = _build_lineage_rows(
            db,
            run=run,
            report=report,
            source_rows=source_rows,
            mapped_rows=mapping_artifact.mapped_rows,
            field_bindings=mapping_snapshot.field_bindings,
        )
    except ValueError as exc:
        gap_checks = [_to_check("source_row_gap", "fail", str(exc))]
    lineage_counts = _count_lineages(db, report_id=report.report_id)
    row_count_summary = _compute_row_count_summary(
        source_rows=source_rows,
        mapped_rows=mapping_artifact.mapped_rows,
        lineage_counts=lineage_counts,
    )

    checks = [
        _evaluate_row_count_check(row_count_summary),
        _evaluate_key_integrity_check(source_rows=source_rows, report_id=report.report_id, db=db),
        _evaluate_null_rate_check(mapped_rows=mapping_artifact.mapped_rows, field_bindings=mapping_snapshot.field_bindings),
        _evaluate_lookup_coverage_check(mapped_rows=mapping_artifact.mapped_rows, field_bindings=mapping_snapshot.field_bindings),
        *gap_checks,
    ]
    report.checks = [check.model_dump() for check in checks]
    report.row_count_summary = row_count_summary.model_dump()
    report.overall_status = "fail" if any(check.status == "fail" for check in checks) else "pass"
    report.completed_at = datetime.now(UTC)

    db.commit()
    db.refresh(report)
    return ReconciliationReportResponse.model_validate(report)


def get_latest_report(
    db: Session,
    *,
    project_id: str,
    run_id: str,
) -> ReconciliationReportResponse:
    _ = _get_run_or_404(db, project_id=project_id, run_id=run_id)
    report = db.scalar(
        select(ReconciliationReport)
        .join(RunRecord, RunRecord.run_id == ReconciliationReport.run_id)
        .where(ReconciliationReport.run_id == run_id, RunRecord.project_id == project_id)
        .order_by(ReconciliationReport.created_at.desc())
    )
    if report is None:
        raise AuthApiError("reconciliation_not_found", "Reconciliation report not found.", 404)
    return ReconciliationReportResponse.model_validate(report)


def list_reports(
    db: Session,
    *,
    project_id: str,
    run_id: str,
) -> list[ReconciliationReportResponse]:
    _ = _get_run_or_404(db, project_id=project_id, run_id=run_id)
    reports = list(
        db.scalars(
            select(ReconciliationReport)
            .join(RunRecord, RunRecord.run_id == ReconciliationReport.run_id)
            .where(ReconciliationReport.run_id == run_id, RunRecord.project_id == project_id)
            .order_by(ReconciliationReport.created_at.desc())
        )
    )
    return [ReconciliationReportResponse.model_validate(report) for report in reports]


def get_lineage(
    db: Session,
    *,
    project_id: str,
    run_id: str,
    report_id: str,
    offset: int = 0,
    limit: int = 100,
    outcome: str | None = None,
    source_row_index: int | None = None,
    destination_row_id: str | None = None,
) -> LineageResponse:
    if source_row_index is not None and destination_row_id is not None:
        raise AuthApiError(
            "invalid_filter",
            "source_row_index and destination_row_id are mutually exclusive.",
            400,
        )
    _ = _get_run_or_404(db, project_id=project_id, run_id=run_id)
    report = db.scalar(
        select(ReconciliationReport).where(
            ReconciliationReport.report_id == report_id,
            ReconciliationReport.run_id == run_id,
        )
    )
    if report is None:
        raise AuthApiError("reconciliation_not_found", "Reconciliation report not found.", 404)

    stmt = select(ReconciliationLineageRow).where(ReconciliationLineageRow.report_id == report_id)
    if outcome is not None:
        stmt = stmt.where(ReconciliationLineageRow.outcome == outcome)
    if source_row_index is not None:
        stmt = stmt.where(ReconciliationLineageRow.source_row_index == source_row_index)
    if destination_row_id is not None:
        stmt = stmt.where(ReconciliationLineageRow.destination_row_id == destination_row_id)

    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = list(db.scalars(stmt.order_by(ReconciliationLineageRow.created_at.asc()).offset(offset).limit(limit)))
    return LineageResponse(
        rows=[LineageRowResponse.model_validate(row) for row in rows],
        total=total,
        offset=offset,
        limit=limit,
    )


def export_report(
    db: Session,
    *,
    project_id: str,
    run_id: str,
    report_id: str,
) -> ReconciliationExportResponse:
    report = db.scalar(
        select(ReconciliationReport)
        .join(RunRecord, RunRecord.run_id == ReconciliationReport.run_id)
        .where(
            ReconciliationReport.report_id == report_id,
            ReconciliationReport.run_id == run_id,
            RunRecord.project_id == project_id,
        )
    )
    if report is None:
        raise AuthApiError("reconciliation_not_found", "Reconciliation report not found.", 404)

    lineage_rows = list(
        db.scalars(
            select(ReconciliationLineageRow)
            .where(ReconciliationLineageRow.report_id == report_id)
            .order_by(ReconciliationLineageRow.created_at.asc())
        )
    )
    exported_at = datetime.now(UTC)
    return ReconciliationExportResponse(
        report_id=report.report_id,
        run_id=report.run_id,
        exported_at=exported_at,
        checks=[ReconciliationCheckResult.model_validate(item) for item in report.checks],
        overall_status=report.overall_status,  # type: ignore[arg-type]
        row_count_summary=RowCountSummary.model_validate(report.row_count_summary) if report.row_count_summary else None,
        lineage_rows=[LineageRowResponse.model_validate(row) for row in lineage_rows],
    )
