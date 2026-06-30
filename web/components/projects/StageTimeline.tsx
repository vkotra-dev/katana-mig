"use client";

import type { LatestRunSummary } from "../../lib/projects-api";

const STAGES = [
  "ingestion",
  "intake",
  "planning",
  "approval gate",
  "implementation",
  "verification",
  "review",
  "delivery",
];

function normalizeStage(value: string | null | undefined): string {
  return (value ?? "")
    .toLowerCase()
    .replace(/[_-]+/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function formatLabel(value: string): string {
  return value
    .split(" ")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

function formatDate(value: string): string {
  return value.slice(0, 10);
}

function daysInStage(value: string): string {
  const enteredAt = new Date(value);
  const now = new Date();
  const delta = Math.max(0, now.getTime() - enteredAt.getTime());
  const days = Math.floor(delta / (24 * 60 * 60 * 1000));
  return `${days} day${days === 1 ? "" : "s"}`;
}

function stageTone(stageIndex: number, currentIndex: number, runStatus: string): string {
  if (stageIndex < currentIndex) {
    return "bg-emerald-100 text-emerald-800";
  }
  if (stageIndex === currentIndex) {
    if (runStatus === "paused" || runStatus === "awaiting_approval") {
      return "bg-amber-100 text-amber-800";
    }
    if (runStatus === "failed") {
      return "bg-red-100 text-red-800";
    }
    return "bg-blue-100 text-blue-800";
  }
  return "bg-slate-100 text-slate-500";
}

export interface StageTimelineProps {
  latestRunSummary: LatestRunSummary | null;
}

export function StageTimeline({ latestRunSummary }: StageTimelineProps) {
  if (!latestRunSummary) {
    return (
      <section className="space-y-3 rounded-2xl border border-outline-variant bg-surface-container p-6 shadow-sm">
        <div>
          <h2 className="text-xl font-semibold text-slate-900">Lifecycle timeline</h2>
          <p className="text-sm text-slate-600">No runs have started for this project yet.</p>
        </div>
      </section>
    );
  }

  const currentStage = normalizeStage(latestRunSummary.currentStage);
  const currentIndex = STAGES.findIndex((stage) => stage === currentStage);

  return (
    <section className="space-y-4 rounded-2xl border border-outline-variant bg-surface-container p-6 shadow-sm">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-xl font-semibold text-slate-900">Lifecycle timeline</h2>
          <p className="text-sm text-slate-600">
            Current stage: <span className="font-semibold text-slate-900">{formatLabel(currentStage || "unknown")}</span>
          </p>
        </div>
        <div className="space-y-1 text-right text-sm text-slate-600">
          <div>
            Entered <span className="font-mono">{formatDate(latestRunSummary.stageEnteredAt)}</span>
          </div>
          <div>{daysInStage(latestRunSummary.stageEnteredAt)} in stage</div>
        </div>
      </div>

      <div className="grid gap-3 md:grid-cols-4 xl:grid-cols-8">
        {STAGES.map((stage, index) => {
          const tone = stageTone(index, currentIndex, latestRunSummary.runStatus);
          const isCurrent = index === currentIndex;
          const isPassed = currentIndex >= 0 && index < currentIndex;

          return (
            <div key={stage} className="space-y-2 rounded-xl border border-outline-variant bg-surface px-3 py-3">
              <div className="flex items-center gap-2">
                <span className={`inline-flex h-7 min-w-7 items-center justify-center rounded-full px-2 text-xs font-semibold ${tone}`}>
                  {index + 1}
                </span>
                <span className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">
                  {isCurrent ? "Current" : isPassed ? "Complete" : "Pending"}
                </span>
              </div>
              <div className="text-sm font-semibold text-slate-900">{formatLabel(stage)}</div>
            </div>
          );
        })}
      </div>
    </section>
  );
}
