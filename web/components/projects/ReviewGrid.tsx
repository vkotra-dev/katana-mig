"use client";

import { useState } from "react";

export interface MappingTableRecord {
  destinationTableName: string;
  bindings: Array<{
    sourceField: string;
    destinationField: string;
    bindingType: "direct" | "detail_fk" | "lookup_fk";
    referenceTableName?: string | null;
  }>;
}

export interface LookupValueGroup {
  lookupName: string;
  referenceTableName: string;
  pairs: Array<{
    sourceValue: string;
    destinationRow: Record<string, unknown>;
    confidenceScore: number;
    status: "confirmed" | "pending" | "rejected";
  }>;
}

interface ReviewGridProps {
  mappingTables: MappingTableRecord[];
  lookupGroups: LookupValueGroup[];
  sampleValues?: Record<string, string[]>;
  unmappedSourceFields?: string[];
  onApprove?: () => void;           // present for business_user only
  onRequestRevision?: (comment: string) => void;
}

export function ReviewGrid({
  mappingTables,
  lookupGroups,
  sampleValues = {},
  unmappedSourceFields = [],
  onApprove,
  onRequestRevision,
}: ReviewGridProps) {
  const [expandedTables, setExpandedTables] = useState<Record<string, boolean>>({});
  const [revisionOpen, setRevisionOpen] = useState(false);
  const [revisionComment, setRevisionComment] = useState("");

  const toggleTable = (tableName: string) => {
    setExpandedTables((current) => ({
      ...current,
      [tableName]: !current[tableName],
    }));
  };

  const getBindingBadge = (type: "direct" | "detail_fk" | "lookup_fk") => {
    switch (type) {
      case "direct":
        return (
          <span className="inline-flex items-center rounded-full bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-600 border border-slate-200">
            direct
          </span>
        );
      case "detail_fk":
        return (
          <span className="inline-flex items-center rounded-full bg-blue-100 px-2 py-0.5 text-xs font-medium text-blue-700 border border-blue-200">
            detail_fk
          </span>
        );
      case "lookup_fk":
        return (
          <span className="inline-flex items-center rounded-full bg-amber-50 px-2 py-0.5 text-xs font-medium text-amber-700 border border-amber-200/55 bg-amber-500/10">
            lookup_fk
          </span>
        );
    }
  };

  const getStatusBadge = (status: "confirmed" | "pending" | "rejected") => {
    switch (status) {
      case "confirmed":
        return (
          <span className="inline-flex items-center rounded-full bg-emerald-100 px-2 py-0.5 text-xs font-medium text-emerald-700 border border-emerald-200">
            confirmed
          </span>
        );
      case "pending":
        return (
          <span className="inline-flex items-center rounded-full bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-700 border border-amber-200">
            pending
          </span>
        );
      case "rejected":
        return (
          <span className="inline-flex items-center rounded-full bg-red-100 px-2 py-0.5 text-xs font-medium text-red-700 border border-red-200">
            rejected
          </span>
        );
    }
  };

  return (
    <div className="space-y-6">
      {/* 1. Table Mapping Section */}
      <div className="space-y-4">
        <h3 className="text-lg font-bold tracking-tight text-slate-900 flex items-center gap-2">
          <span className="w-1.5 h-6 bg-primary rounded-full inline-block"></span>
          Table Mappings
        </h3>

        {mappingTables.length === 0 ? (
          <div className="rounded-xl border border-dashed border-outline-variant bg-surface p-6 text-sm text-slate-500 text-center">
            No mappings available.
          </div>
        ) : (
          <div className="grid gap-3">
            {mappingTables.map((table) => {
              const isExpanded = !!expandedTables[table.destinationTableName];
              return (
                <div
                  key={table.destinationTableName}
                  className="overflow-hidden rounded-2xl border border-outline-variant bg-surface-container shadow-sm transition-all hover:shadow"
                >
                  <button
                    onClick={() => toggleTable(table.destinationTableName)}
                    className="flex w-full items-center justify-between px-5 py-4 text-left font-semibold text-slate-900 hover:bg-slate-50 focus:outline-none"
                    type="button"
                  >
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-mono text-primary font-bold">
                        {table.destinationTableName}
                      </span>
                      <span className="text-xs font-normal text-slate-500">
                        ({table.bindings.length} fields mapped)
                      </span>
                    </div>
                    <svg
                      className={`h-5 w-5 text-slate-400 transition-transform ${isExpanded ? "rotate-180" : ""}`}
                      fill="none"
                      viewBox="0 0 24 24"
                      stroke="currentColor"
                    >
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                    </svg>
                  </button>

                  {isExpanded && (
                    <div className="border-t border-outline-variant bg-white px-5 py-4">
                      <div className="overflow-x-auto">
                        <table className="w-full border-collapse text-left text-xs">
                          <thead>
                            <tr className="border-b border-slate-100 pb-2 text-slate-400 font-semibold uppercase tracking-wider">
                              <th className="py-2">Source Field</th>
                              <th className="py-2">Destination Field</th>
                              <th className="py-2">Type</th>
                            </tr>
                          </thead>
                          <tbody className="divide-y divide-slate-100">
                            {table.bindings.map((binding, idx) => (
                              <tr key={idx} className="hover:bg-slate-50/50">
                                <td className="py-2.5">
                                  <div className="font-mono text-slate-700">{binding.sourceField}</div>
                                  {(() => {
                                    const samples = sampleValues[binding.sourceField.toLowerCase()] ?? [];
                                    if (samples.length === 0) return null;
                                    return (
                                      <div className="mt-0.5 flex flex-wrap gap-1">
                                        {samples.map((v, i) => (
                                          <span key={i} className="rounded bg-slate-100 px-1.5 py-0.5 text-[10px] text-slate-500 font-mono">
                                            {v}
                                          </span>
                                        ))}
                                      </div>
                                    );
                                  })()}
                                </td>
                                <td className="py-2.5 font-mono text-slate-900 font-medium">
                                  {binding.destinationField}
                                </td>
                                <td className="py-2.5">{getBindingBadge(binding.bindingType)}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>

      {unmappedSourceFields.length > 0 && (
        <div className="rounded-xl border border-amber-300 bg-amber-50/50 p-5 space-y-3">
          <div className="flex items-center gap-2 text-amber-800">
            <span className="text-lg">⚠️</span>
            <p className="text-sm font-semibold">
              Unmapped source fields — data in these columns will not be migrated
            </p>
          </div>
          <ul className="space-y-2.5 pl-7">
            {unmappedSourceFields.map((col) => {
              const samples = sampleValues[col] || sampleValues[col.toLowerCase()] || sampleValues[col.toUpperCase()] || [];
              return (
                <li key={col} className="flex flex-col sm:flex-row sm:items-center gap-2">
                  <span className="font-mono text-sm font-bold text-amber-900 bg-amber-100 px-2 py-0.5 rounded">{col}</span>
                  {samples.length > 0 && (
                    <div className="flex flex-wrap items-center gap-1.5">
                      <span className="text-[10px] text-amber-600 font-medium mr-1">Sample values:</span>
                      {samples.map((v, i) => (
                        <span
                          key={i}
                          className="rounded bg-amber-50 border border-amber-200/60 px-1.5 py-0.5 text-xs font-mono text-amber-700"
                        >
                          {v}
                        </span>
                      ))}
                    </div>
                  )}
                </li>
              );
            })}
          </ul>
        </div>
      )}

      {/* 2. Lookup Value Mapping Section */}
      <div className="space-y-4">
        <h3 className="text-lg font-bold tracking-tight text-slate-900 flex items-center gap-2">
          <span className="w-1.5 h-6 bg-amber-500 rounded-full inline-block"></span>
          Lookup Value Mappings
        </h3>

        {lookupGroups.length === 0 ? (
          <div className="rounded-xl border border-dashed border-outline-variant bg-surface p-6 text-sm text-slate-500 text-center">
            No lookup fields present.
          </div>
        ) : (
          <div className="grid gap-6">
            {lookupGroups.map((group) => (
              <div
                key={group.lookupName}
                className="rounded-2xl border border-outline-variant bg-surface-container p-5 shadow-sm space-y-4"
              >
                <div className="flex items-center justify-between border-b border-slate-200/60 pb-3">
                  <div className="space-y-1">
                    <h4 className="text-base font-bold text-slate-900">{group.lookupName}</h4>
                    <p className="text-xs text-slate-500">
                      Maps to reference table:{" "}
                      <span className="font-mono text-slate-700 bg-slate-100 border border-slate-200 rounded px-1.5 py-0.5">
                        {group.referenceTableName}
                      </span>
                    </p>
                  </div>
                </div>

                <div className="overflow-x-auto">
                  <table className="w-full border-collapse text-left text-xs">
                    <thead>
                      <tr className="border-b border-slate-100 pb-2 text-slate-400 font-semibold uppercase tracking-wider">
                        <th className="py-2">Source Value</th>
                        <th className="py-2">Destination Row</th>
                        <th className="py-2">Confidence</th>
                        <th className="py-2">Status</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100">
                      {group.pairs.map((pair, idx) => (
                        <tr key={idx} className="hover:bg-slate-50/50">
                          <td className="py-3 font-medium text-slate-800">{pair.sourceValue}</td>
                          <td className="py-3 font-mono text-slate-600 max-w-md truncate">
                            {JSON.stringify(pair.destinationRow)}
                          </td>
                          <td className="py-3">
                            <div className="flex items-center gap-2">
                              <span className="font-semibold text-slate-700">
                                {Math.round(pair.confidenceScore * 100)}%
                              </span>
                              <div className="w-16 h-1.5 bg-slate-100 rounded-full overflow-hidden">
                                <div
                                  className={`h-full ${
                                    pair.confidenceScore >= 0.8
                                      ? "bg-emerald-500"
                                      : pair.confidenceScore >= 0.5
                                      ? "bg-amber-500"
                                      : "bg-red-500"
                                  }`}
                                  style={{ width: `${pair.confidenceScore * 100}%` }}
                                ></div>
                              </div>
                            </div>
                          </td>
                          <td className="py-3">{getStatusBadge(pair.status)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* 3. Conditional Approval Strip */}
      {(onApprove || onRequestRevision) && (
        <div className="rounded-2xl border border-primary/20 bg-primary/5 p-5 shadow-sm space-y-4 transition-all">
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div>
              <h4 className="text-sm font-bold text-slate-900">Decision Pending</h4>
              <p className="text-xs text-slate-600">Review the AI proposed table & lookup mapping changes.</p>
            </div>
            <div className="flex items-center gap-3">
              {onRequestRevision && (
                <button
                  onClick={() => setRevisionOpen(!revisionOpen)}
                  className="rounded-lg border border-slate-300 bg-white px-4 py-2.5 text-sm font-semibold text-slate-700 hover:bg-slate-50 focus:outline-none focus:ring-2 focus:ring-primary/20"
                  type="button"
                >
                  Request Revision
                </button>
              )}
              {onApprove && (
                <button
                  onClick={onApprove}
                  className="rounded-lg bg-primary px-5 py-2.5 text-sm font-semibold text-white shadow hover:bg-primary-hover focus:outline-none focus:ring-2 focus:ring-primary/20"
                  type="button"
                >
                  Approve
                </button>
              )}
            </div>
          </div>

          {revisionOpen && onRequestRevision && (
            <div className="border-t border-primary/10 pt-4 space-y-3">
              <label htmlFor="revision-comment" className="block text-xs font-semibold text-slate-700">
                Revision feedback / comment
              </label>
              <textarea
                id="revision-comment"
                value={revisionComment}
                onChange={(e) => setRevisionComment(e.target.value)}
                placeholder="Describe what needs to be changed in these mappings..."
                className="w-full rounded-lg border border-slate-300 bg-white p-3 text-sm text-slate-900 focus:border-primary focus:outline-none"
                rows={3}
              />
              <div className="flex justify-end gap-2">
                <button
                  onClick={() => setRevisionOpen(false)}
                  className="rounded-md border border-slate-300 px-3 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-50"
                  type="button"
                >
                  Cancel
                </button>
                <button
                  onClick={() => {
                    if (revisionComment.trim()) {
                      onRequestRevision(revisionComment.trim());
                      setRevisionComment("");
                      setRevisionOpen(false);
                    }
                  }}
                  disabled={!revisionComment.trim()}
                  className="rounded-md bg-primary px-3.5 py-1.5 text-xs font-semibold text-white disabled:opacity-50"
                  type="button"
                >
                  Submit Revision Request
                </button>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
