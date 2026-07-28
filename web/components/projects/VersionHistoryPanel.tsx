"use client";

import { useState } from "react";

export interface VersionHistoryEntry {
  versionId: string;
  fieldName: string;
  oldValue: string | null;
  newValue: string | null;
  changedBy: string | null;
  changedAt: string;
}

interface VersionHistoryPanelProps {
  entries: VersionHistoryEntry[];
  loading: boolean;
  error: string | null;
}

function formatTimestamp(ts: string): string {
  try {
    return new Date(ts).toLocaleString();
  } catch {
    return ts;
  }
}

export function VersionHistoryPanel({ entries, loading, error }: VersionHistoryPanelProps) {
  const [expandedEntry, setExpandedEntry] = useState<string | null>(null);

  return (
    <div className="mt-3 rounded-lg border border-outline-variant bg-white">
      <div className="flex items-center justify-between border-b border-slate-200 px-3 py-2">
        <span className="text-xs font-semibold text-slate-700">
          Version History ({entries.length})
        </span>
      </div>

      {loading ? (
        <div className="px-3 py-4 text-xs text-slate-500">Loading…</div>
      ) : error ? (
        <div className="px-3 py-4 text-xs text-red-600">{error}</div>
      ) : entries.length === 0 ? (
        <div className="px-3 py-4 text-xs text-slate-400 italic">No history yet.</div>
      ) : (
        <div className="divide-y divide-slate-100">
          {entries.map((entry) => {
            const isExpanded = expandedEntry === entry.versionId;
            return (
              <div key={entry.versionId}>
                <button
                  type="button"
                  onClick={() =>
                    setExpandedEntry(isExpanded ? null : entry.versionId)
                  }
                  className="flex w-full items-center justify-between px-3 py-2 text-left text-xs hover:bg-slate-50"
                >
                  <div className="flex items-center gap-2">
                    <span className="font-medium text-slate-700">
                      {formatTimestamp(entry.changedAt)}
                    </span>
                    {entry.changedBy && (
                      <span className="text-slate-400">by {entry.changedBy}</span>
                    )}
                    {entry.fieldName && (
                      <span className="rounded bg-slate-100 px-1.5 py-0.5 text-[10px] font-mono text-slate-500">
                        {entry.fieldName}
                      </span>
                    )}
                  </div>
                  <svg
                    className={`h-3.5 w-3.5 text-slate-400 transition-transform duration-150 ${isExpanded ? "rotate-180" : ""}`}
                    fill="none"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                    strokeWidth={2.5}
                  >
                    <path strokeLinecap="round" strokeLinejoin="round" d="m19 9-7 7-7-7" />
                  </svg>
                </button>
                {isExpanded && (
                  <div className="space-y-2 bg-slate-50 px-3 py-2">
                    <div>
                      <span className="text-[10px] font-semibold uppercase tracking-wider text-slate-400">Old value</span>
                      <pre className="mt-0.5 max-h-32 overflow-auto whitespace-pre-wrap rounded bg-white px-2 py-1 text-xs font-mono text-slate-700 border border-slate-200">
                        {entry.oldValue ?? "(none)"}
                      </pre>
                    </div>
                    <div>
                      <span className="text-[10px] font-semibold uppercase tracking-wider text-slate-400">New value</span>
                      <pre className="mt-0.5 max-h-32 overflow-auto whitespace-pre-wrap rounded bg-white px-2 py-1 text-xs font-mono text-slate-700 border border-slate-200">
                        {entry.newValue ?? "(none)"}
                      </pre>
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
