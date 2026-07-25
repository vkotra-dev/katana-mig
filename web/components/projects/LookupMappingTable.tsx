"use client";

import { useState } from "react";
import { DestinationMappingGroup } from "../../lib/lookup-api";

interface LookupMappingTableProps {
  groups: DestinationMappingGroup[];
  unmappedRowCount?: number;
  unmappedSourceValues?: string[];
  editingEnabled?: boolean;
  onAddSourceValue?: (destId: string, sourceValue: string) => void;
  onRemoveSourceValue?: (destId: string, sourceValue: string) => void;
}

function getStatusBadge(status: string) {
  switch (status) {
    case "confirmed":
    case "approved":
      return (
        <span className="inline-flex rounded-full bg-emerald-100 px-2 py-0.5 text-[10px] font-semibold text-emerald-700">
          Confirmed
        </span>
      );
    default:
      return (
        <span className="inline-flex rounded-full bg-amber-100 px-2 py-0.5 text-[10px] font-semibold text-amber-700">
          Pending
        </span>
      );
  }
}

export function LookupMappingTable({
  groups,
  unmappedRowCount,
  unmappedSourceValues,
  editingEnabled,
  onAddSourceValue,
  onRemoveSourceValue,
}: LookupMappingTableProps) {
  const [addingDestId, setAddingDestId] = useState<string | null>(null);
  const [newSourceValue, setNewSourceValue] = useState("");

  const handleStartAdd = (destId: string) => {
    setAddingDestId(destId);
    setNewSourceValue("");
  };

  const handleCancelAdd = () => {
    setAddingDestId(null);
    setNewSourceValue("");
  };

  const handleConfirmAdd = (destId: string) => {
    const value = newSourceValue.trim();
    if (value && onAddSourceValue) {
      onAddSourceValue(destId, value);
    }
    handleCancelAdd();
  };

  return (
    <div className="overflow-x-auto">
      {unmappedRowCount != null && unmappedRowCount > 0 && (
        <div className="flex items-center gap-2 text-amber-700 bg-amber-50 rounded-lg px-3 py-2 mb-3 text-xs font-medium">
          <span className="text-base">⚠️</span>
          <span>{unmappedRowCount.toLocaleString()} rows unmapped</span>
        </div>
      )}
      <table className="w-full border-collapse text-left text-xs">
        <thead>
          <tr className="border-b border-slate-100 pb-2 text-slate-400 font-semibold uppercase tracking-wider">
            <th className="py-2 w-1/3">Destination</th>
            <th className="py-2 w-1/2">Mapped Source Values</th>
            <th className="py-2 w-1/6">Status</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {groups.map((group, groupIdx) => (
            <tr key={`${group.destId || 'empty'}-${groupIdx}`} className="hover:bg-slate-50/50">
              <td className="py-2.5 pr-4">
                {group.destLabel && group.destLabel !== group.destId ? (
                  <>
                    {group.destLabel}{" "}
                    <span className="text-slate-400">({group.destId})</span>
                  </>
                ) : (
                  group.destId || "—"
                )}
              </td>
              <td className="py-2.5">
                <div className="flex flex-col gap-1.5 w-full">
                  {group.sourceValues.map((srcVal, idx) => (
                    <div key={`${group.destId}-sv-${idx}`} className="flex items-center gap-2">
                      <input
                        type="text"
                        readOnly
                        value={srcVal}
                        className="px-2.5 py-1 text-sm border rounded bg-slate-50 border-slate-200 text-slate-800 focus:outline-none focus:bg-white focus:border-indigo-500 w-full max-w-sm font-mono"
                      />
                      {editingEnabled && onRemoveSourceValue && group.destId && (
                        <button
                          type="button"
                          onClick={() => onRemoveSourceValue(group.destId, srcVal)}
                          className="text-slate-400 hover:text-red-600 focus:outline-none text-xs font-bold leading-none p-1 transition-colors"
                          title="Remove source value"
                        >
                          ×
                        </button>
                      )}
                    </div>
                  ))}
                  {editingEnabled && onAddSourceValue && group.destId && (
                    addingDestId === group.destId ? (
                      <div className="flex items-center gap-2 mt-1">
                        <input
                          type="text"
                          autoFocus
                          value={newSourceValue}
                          onChange={(e) => setNewSourceValue(e.target.value)}
                          onKeyDown={(e) => {
                            if (e.key === "Enter") handleConfirmAdd(group.destId);
                            if (e.key === "Escape") handleCancelAdd();
                          }}
                          placeholder="Enter source value alias..."
                          className="px-2.5 py-1 text-xs border border-indigo-300 rounded bg-white text-slate-800 focus:outline-none focus:ring-1 focus:ring-indigo-500 w-full max-w-xs font-mono"
                        />
                        <button
                          type="button"
                          onClick={() => handleConfirmAdd(group.destId)}
                          disabled={!newSourceValue.trim()}
                          className="px-2 py-1 text-xs font-semibold rounded bg-indigo-600 text-white hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed"
                        >
                          Add
                        </button>
                        <button
                          type="button"
                          onClick={handleCancelAdd}
                          className="px-1.5 py-1 text-xs font-medium text-slate-500 hover:text-slate-700"
                        >
                          Cancel
                        </button>
                      </div>
                    ) : (
                      <button
                        type="button"
                        onClick={() => handleStartAdd(group.destId)}
                        className="text-xs text-indigo-600 font-medium hover:text-indigo-800 self-start mt-1 flex items-center gap-1"
                      >
                        + Add another source value
                      </button>
                    )
                  )}
                </div>
              </td>
              <td className="py-2.5">{getStatusBadge(group.status)}</td>
            </tr>
          ))}
          {groups.length === 0 && (
            <tr>
              <td colSpan={3} className="py-8 text-center text-slate-400 italic">
                No mappings yet.
              </td>
            </tr>
          )}
        </tbody>
      </table>
      {unmappedSourceValues && unmappedSourceValues.length > 0 && (
        <div className="mt-3 space-y-1">
          <div className="flex items-center gap-2 text-amber-700 bg-amber-50 rounded-lg px-3 py-1.5 text-xs font-medium">
            <span className="text-sm">⚠️</span>
            <span>Unmapped source values</span>
          </div>
          <ul className="space-y-0.5 pl-4">
            {unmappedSourceValues.map((val, idx) => (
              <li key={idx} className="text-xs text-amber-700 font-mono">{val}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
