"use client";

export interface SummaryStripProps {
  total: number;
  active: number;
  archived: number;
  needsAttention: number;
  pendingReview: number;
}

function MetricCard({
  accent,
  label,
  value,
}: {
  accent?: string;
  label: string;
  value: number;
}) {
  return (
    <div className="space-y-1 rounded-2xl border border-outline-variant bg-surface-container p-5 shadow-sm">
      <div className={`text-3xl font-semibold tabular-nums ${accent ?? "text-slate-900"}`}>{value}</div>
      <div className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">{label}</div>
    </div>
  );
}

export function SummaryStrip({ total, active, archived, needsAttention, pendingReview }: SummaryStripProps) {
  return (
    <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-5">
      <MetricCard label="Total Projects" value={total} />
      <MetricCard accent="text-primary" label="Active" value={active} />
      <MetricCard accent="text-red-600" label="Needs Attention" value={needsAttention} />
      <MetricCard accent="text-amber-600" label="Pending Review" value={pendingReview} />
      <MetricCard label="Archived" value={archived} />
    </div>
  );
}
