"use client";

import type { RunStatus } from "../../lib/runs-api";

const STATUS_LABELS: Record<RunStatus, string> = {
  queued: "queued",
  running: "running",
  paused: "paused",
  completed: "completed",
  failed: "failed",
  awaiting_approval: "awaiting approval",
};

const STATUS_STYLES: Record<RunStatus, string> = {
  queued: "bg-slate-100 text-slate-600",
  running: "bg-blue-100 text-blue-700",
  paused: "bg-amber-100 text-amber-800",
  completed: "bg-emerald-100 text-emerald-700",
  failed: "bg-red-100 text-red-700",
  awaiting_approval: "bg-amber-100 text-amber-800",
};

export function runStatusLabel(status: RunStatus): string {
  return STATUS_LABELS[status];
}

export function runStatusClassName(status: RunStatus): string {
  return STATUS_STYLES[status];
}

export interface RunStatusChipProps {
  status: RunStatus;
}

export function RunStatusChip({ status }: RunStatusChipProps) {
  return (
    <span
      className={`status-chip inline-flex items-center ${runStatusClassName(status)}`}
      data-status={status}
    >
      {runStatusLabel(status)}
    </span>
  );
}
