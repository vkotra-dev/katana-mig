"use client";

import { use, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Topbar } from "../../../../../../components/Topbar";
import {
  getAllApprovedMappingSnapshots,
  approveMappingSnapshot,
  requestRevision,
  patchMappingSnapshot,
  rejectMappingSnapshot,
  unapproveMappingSnapshot,
  type MappingSnapshotRecord,
} from "../../../../../../lib/mapping-api";
import {
  listLookupValueMaps,
  patchLookupValueMap,
  type LookupValueMapRecord,
} from "../../../../../../lib/lookup-api";
import { listFeedSlices, getFeedContract, listFeedFibers, type FeedContractRecord } from "../../../../../../lib/feeds-api";
import { loadUiSession, type SessionRole, type UiSession } from "../../../../../../lib/session";
import { ReviewGrid, type MappingTableRecord, type LookupValueGroup } from "../../../../../../components/projects/ReviewGrid";
import { splitCsvRow } from "../../../../../../lib/csv-utils";
import {
  getSignOffStatus,
  signBinding,
  unsignBinding,
  signLookup,
  unsignLookup,
  pushForReview,
  pokeReviewer,
  type SignOffStatusRecord,
} from "../../../../../../lib/sign-offs-api";
import { UnifiedCommentThread } from "../../../../../../components/feeds/UnifiedCommentThread";
import { type FeedSliceRecord } from "../../../../../../lib/feeds-api";

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
  const [sampleValues, setSampleValues] = useState<Record<string, string[]>>({});
  const [allSourceColumns, setAllSourceColumns] = useState<string[]>([]);
  const [signOffStatus, setSignOffStatus] = useState<SignOffStatusRecord | null>(null);
  const [approvedSlice, setApprovedSlice] = useState<FeedSliceRecord | null>(null);
  const [latestSliceId, setLatestSliceId] = useState<string | undefined>(undefined);
  const [feed, setFeed] = useState<FeedContractRecord | null>(null);
  const [fibers, setFibers] = useState<any[]>([]);

  useEffect(() => {
    const s = loadUiSession();
    setSession(s);
    if (s) {
      setRole(s.role);
    }
  }, []);

  const loadData = async (token: string) => {
    try {
      const [snapshotsData, mapsData, slicesData, feedData, fibersData] = await Promise.all([
        getAllApprovedMappingSnapshots(token, projectId, feedId, true),
        listLookupValueMaps(token, projectId, feedId),
        listFeedSlices(token, projectId, feedId),
        getFeedContract(token, projectId, feedId),
        listFeedFibers(token, projectId, feedId),
      ]);
      setMappingSnapshots(snapshotsData);
      setLookupMaps(mapsData);
      setFeed(feedData);
      setFibers(fibersData);

      // Fetch sign-off status independently so a failure doesn't break the whole page
      getSignOffStatus(token, projectId, feedId)
        .then(setSignOffStatus)
        .catch(() => setSignOffStatus(null));

      const approvedSlice = slicesData
        .filter((s) => s.status === "approved")
        .sort((a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime())[0] ?? null;

      setApprovedSlice(approvedSlice);

      const latest = slicesData
        .sort((a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime())[0] ?? null;
      setLatestSliceId(latest?.sourceSliceId);

      if (approvedSlice?.headerCsv) {
        const headers = splitCsvRow(approvedSlice.headerCsv);
        setAllSourceColumns(headers);

        if (approvedSlice.previewRows.length > 0) {
          const parsed: Record<string, string[]> = {};

          for (const rowCsv of approvedSlice.previewRows.slice(0, 5)) {
            const cells = splitCsvRow(rowCsv);
            headers.forEach((col, i) => {
              const val = (cells[i] ?? "").trim();
              if (val) {
                const key = col.toLowerCase();
                if (!parsed[key]) parsed[key] = [];
                if (parsed[key].length < 3) parsed[key].push(val);
              }
            });
          }
          setSampleValues(parsed);
        }
      }
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
      await requestRevision(session.accessToken, projectId, feedId, comment);
      setNotice(`Revision requested: "${comment}"`);
      await loadData(session.accessToken);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to submit revision request.");
      setLoading(false);
    }
  };

  const handleRevertToDraft = async () => {
    if (!session) return;
    setLoading(true);
    setError(null);
    setNotice(null);
    try {
      await unapproveMappingSnapshot(session.accessToken, projectId, feedId);
      setNotice("Mapping snapshot reverted back to draft.");
      await loadData(session.accessToken);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to revert mapping snapshot back to draft.");
      setLoading(false);
    }
  };

  const handleReject = async () => {
    if (!session) return;
    setLoading(true);
    setError(null);
    setNotice(null);
    try {
      await rejectMappingSnapshot(session.accessToken, projectId, feedId);
      setNotice("Mapping snapshot rejected.");
      await loadData(session.accessToken);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to reject mapping snapshot.");
      setLoading(false);
    }
  };

  const handleSignBinding = async (tableName: string, sourceField: string, destField: string) => {
    if (!session) return;
    try {
      const updated = await signBinding(session.accessToken, projectId, feedId, tableName, sourceField, destField);
      setSignOffStatus(updated);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to sign field binding.");
    }
  };

  const handleUnsignBinding = async (tableName: string, sourceField: string, destField: string) => {
    if (!session) return;
    try {
      const updated = await unsignBinding(session.accessToken, projectId, feedId, tableName, sourceField, destField);
      setSignOffStatus(updated);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to unsign field binding.");
    }
  };

  const handleSignLookup = async (lookupValueMapId: string) => {
    if (!session) return;
    try {
      const updated = await signLookup(session.accessToken, projectId, feedId, lookupValueMapId);
      setSignOffStatus(updated);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to sign lookup mapping.");
    }
  };

  const handleUnsignLookup = async (lookupValueMapId: string) => {
    if (!session) return;
    try {
      const updated = await unsignLookup(session.accessToken, projectId, feedId, lookupValueMapId);
      setSignOffStatus(updated);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to unsign lookup mapping.");
    }
  };

  const handleAddSourceValue = async (lookupValueMapId: string, destId: string, sourceValue: string) => {
    if (!session) return;
    try {
      await patchLookupValueMap(session.accessToken, projectId, lookupValueMapId, {
        addSourceValue: { destId, sourceValue },
      });
      await loadData(session.accessToken);
      setNotice(`Added source value "${sourceValue}" to ${destId}.`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to add source value.");
    }
  };

  const handleRemoveSourceValue = async (lookupValueMapId: string, destId: string, sourceValue: string) => {
    if (!session) return;
    try {
      await patchLookupValueMap(session.accessToken, projectId, lookupValueMapId, {
        removeSourceValue: { destId, sourceValue },
      });
      await loadData(session.accessToken);
      setNotice(`Removed source value "${sourceValue}" from ${destId}.`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to remove source value.");
    }
  };

  // Wrapper that maps lookupName → lookupValueMapId
  const handleAddSourceByLookup = async (lookupName: string, destId: string, sourceValue: string) => {
    const map = lookupMaps.find(m => m.lookupName === lookupName);
    if (map?.lookupValueMapId) {
      await handleAddSourceValue(map.lookupValueMapId, destId, sourceValue);
    }
  };

  const handleRemoveSourceByLookup = async (lookupName: string, destId: string, sourceValue: string) => {
    const map = lookupMaps.find(m => m.lookupName === lookupName);
    if (map?.lookupValueMapId) {
      await handleRemoveSourceValue(map.lookupValueMapId, destId, sourceValue);
    }
  };

  const handleDestinationFieldChange = async (tableName: string, sourceField: string, oldDest: string, newDest: string) => {
    setError(null);
    // 1. Instantly update the input field value in local state for zero lag
    setMappingSnapshots((prev) =>
      prev.map((snapshot) => {
        if (snapshot.destinationObjectName !== tableName) return snapshot;
        return {
          ...snapshot,
          fieldBindings: snapshot.fieldBindings.map((binding) => {
            if (binding.sourceField !== sourceField || binding.destinationField !== oldDest) return binding;
            return { ...binding, destinationField: newDest };
          }),
        };
      })
    );

    // 2. Commit the patched bindings in the background
    if (!session) return;
    try {
      const targetSnapshot = mappingSnapshots.find((s) => s.destinationObjectName === tableName);
      if (!targetSnapshot) return;

      const updatedBindings = targetSnapshot.fieldBindings.map((binding) => {
        if (binding.sourceField === sourceField && binding.destinationField === oldDest) {
          return { sourceField: binding.sourceField, destinationField: newDest, lookupName: binding.lookupName };
        }
        return { sourceField: binding.sourceField, destinationField: binding.destinationField, lookupName: binding.lookupName };
      });

      await patchMappingSnapshot(session.accessToken, projectId, feedId, updatedBindings, tableName);

      // Sign-off status automatically resets in the DB for modified fields, fetch the new status
      const updated = await getSignOffStatus(session.accessToken, projectId, feedId);
      setSignOffStatus(updated);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update destination field binding.");
    }
  };

  const handleAddBinding = async (tableName: string, sourceField: string, availableFields: string[]) => {
    // Filter out already-mapped destination fields
    const targetSnapshot = mappingSnapshots.find((s) => s.destinationObjectName === tableName);
    if (!targetSnapshot) return;

    const existingDests = new Set(targetSnapshot.fieldBindings.map(b => b.destinationField));
    const available = availableFields.find(d => d && !existingDests.has(d));
    if (!available) {
      setError("All destination fields are already mapped for this source field.");
      return;
    }

    // Optimistically add the binding to local state
    setMappingSnapshots((prev) =>
      prev.map((snapshot) => {
        if (snapshot.destinationObjectName !== tableName) return snapshot;
        return {
          ...snapshot,
          fieldBindings: [
            ...snapshot.fieldBindings,
            { sourceField, destinationField: available, bindingType: "direct", lookupName: null }
          ],
        };
      })
    );

    // Commit in the background
    if (!session) return;
    try {
      // Include the newly added binding in the payload (use the target snapshot from local state,
      // which is the same copy read by the optimistic update above — avoids stale closure)
      const updatedBindings = [...targetSnapshot.fieldBindings, { sourceField, destinationField: available, lookupName: null }];
      await patchMappingSnapshot(session.accessToken, projectId, feedId, updatedBindings, tableName);
      const updated = await getSignOffStatus(session.accessToken, projectId, feedId);
      setSignOffStatus(updated);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to add binding.");
    }
  };

  const handleRemoveBinding = async (tableName: string, sourceField: string, destinationField: string) => {
    const targetSnapshot = mappingSnapshots.find((s) => s.destinationObjectName === tableName);
    if (!targetSnapshot) return;

    // Optimistically remove the binding from local state
    setMappingSnapshots((prev) =>
      prev.map((snapshot) => {
        if (snapshot.destinationObjectName !== tableName) return snapshot;
        return {
          ...snapshot,
          fieldBindings: snapshot.fieldBindings.filter(
            (b) => !(b.sourceField === sourceField && b.destinationField === destinationField)
          ),
        };
      })
    );

    // Commit in the background — build the payload directly from the pre-update targetSnapshot
    // closure captured above, same pattern as handleAddBinding, avoids any stale-closure race.
    if (!session) return;
    try {
      const updatedBindings = targetSnapshot.fieldBindings
        .filter((b) => !(b.sourceField === sourceField && b.destinationField === destinationField))
        .map((b) => ({ sourceField: b.sourceField, destinationField: b.destinationField, lookupName: b.lookupName }));
      await patchMappingSnapshot(session.accessToken, projectId, feedId, updatedBindings, tableName);
      const updated = await getSignOffStatus(session.accessToken, projectId, feedId);
      setSignOffStatus(updated);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to remove binding.");
    }
  };

  const handleToggleSourceField = async (tableName: string, sourceField: string, dropped: boolean) => {
    const targetSnapshot = mappingSnapshots.find((s) => s.destinationObjectName === tableName);
    if (!targetSnapshot) return;

    // Optimistically flip the dropped flag on every binding for this source field
    setMappingSnapshots((prev) =>
      prev.map((snapshot) => {
        if (snapshot.destinationObjectName !== tableName) return snapshot;
        return {
          ...snapshot,
          fieldBindings: snapshot.fieldBindings.map((b) =>
            b.sourceField === sourceField ? { ...b, dropped } : b
          ),
        };
      })
    );

    if (!session) return;
    try {
      // Send the full bindings list (not filtered) so sign-off preservation works
      const updatedBindings = targetSnapshot.fieldBindings.map((b) => ({
        sourceField: b.sourceField,
        destinationField: b.destinationField,
        lookupName: b.lookupName,
        dropped: b.sourceField === sourceField ? dropped : b.dropped ?? false,
      }));
      await patchMappingSnapshot(session.accessToken, projectId, feedId, updatedBindings, tableName);
      const updated = await getSignOffStatus(session.accessToken, projectId, feedId);
      setSignOffStatus(updated);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to toggle source field.");
    }
  };

  const handlePushForReview = async () => {
    if (!session) return;
    setLoading(true);
    try {
      const updated = await pushForReview(session.accessToken, projectId, feedId);
      setSignOffStatus(updated);
      setNotice("Mappings successfully pushed to review state!");
      await loadData(session.accessToken);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to push mappings for review.");
      setLoading(false);
    }
  };

  const handlePoke = async () => {
    if (!session || !signOffStatus?.currentBallRole) return;
    try {
      await pokeReviewer(session.accessToken, projectId, feedId, signOffStatus.currentBallRole);
      setNotice(`Sent review poke notification to ${signOffStatus.currentBallRole === "central_team" ? "Central Team" : "Project Stakeholders"}.`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to send poke notification.");
    }
  };

  // Build props for ReviewGrid
  const mappingTablesMap: Record<string, MappingTableRecord> = {};
  for (const snapshot of mappingSnapshots) {
    const tblName = snapshot.destinationObjectName;
    const fiber = fibers.find((f) => f.fiberType === "domain_object" && f.fiberKey === tblName);
    if (!mappingTablesMap[tblName]) {
      mappingTablesMap[tblName] = {
        destinationTableName: tblName,
        destinationFields: snapshot.destinationFields || [],
        fiberStatus: fiber?.status,
        bindings: [],
      };
    }
    for (const binding of snapshot.fieldBindings) {
      mappingTablesMap[tblName].bindings.push({
        sourceField: binding.sourceField,
        destinationField: binding.destinationField,
        bindingType: binding.bindingType || "direct",
        referenceTableName: binding.referenceTableName || null,
        dropped: binding.dropped ?? false,
      });
    }
  }
  const mappingTables = Object.values(mappingTablesMap);

  const lookupGroups: LookupValueGroup[] = [];
  const seenLookups = new Set<string>();
  for (const snapshot of mappingSnapshots) {
    for (const binding of snapshot.fieldBindings) {
      if (binding.lookupName && !seenLookups.has(binding.lookupName)) {
        seenLookups.add(binding.lookupName);
        const refTable = binding.referenceTableName || "unknown_ref";
        const latestMap = lookupMaps.find((m) => m.lookupName === binding.lookupName);
        const fiber = fibers.find(f => f.fiberKey === binding.lookupName);

        // Build destinationMappings from backend-provided data
        const isConfirmed = latestMap?.status === "approved" || (
          signOffStatus && latestMap &&
          signOffStatus.lookups[latestMap.lookupValueMapId]?.centralTeam.signed &&
          signOffStatus.lookups[latestMap.lookupValueMapId]?.projectStakeholder.signed
        );

        let destinationMappings = latestMap?.destinationMappings ?? [];
        // Repair stale destinationMappings where destLabel is empty (e.g. created before dest_label fix)
        const hasEmptyDestLabels = destinationMappings.length > 0 && destinationMappings.every(g => !g.destLabel);

        // For approved maps without destinationMappings (legacy), fall back to pairs
        if (destinationMappings.length === 0 || hasEmptyDestLabels) {
          const extractDestLabel = (row: Record<string, unknown>): string => {
            for (const key of ["label", "name", "description", "desc", "val", "value", "display"]) {
              const v = row[key];
              if (typeof v === "string" && v.trim()) return v.trim();
            }
            for (const [k, v] of Object.entries(row)) {
              const kl = k.toLowerCase();
              if (["label", "name", "desc", "display"].some((s) => kl.includes(s)) && typeof v === "string" && v.trim())
                return v.trim();
            }
            return "";
          };

          if (latestMap) {
            // Fallback to sourceValueMap + destinationTable from lookup_value_maps
            // When source_value_map values don't match destinationTable IDs (e.g. stale UUIDs),
            // fall back to the fiber's proposed_mappings which has the correct destRow data.
            const fallbackGroups = Object.entries(latestMap.sourceValueMap)
              .filter(([, destId]) => destId && destId.trim())
              .map(([srcVal, destId]) => {
                const destRow = latestMap.destinationTable.find((row: Record<string, unknown>) => {
                  const rowId = (row as any).id ?? (row as any).destination_id;
                  return String(rowId ?? "") === String(destId);
                });
                const destLabel = destRow ? extractDestLabel(destRow) : "";
                return {
                  destId,
                  destLabel,
                  destRow: destRow || {},
                  sourceValues: [srcVal],
                  status: isConfirmed ? "approved" : "draft",
                };
              });

            // If none of the destIds matched destinationTable rows, try fiber proposed_mappings
            const unmatchedCount = fallbackGroups.filter(g => !g.destLabel && g.destId !== "0" && !latestMap.destinationTable.some((r: Record<string, unknown>) => String((r as any).id ?? (r as any).destination_id) === g.destId)).length;
            if (unmatchedCount > 0 && unmatchedCount === fallbackGroups.length && fallbackGroups.length > 0 && fiber?.proposedMappings) {
              // Use fiber proposed_mappings as the source of truth
              const srcToDest = fiber.proposedMappings.reduce((acc, pm) => {
                const sv = pm.sourceValue ?? "";
                const dr = pm.destRow ?? {};
                const did = pm.destEntryId ?? String((dr as any).id ?? (dr as any).destination_id ?? "");
                if (sv && did) {
                  if (!acc[did]) acc[did] = { destId: did, destRow: dr, sourceValues: [] };
                  acc[did].sourceValues.push(sv);
                }
                return acc;
              }, {} as Record<string, { destId: string; destRow: Record<string, unknown>; sourceValues: string[] }>);
              destinationMappings = Object.values(srcToDest).map(({ destId, destRow, sourceValues }) => ({
                destId,
                destLabel: extractDestLabel(destRow),
                destRow,
                sourceValues,
                status: isConfirmed ? "approved" : "draft",
              }));
            } else {
              destinationMappings = fallbackGroups;
            }
          } else if (fiber?.proposedMappings) {
            // Fallback to fiber proposed_mappings when no lookup_value_maps record exists
            const srcToDest = fiber.proposedMappings.reduce((acc, pm) => {
              const sv = pm.sourceValue ?? "";
              const dr = pm.destRow ?? {};
              const did = pm.destEntryId ?? String((dr as any).id ?? (dr as any).destination_id ?? "");
              if (sv && did) {
                if (!acc[did]) acc[did] = { destId: did, destRow: dr, sourceValues: [] };
                acc[did].sourceValues.push(sv);
              }
              return acc;
            }, {} as Record<string, { destId: string; destRow: Record<string, unknown>; sourceValues: string[] }>);
            destinationMappings = Object.values(srcToDest).map(({ destId, destRow, sourceValues }) => ({
              destId,
              destLabel: extractDestLabel(destRow),
              destRow,
              sourceValues,
              status: isConfirmed ? "approved" : "draft",
            }));
          }
        }

        lookupGroups.push({
          lookupName: binding.lookupName,
          referenceTableName: refTable,
          lookupValueMapId: latestMap?.lookupValueMapId,
          unmappedRowCount: latestMap?.unmappedRowCount,
          unmappedSourceValues: latestMap?.unmappedSourceValues,
          fiberStatus: fiber?.status,
          destinationTable: latestMap?.destinationTable || [],
          destinationMappings,
        });
      }
    }
  }

  const representativeSnapshot = mappingSnapshots[0] || null;

  const aggregateStatus = mappingSnapshots.length === 0
    ? null
    : mappingSnapshots.every(s => s.status === "approved")
    ? "approved"
    : "draft";

  // Check editing and notification controls
  const isAnyDraft = mappingSnapshots.some(s => s.status === "draft");
  const editingEnabled = signOffStatus?.currentBallRole === role && isAnyDraft;
  const isActorSignOffComplete = (() => {
    if (!signOffStatus || !role) return false;
    const rKey = role === "project_stakeholder" ? "projectStakeholder" : "centralTeam";
    for (const table of Object.values(signOffStatus.bindings)) {
      for (const binding of Object.values(table)) {
        if (!binding || !binding[rKey]?.signed) return false;
      }
    }
    for (const lookup of Object.values(signOffStatus.lookups)) {
      if (!lookup || !lookup[rKey]?.signed) return false;
    }
    return true;
  })();
  const showStakeholderActionButtons = role === "project_stakeholder" && isAnyDraft;
  const showPokeButton = (role === "pm" || role === "admin") && isAnyDraft;

  return (
    <main className="flex min-h-screen flex-col bg-surface text-slate-800">
      <Topbar role={role} />

      <section className="mx-auto w-full max-w-[1400px] flex-1 px-6 py-6 space-y-6">
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
            <h1 className="text-xl font-bold text-slate-900">
              Review Mappings & Lookups{feed ? `: ${feed.label}` : ""}
            </h1>
            {aggregateStatus && (
              <span className={`mt-1 inline-flex rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider ${
                aggregateStatus === "approved"
                  ? "bg-emerald-100 text-emerald-700"
                  : "bg-amber-100 text-amber-700"
              }`}>
                {aggregateStatus}
              </span>
            )}
            {(role === "pm" || role === "admin") && aggregateStatus === "approved" && (
              <div className="mt-2 flex items-center gap-2">
                <button
                  onClick={handleRevertToDraft}
                  className="rounded-lg border border-amber-300 bg-amber-50 hover:bg-amber-100 px-3 py-1 text-xs font-semibold text-amber-700 transition-colors"
                  type="button"
                >
                  Revert to Draft
                </button>
                <button
                  onClick={handleReject}
                  className="rounded-lg border border-red-300 bg-red-50 hover:bg-red-100 px-3 py-1 text-xs font-semibold text-red-700 transition-colors"
                  type="button"
                >
                  Reject
                </button>
              </div>
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

        {mappingSnapshots.some(s => s.status === "draft") && signOffStatus && (
          <div className="rounded-xl border border-slate-200 bg-slate-50 p-4 flex flex-wrap items-center justify-between gap-4">
            <div className="flex items-center gap-2">
              <span className="text-base">ℹ️</span>
              <div>
                <p className="text-sm font-medium text-slate-700">
                  Editing ball: <span className="font-bold uppercase">{signOffStatus.currentBallRole?.replace("_", " ")}</span>
                </p>
                <p className="text-xs text-slate-500">
                  {editingEnabled
                    ? "You hold the ball. You can make inline edits, sign off, and push to review."
                    : `Viewing read-only. Edit control currently resides with the ${signOffStatus.currentBallRole?.replace("_", " ")}.`}
                </p>
              </div>
            </div>

            <div className="flex items-center gap-2">
              {editingEnabled && (
                <button
                  onClick={handlePushForReview}
                  disabled={!isActorSignOffComplete}
                  title={!isActorSignOffComplete ? "Not all field bindings and lookups are signed by you yet." : undefined}
                  className="rounded-lg bg-primary px-4 py-2 text-xs font-semibold text-white shadow hover:bg-primary-hover focus:outline-none disabled:opacity-50 disabled:cursor-not-allowed"
                  type="button"
                >
                  Push for Review
                </button>
              )}
              {showPokeButton && (
                <button
                  onClick={handlePoke}
                  className="rounded-lg border border-slate-300 bg-white px-4 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-50 focus:outline-none"
                  type="button"
                >
                  Poke Reviewer ({signOffStatus.currentBallRole === "central_team" ? "Central Team" : "Stakeholders"})
                </button>
              )}
            </div>
          </div>
        )}

        {loading ? (
          <div className="rounded-2xl border border-outline-variant bg-surface-container p-8 text-sm text-slate-600">
            Loading review grids...
          </div>
        ) : (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <div className="lg:col-span-2 bg-surface-container border border-outline-variant rounded-2xl p-6 shadow-sm">
              {representativeSnapshot ? (
                (() => {
                  const boundSet = new Set(mappingSnapshots.flatMap((s) => s.fieldBindings || []).map((b) => b.sourceField.toLowerCase()));
                  const unmappedSourceFields = allSourceColumns.filter((h) => h && h.trim() && !boundSet.has(h.trim().toLowerCase()));
                  const unmappedDestinationFields = mappingSnapshots.flatMap((s) => {
                    const destBoundSet = new Set((s.fieldBindings || []).map((b) => b.destinationField?.toLowerCase()));
                    return (s.destinationFields || [])
                      .filter((f) => f && f.trim() && !destBoundSet.has(f.trim().toLowerCase()))
                      .map((f) => ({ tableName: s.destinationObjectName, fieldName: f }));
                  });
                  return (
                    <ReviewGrid
                      mappingTables={mappingTables}
                      lookupGroups={lookupGroups}
                      sampleValues={sampleValues}
                      unmappedSourceFields={unmappedSourceFields}
                      unmappedDestinationFields={unmappedDestinationFields}
                      onApprove={showStakeholderActionButtons ? handleApprove : undefined}
                      onRequestRevision={showStakeholderActionButtons ? handleRequestRevision : undefined}
                      signOffStatus={signOffStatus || undefined}
                      currentUserRole={role}
                      editingEnabled={editingEnabled}
                      onSignBinding={handleSignBinding}
                      onUnsignBinding={handleUnsignBinding}
                      onDestinationFieldChange={handleDestinationFieldChange}
                      onAddBinding={handleAddBinding}
                      onRemoveBinding={handleRemoveBinding}
                      onToggleSourceField={handleToggleSourceField}
                      onSignLookup={handleSignLookup}
                      onUnsignLookup={handleUnsignLookup}
                      onAddLookupSourceValue={handleAddSourceByLookup}
                      onRemoveLookupSourceValue={handleRemoveSourceByLookup}
                    />
                  );
                })()
              ) : (
                <div className="text-sm text-slate-500 text-center py-12">
                  No mapping snapshot has been proposed yet for this feed.
                </div>
              )}
            </div>

            <div>
              {session && (
                <UnifiedCommentThread
                  projectId={projectId}
                  feedId={feedId}
                  sliceId={latestSliceId}
                  token={session.accessToken}
                />
              )}
            </div>
          </div>
        )}
      </section>
    </main>
  );
}
