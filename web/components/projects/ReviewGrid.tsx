"use client";

import { useState, useRef, useEffect } from "react";
import { SignOffStatusRecord } from "../../lib/sign-offs-api";
import { LookupMappingTable } from "./LookupMappingTable";

export interface MappingTableRecord {
  destinationTableName: string;
  destinationFields?: string[];
  fiberStatus?: string;
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
  lookupValueMapId?: string;
  unmappedRowCount?: number;
  fiberStatus?: string;
  pairs: Array<{
    sourceValue: string;
    destinationRow: Record<string, unknown> | null;
    confidenceScore: number;
    status: "confirmed" | "pending" | "rejected";
  }>;
}

interface ReviewGridProps {
  mappingTables: MappingTableRecord[];
  lookupGroups: LookupValueGroup[];
  sampleValues?: Record<string, string[]>;
  unmappedSourceFields?: string[];
  unmappedDestinationFields?: { tableName: string; fieldName: string }[];
  onApprove?: () => void;           // present for business_user only
  onRequestRevision?: (comment: string) => void;
  signOffStatus?: SignOffStatusRecord;
  currentUserRole?: string;
  editingEnabled?: boolean;
  onSignBinding?: (tableName: string, sourceField: string, destField: string) => void;
  onUnsignBinding?: (tableName: string, sourceField: string, destField: string) => void;
  onDestinationFieldChange?: (tableName: string, sourceField: string, oldDest: string, newDest: string) => void;
  onAddBinding?: (tableName: string, sourceField: string, availableFields: string[]) => void;
  onRemoveBinding?: (tableName: string, sourceField: string, destinationField: string) => void;
  onRemoveSourceField?: (tableName: string, sourceField: string) => void;
  onSignLookup?: (lookupValueMapId: string) => void;
  onUnsignLookup?: (lookupValueMapId: string) => void;
  onEditLookup?: (lookupValueMapId: string, pairs: Array<{
    sourceValue: string;
    destinationRow: Record<string, unknown> | null;
    confidenceScore: number;
    status: "confirmed" | "pending" | "rejected";
    destinationId?: string;
  }>) => void;
}

interface AutocompleteInputProps {
  value: string;
  options: string[];
  onChange: (value: string) => void;
  className?: string;
  placeholder?: string;
}

function AutocompleteInput({
  value,
  options,
  onChange,
  className = "",
  placeholder = "",
}: AutocompleteInputProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [query, setQuery] = useState(value);
  const [highlightedIndex, setHighlightedIndex] = useState(-1);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    setQuery(value);
  }, [value]);

  const filteredOptions = query.trim() === "" || query === value
    ? options
    : options.filter((opt) =>
        opt.toLowerCase().includes(query.toLowerCase())
      );

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
    };
  }, []);

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setIsOpen(true);
      setHighlightedIndex((prev) =>
        prev < filteredOptions.length - 1 ? prev + 1 : 0
      );
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setIsOpen(true);
      setHighlightedIndex((prev) =>
        prev > 0 ? prev - 1 : filteredOptions.length - 1
      );
    } else if (e.key === "Enter") {
      e.preventDefault();
      if (isOpen && highlightedIndex >= 0 && highlightedIndex < filteredOptions.length) {
        selectOption(filteredOptions[highlightedIndex]);
      } else {
        onChange(query);
        setIsOpen(false);
      }
    } else if (e.key === "Escape") {
      setIsOpen(false);
    }
  };

  const selectOption = (opt: string) => {
    setQuery(opt);
    onChange(opt);
    setIsOpen(false);
    setHighlightedIndex(-1);
  };

  return (
    <div ref={containerRef} className="relative w-full max-w-[240px]">
      <div className="relative flex items-center">
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
            onChange(query);
            setIsOpen(false);
          }}
          onKeyDown={handleKeyDown}
          placeholder={placeholder}
          className={`${className} pr-8`}
        />
        <button
          type="button"
          onClick={() => setIsOpen((prev) => !prev)}
          className="absolute right-0 top-1/2 -translate-y-1/2 px-2.5 py-1 text-slate-400 hover:text-slate-600 focus:outline-none"
        >
          <svg
            className={`h-3 w-3 transition-transform duration-200 ${isOpen ? "rotate-180" : ""}`}
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
          </svg>
        </button>
      </div>

      {isOpen && filteredOptions.length > 0 && (
        <ul className="absolute left-0 right-0 z-[100] mt-1 max-h-48 overflow-y-auto rounded-lg border border-slate-200 bg-white py-1 text-xs shadow-lg ring-1 ring-black/5 focus:outline-none font-mono">
          {filteredOptions.map((opt, index) => {
            const isHighlighted = index === highlightedIndex;
            const isSelected = opt === value;
            return (
              <li
                key={opt}
                onMouseDown={(e) => {
                  e.preventDefault(); // Prevents input blur before selection
                  selectOption(opt);
                }}
                onClick={() => selectOption(opt)}
                onMouseEnter={() => setHighlightedIndex(index)}
                className={`relative cursor-pointer select-none px-3 py-1.5 transition-colors ${
                  isHighlighted
                    ? "bg-primary text-white"
                    : isSelected
                    ? "bg-slate-100 text-slate-900 font-bold"
                    : "text-slate-700 hover:bg-slate-50"
                }`}
              >
                {opt}
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}

export function ReviewGrid({
  mappingTables,
  lookupGroups,
  sampleValues = {},
  unmappedSourceFields = [],
  unmappedDestinationFields = [],
  onApprove,
  onRequestRevision,
  signOffStatus,
  currentUserRole,
  editingEnabled = false,
  onSignBinding,
  onUnsignBinding,
  onDestinationFieldChange,
  onAddBinding,
  onRemoveBinding,
  onRemoveSourceField,
  onSignLookup,
  onUnsignLookup,
  onEditLookup,
}: ReviewGridProps) {
  const [expandedTables, setExpandedTables] = useState<Record<string, boolean>>({});
  const [revisionOpen, setRevisionOpen] = useState(false);
  const [revisionComment, setRevisionComment] = useState("");

  const allSignedByStakeholder = (() => {
    if (!signOffStatus) return false;
    // Check bindings
    for (const table of Object.values(signOffStatus.bindings)) {
      for (const sourceFieldDests of Object.values(table)) {
        for (const binding of Object.values(sourceFieldDests)) {
          if (!binding.projectStakeholder.signed) return false;
        }
      }
    }
    // Check lookups
    for (const lookup of Object.values(signOffStatus.lookups)) {
      if (!lookup.projectStakeholder.signed) return false;
    }
    return true;
  })();

  const renderSignOffChips = (tableName: string, sourceField: string, destField: string) => {
    if (!signOffStatus) return null;
    const bindingStatus = signOffStatus.bindings[tableName]?.[sourceField]?.[destField];
    if (!bindingStatus) return null;

    const op = bindingStatus.centralTeam;
    const st = bindingStatus.projectStakeholder;

    const handleSignClick = () => {
      if (currentUserRole === "central_team") {
        if (op.signed) {
          onUnsignBinding?.(tableName, sourceField, destField);
        } else {
          onSignBinding?.(tableName, sourceField, destField);
        }
      } else if (currentUserRole === "project_stakeholder") {
        if (st.signed) {
          onUnsignBinding?.(tableName, sourceField, destField);
        } else {
          onSignBinding?.(tableName, sourceField, destField);
        }
      }
    };

    const showSignButton =
      (currentUserRole === "central_team" || currentUserRole === "project_stakeholder");

    return (
      <div className="flex items-center gap-1.5 font-sans">
        <span
          title={op.signed && op.signedAt ? `Signed at ${op.signedAt} by ${op.userId}` : "Unsigned"}
          className={`inline-flex items-center rounded px-1.5 py-0.5 text-[9px] font-semibold ${
            op.signed ? "bg-emerald-100 text-emerald-800 border border-emerald-200" : "bg-slate-100 text-slate-400 border border-slate-200"
          }`}
        >
          OP {op.signed ? "✓" : "—"}
        </span>

        <span
          title={st.signed && st.signedAt ? `Signed at ${st.signedAt} by ${st.userId}` : "Unsigned"}
          className={`inline-flex items-center rounded px-1.5 py-0.5 text-[9px] font-semibold ${
            st.signed ? "bg-emerald-100 text-emerald-800 border border-emerald-200" : "bg-slate-100 text-slate-400 border border-slate-200"
          }`}
        >
          ST {st.signed ? "✓" : "—"}
        </span>

        {showSignButton && (
          <button
            type="button"
            onClick={handleSignClick}
            className={`text-[9px] font-semibold px-2 py-0.5 rounded border focus:outline-none transition-colors ${
              ((currentUserRole === "central_team" && op.signed) ||
                (currentUserRole === "project_stakeholder" && st.signed))
                ? "border-slate-300 bg-slate-100 text-slate-600 hover:bg-slate-200"
                : "border-primary bg-primary text-white hover:bg-primary-hover"
            }`}
          >
            {((currentUserRole === "central_team" && op.signed) ||
              (currentUserRole === "project_stakeholder" && st.signed))
              ? "Unsign"
              : "Sign off"}
          </button>
        )}
      </div>
    );
  };

  const renderLookupSignOffChips = (lookupValueMapId: string) => {
    if (!signOffStatus) return null;
    const lookupStatus = signOffStatus.lookups[lookupValueMapId];
    if (!lookupStatus) return null;

    const op = lookupStatus.centralTeam;
    const st = lookupStatus.projectStakeholder;

    const handleSignClick = () => {
      if (currentUserRole === "central_team") {
        if (op.signed) {
          onUnsignLookup?.(lookupValueMapId);
        } else {
          onSignLookup?.(lookupValueMapId);
        }
      } else if (currentUserRole === "project_stakeholder") {
        if (st.signed) {
          onUnsignLookup?.(lookupValueMapId);
        } else {
          onSignLookup?.(lookupValueMapId);
        }
      }
    };

    const showSignButton =
      (currentUserRole === "central_team" || currentUserRole === "project_stakeholder");

    return (
      <div className="flex items-center gap-1.5 font-sans">
        <span
          title={op.signed && op.signedAt ? `Signed at ${op.signedAt} by ${op.userId}` : "Unsigned"}
          className={`inline-flex items-center rounded px-1.5 py-0.5 text-[9px] font-semibold ${
            op.signed ? "bg-emerald-100 text-emerald-800 border border-emerald-200" : "bg-slate-100 text-slate-400 border border-slate-200"
          }`}
        >
          OP {op.signed ? "✓" : "—"}
        </span>

        <span
          title={st.signed && st.signedAt ? `Signed at ${st.signedAt} by ${st.userId}` : "Unsigned"}
          className={`inline-flex items-center rounded px-1.5 py-0.5 text-[9px] font-semibold ${
            st.signed ? "bg-emerald-100 text-emerald-800 border border-emerald-200" : "bg-slate-100 text-slate-400 border border-slate-200"
          }`}
        >
          ST {st.signed ? "✓" : "—"}
        </span>

        {showSignButton && (
          <button
            type="button"
            onClick={handleSignClick}
            className={`text-[9px] font-semibold px-2 py-0.5 rounded border focus:outline-none transition-colors ${
              ((currentUserRole === "central_team" && op.signed) ||
                (currentUserRole === "project_stakeholder" && st.signed))
                ? "border-slate-300 bg-slate-100 text-slate-600 hover:bg-slate-200"
                : "border-primary bg-primary text-white hover:bg-primary-hover"
            }`}
          >
            {((currentUserRole === "central_team" && op.signed) ||
              (currentUserRole === "project_stakeholder" && st.signed))
              ? "Unsign"
              : "Sign off"}
          </button>
        )}
      </div>
    );
  };

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
              type BindingEntry = MappingTableRecord["bindings"][number];
              const groups: Array<{ sourceField: string; bindings: BindingEntry[] }> = [];
              const groupIndexBySourceField: Record<string, number> = {};
              table.bindings.forEach((b) => {
                if (groupIndexBySourceField[b.sourceField] === undefined) {
                  groupIndexBySourceField[b.sourceField] = groups.length;
                  groups.push({ sourceField: b.sourceField, bindings: [] });
                }
                groups[groupIndexBySourceField[b.sourceField]].bindings.push(b);
              });
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
                      {table.fiberStatus && (
                        <span className={`inline-flex rounded-full border px-2 py-0.5 text-[10px] font-mono uppercase font-semibold ${
                          table.fiberStatus === "operator_triggered" || table.fiberStatus === "codegen_complete"
                            ? "border-emerald-500/20 bg-emerald-500/10 text-emerald-700"
                            : table.fiberStatus === "business_approved"
                            ? "border-blue-500/20 bg-blue-500/10 text-blue-700"
                            : table.fiberStatus === "operator_assigned"
                            ? "border-amber-500/20 bg-amber-500/10 text-amber-700"
                            : "border-slate-200 bg-slate-50 text-slate-600"
                        }`}>
                          {table.fiberStatus.replace(/_/g, " ")}
                        </span>
                      )}
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
                              {signOffStatus && <th className="py-2">Sign-offs</th>}
                            </tr>
                          </thead>
                          <tbody className="divide-y divide-slate-100">
                            {groups.map((group) => (
                              <tr key={group.sourceField} className="hover:bg-slate-50/50">
                                <td className="py-2.5 align-top">
                                  <div className="flex items-center gap-1.5">
                                    {editingEnabled && (
                                      <button
                                        type="button"
                                        onClick={() => onRemoveSourceField?.(table.destinationTableName, group.sourceField)}
                                        title="Drop this source field from migration"
                                        className="text-slate-400 hover:text-red-600 focus:outline-none text-xs font-bold leading-none"
                                      >
                                        ×
                                      </button>
                                    )}
                                    <span className="font-mono text-slate-700">{group.sourceField}</span>
                                    {group.bindings.length > 1 && (
                                      <span className="inline-flex items-center rounded bg-primary/10 px-1.5 py-0.5 text-[9px] font-semibold text-primary">
                                        1-to-{group.bindings.length}
                                      </span>
                                    )}
                                  </div>
                                  {(() => {
                                    const samples = sampleValues[group.sourceField.toLowerCase()] ?? [];
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
                                <td className="py-2.5 font-mono text-slate-900 font-medium align-top">
                                  <div className="flex flex-col gap-1.5">
                                    {group.bindings.map((binding, entryIdx) => {
                                      const bindingStatus = signOffStatus?.bindings[table.destinationTableName]?.[binding.sourceField]?.[binding.destinationField];
                                      const isSignedByEither = !!(bindingStatus && (bindingStatus.centralTeam.signed || bindingStatus.projectStakeholder.signed));
                                      const rowEditable = editingEnabled && !isSignedByEither;
                                      return (
                                        <div key={entryIdx} className="flex items-center gap-1.5">
                                          {rowEditable ? (
                                            <AutocompleteInput
                                              value={binding.destinationField}
                                              options={table.destinationFields || []}
                                              onChange={(newVal) => onDestinationFieldChange?.(table.destinationTableName, binding.sourceField, binding.destinationField, newVal)}
                                              className="rounded border border-slate-200 bg-white px-2 py-1 font-mono text-xs w-full focus:border-primary focus:ring-1 focus:ring-primary focus:outline-none"
                                              placeholder="destination field..."
                                            />
                                          ) : (
                                            <div className="flex items-center gap-1.5 py-1 text-slate-700">
                                              <span>{binding.destinationField || <span className="text-slate-400 italic font-sans text-xs">unmapped</span>}</span>
                                              {isSignedByEither && (
                                                <span title="Locked because this mapping has been signed off by a reviewer" className="text-[10px] text-slate-400 select-none">
                                                  🔒
                                                </span>
                                              )}
                                            </div>
                                          )}
                                          {editingEnabled && entryIdx > 0 && (
                                            <button
                                              type="button"
                                              onClick={() => onRemoveBinding?.(table.destinationTableName, binding.sourceField, binding.destinationField)}
                                              title="Remove this destination mapping"
                                              className="text-slate-400 hover:text-red-600 focus:outline-none text-xs font-bold leading-none"
                                            >
                                              ×
                                            </button>
                                          )}
                                        </div>
                                      );
                                    })}
                                    {editingEnabled && (() => {
                                      const mappedDests = new Set(group.bindings.map((b) => b.destinationField));
                                      const available = (table.destinationFields || []).filter((d) => d && !mappedDests.has(d));
                                      if (available.length === 0) return null;
                                      return (
                                        <button
                                          type="button"
                                          onClick={() => onAddBinding?.(table.destinationTableName, group.sourceField, available)}
                                          className="text-xs text-primary font-semibold hover:text-primary-hover flex items-center gap-1"
                                        >
                                          <span className="text-sm leading-none">+</span> Map to another destination
                                        </button>
                                      );
                                    })()}
                                  </div>
                                </td>
                                <td className="py-2.5 align-top">
                                  <div className="flex flex-col gap-1.5">
                                    {group.bindings.map((binding, entryIdx) => (
                                      <div key={entryIdx} className="py-1">{getBindingBadge(binding.bindingType)}</div>
                                    ))}
                                  </div>
                                </td>
                                {signOffStatus && (
                                  <td className="py-2.5 align-top">
                                    <div className="flex flex-col gap-1.5">
                                      {group.bindings.map((binding, entryIdx) => (
                                        <div key={entryIdx} className="py-1">
                                          {renderSignOffChips(table.destinationTableName, binding.sourceField, binding.destinationField)}
                                        </div>
                                      ))}
                                    </div>
                                  </td>
                                )}
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

      {unmappedDestinationFields.length > 0 && (
        <div className="rounded-xl border border-red-300 bg-red-50/50 p-5 space-y-3 mt-4">
          <div className="flex items-center gap-2 text-red-800">
            <span className="text-lg">🚨</span>
            <p className="text-sm font-semibold">
              Unmapped destination fields — data in these columns will not be populated. If these fields are required, code generation will fail.
            </p>
          </div>
          <ul className="space-y-2.5 pl-7">
            {unmappedDestinationFields.map((f, idx) => (
              <li key={idx} className="flex flex-col sm:flex-row sm:items-center gap-2">
                <span className="font-mono text-sm font-bold text-red-900 bg-red-100 px-2 py-0.5 rounded">
                  {f.tableName}.{f.fieldName}
                </span>
              </li>
            ))}
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
                    <h4 className="text-base font-bold text-slate-900 flex items-center gap-3">
                      <span>{group.lookupName}</span>
                      {group.fiberStatus && (
                        <span className={`inline-flex rounded-full border px-2 py-0.5 text-[10px] font-mono uppercase font-semibold ${
                          group.fiberStatus === "operator_triggered" || group.fiberStatus === "codegen_complete"
                            ? "border-emerald-500/20 bg-emerald-500/10 text-emerald-700"
                            : group.fiberStatus === "business_approved"
                            ? "border-blue-500/20 bg-blue-500/10 text-blue-700"
                            : group.fiberStatus === "operator_assigned"
                            ? "border-amber-500/20 bg-amber-500/10 text-amber-700"
                            : "border-slate-200 bg-slate-50 text-slate-600"
                        }`}>
                          {group.fiberStatus.replace(/_/g, " ")}
                        </span>
                      )}
                      {group.lookupValueMapId && renderLookupSignOffChips(group.lookupValueMapId)}
                    </h4>
                    <p className="text-xs text-slate-500">
                      Maps to reference table:{" "}
                      <span className="font-mono text-slate-700 bg-slate-100 border border-slate-200 rounded px-1.5 py-0.5">
                        {group.referenceTableName}
                      </span>
                    </p>
                  </div>
                </div>

                <LookupMappingTable
                  pairs={group.pairs}
                  destinationRows={group.pairs.map((p) => p.destinationRow).filter(Boolean) as Record<string, unknown>[]}
                  lookupValueMapId={group.lookupValueMapId}
                  unmappedRowCount={group.unmappedRowCount}
                  editingEnabled={editingEnabled}
                  onEditLookup={onEditLookup}
                />
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
                  disabled={!allSignedByStakeholder}
                  title={!allSignedByStakeholder ? "Please sign off all individual field and lookup mappings first." : undefined}
                  className="rounded-lg bg-primary px-5 py-2.5 text-sm font-semibold text-white shadow hover:bg-primary-hover focus:outline-none focus:ring-2 focus:ring-primary/20 disabled:opacity-50 disabled:cursor-not-allowed"
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
