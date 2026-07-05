"use client";

import { use, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Topbar } from "../../../../../components/Topbar";
import {
  getFeedContract,
  listFeedSlices,
  listFeedFibers,
  listFeedSchema,
  type FeedContractRecord,
  type FeedSliceRecord,
  type FiberRecord,
  type FeedSchemaColumnRecord,
} from "../../../../../lib/feeds-api";
import {
  getMappingSnapshot,
  proposeMappingSnapshot,
  type MappingReviewRecord,
} from "../../../../../lib/mapping-api";
import {
  listLookupValueMaps,
  createLookupValueMap,
  submitLookupInputs,
  type LookupValueMapRecord,
} from "../../../../../lib/lookup-api";
import { loadUiSession, type SessionRole, type UiSession } from "../../../../../lib/session";
import { ReviewGrid, type MappingTableRecord, type LookupValueGroup } from "../../../../../components/projects/ReviewGrid";

export default function FeedDetailPage({ params }: { params: Promise<{ id: string; feedId: string }> }) {
  const router = useRouter();
  const { id: projectId, feedId } = use(params);

  const [session, setSession] = useState<UiSession | null>(null);
  const [role, setRole] = useState<SessionRole>("read_only_auditor");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [feed, setFeed] = useState<FeedContractRecord | null>(null);
  const [slices, setSlices] = useState<FeedSliceRecord[]>([]);
  const [feedSchema, setFeedSchema] = useState<FeedSchemaColumnRecord[]>([]);
  const [mappingSnapshot, setMappingSnapshot] = useState<MappingReviewRecord | null>(null);
  const [lookupMaps, setLookupMaps] = useState<LookupValueMapRecord[]>([]);
  const [fibers, setFibers] = useState<FiberRecord[]>([]);
  
  // AI analysis state
  const [analyzing, setAnalyzing] = useState(false);
  const [analysisError, setAnalysisError] = useState<string | null>(null);

  // Lookup fibers drafts state
  const [lookupDrafts, setLookupDrafts] = useState<Record<string, { sourceText: string; destText: string; analyzing: boolean; error: string | null }>>({});

  useEffect(() => {
    const s = loadUiSession();
    setSession(s);
    if (s) {
      setRole(s.role);
    }
  }, []);

  const loadAllData = async (token: string) => {
    try {
      const [feedData, slicesData, fibersData, schemaData] = await Promise.all([
        getFeedContract(token, projectId, feedId),
        listFeedSlices(token, projectId, feedId),
        listFeedFibers(token, projectId, feedId),
        listFeedSchema(token, projectId, feedId),
      ]);

      setFeed(feedData);
      setSlices(slicesData);
      setFibers(fibersData);
      setFeedSchema(schemaData);

      // Try fetching mapping snapshot (might fail with 404 if not proposed yet)
      try {
        const mappingData = await getMappingSnapshot(token, projectId, feedId);
        setMappingSnapshot(mappingData);

        const mapsData = await listLookupValueMaps(token, projectId, feedId);
        setLookupMaps(mapsData);
      } catch (err) {
        setMappingSnapshot(null);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to load feed data.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (session) {
      void loadAllData(session.accessToken);
    }
  }, [session, projectId, feedId]);

  const latestSlice = slices[slices.length - 1]; // backend returns asc order
  const hasNoSlices = slices.length === 0;

  const handleAnalyzeWithAi = async () => {
    if (!session) return;
    setAnalyzing(true);
    setAnalysisError(null);
    try {
      try {
        await proposeMappingSnapshot(session.accessToken, projectId, feedId);
      } catch (err) {
        const status = (err as any).status || 0;
        const isConflict = err instanceof Error && (err.message.includes("conflict") || err.message.includes("409"));
        if (status === 409 || isConflict) {
          console.log("Mapping proposal already exists, reloading...");
        } else {
          throw err;
        }
      }
      await loadAllData(session.accessToken);
    } catch (err) {
      setAnalysisError(err instanceof Error ? err.message : "Unable to trigger AI analysis.");
    } finally {
      setAnalyzing(false);
    }
  };



  function parseAndConvertDestToCsv(destText: string): string {
    const trimmed = destText.trim();
    if (trimmed.startsWith("{") || trimmed.startsWith("[")) {
      let rows: any[] = [];
      if (trimmed.startsWith("[")) {
        rows = JSON.parse(trimmed);
      } else {
        rows = trimmed.split(/\r?\n/).map(line => line.trim()).filter(Boolean).map(line => JSON.parse(line));
      }
      if (!Array.isArray(rows) || rows.length === 0) {
        throw new Error("JSON must be a non-empty array/list of objects.");
      }
      const keys = Array.from(new Set(rows.flatMap(r => Object.keys(r))));
      const headerRow = keys.join(",");
      const dataRows = rows.map(row => keys.map(k => {
        const val = row[k];
        if (val === null || val === undefined) return "";
        const str = String(val);
        if (str.includes(",") || str.includes("\"") || str.includes("\n")) {
          return `"${str.replace(/"/g, '""')}"`;
        }
        return str;
      }).join(","));
      return [headerRow, ...dataRows].join("\n");
    } else {
      // Already CSV, validate it has at least header + 1 row
      const lines = trimmed.split(/\r?\n/).map(l => l.trim()).filter(Boolean);
      if (lines.length < 2) {
        throw new Error("CSV must contain a header row and at least one data row.");
      }
      return lines.join("\n");
    }
  }

  const handleAnalyzeLookup = async (lookupName: string, fiberId: string) => {
    if (!session) return;
    const draft = lookupDrafts[lookupName] || { sourceText: "", destText: "", analyzing: false, error: null };
    
    setLookupDrafts(current => ({
      ...current,
      [lookupName]: { ...draft, analyzing: true, error: null }
    }));

    try {
      const sourceValues = draft.sourceText
        .split(/\r?\n/)
        .map(line => line.trim())
        .filter(Boolean);
      
      if (sourceValues.length === 0) {
        throw new Error("Source values cannot be empty.");
      }

      const destinationLookupCsv = parseAndConvertDestToCsv(draft.destText);

      await submitLookupInputs(session.accessToken, projectId, feedId, fiberId, {
        sourceValues,
        destinationLookupCsv,
      });

      const mapsData = await listLookupValueMaps(session.accessToken, projectId, feedId);
      setLookupMaps(mapsData);

      setLookupDrafts(current => ({
        ...current,
        [lookupName]: { ...draft, error: null, analyzing: false }
      }));
    } catch (err) {
      setLookupDrafts(current => ({
        ...current,
        [lookupName]: {
          ...draft,
          analyzing: false,
          error: err instanceof Error ? err.message : String(err)
        }
      }));
    }
  };

  // Build props for ReviewGrid
  const mappingTablesMap: Record<string, MappingTableRecord> = {};
  if (mappingSnapshot) {
    for (const binding of mappingSnapshot.fieldBindings) {
      const tblName = binding.destinationTableName || mappingSnapshot.destinationObjectName;
      if (!mappingTablesMap[tblName]) {
        mappingTablesMap[tblName] = {
          destinationTableName: tblName,
          bindings: [],
        };
      }
      mappingTablesMap[tblName].bindings.push({
        sourceField: binding.sourceField,
        destinationField: binding.destinationField,
        bindingType: binding.bindingType || "direct",
        referenceTableName: binding.referenceTableName || null,
      });
    }
  }
  const mappingTables = Object.values(mappingTablesMap);

  const lookupGroups: LookupValueGroup[] = [];
  if (mappingSnapshot) {
    const refMap = Object.fromEntries(
      (mappingSnapshot.lookupTableReferences ?? []).map((r) => [r.lookupName, r.destinationTableName])
    );
    const seenLookups = new Set<string>();
    for (const binding of mappingSnapshot.fieldBindings) {
      if (binding.lookupName && !seenLookups.has(binding.lookupName)) {
        seenLookups.add(binding.lookupName);
        const refTable = refMap[binding.lookupName] || "unknown_ref";
        const latestMap = lookupMaps.find((m) => m.lookupName === binding.lookupName);
        const pairs = [];
        if (latestMap) {
          for (const [srcVal, destId] of Object.entries(latestMap.sourceValueMap)) {
            const destRow = latestMap.destinationTable.find(
              (row) => String(row.id) === String(destId) || String(row.destination_id) === String(destId)
            ) || { id: destId };
            pairs.push({
              sourceValue: srcVal,
              destinationRow: destRow,
              confidenceScore: 0.95,
              status: (latestMap.status === "approved" ? "confirmed" : "pending") as any,
            });
          }
        }
        lookupGroups.push({
          lookupName: binding.lookupName,
          referenceTableName: refTable,
          pairs,
        });
      }
    }
  }

  // Lookup FK bindings for fibers section
  const lookupFkBinds = mappingSnapshot
    ? mappingSnapshot.fieldBindings.filter((b) => b.bindingType === "lookup_fk" && b.lookupName)
    : [];

  return (
    <main className="flex min-h-screen flex-col bg-surface text-slate-800">
      <Topbar role={role} />
      
      <section className="mx-auto w-full max-w-[1600px] flex-1 px-6 py-6 space-y-6">
        <div className="flex items-center justify-between">
          <button
            onClick={() => router.push(`/projects/${projectId}?tab=feeds`)}
            className="rounded-lg border border-outline-variant bg-surface-container px-3 py-2 text-sm font-semibold text-slate-700 hover:bg-outline-variant"
            type="button"
          >
            Back to project
          </button>
          
          <div className="flex items-center gap-3">
            <h1 className="text-xl font-bold text-slate-900">{feed?.label || "Feed details"}</h1>
            <span className="text-xs text-slate-500 font-mono">({feedId})</span>
          </div>
        </div>

        {error && (
          <div role="alert" className="rounded-xl border border-red-500/20 bg-red-500/10 px-4 py-3 text-sm text-red-700">
            {error}
          </div>
        )}

        {loading ? (
          <div className="rounded-2xl border border-outline-variant bg-surface-container p-8 text-sm text-slate-600">
            Loading workspace details...
          </div>
        ) : (
          <div className="grid gap-6 lg:grid-cols-[1fr_2fr]">
            {/* Left Column: Slice & Upload Info */}
            <div className="space-y-6">
              {/* Slice Panel */}
              <div className="rounded-2xl border border-outline-variant bg-surface-container p-5 shadow-sm space-y-4">
                <h3 className="text-base font-bold text-slate-900">Slice</h3>
                
                {hasNoSlices ? (
                  <div className="text-sm text-slate-500">No slices uploaded yet.</div>
                ) : (
                  <div className="space-y-4">
                    <div className="space-y-2">
                      <div className="flex items-center justify-between text-xs">
                        <span className="text-slate-500">Latest Slice:</span>
                        <span className="font-mono font-medium text-slate-700">{latestSlice.sourceSliceVersion}</span>
                      </div>
                      <div className="flex items-center justify-between text-xs">
                        <span className="text-slate-500">Rows:</span>
                        <span className="font-bold text-slate-900">{latestSlice.rowCount}</span>
                      </div>
                      <div className="flex items-center justify-between">
                        <span className="text-xs text-slate-500">Status:</span>
                        <span className="inline-flex items-center gap-1.5 rounded-full bg-emerald-50 px-2 py-0.5 text-xs font-semibold text-emerald-700">
                          <span className="h-1.5 w-1.5 rounded-full bg-emerald-600"></span>
                          received
                        </span>
                      </div>
                    </div>

                    {/* Preview Table */}
                    {(latestSlice.previewRows || []).length === 0 ? (
                      <div className="text-xs text-slate-500 italic bg-slate-50 rounded-lg p-3 text-center">
                        No preview available.
                      </div>
                    ) : (
                      <div className="space-y-1.5">
                        <div className="text-[10px] font-bold uppercase tracking-wider text-slate-500">Masked Data Preview</div>
                        <div className="max-h-48 overflow-auto border border-outline-variant rounded-lg bg-white">
                          <table className="w-full text-left text-[10px] border-collapse font-mono">
                            <thead className="bg-slate-50 border-b border-outline-variant sticky top-0">
                              <tr>
                                {feedSchema.map((col, i) => (
                                  <th key={i} className="px-3 py-1.5 font-bold text-slate-700 whitespace-nowrap">{col.fieldName}</th>
                                ))}
                              </tr>
                            </thead>
                            <tbody className="divide-y divide-slate-100">
                              {(latestSlice.previewRows || []).map((rowStr, rowIdx) => {
                                const rowCells = rowStr.split(",");
                                return (
                                  <tr key={rowIdx} className="hover:bg-slate-50/50">
                                    {rowCells.map((cell, cellIdx) => (
                                      <td key={cellIdx} className="px-3 py-1.5 text-slate-600 whitespace-nowrap">{cell}</td>
                                    ))}
                                  </tr>
                                );
                              })}
                            </tbody>
                          </table>
                        </div>
                      </div>
                    )}

                    {/* Analyze with AI Button */}
                    <div className="pt-2 border-t border-slate-100 space-y-2">
                      <button
                        onClick={handleAnalyzeWithAi}
                        disabled={analyzing}
                        className="w-full rounded-xl bg-primary py-2.5 text-sm font-semibold text-white hover:bg-primary-hover disabled:opacity-50 disabled:cursor-not-allowed shadow-sm flex items-center justify-center gap-2 transition"
                        type="button"
                      >
                        {analyzing ? (
                          <>
                            <svg className="animate-spin -ml-1 mr-2 h-4 w-4 text-white" fill="none" viewBox="0 0 24 24">
                              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                            </svg>
                            Analyzing…
                          </>
                        ) : (
                          "Analyze with AI"
                        )}
                      </button>
                      
                      {analysisError && (
                        <div role="alert" className="rounded-lg bg-red-50 border border-red-100 p-3 text-xs text-red-700">
                          {analysisError}
                        </div>
                      )}
                    </div>
                  </div>
                )}
              </div>


            </div>

            {/* Right Column: downstream steps */}
            <div className="space-y-6">

              {/* A. Mapping Tables Accordions */}
              <div className="rounded-2xl border border-outline-variant bg-surface-container p-6 shadow-sm space-y-4">
                <h3 className="text-lg font-bold text-slate-900">Field Mappings</h3>
                <p className="text-xs text-slate-500">Verify AI extraction classifications across destination tables.</p>
                
                {mappingTables.length === 0 ? (
                  <div className="text-sm text-slate-500">No mapping proposals generated yet.</div>
                ) : (
                  <div className="space-y-3">
                    {mappingTables.map((tbl) => (
                      <div key={tbl.destinationTableName} className="border border-outline-variant rounded-xl overflow-hidden bg-white">
                        <div className="bg-slate-50 px-4 py-3 border-b border-outline-variant font-mono text-xs font-bold text-slate-700">
                          {tbl.destinationTableName}
                        </div>
                        <table className="w-full text-left text-xs border-collapse">
                          <tbody className="divide-y divide-slate-100">
                            {tbl.bindings.map((b, idx) => (
                              <tr key={idx} className="hover:bg-slate-50/40">
                                <td className="px-4 py-2 font-mono text-slate-600">{b.sourceField}</td>
                                <td className="px-4 py-2 font-mono font-bold text-slate-800">{b.destinationField}</td>
                                <td className="px-4 py-2">
                                  {b.bindingType === "direct" && (
                                    <span className="inline-flex rounded bg-slate-100 px-1.5 py-0.5 text-[10px] text-slate-600">direct</span>
                                  )}
                                  {b.bindingType === "detail_fk" && (
                                    <span className="inline-flex rounded bg-blue-100 px-1.5 py-0.5 text-[10px] text-blue-700">detail_fk</span>
                                  )}
                                  {b.bindingType === "lookup_fk" && (
                                    <span className="inline-flex rounded bg-amber-100 px-1.5 py-0.5 text-[10px] text-amber-700">lookup_fk</span>
                                  )}
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {/* B. Lookup Fibers cards */}
              <div className="rounded-2xl border border-outline-variant bg-surface-container p-6 shadow-sm space-y-4">
                <h3 className="text-lg font-bold text-slate-900">Lookup Fibers</h3>
                <p className="text-xs text-slate-500">Provide local mappings for value replacement lists.</p>

                {lookupFkBinds.length === 0 ? (
                  <div className="text-sm text-slate-500">No lookup foreign keys mapped in the snapshot.</div>
                ) : (
                  <div className="grid gap-6 md:grid-cols-2">
                    {lookupFkBinds.map((binding) => {
                      const lName = binding.lookupName!;
                      const refTable = binding.referenceTableName || "unknown_ref";
                      const fiber = fibers.find((f) => f.fiberType === "lookup" && f.fiberKey === lName);
                      const fiberId = fiber?.fiberId || "";

                      const draft = lookupDrafts[lName] || { sourceText: "", destText: "", analyzing: false, error: null };

                      const handleSourceChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
                        setLookupDrafts((current) => ({
                          ...current,
                          [lName]: {
                            ...(current[lName] || { sourceText: "", destText: "", analyzing: false, error: null }),
                            sourceText: e.target.value,
                          },
                        }));
                      };

                      const handleDestChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
                        setLookupDrafts((current) => ({
                          ...current,
                          [lName]: {
                            ...(current[lName] || { sourceText: "", destText: "", analyzing: false, error: null }),
                            destText: e.target.value,
                          },
                        }));
                      };

                      const isAnalyzeDisabled =
                        !draft.sourceText.trim() ||
                        !draft.destText.trim() ||
                        draft.analyzing ||
                        !fiberId;

                      return (
                        <div key={lName} className="border border-outline-variant rounded-xl p-4 bg-white space-y-4 shadow-sm">
                          <div className="flex items-center justify-between">
                            <span className="text-sm font-bold text-slate-800">{lName}</span>
                            <span className="text-[10px] bg-amber-500/10 text-amber-700 px-1.5 py-0.5 rounded font-mono">
                              ref: {refTable}
                            </span>
                          </div>

                          <div className="space-y-3">
                            <div className="space-y-1">
                              <label className="text-[10px] font-bold uppercase tracking-wider text-slate-500">
                                Source values (one per line)
                              </label>
                              <textarea
                                value={draft.sourceText}
                                onChange={handleSourceChange}
                                placeholder="VALUE_A&#10;VALUE_B&#10;..."
                                className="h-24 w-full rounded border border-slate-200 bg-white p-2 font-mono text-xs text-slate-900 focus:outline-none focus:ring-1 focus:ring-primary"
                              />
                            </div>

                            <div className="space-y-1">
                              <label className="text-[10px] font-bold uppercase tracking-wider text-slate-500">
                                Rows from {refTable} (CSV or JSON)
                              </label>
                              <textarea
                                value={draft.destText}
                                onChange={handleDestChange}
                                placeholder="id,description&#10;1,Active&#10;2,Inactive&#10;..."
                                className="h-24 w-full rounded border border-slate-200 bg-white p-2 font-mono text-xs text-slate-900 focus:outline-none focus:ring-1 focus:ring-primary"
                              />
                            </div>
                          </div>

                          {draft.error && (
                            <div role="alert" className="rounded bg-error/10 border border-error/20 p-2 text-xs text-error">
                              {draft.error}
                            </div>
                          )}

                          <div className="pt-2">
                            <button
                              onClick={() => void handleAnalyzeLookup(lName, fiberId)}
                              disabled={isAnalyzeDisabled}
                              className="w-full rounded bg-primary py-2 text-xs font-semibold text-white hover:bg-primary-hover disabled:opacity-50 disabled:cursor-not-allowed"
                              type="button"
                            >
                              {draft.analyzing ? "Analyzing..." : "AI Analyze"}
                            </button>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>

              {/* C. Reviews panel */}
              <div className="rounded-2xl border border-outline-variant bg-surface-container p-6 shadow-sm space-y-4">
                <div className="flex items-center justify-between">
                  <h3 className="text-lg font-bold text-slate-900 font-bold">Reviews</h3>
                  <button
                    onClick={() => router.push(`/projects/${projectId}/feeds/${feedId}/review`)}
                    className="rounded border border-primary text-primary px-3 py-1.5 text-xs font-semibold hover:bg-primary/5"
                    type="button"
                  >
                    View review page
                  </button>
                </div>
                
                {mappingSnapshot ? (
                  <ReviewGrid
                    mappingTables={mappingTables}
                    lookupGroups={lookupGroups}
                  />
                ) : (
                  <div className="text-sm text-slate-500 text-center py-6">
                    No approved mapping snapshot to render reviews.
                  </div>
                )}
              </div>
            </div>
          </div>
        )}
      </section>
    </main>
  );
}
