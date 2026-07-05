"use client";

import { use, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Topbar } from "../../../../../components/Topbar";
import {
  getFeedContract,
  listFeedSlices,
  approveFeedSlice,
  rejectFeedSlice,
  listFeedValueSummaries,
  listFeedSchema,
  type FeedContractRecord,
  type FeedSliceRecord,
  type FeedValueSummaryRecord,
  type FeedSchemaColumnRecord,
} from "../../../../../lib/feeds-api";
import {
  getMappingSnapshot,
  type MappingReviewRecord,
} from "../../../../../lib/mapping-api";
import {
  listLookupValueMaps,
  createLookupValueMap,
  generateLookupSnapshot,
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
  const [mappingSnapshot, setMappingSnapshot] = useState<MappingReviewRecord | null>(null);
  const [lookupMaps, setLookupMaps] = useState<LookupValueMapRecord[]>([]);
  const [valueSummaries, setValueSummaries] = useState<FeedValueSummaryRecord[]>([]);
  
  const [rejectionReason, setRejectionReason] = useState("");
  const [showRejectForm, setShowRejectForm] = useState(false);

  // Lookup fibers editing state
  const [lookupEdits, setLookupEdits] = useState<Record<string, Record<string, string>>>({});
  const [savingLookup, setSavingLookup] = useState<Record<string, boolean>>({});

  useEffect(() => {
    const s = loadUiSession();
    setSession(s);
    if (s) {
      setRole(s.role);
    }
  }, []);

  const loadAllData = async (token: string) => {
    try {
      const [feedData, slicesData, summariesData] = await Promise.all([
        getFeedContract(token, projectId, feedId),
        listFeedSlices(token, projectId, feedId),
        listFeedValueSummaries(token, projectId, feedId),
      ]);

      setFeed(feedData);
      setSlices(slicesData);
      setValueSummaries(summariesData);

      // Try fetching mapping snapshot (might fail with 404 if not proposed yet)
      try {
        const mappingData = await getMappingSnapshot(token, projectId, feedId);
        setMappingSnapshot(mappingData);

        const mapsData = await listLookupValueMaps(token, projectId, feedId);
        setLookupMaps(mapsData);

        // Prepopulate lookup fiber edits
        const initialEdits: Record<string, Record<string, string>> = {};
        for (const m of mapsData) {
          initialEdits[m.lookupName] = { ...m.sourceValueMap };
        }
        setLookupEdits(initialEdits);
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
  const isSliceApproved = latestSlice?.status === "approved";
  const hasNoSlices = slices.length === 0;
  const isHardGated = hasNoSlices || !isSliceApproved;

  const handleApproveSlice = async () => {
    if (!session || !latestSlice) return;
    setLoading(true);
    try {
      await approveFeedSlice(session.accessToken, projectId, feedId, latestSlice.sourceSliceId);
      await loadAllData(session.accessToken);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to approve slice.");
      setLoading(false);
    }
  };

  const handleRejectSlice = async () => {
    if (!session || !latestSlice || !rejectionReason.trim()) return;
    setLoading(true);
    try {
      await rejectFeedSlice(session.accessToken, projectId, feedId, latestSlice.sourceSliceId, rejectionReason.trim());
      setRejectionReason("");
      setShowRejectForm(false);
      await loadAllData(session.accessToken);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to reject slice.");
      setLoading(false);
    }
  };



  const handleSaveLookup = async (lookupName: string, refTable: string) => {
    if (!session) return;
    setSavingLookup((prev) => ({ ...prev, [lookupName]: true }));
    try {
      const edits = lookupEdits[lookupName] || {};
      const latestMap = lookupMaps.find((m) => m.lookupName === lookupName);
      
      const existingRows = latestMap?.destinationTable || [];
      const existingIds = new Set(
        existingRows.map((r) => String(r.id || r.destination_id || "")).filter(Boolean)
      );

      const nextRows = [...existingRows];
      for (const val of Object.values(edits)) {
        const destId = val?.trim();
        if (destId && !existingIds.has(destId)) {
          nextRows.push({ id: destId, label: destId });
          existingIds.add(destId);
        }
      }

      await createLookupValueMap(session.accessToken, projectId, feedId, {
        lookupName,
        destinationTable: nextRows,
        sourceValueMap: edits,
      });

      // Reload
      const mapsData = await listLookupValueMaps(session.accessToken, projectId, feedId);
      setLookupMaps(mapsData);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to save lookup.");
    } finally {
      setSavingLookup((prev) => ({ ...prev, [lookupName]: false }));
    }
  };

  const handleRunAiLookup = async (lookupName: string) => {
    if (!session) return;
    setSavingLookup((prev) => ({ ...prev, [lookupName]: true }));
    try {
      await generateLookupSnapshot(session.accessToken, projectId, feedId, { lookupName });
      // Reload
      const mapsData = await listLookupValueMaps(session.accessToken, projectId, feedId);
      setLookupMaps(mapsData);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to run AI lookup.");
    } finally {
      setSavingLookup((prev) => ({ ...prev, [lookupName]: false }));
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
              {/* Slice Status Panel */}
              <div className="rounded-2xl border border-outline-variant bg-surface-container p-5 shadow-sm space-y-4">
                <h3 className="text-base font-bold text-slate-900">Slice Status</h3>
                
                {hasNoSlices ? (
                  <div className="text-sm text-slate-500">No slices uploaded yet.</div>
                ) : (
                  <div className="space-y-3">
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
                      <span className={`inline-flex rounded-full px-2.5 py-0.5 text-xs font-semibold ${
                        latestSlice.status === "approved"
                          ? "bg-emerald-100 text-emerald-700"
                          : latestSlice.status === "pending"
                          ? "bg-amber-100 text-amber-700"
                          : "bg-red-100 text-red-700"
                      }`}>
                        {latestSlice.status}
                      </span>
                    </div>
                    
                    {latestSlice.approvalRejectionReason && (
                      <div className="rounded-lg bg-red-50 p-3 text-xs text-red-700 border border-red-100">
                        <strong>Reason:</strong> {latestSlice.approvalRejectionReason}
                      </div>
                    )}

                    {latestSlice.status === "pending" && role === "central_team" && (
                      <div className="flex flex-col gap-2 pt-2">
                        <div className="flex gap-2">
                          <button
                            onClick={handleApproveSlice}
                            className="flex-1 rounded-md bg-emerald-600 py-2 text-xs font-semibold text-white hover:bg-emerald-700"
                            type="button"
                          >
                            Approve Slice
                          </button>
                          <button
                            onClick={() => setShowRejectForm(!showRejectForm)}
                            className="flex-1 rounded-md border border-red-300 py-2 text-xs font-semibold text-red-700 hover:bg-red-50"
                            type="button"
                          >
                            Reject Slice
                          </button>
                        </div>

                        {showRejectForm && (
                          <div className="space-y-2 border-t border-slate-200 pt-3">
                            <label htmlFor="rejection-reason" className="block text-xs font-semibold text-slate-700">
                              Rejection comment
                            </label>
                            <input
                              id="rejection-reason"
                              type="text"
                              value={rejectionReason}
                              onChange={(e) => setRejectionReason(e.target.value)}
                              placeholder="Describe slice parse failure..."
                              className="w-full rounded-md border border-slate-300 bg-white px-2 py-1.5 text-xs text-slate-900"
                            />
                            <button
                              onClick={handleRejectSlice}
                              disabled={!rejectionReason.trim()}
                              className="w-full rounded-md bg-red-600 py-1.5 text-xs font-semibold text-white disabled:opacity-50"
                              type="button"
                            >
                              Confirm Rejection
                            </button>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                )}
              </div>


            </div>

            {/* Right Column: downstream steps gated by slice status */}
            <div className="space-y-6 relative">
              {isHardGated && (
                <div className="absolute inset-0 bg-slate-50/70 backdrop-blur-[1px] z-20 flex items-center justify-center p-6">
                  <div className="rounded-2xl border border-amber-200 bg-amber-50 p-6 shadow-md text-center max-w-md space-y-2">
                    <h3 className="text-sm font-bold text-amber-800">Workspace Locked</h3>
                    <p className="text-xs text-amber-700">
                      Slice approval is required before mapping and lookups can proceed. Approve the uploaded slice.
                    </p>
                  </div>
                </div>
              )}

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
                  <div className="grid gap-4 md:grid-cols-2">
                    {lookupFkBinds.map((binding) => {
                      const lName = binding.lookupName!;
                      const refTable = binding.referenceTableName || "unknown_ref";
                      const mapState = lookupMaps.find((m) => m.lookupName === lName);
                      const fieldSummary = valueSummaries.find((s) => s.fieldName === binding.sourceField);
                      const sourceValuesList = fieldSummary ? Object.keys(fieldSummary.valueCounts) : [];

                      const edits = lookupEdits[lName] || {};
                      const isSaving = !!savingLookup[lName];

                      return (
                        <div key={lName} className="border border-outline-variant rounded-xl p-4 bg-white space-y-3">
                          <div className="flex items-center justify-between">
                            <span className="text-sm font-bold text-slate-800">{lName}</span>
                            <span className="text-[10px] bg-amber-500/10 text-amber-700 px-1.5 py-0.5 rounded font-mono">
                              ref: {refTable}
                            </span>
                          </div>

                          <div className="space-y-2 max-h-48 overflow-y-auto pr-1">
                            {sourceValuesList.map((val) => (
                              <div key={val} className="flex items-center justify-between text-xs gap-2">
                                <span className="text-slate-600 truncate max-w-[120px]">{val}</span>
                                <input
                                  type="text"
                                  value={edits[val] || ""}
                                  onChange={(e) => {
                                    setLookupEdits((current) => ({
                                      ...current,
                                      [lName]: {
                                        ...(current[lName] || {}),
                                        [val]: e.target.value,
                                      },
                                    }));
                                  }}
                                  placeholder="mapped code"
                                  className="w-24 rounded border border-slate-200 px-2 py-0.5 text-xs focus:outline-none"
                                />
                              </div>
                            ))}
                          </div>

                          <div className="flex gap-2 pt-2 border-t border-slate-100">
                            <button
                              onClick={() => handleSaveLookup(lName, refTable)}
                              disabled={isSaving}
                              className="flex-1 rounded bg-slate-100 hover:bg-slate-200 py-1.5 text-xs font-semibold text-slate-700"
                              type="button"
                            >
                              Save Draft
                            </button>
                            <button
                              onClick={() => handleRunAiLookup(lName)}
                              disabled={isSaving}
                              className="flex-1 rounded bg-primary py-1.5 text-xs font-semibold text-white hover:bg-primary-hover"
                              type="button"
                            >
                              Run AI
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
