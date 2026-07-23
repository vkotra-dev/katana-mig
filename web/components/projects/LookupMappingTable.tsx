"use client";

import { useRef, useState, useEffect, useCallback } from "react";

const BATCH_SIZE = 50;

interface LookupMappingTableProps {
  pairs: Array<{
    sourceValue: string;
    destinationRow: Record<string, unknown> | null;
    confidenceScore: number;
    status: "confirmed" | "pending" | "rejected";
    destinationId?: string;
  }>;
  destinationRows: Array<{ [key: string]: unknown }>;
  lookupValueMapId?: string;
  unmappedRowCount?: number;
  editingEnabled?: boolean;
  onEditLookup?: (lookupValueMapId: string, pairs: Array<{
    sourceValue: string;
    destinationRow: Record<string, unknown> | null;
    confidenceScore: number;
    status: "confirmed" | "pending" | "rejected";
    destinationId?: string;
  }>) => void;
}

function AutocompleteDropdown({
  value,
  options,
  onChange,
}: {
  value: string;
  options: Array<{value: string, label: string}>;
  onChange: (value: string) => void;
}) {
  const selectedLabel = options.find((o) => o.value === value)?.label || value;
  const [isOpen, setIsOpen] = useState(false);
  const [query, setQuery] = useState(selectedLabel);
  const [highlightedIndex, setHighlightedIndex] = useState(-1);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    setQuery(options.find((o) => o.value === value)?.label || value);
  }, [value, options]);

  const filteredOptions = query.trim() === "" || query === selectedLabel
    ? options
    : options.filter((opt) => opt.label.toLowerCase().includes(query.toLowerCase()));

  const selectOption = (opt: {value: string, label: string}) => {
    setQuery(opt.label);
    onChange(opt.value);
    setIsOpen(false);
    setHighlightedIndex(-1);
  };

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setIsOpen(true);
      setHighlightedIndex((prev) =>
        prev < filteredOptions.length - 1 ? prev + 1 : 0,
      );
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setIsOpen(true);
      setHighlightedIndex((prev) =>
        prev > 0 ? prev - 1 : filteredOptions.length - 1,
      );
    } else if (e.key === "Enter") {
      e.preventDefault();
      if (isOpen && highlightedIndex >= 0 && highlightedIndex < filteredOptions.length) {
        selectOption(filteredOptions[highlightedIndex]);
      } else {
        onChange(query); // Fallback to raw text if custom text is entered
        setIsOpen(false);
      }
    } else if (e.key === "Escape") {
      setIsOpen(false);
    }
  };

  return (
    <div ref={containerRef} className="relative w-full max-w-[200px]">
      <div className="flex items-center">
        <input
          type="text"
          value={query}
          onChange={(e) => {
            setQuery(e.target.value);
            setIsOpen(true);
            setHighlightedIndex(-1);
          }}
          onFocus={() => setIsOpen(true)}
          onBlur={() => {
            onChange(options.find(o => o.label === query)?.value || query);
            setIsOpen(false);
          }}
          onKeyDown={handleKeyDown}
          className="rounded border border-slate-200 bg-white px-2 py-0.5 text-[10px] font-mono w-full focus:border-primary focus:ring-1 focus:ring-primary focus:outline-none"
        />
        <button
          type="button"
          onClick={() => setIsOpen((prev) => !prev)}
          className="absolute right-1 top-1/2 -translate-y-1/2 px-1 py-0.5 text-slate-400 hover:text-slate-600 focus:outline-none"
        >
          <svg
            className={`h-2.5 w-2.5 transition-transform duration-200 ${isOpen ? "rotate-180" : ""}`}
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
          </svg>
        </button>
      </div>

      {isOpen && filteredOptions.length > 0 && (
        <ul className="absolute left-0 right-0 z-[100] mt-1 max-h-48 overflow-y-auto rounded-lg border border-slate-200 bg-white py-1 text-[10px] shadow-lg ring-1 ring-black/5 focus:outline-none font-mono">
          {filteredOptions.map((opt, index) => (
            <li
              key={opt.value}
              onMouseDown={(e) => {
                e.preventDefault();
                selectOption(opt);
              }}
              onClick={() => selectOption(opt)}
              onMouseEnter={() => setHighlightedIndex(index)}
              className={`relative cursor-pointer select-none px-2 py-1 transition-colors ${
                index === highlightedIndex
                  ? "bg-primary text-white"
                  : "text-slate-700 hover:bg-slate-100"
              }`}
            >
              {opt.label}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function ConfidenceBadge({ score }: { score: number }) {
  return (
    <div className="flex items-center gap-1.5">
      <span className="font-semibold text-[11px] text-slate-700">
        {Math.round(score * 100)}%
      </span>
      <div className="w-12 h-1.5 bg-slate-100 rounded-full overflow-hidden">
        <div
          className={`h-full ${
            score >= 0.8 ? "bg-emerald-500" : score >= 0.5 ? "bg-amber-500" : "bg-red-500"
          }`}
          style={{ width: `${score * 100}%` }}
        />
      </div>
    </div>
  );
}

function getStatusBadge(status: string) {
  switch (status) {
    case "confirmed":
      return (
        <span className="inline-flex rounded-full bg-emerald-100 px-2 py-0.5 text-[10px] font-semibold text-emerald-700">
          Confirmed
        </span>
      );
    case "rejected":
      return (
        <span className="inline-flex rounded-full bg-red-100 px-2 py-0.5 text-[10px] font-semibold text-red-700">
          Rejected
        </span>
      );
    default:
      return (
        <span className="inline-flex rounded-full bg-slate-100 px-2 py-0.5 text-[10px] font-semibold text-slate-600">
          Pending
        </span>
      );
  }
}

export function LookupMappingTable({
  pairs,
  destinationRows,
  lookupValueMapId,
  unmappedRowCount,
  editingEnabled,
  onEditLookup,
}: LookupMappingTableProps) {
  const [visibleCount, setVisibleCount] = useState(BATCH_SIZE);
  const sentinelRef = useRef<HTMLDivElement>(null);
  const observerRef = useRef<IntersectionObserver | null>(null);

  const lastRowRef = useCallback(
    (node: HTMLTableRowElement | null) => {
      if (observerRef.current) observerRef.current.disconnect();
      if (!node) return;
      observerRef.current = new IntersectionObserver((entries) => {
        if (entries[0]?.isIntersecting && visibleCount < pairs.length) {
          setVisibleCount((prev) => Math.min(prev + BATCH_SIZE, pairs.length));
        }
      }, { rootMargin: "100px" });
      observerRef.current.observe(node);
    },
    [visibleCount, pairs.length],
  );

  const handleChange = (index: number, destinationRow: Record<string, unknown> | null, destinationId?: string) => {
    const updated = pairs.map((p, i) => (i === index ? { ...p, destinationRow, destinationId } : p));
    if (lookupValueMapId) {
      onEditLookup?.(lookupValueMapId, updated);
    } else {
      onEditLookup?.("", updated);
    }
  };

  // Extract available destination options from mapped pairs
  const availableDestinationOptions = Array.from(
    new Map(
      pairs
        .filter((p) => p.destinationRow && p.destinationId)
        .map((p) => {
          const label = Object.entries(p.destinationRow!)
            .filter(([key]) => key !== "id" && key !== "destination_id" && key !== "entry_id" && !key.toLowerCase().endsWith("_id"))
            .map(([_, val]) => String(val).replace(/['"`]/g, ""))
            .join(" | ");
          return [p.destinationId!, { value: p.destinationId!, label: label || p.destinationId! }];
        })
    ).values()
  );

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
            <th className="py-2">Source Value</th>
            <th className="py-2">Destination Row</th>
            <th className="py-2">Confidence</th>
            <th className="py-2">Status</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {pairs.slice(0, visibleCount).map((pair, idx) => {
            const displayRow = editingEnabled ? pair.destinationRow : pair.destinationRow;
            const destId = pair.destinationId ?? (displayRow?.id as string) ?? (displayRow?.destination_id as string);
            const destLabel = displayRow ? (
              <div className="grid grid-cols-[repeat(auto-fit,minmax(72px,1fr))] gap-2 p-2 border border-slate-100 rounded-lg bg-slate-50/40 text-[10px] font-mono w-full">
                {Object.entries(displayRow)
                  .filter(([key]) => key !== "id" && key !== "destination_id")
                  .map(([key, val]) => (
                    <div key={key} className="flex flex-col border-l-2 border-primary/20 pl-2 min-w-[72px]">
                      <span className="text-slate-400 font-medium text-[8px] uppercase tracking-wider truncate" title={key}>
                        {key.trim().replace(/['"`]/g, "")}
                      </span>
                      <span className="text-slate-800 font-semibold truncate" title={String(val)}>
                        {String(val).replace(/['"`]/g, "")}
                      </span>
                    </div>
                  ))}
              </div>
            ) : (
              <span className="text-slate-400 italic">-</span>
            );

            return (
              <tr key={idx} className="hover:bg-slate-50/50" ref={idx === visibleCount - 1 ? lastRowRef : undefined}>
                <td className="py-2.5 font-medium text-slate-800">{pair.sourceValue}</td>
                <td className="py-2.5 pr-4">
                  {editingEnabled ? (
                    <div className="space-y-1.5">
                      {destLabel}
                      {availableDestinationOptions.length > 0 && (
                        <AutocompleteDropdown
                          value={destId ?? ""}
                          options={availableDestinationOptions}
                          onChange={(newDestId) => {
                            const targetPair = pairs.find((p) => p.destinationId === newDestId);
                            handleChange(idx, targetPair?.destinationRow ?? null, newDestId);
                          }}
                        />
                      )}
                    </div>
                  ) : (
                    destLabel
                  )}
                </td>
                <td className="py-2.5">
                  <ConfidenceBadge score={pair.confidenceScore} />
                </td>
                <td className="py-2.5">{getStatusBadge(pair.status)}</td>
              </tr>
            );
          })}
          {pairs.length === 0 && (
            <tr>
              <td colSpan={4} className="py-8 text-center text-slate-400 italic">
                No mappings yet.
              </td>
            </tr>
          )}
        </tbody>
      </table>
      <div ref={sentinelRef} className="h-px" />
    </div>
  );
}
