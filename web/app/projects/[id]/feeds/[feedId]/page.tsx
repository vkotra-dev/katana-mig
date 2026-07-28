"use client";

import { use, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Topbar } from "../../../../../components/Topbar";
import {
  getFeedContract,
  listFeedSlices,
  listFeedFibers,
  listFeedSchema,
  analyzeFeedSource,
  getSourceSchemaArtifact,
  createFiber,
  patchFeedMappingHints,
  uploadFeedSlice,
  resubmitFeedSlice,
  discardFeed,
  type FeedContractRecord,
  type FeedSliceRecord,
  type FiberRecord,
  type FeedSchemaColumnRecord,
} from "../../../../../lib/feeds-api";
import {
  getAllApprovedMappingSnapshots,
  proposeMappingSnapshot,
  type MappingSnapshotRecord,
} from "../../../../../lib/mapping-api";
import {
  listLookupValueMaps,
  createLookupValueMap,
  submitLookupInputs,
  type LookupValueMapRecord,
} from "../../../../../lib/lookup-api";
import { loadUiSession, type SessionRole, type UiSession } from "../../../../../lib/session";
import { type MappingTableRecord } from "../../../../../components/projects/ReviewGrid";
import { splitCsvRow } from "../../../../../lib/csv-utils";
import { UnifiedCommentThread } from "../../../../../components/feeds/UnifiedCommentThread";
import { AiLogViewer } from "../../../../../components/ai-logs/AiLogViewer";

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
  const [allMappingSnapshots, setAllMappingSnapshots] = useState<MappingSnapshotRecord[]>([]);
  const [expandedTables, setExpandedTables] = useState<Set<string>>(new Set());
  const [expandedLookups, setExpandedLookups] = useState<Set<string>>(new Set());
  const [lookupMaps, setLookupMaps] = useState<LookupValueMapRecord[]>([]);
  const [fibers, setFibers] = useState<FiberRecord[]>([]);
  
  // AI analysis state
  const [analyzing, setAnalyzing] = useState(false);
  const [analysisError, setAnalysisError] = useState<string | null>(null);
  const [sourceDDL, setSourceDDL] = useState<string | null>(null);
  const [sourceDdlExpanded, setSourceDdlExpanded] = useState(false);

  // Lookup fibers drafts state
  const [lookupDrafts, setLookupDrafts] = useState<Record<string, { sourceText: string; destText: string; analyzing: boolean; error: string | null }>>({});


  const [notice, setNotice] = useState<string | null>(null);

  // Hints state
  const [mappingHints, setMappingHints] = useState<string>("");
  const [savingHints, setSavingHints] = useState(false);

  const [replacementFile, setReplacementFile] = useState<string | null>(null);
  const [uploadingReplacement, setUploadingReplacement] = useState(false);
  const [showOriginal, setShowOriginal] = useState(false);
  const [loadingPreview, setLoadingPreview] = useState(false);

  const [discardConfirm, setDiscardConfirm] = useState(false);
  const [discarding, setDiscarding] = useState(false);

  useEffect(() => {
    const s = loadUiSession();
    setSession(s);
    if (s) {
      setRole(s.role);
    }
  }, []);

  const loadAllData = async (token: string) => {
    try {
      const [feedData, slicesData, fibersData, mapsData] = await Promise.all([
        getFeedContract(token, projectId, feedId),
        listFeedSlices(token, projectId, feedId),
        listFeedFibers(token, projectId, feedId),
        listLookupValueMaps(token, projectId, feedId),
      ]);

      setFeed(feedData);
      setMappingHints(feedData.mappingHints || "");
      setSlices(slicesData);
      setFibers(fibersData);

      // Populate lookup drafts for lookups if they exist in DB/proposed mappings
      for (const fiber of fibersData) {
        if (fiber.fiberType === "lookup") {
          try {
            const sharedMap = mapsData.find((m) => m.lookupName === fiber.fiberKey);
            let sourceText = "";
            
            if (sharedMap) {
              sourceText = Object.keys(sharedMap.sourceValueMap).join("\n");
            } else if (fiber.proposedMappings && fiber.proposedMappings.length > 0) {
              const srcVals = fiber.proposedMappings.map((pm) => pm.sourceValue || pm.source_value).filter(Boolean);
              sourceText = Array.from(new Set(srcVals)).join("\n");
            }
            
            // Reconstruct CSV for destination entries
            let destText = "";
            if (sharedMap && sharedMap.destinationTable.length > 0) {
              const columns = Object.keys(sharedMap.destinationTable[0]);
              const headerRow = columns.join(",");
              const dataRows = sharedMap.destinationTable.map((row) =>
                columns.map((col) => {
                  const val = row[col];
                  if (typeof val === "string") {
                    return val.startsWith("'") && val.endsWith("'") ? val : `'${val}'`;
                  }
                  return val;
                }).join(",")
              );
              destText = [headerRow, ...dataRows].join("\n");
            } else if (fiber.proposedMappings && fiber.proposedMappings.length > 0) {
              const destRows = fiber.proposedMappings.map((pm) => pm.destRow || pm.dest_row).filter(Boolean);
              if (destRows.length > 0) {
                const columns = Object.keys(destRows[0]);
                const headerRow = columns.join(",");
                const dataRows = destRows.map((row) =>
                  columns.map((col) => {
                    const val = row[col];
                    if (typeof val === "string") {
                      return val.startsWith("'") && val.endsWith("'") ? val : `'${val}'`;
                    }
                    return val;
                  }).join(",")
                );
                destText = [headerRow, ...dataRows].join("\n");
              }
            }

            setLookupDrafts((current) => ({
              ...current,
              [fiber.fiberKey]: {
                sourceText,
                destText,
                analyzing: false,
                error: null,
              },
            }));
          } catch (e) {
            console.error("Failed to load lookup draft values for", fiber.fiberKey, e);
          }
        }
      }

      // Try fetching feed schema (might fail with 404 if no slices/schema parsed yet)
      let sourceDDLValue: string | null = null;
      try {
        const schemaData = await listFeedSchema(token, projectId, feedId);
        setFeedSchema(schemaData);
      } catch {
        setFeedSchema([]);
      }

      // Fetch full schema artifact for destination DDL (persists across reloads)
      try {
        const artifact = await getSourceSchemaArtifact(token, projectId, feedId);
        sourceDDLValue = artifact.destinationDDL;
      } catch {
        /* No artifact yet — DDL stays null */
      }
      setSourceDDL(sourceDDLValue);

      // Try fetching all mapping snapshots (draft or approved)
      try {
        const snapshotsData = await getAllApprovedMappingSnapshots(token, projectId, feedId, true);
        setAllMappingSnapshots(snapshotsData);
        if (snapshotsData.length > 0) {
          const mapsData = await listLookupValueMaps(token, projectId, feedId);
          setLookupMaps(mapsData);
        }
      } catch (err) {
        setAllMappingSnapshots([]);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to load feed data.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    setShowOriginal(false);
    if (session) {
      void loadAllData(session.accessToken);
    }
  }, [session, projectId, feedId]);

  const handleToggleShowOriginal = async () => {
    if (!session || !latestSlice) return;
    const nextShowOriginal = !showOriginal;
    try {
      setLoadingPreview(true);
      const refreshedSlices = await listFeedSlices(session.accessToken, projectId, feedId, !nextShowOriginal);
      setSlices(refreshedSlices);
      setShowOriginal(nextShowOriginal);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load original values.");
    } finally {
      setLoadingPreview(false);
    }
  };

  const latestSlice = slices[slices.length - 1]; // backend returns asc order
  const hasNoSlices = slices.length === 0;

  const handleAnalyzeWithAi = async () => {
    if (!session) return;
    setAnalyzing(true);
    setAnalysisError(null);
    try {
      // Step 1: extract source column schema from the slice
      const analyzeResult = await analyzeFeedSource(session.accessToken, projectId, feedId);
      setSourceDDL(analyzeResult.destinationDDL ?? null);
      // Step 2: propose field mappings using AI
      try {
        await proposeMappingSnapshot(session.accessToken, projectId, feedId);
      } catch (err) {
        const status = (err as any).status || 0;
        const isConflict = err instanceof Error && (err.message.includes("conflict") || err.message.includes("409"));
        if (status !== 409 && !isConflict) throw err;
        // 409 is expected when mapping already exists — load data to show the existing state
      }
      await loadAllData(session.accessToken);

    } catch (err) {
      setAnalysisError(err instanceof Error ? err.message : "Unable to trigger AI analysis.");
    } finally {
      setAnalyzing(false);
    }
  };

  const handleSaveMappingHints = async () => {
    if (!session) return;
    setSavingHints(true);
    setError(null);
    setNotice(null);
    try {
      await patchFeedMappingHints(session.accessToken, projectId, feedId, mappingHints);
      setNotice("Mapping hints saved successfully.");
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setSavingHints(false);
    }
  };

  const handleUploadReplacement = async () => {
    if (!replacementFile || !session?.accessToken) return;
    setUploadingReplacement(true);
    setError(null);
    setNotice(null);
    try {
      await uploadFeedSlice(session.accessToken, projectId, feedId, { content: replacementFile });
      setReplacementFile(null);
      // Reload slices
      const refreshed = await listFeedSlices(session.accessToken, projectId, feedId);
      setSlices(refreshed);
      setNotice("Replacement data uploaded successfully.");
    } catch (err) {
      setError("Failed to upload replacement file.");
    } finally {
      setUploadingReplacement(false);
    }
  };

  const handleReplacementFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = (ev) => {
      setReplacementFile(ev.target?.result as string);
    };
    reader.readAsText(file);
  };



  const handleDiscard = async () => {
    if (!session) return;
    setDiscarding(true);
    setError(null);
    try {
      await discardFeed(session.accessToken, projectId, feedId);
      router.push(`/projects/${projectId}?tab=feeds`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to discard feed.");
      setDiscardConfirm(false);
    } finally {
      setDiscarding(false);
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

  const handleAnalyzeLookup = async (lookupName: string, passedFiberId: string) => {
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

      let targetFiberId = passedFiberId;
      if (!targetFiberId) {
        const newFiber = await createFiber(session.accessToken, projectId, feedId, {
          fiberType: "lookup",
          fiberKey: lookupName,
          source: "manual",
        });
        targetFiberId = newFiber.fiberId;
      }

      await submitLookupInputs(session.accessToken, projectId, feedId, targetFiberId, {
        sourceValues,
        destinationLookupCsv,
      });

      const nextFibers = await listFeedFibers(session.accessToken, projectId, feedId);
      setFibers(nextFibers);

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

  const mappingTablesMap: Record<string, MappingTableRecord> = {};
  for (const snapshot of allMappingSnapshots) {
    const tblName = snapshot.destinationObjectName;
    if (!mappingTablesMap[tblName]) {
      mappingTablesMap[tblName] = {
        destinationTableName: tblName,
        destinationFields: snapshot.destinationFields || [],
        bindings: [],
      };
    }
    for (const binding of snapshot.fieldBindings) {
      mappingTablesMap[tblName].bindings.push({
        sourceField: binding.sourceField,
        destinationField: binding.destinationField,
        bindingType: binding.bindingType || "direct",
        referenceTableName: binding.referenceTableName || null,
      });
    }
  }
  const mappingTables = Object.values(mappingTablesMap);

  const allBoundFields = allMappingSnapshots.flatMap((s) => s.fieldBindings || []);
  const boundSet = new Set(allBoundFields.map((b) => b.sourceField.toLowerCase()));
  const unmappedSourceFields =
    latestSlice?.headerCsv && allMappingSnapshots.length > 0
      ? splitCsvRow(latestSlice.headerCsv)
          .map((h) => h.trim())
          .filter((h) => h && !boundSet.has(h.toLowerCase()))
      : [];

  // Lookup FK bindings for fibers section
  const lookupFkBinds = allMappingSnapshots.flatMap((s) =>
    s.fieldBindings.filter((b) => b.bindingType === "lookup_fk" && b.lookupName)
  );

  const toggleTable = (name: string) => {
    setExpandedTables((prev) => {
      const next = new Set(prev);
      if (next.has(name)) next.delete(name); else next.add(name);
      return next;
    });
  };


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
            {feed?.status === "discarded" && (
              <span className="inline-flex items-center rounded px-2 py-0.5 text-xs font-semibold bg-slate-100 text-slate-500 ring-1 ring-inset ring-slate-200">
                discarded
              </span>
            )}
            {(role === "central_team" || role === "admin") && !loading && feed?.status !== "discarded" && (
              <button
                type="button"
                onClick={() => setDiscardConfirm(true)}
                className="rounded-lg border border-red-300 px-3 py-2 text-xs font-semibold text-red-600 hover:bg-red-50"
              >
                Discard feed
              </button>
            )}
          </div>
        </div>

        {discardConfirm && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
            <div className="w-full max-w-sm rounded-2xl bg-white p-6 shadow-xl space-y-4">
              <h2 className="text-lg font-bold text-slate-900">Discard this feed?</h2>
              <p className="text-sm text-slate-600">
                This will mark <span className="font-semibold">{feed?.label}</span> as discarded. It will no longer appear in the active feeds list. This cannot be undone from the UI.
              </p>
              {error && (
                <div role="alert" className="rounded-lg bg-red-50 border border-red-100 px-3 py-2 text-sm text-red-700">
                  {error}
                </div>
              )}
              <div className="flex justify-end gap-3">
                <button
                  type="button"
                  onClick={() => { setDiscardConfirm(false); setError(null); }}
                  className="rounded-lg border border-outline-variant px-4 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-50"
                  disabled={discarding}
                >
                  Cancel
                </button>
                <button
                  type="button"
                  onClick={() => void handleDiscard()}
                  className="rounded-lg bg-red-600 px-4 py-2 text-sm font-semibold text-white hover:bg-red-700 disabled:opacity-50"
                  disabled={discarding}
                >
                  {discarding ? "Discarding…" : "Discard feed"}
                </button>
              </div>
            </div>
          </div>
        )}

        {error && (
          <div role="alert" className="rounded-xl border border-red-500/20 bg-red-500/10 px-4 py-3 text-sm text-red-700">
            {error}
          </div>
        )}

        {notice && (
          <div role="alert" className="rounded-xl border border-emerald-500/20 bg-emerald-500/10 px-4 py-3 text-sm text-emerald-700">
            {notice}
          </div>
        )}

        {/* Pending approval banner */}
        {!loading && latestSlice?.status === "pending_approval" && (
          <div
            role="alert"
            className="rounded-xl border border-amber-400/30 bg-amber-50 px-4 py-3 text-sm text-amber-800"
          >
            Source data is pending approval — field mapping analysis will be available once the slice is approved.
          </div>
        )}

        {/* Rejection banner + replacement upload */}
        {!loading && latestSlice?.status === "rejected" && (
          <div
            role="alert"
            className="rounded-xl border border-red-400/30 bg-red-50 px-4 py-3 text-sm text-red-800 space-y-3"
          >
            <p className="font-medium">
              Source data was rejected
              {latestSlice.approvalRejectionReason
                ? `: ${latestSlice.approvalRejectionReason}`
                : "."}
            </p>
            <p className="text-xs text-red-700">
              Upload a replacement file to re-enter the approval queue.
            </p>
            <div className="flex items-center gap-3">
              <input
                type="file"
                accept=".csv,.txt"
                onChange={handleReplacementFileChange}
                className="text-xs text-red-800"
              />
              <button
                type="button"
                onClick={handleUploadReplacement}
                disabled={!replacementFile || uploadingReplacement}
                className="rounded-lg bg-red-600 px-3 py-1.5 text-xs font-semibold text-white disabled:opacity-40 hover:bg-red-700"
              >
                {uploadingReplacement ? "Uploading…" : "Upload replacement"}
              </button>
            </div>
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
                        <span
                          className={`inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-xs font-semibold ${
                            latestSlice.status === "approved"
                              ? "bg-emerald-50 text-emerald-700"
                              : latestSlice.status === "rejected"
                                ? "bg-red-50 text-red-700"
                                : "bg-amber-50 text-amber-700"
                          }`}
                        >
                          <span
                            className={`h-1.5 w-1.5 rounded-full ${
                              latestSlice.status === "approved"
                                ? "bg-emerald-600"
                                : latestSlice.status === "rejected"
                                  ? "bg-red-500"
                                  : "bg-amber-500"
                            }`}
                          />
                          {latestSlice.status === "approved"
                            ? "approved"
                            : latestSlice.status === "rejected"
                              ? "rejected"
                              : "pending approval"}
                        </span>
                      </div>
                    </div>

                    {/* Preview Table — only shown after approval */}
                    {latestSlice.status === "approved" && (
                      (latestSlice.previewRows || []).length === 0 ? (
                        <div className="text-xs text-slate-500 italic bg-slate-50 rounded-lg p-3 text-center">
                          No preview available.
                        </div>
                      ) : (
                        <div className="space-y-1.5">
                          <div className="flex items-center justify-between">
                            <div className="text-[10px] font-bold uppercase tracking-wider text-slate-500">
                              {showOriginal ? "Original Data Preview" : "Masked Data Preview"}
                            </div>
                            {(role === "admin" || role === "pm" || role === "central_team") && (
                              <button
                                onClick={handleToggleShowOriginal}
                                className="text-[10px] font-semibold text-primary hover:underline"
                                type="button"
                              >
                                {showOriginal ? "Show masked" : "Show original"}
                              </button>
                            )}
                          </div>
                          <div className="relative max-h-72 max-w-[50vw] overflow-auto border border-outline-variant rounded-lg bg-white">
                            {loadingPreview && (
                              <div className="absolute inset-0 bg-white/70 flex items-center justify-center text-xs font-semibold text-slate-600 z-10">
                                Loading preview...
                              </div>
                            )}
                            <table className="text-left text-[10px] border-collapse font-mono w-full">
                              <thead className="bg-slate-50 border-b border-outline-variant sticky top-0">
                                <tr>
                                  {(latestSlice.headerCsv ? splitCsvRow(latestSlice.headerCsv) : []).map((col, i) => (
                                    <th key={i} className="px-3 py-1.5 font-bold text-slate-700 whitespace-nowrap">{col.trim()}</th>
                                  ))}
                                </tr>
                              </thead>
                              <tbody className="divide-y divide-slate-100">
                                {(latestSlice.previewRows || []).map((rowStr, rowIdx) => {
                                  const rowCells = splitCsvRow(rowStr);
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
                      )
                    )}

                    {/* Analyze with AI Button */}
                    <div className="pt-4 border-t border-slate-100 space-y-2">
                      <button
                        onClick={handleAnalyzeWithAi}
                        disabled={analyzing}
                        className="w-full rounded-md bg-primary px-4 py-3 text-sm font-semibold text-white hover:bg-primary-hover disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
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

                    {/* Quiet re-upload in Slice panel when approved */}
                    {latestSlice?.status === "approved" && (
                      <div className="border-t border-slate-100 pt-4 mt-4 space-y-2">
                        <p className="text-xs text-slate-500 font-medium">Upload a corrected file to replace this slice:</p>
                        <div className="flex flex-col sm:flex-row sm:items-center gap-2">
                          <input
                            type="file"
                            accept=".csv,.txt"
                            onChange={handleReplacementFileChange}
                            className="text-xs text-slate-600 file:mr-2 file:py-1 file:px-2 file:rounded file:border-0 file:text-xs file:font-semibold file:bg-slate-100 file:text-slate-700 hover:file:bg-slate-200"
                          />
                          <button
                            type="button"
                            onClick={handleUploadReplacement}
                            disabled={!replacementFile || uploadingReplacement}
                            className="rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-xs font-semibold text-slate-700 disabled:opacity-40 hover:bg-slate-50 self-start sm:self-auto"
                          >
                            {uploadingReplacement ? "Uploading…" : "Upload new slice"}
                          </button>
                        </div>
                      </div>
                    )}

                    {/* Source DDL section — collapsible, shown at bottom of Slice panel */}
                    {sourceDDL && (
                      <div className="pt-4 border-t border-slate-100 space-y-2">
                        <div className="flex items-center justify-between mb-1">
                          <h4 className="text-sm font-semibold text-slate-700">Source DDL</h4>
                          <button
                            type="button"
                            onClick={() => {
                              navigator.clipboard.writeText(sourceDDL);
                              setNotice("DDL copied to clipboard.");
                            }}
                            className="text-xs text-primary hover:text-primary-hover font-medium"
                          >
                            Copy to clipboard
                          </button>
                        </div>
                        {!sourceDdlExpanded ? (
                          <button
                            type="button"
                            onClick={() => setSourceDdlExpanded(true)}
                            className="w-full text-left text-xs text-slate-500 hover:text-slate-700 font-medium py-1"
                          >
                            Show Source DDL
                          </button>
                        ) : (
                          <div className="space-y-2">
                            <pre className="text-xs bg-slate-950 text-slate-100 rounded-lg p-3 font-mono whitespace-pre-wrap max-h-64 overflow-auto">
                              {sourceDDL}
                            </pre>
                            <button
                              type="button"
                              onClick={() => setSourceDdlExpanded(false)}
                              className="text-xs text-slate-500 hover:text-slate-700 font-medium"
                            >
                              Hide Source DDL
                            </button>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                )}
              </div>

              {session && (
                <div className="mt-4">
                  <UnifiedCommentThread
                    projectId={projectId}
                    feedId={feedId}
                    sliceId={latestSlice?.sourceSliceId}
                    token={session.accessToken}
                  />
                </div>
              )}

            </div>

            {/* Right Column: downstream steps */}
            <div className="space-y-6">

              {/* AI Mapping Hints (central_team only) */}
              {session?.role === "central_team" && (
                <div className="rounded-2xl border border-outline-variant bg-surface-container p-5 shadow-sm space-y-4">
                  <div className="flex items-center justify-between">
                    <label htmlFor="mapping-hints-textarea" className="text-base font-bold text-slate-900">AI Mapping Hints</label>
                    <button
                      type="button"
                      disabled={savingHints}
                      onClick={handleSaveMappingHints}
                      className="rounded bg-slate-100 px-2 py-0.5 text-[10px] font-semibold text-slate-700 hover:bg-slate-200 disabled:opacity-50"
                    >
                      {savingHints ? "Saving..." : "Save Hints"}
                    </button>
                  </div>
                  <textarea
                    id="mapping-hints-textarea"
                    rows={3}
                    value={mappingHints}
                    onChange={(e) => setMappingHints(e.target.value)}
                    placeholder="Provide hints for field matching, formatting, or target columns..."
                    className="w-full rounded-lg border border-slate-200 bg-white p-2.5 font-sans text-xs text-slate-800 placeholder-slate-400 focus:border-primary focus:ring-1 focus:ring-primary focus:outline-none"
                  />
                </div>
              )}

              {/* A. Mapping Tables Accordions */}
              <div className="rounded-2xl border border-outline-variant bg-surface-container p-6 shadow-sm space-y-4">
                <div className="flex items-center justify-between">
                  <div className="space-y-1">
                    <h3 className="text-lg font-bold text-slate-900">Field Mappings</h3>
                    <p className="text-xs text-slate-500">Verify AI extraction classifications across destination tables.</p>
                  </div>
                  {allMappingSnapshots.length > 0 && (
                    <button
                      type="button"
                      onClick={() => router.push(`/projects/${projectId}/feeds/${feedId}/review`)}
                      className="rounded-md border border-outline-variant px-3 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-50"
                    >
                      Go to review page
                    </button>
                  )}
                </div>


                {mappingTables.length === 0 ? (
                  <div className="text-sm text-slate-500">No mapping proposals generated yet.</div>
                ) : (
                  <div className="space-y-2">
                    {mappingTables.map((tbl) => {
                      const tblName = tbl.destinationTableName;
                      const isOpen = expandedTables.has(tblName);
                      const snapshot = allMappingSnapshots.find(s => s.destinationObjectName === tblName);
                      const fiber = fibers.find((f) => f.fiberType === "domain_object" && f.fiberKey === tblName);

                      return (
                        <div key={tblName} className="border border-outline-variant rounded-xl overflow-hidden bg-white">
                          <button
                            type="button"
                            onClick={() => toggleTable(tblName)}
                            className="w-full flex items-center justify-between bg-slate-50 px-4 py-3 hover:bg-slate-100 transition-colors text-left"
                          >
                            <span className="font-mono text-xs font-bold text-slate-700">{tblName}</span>
                            <div className="flex items-center gap-2">
                              {fiber?.status && (
                                <span className={`inline-flex rounded-full border px-2 py-0.5 text-[10px] font-mono uppercase font-semibold ${
                                  fiber.status === "operator_triggered" || fiber.status === "codegen_complete"
                                    ? "border-emerald-500/20 bg-emerald-500/10 text-emerald-700"
                                    : fiber.status === "business_approved"
                                    ? "border-blue-500/20 bg-blue-500/10 text-blue-700"
                                    : fiber.status === "operator_assigned"
                                    ? "border-amber-500/20 bg-amber-500/10 text-amber-700"
                                    : "border-slate-200 bg-slate-50 text-slate-600"
                                }`}>
                                  {fiber.status.replace(/_/g, " ")}
                                </span>
                              )}
                              <span className="text-[10px] bg-slate-200 text-slate-600 px-1.5 py-0.5 rounded">{tbl.bindings.length} fields</span>
                              <svg
                                className={`w-3.5 h-3.5 text-slate-500 transition-transform duration-150 ${isOpen ? "rotate-180" : ""}`}
                                fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}
                              >
                                <path strokeLinecap="round" strokeLinejoin="round" d="m19 9-7 7-7-7" />
                              </svg>
                            </div>
                          </button>
                          {isOpen && (
                            <>
                              <table className="w-full text-left text-xs border-collapse border-t border-outline-variant">
                                <tbody className="divide-y divide-slate-100">
                                  {(snapshot?.fieldBindings || []).map((b, idx) => (
                                    <tr key={idx} className="hover:bg-slate-50/40">
                                      <td className="px-4 py-2 font-mono text-slate-600 w-1/3">{b.sourceField}</td>
                                      <td className="px-4 py-2 font-mono font-bold text-slate-800 w-1/2">
                                        <span>{b.destinationField}</span>
                                      </td>
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

                            </>
                          )}
                        </div>
                      );
                    })}
                  </div>
                )}

                {unmappedSourceFields.length > 0 && (
                  <div className="rounded-xl border border-amber-300 bg-amber-50/50 p-4 space-y-2 mt-4">
                    <p className="text-xs font-semibold text-amber-800">
                      Unmapped source fields — data in these columns will not be migrated
                    </p>
                    <ul className="flex flex-wrap gap-1.5">
                      {unmappedSourceFields.map((col) => (
                        <li key={col} className="font-mono text-[10px] font-bold text-amber-900 bg-amber-100 px-2 py-0.5 rounded">
                          {col}
                        </li>
                      ))}
                    </ul>
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
                  <div className="space-y-4">
                    {lookupFkBinds.map((binding) => {
                      const lName = binding.lookupName!;
                      const refTable = binding.referenceTableName || "unknown_ref";
                      const fiber = fibers.find((f) => f.fiberType === "lookup" && f.fiberKey === lName);
                      const fiberId = fiber?.fiberId || "";
                      const lookupMap = lookupMaps.find((m) => m.lookupName === lName);

                      const defaultSourceText = lookupMap?.sourceValueMap
                        ? Object.keys(lookupMap.sourceValueMap).join("\n")
                        : fiber?.proposedMappings
                        ? Array.from(new Set(fiber.proposedMappings.map((pm) => pm.sourceValue).filter(Boolean))).join("\n")
                        : "";

                      const defaultDestText = lookupMap?.destinationTable && lookupMap.destinationTable.length > 0
                        ? (() => {
                            const keys = Array.from(new Set(lookupMap.destinationTable.flatMap((r) => Object.keys(r))));
                            const header = keys.join(",");
                            const rows = lookupMap.destinationTable.map((r) => keys.map((k) => {
                              const val = r[k];
                              if (val === null || val === undefined) return "";
                              const str = String(val);
                              return str.includes(",") || str.includes('"') || str.includes("\n")
                                ? `"${str.replace(/"/g, '""')}"`
                                : str;
                            }).join(","));
                            return [header, ...rows].join("\n");
                          })()
                        : "";

                      const userDraft = lookupDrafts[lName];
                      const draft = {
                        sourceText: userDraft?.sourceText ?? defaultSourceText,
                        destText: userDraft?.destText ?? defaultDestText,
                        analyzing: userDraft?.analyzing ?? false,
                        error: userDraft?.error ?? null,
                      };

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
                        draft.analyzing;

                      const isLookupOpen = expandedLookups.has(lName);
                      return (
                        <div key={lName} className="border border-outline-variant rounded-xl bg-white shadow-sm">
                          <button
                            type="button"
                            onClick={() => setExpandedLookups((prev) => {
                              const next = new Set(prev);
                              if (next.has(lName)) next.delete(lName); else next.add(lName);
                              return next;
                            })}
                            className="flex w-full items-center justify-between p-4 text-left"
                          >
                            <span className="text-sm font-bold text-slate-800">{lName}</span>
                            <div className="flex items-center gap-2">
                              {fiber?.status && (
                                <span className={`inline-flex rounded-full border px-2 py-0.5 text-[10px] font-mono uppercase font-semibold ${
                                  fiber.status === "operator_triggered" || fiber.status === "codegen_complete"
                                    ? "border-emerald-500/20 bg-emerald-500/10 text-emerald-700"
                                    : fiber.status === "business_approved"
                                    ? "border-blue-500/20 bg-blue-500/10 text-blue-700"
                                    : fiber.status === "operator_assigned"
                                    ? "border-amber-500/20 bg-amber-500/10 text-amber-700"
                                    : "border-slate-200 bg-slate-50 text-slate-600"
                                }`}>
                                  {fiber.status.replace(/_/g, " ")}
                                </span>
                              )}
                              <span className="text-[10px] bg-amber-500/10 text-amber-700 px-1.5 py-0.5 rounded font-mono">
                                ref: {refTable}
                              </span>
                              {lookupMap?.unmappedRowCount != null && lookupMap.unmappedRowCount > 0 && (
                                <span className="text-[10px] bg-amber-100 text-amber-700 px-1.5 py-0.5 rounded font-mono font-bold">
                                  ⚠️ {lookupMap.unmappedRowCount} unmapped
                                </span>
                              )}
                              <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className={`w-3.5 h-3.5 text-slate-500 transition-transform duration-150 ${isLookupOpen ? "rotate-180" : ""}`}>
                                <path fillRule="evenodd" d="M5.23 7.21a.75.75 0 011.06.02L10 11.168l3.71-3.938a.75.75 0 111.08 1.04l-4.25 4.5a.75.75 0 01-1.08 0l-4.25-4.5a.75.75 0 01.02-1.06z" clipRule="evenodd" />
                              </svg>
                            </div>
                          </button>

                          {isLookupOpen && (
                            <div className="px-4 pb-4 space-y-3">
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

                              {fiber?.proposedMappings && fiber.proposedMappings.length > 0 && (
                                <div className="mt-4 pt-4 border-t border-slate-100 space-y-2">
                                  <div className="text-[10px] font-bold uppercase tracking-wider text-slate-500">
                                    AI Proposed Mappings ({fiber.proposedMappings.length})
                                  </div>
                                  <div className="overflow-hidden rounded-lg border border-slate-200 bg-white">
                                    <table className="w-full border-collapse text-left text-xs">
                                      <thead>
                                        <tr className="border-b border-slate-100 bg-slate-50 text-slate-500 font-semibold">
                                          <th className="px-3 py-2">Destination Value (ID)</th>
                                          <th className="px-3 py-2">Mapped Source Value</th>
                                          <th className="px-3 py-2 text-right">Confidence</th>
                                        </tr>
                                      </thead>
                                      <tbody className="divide-y divide-slate-100 bg-white text-slate-900">
                                        {fiber.proposedMappings.map((pm, idx) => (
                                          <tr key={idx} className="hover:bg-slate-50/50">
                                            <td className="px-3 py-2">
                                              {pm.destRow && (() => {
                                                const dr = pm.destRow;
                                                const id = dr.id || "—";
                                                const extractLabel = (r: any) => {
                                                  for (const key of ["label", "name", "description", "desc", "val", "value", "display"]) {
                                                    if (r[key] != null && typeof r[key] === "string" && r[key].trim()) return r[key].trim();
                                                  }
                                                  for (const [key, val] of Object.entries(r)) {
                                                    const kl = key.toLowerCase();
                                                    if (["name", "label", "desc", "display"].some(sub => kl.includes(sub)) && typeof val === "string" && val.trim()) return val.trim();
                                                  }
                                                  return "";
                                                };
                                                const label = extractLabel(dr);
                                                const labelText = label && label !== id ? label : undefined;
                                                return labelText != null ? (
                                                  <>
                                                    {labelText}{" "}
                                                    <span className="text-slate-400">({id})</span>
                                                  </>
                                                ) : (
                                                  <span className="text-slate-800 font-mono text-[10px]">{id}</span>
                                                );
                                              })()}
                                            </td>
                                            <td className="px-3 py-2 font-medium">{pm.sourceValue}</td>
                                            <td className="px-3 py-2 text-right font-semibold">
                                              {pm.confidenceScore != null ? (
                                                <span className={
                                                  pm.confidenceScore >= 0.8
                                                    ? "text-emerald-600"
                                                    : pm.confidenceScore >= 0.5
                                                    ? "text-amber-600"
                                                    : "text-red-600"
                                                }>
                                                  {Math.round(pm.confidenceScore * 100)}%
                                                </span>
                                              ) : (
                                                "—"
                                              )}
                                            </td>
                                          </tr>
                                        ))}
                                      </tbody>
                                    </table>
                                  </div>
                                </div>
                              )}

                            </div>
                          )}
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>

              {/* Consolidated AI Logs for the entire Feed */}
              {(role === "central_team" || role === "admin") && (
                <div className="mt-8 space-y-4">
                  <h2 className="text-lg font-bold text-slate-800 border-b border-outline-variant pb-2">
                    Project AI Trace & Reasoning
                  </h2>
                  <AiLogViewer
                    token={session?.accessToken}
                    projectId={projectId}
                    feature="feed_mapping"
                    artifactId={feedId}
                    canViewLogs={true}
                  />
                </div>
              )}
            </div>
          </div>
        )}
      </section>
    </main>
  );
}
