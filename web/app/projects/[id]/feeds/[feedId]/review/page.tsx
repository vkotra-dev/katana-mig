"use client";

import { use, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Topbar } from "../../../../../../components/Topbar";
import {
  getMappingSnapshot,
  approveMappingSnapshot,
  rejectMappingSnapshot,
  type MappingReviewRecord,
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

  const [mappingSnapshot, setMappingSnapshot] = useState<MappingReviewRecord | null>(null);
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
      const [mappingData, mapsData] = await Promise.all([
        getMappingSnapshot(token, projectId, feedId),
        listLookupValueMaps(token, projectId, feedId),
      ]);
      setMappingSnapshot(mappingData);
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
      const next = await approveMappingSnapshot(session.accessToken, projectId, feedId);
      setMappingSnapshot(next);
      setNotice("Mapping snapshot approved successfully.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to approve mapping snapshot.");
    } finally {
      setLoading(false);
    }
  };

  const handleRequestRevision = async (comment: string) => {
    if (!session) return;
    setLoading(true);
    try {
      const next = await rejectMappingSnapshot(session.accessToken, projectId, feedId, comment);
      setMappingSnapshot(next);
      setNotice(`Revision requested: "${comment}"`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to submit revision request.");
    } finally {
      setLoading(false);
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

  // Only business_user has decision controls in this version
  const showControls = role === "business_user" && mappingSnapshot?.status === "draft";

  return (
    <main className="flex min-h-screen flex-col bg-surface text-slate-800">
      <Topbar role={role} />
      
      <section className="mx-auto w-full max-w-[1200px] flex-1 px-6 py-6 space-y-6">
        <div className="flex items-center justify-between">
          <button
            onClick={() => {
              if (role === "business_user") {
                router.push(`/projects/${projectId}?tab=feeds`);
              } else {
                router.push(`/projects/${projectId}/feeds/${feedId}`);
              }
            }}
            className="rounded-lg border border-outline-variant bg-surface-container px-3 py-2 text-sm font-semibold text-slate-700 hover:bg-outline-variant"
            type="button"
          >
            Back to {role === "business_user" ? "project" : "workspace"}
          </button>
          
          <div className="flex flex-col items-end">
            <h1 className="text-xl font-bold text-slate-900">Review Mappings & Lookups</h1>
            {mappingSnapshot && (
              <span className={`mt-1 inline-flex rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider ${
                mappingSnapshot.status === "approved"
                  ? "bg-emerald-100 text-emerald-700"
                  : mappingSnapshot.status === "rejected"
                  ? "bg-red-100 text-red-700"
                  : "bg-amber-100 text-amber-700"
              }`}>
                {mappingSnapshot.status}
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
            {mappingSnapshot ? (
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
