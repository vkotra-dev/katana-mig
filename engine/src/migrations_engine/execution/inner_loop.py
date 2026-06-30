from __future__ import annotations

import csv
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db.models import LookupSnapshot, MappingSnapshot, RunRecord, SourceSlice, SourceSliceRow
from ..mapping import FieldBinding, UnmappedLookupValueError, apply_lookup_value
from .checkpoints import write_checkpoint
from .lookup_delta import mark_run_paused_for_lookup_delta, open_lookup_delta_change_request


@dataclass(frozen=True)
class InnerLoopResult:
    processed_rows: int
    paused: bool
    last_completed_row: int | None
    pause_reason: str | None = None


def _parse_source_row(header_csv: str | None, row_csv: str) -> dict[str, str]:
    headers = next(csv.reader([header_csv])) if header_csv else []
    values = next(csv.reader([row_csv]))
    if not headers:
        return {str(index): value for index, value in enumerate(values)}
    return {header: values[index] if index < len(values) else "" for index, header in enumerate(headers)}


def _select_lookup_snapshot(lookup_snapshots: dict[str, LookupSnapshot], lookup_name: str) -> LookupSnapshot:
    snapshot = lookup_snapshots.get(lookup_name)
    if snapshot is None:
        raise KeyError(f"Missing lookup snapshot for {lookup_name!r}.")
    return snapshot


def _approved_snapshots_for_run(run: RunRecord) -> dict[str, Any]:
    snapshots: dict[str, Any] = {
        "source_slice_version": run.source_slice_version,
        "mapping_snapshot_version": run.mapping_snapshot_version,
        "lookup_snapshot_version": run.lookup_snapshot_version,
        "lookup_snapshot_versions": run.lookup_snapshot_versions or {},
    }
    return snapshots


def process_inner_loop(
    db: Session,
    *,
    run: RunRecord,
    source_slice: SourceSlice,
    mapping_snapshot: MappingSnapshot,
    lookup_snapshots: dict[str, LookupSnapshot],
    start_row_index: int,
    actor_user_id: str | None,
    checkpoint_interval: int,
) -> InnerLoopResult:
    bindings = [
        FieldBinding(
            source_field=str(binding["source_field"]),
            destination_field=str(binding["destination_field"]),
            lookup_name=str(binding["lookup_name"]),
        )
        for binding in mapping_snapshot.field_bindings
    ]
    rows = list(
        db.scalars(
            select(SourceSliceRow)
            .where(SourceSliceRow.source_slice_id == source_slice.source_slice_id)
            .order_by(SourceSliceRow.row_index.asc())
        )
    )

    processed_rows = 0
    last_completed_row: int | None = start_row_index - 1 if start_row_index > 0 else None
    for row in rows:
        if row.row_index < start_row_index:
            continue
        parsed = _parse_source_row(source_slice.header_csv, row.row_csv)
        for binding in bindings:
            source_value = parsed.get(binding.source_field, "")
            lookup_snapshot = _select_lookup_snapshot(lookup_snapshots, binding.lookup_name)
            try:
                apply_lookup_value(lookup_snapshot, source_value)
            except UnmappedLookupValueError:
                checkpoint = write_checkpoint(
                    db,
                    run=run,
                    current_object=run.destination_object_name,
                    current_environment=run.environment,
                    approved_snapshots=_approved_snapshots_for_run(run),
                    last_completed_row=last_completed_row,
                    pause_reason="lookup_delta",
                )
                change_request = open_lookup_delta_change_request(
                    db,
                    run=run,
                    lookup_name=binding.lookup_name,
                    unmapped_value=source_value,
                    mapping_snapshot_version=run.mapping_snapshot_version,
                    lookup_snapshot_version=lookup_snapshot.lookup_snapshot_version,
                    actor_user_id=actor_user_id,
                )
                mark_run_paused_for_lookup_delta(
                    db,
                    run=run,
                    change_request_id=change_request.change_request_id,
                    last_completed_row=last_completed_row,
                )
                db.flush()
                return InnerLoopResult(
                    processed_rows=processed_rows,
                    paused=True,
                    last_completed_row=last_completed_row,
                    pause_reason=checkpoint.pause_reason,
                )
        processed_rows += 1
        last_completed_row = row.row_index
        if (row.row_index + 1) % checkpoint_interval == 0:
            write_checkpoint(
                db,
                run=run,
                current_object=run.destination_object_name,
                current_environment=run.environment,
                approved_snapshots=_approved_snapshots_for_run(run),
                last_completed_row=last_completed_row,
            )
    return InnerLoopResult(processed_rows=processed_rows, paused=False, last_completed_row=last_completed_row)
