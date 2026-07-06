"use client";

import { use, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Topbar } from "../../../../../../components/Topbar";
import {
  getAllApprovedMappingSnapshots,
  approveMappingSnapshot,
  rejectMappingSnapshot,
  type MappingSnapshotRecord,
} from "../../../../../../lib/mapping-api";
import {
  listLookupValueMaps,
  type LookupValueMapRecord,
} from "../../../../../../lib/lookup-api";
import { loadUiSession, type SessionRole, type UiSession } from "../../../../../../lib/session";
import { ReviewGrid, type MappingTableRecord, type LookupValueGroup } from "../../../../../../components/projects/ReviewGrid";

export default function ReviewPage({ params }: { params: Promise<{ id: string; feedId: string }> }) {
  const router = useRouter();
  const { id: projectId, feedId } = use(params);

  const [session, setSession] = useState<UiSession | null>(null);
  const [role, setRole] = useState<SessionRole>("read_only_auditor");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const [mappingSnapshots, setMappingSnapshots] = useState<MappingSnapshotRecord[]>([]);
  const [lookupMaps, setLookupMaps] = useState<LookupValueMapRecord[]>([]);

  useEffect(() => {
    const s = loadUiSession();
    setSession(s);
    if (s) {
      setRole(s.role);
    }
  }, []);

  const loadData = async (token: string) => {
    try {
      const [snapshotsData, mapsData] = await Promise.all([
        getAllApprovedMappingSnapshots(token, projectId, feedId, true),
        listLookupValueMaps(token, projectId, feedId),
      ]);
      setMappingSnapshots(snapshotsData);
      setLookupMaps(mapsData);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to load mapping review data.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (session) {
      void loadData(session.accessToken);
    }
  }, [session, projectId, feedId]);

  const handleApprove = async () => {
    if (!session) return;
    setLoading(true);
    try {
      await approveMappingSnapshot(session.accessToken, projectId, feedId);
      setNotice("Mapping snapshot approved successfully.");
      await loadData(session.accessToken);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to approve mapping snapshot.");
      setLoading(false);
    }
  };

  const handleRequestRevision = async (comment: string) => {
    if (!session) return;
    setLoading(true);
    try {
      await rejectMappingSnapshot(session.accessToken, projectId, feedId, comment);
      setNotice(`Revision requested: "${comment}"`);
      await loadData(session.accessToken);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to submit revision request.");
      setLoading(false);
    }
  };

  // Build props for ReviewGrid
  const mappingTablesMap: Record<string, MappingTableRecord> = {};
  for (const snapshot of mappingSnapshots) {
    const tblName = snapshot.destinationObjectName;
    if (!mappingTablesMap[tblName]) {
      mappingTablesMap[tblName] = {
        destinationTableName: tblName,
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

  const lookupGroups: LookupValueGroup[] = [];
  const seenLookups = new Set<string>();
  for (const snapshot of mappingSnapshots) {
    const refMap = Object.fromEntries(
      (snapshot.lookupTableReferences ?? []).map((r) => [r.lookupName, r.destinationTableName])
    );
    for (const binding of snapshot.fieldBindings) {
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

  const representativeSnapshot = mappingSnapshots[0] || null;

  const aggregateStatus = mappingSnapshots.length === 0
    ? null
    : mappingSnapshots.every(s => s.status === "approved")
    ? "approved"
    : mappingSnapshots.some(s => s.status === "rejected")
    ? "rejected"
    : "draft";

  // Only project_stakeholder has decision controls in this version
  const showControls = role === "project_stakeholder" && mappingSnapshots.some(s => s.status === "draft");

  return (
    <main className="flex min-h-screen flex-col bg-surface text-slate-800">
      <Topbar role={role} />
      
      <section className="mx-auto w-full max-w-[1200px] flex-1 px-6 py-6 space-y-6">
        <div className="flex items-center justify-between">
          <button
            onClick={() => {
              if (role === "project_stakeholder") {
                router.push(`/projects/${projectId}?tab=feeds`);
              } else {
                router.push(`/projects/${projectId}/feeds/${feedId}`);
              }
            }}
            className="rounded-lg border border-outline-variant bg-surface-container px-3 py-2 text-sm font-semibold text-slate-700 hover:bg-outline-variant"
            type="button"
          >
            Back to {role === "project_stakeholder" ? "project" : "workspace"}
          </button>
          
          <div className="flex flex-col items-end">
            <h1 className="text-xl font-bold text-slate-900">Review Mappings & Lookups</h1>
            {aggregateStatus && (
              <span className={`mt-1 inline-flex rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider ${
                aggregateStatus === "approved"
                  ? "bg-emerald-100 text-emerald-700"
                  : aggregateStatus === "rejected"
                  ? "bg-red-100 text-red-700"
                  : "bg-amber-100 text-amber-700"
              }`}>
                {aggregateStatus}
              </span>
            )}
          </div>
        </div>

        {error && (
          <div role="alert" className="rounded-xl border border-red-500/20 bg-red-500/10 px-4 py-3 text-sm text-red-700">
            {error}
          </div>
        )}

        {notice && (
          <div className="rounded-xl border border-primary/20 bg-primary/5 px-4 py-3 text-sm text-primary">
            {notice}
          </div>
        )}

        {loading ? (
          <div className="rounded-2xl border border-outline-variant bg-surface-container p-8 text-sm text-slate-600">
            Loading review grids...
          </div>
        ) : (
          <div className="bg-surface-container border border-outline-variant rounded-2xl p-6 shadow-sm">
            {representativeSnapshot ? (
              <ReviewGrid
                mappingTables={mappingTables}
                lookupGroups={lookupGroups}
                onApprove={showControls ? handleApprove : undefined}
                onRequestRevision={showControls ? handleRequestRevision : undefined}
              />
            ) : (
              <div className="text-sm text-slate-500 text-center py-12">
                No mapping snapshot has been proposed yet for this feed.
              </div>
            )}
          </div>
        )}
      </section>
    </main>
  );
}
