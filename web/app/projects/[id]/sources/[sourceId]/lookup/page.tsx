"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { Topbar } from "../../../../../../components/Topbar";
import {
  getFeedContract,
  listFeedSchema,
  listFeedValueSummaries,
  type FeedContractRecord,
  type FeedSchemaColumnRecord,
  type FeedValueSummaryRecord,
} from "../../../../../../lib/feeds-api";
import {
  approveLookupSnapshot,
  createLookupValueMap,
  generateLookupSnapshot,
  listLookupValueMaps,
  type LookupSnapshotRecord,
  type LookupValueMapRecord,
} from "../../../../../../lib/lookup-api";
import {
  getLatestApprovedMappingSnapshot,
  type MappingSnapshotRecord,
} from "../../../../../../lib/mapping-api";
import { loadUiSession, type SessionRole, type UiSession } from "../../../../../../lib/session";

interface LookupFieldState {
  lookupName: string;
  sourceField: string;
  draftText: string;
  destinationRows: Array<Record<string, unknown>>;
  valueMap: Record<string, string>;
  draftRecord: LookupValueMapRecord | null;
  snapshotRecord: LookupSnapshotRecord | null;
  noticeMessage: string | null;
  errorMessage: string | null;
}

interface LookupTab {
  lookupName: string;
  sourceField: string;
}

function formatDate(value: string): string {
  return value.slice(0, 16).replace("T", " ");
}

function formatCount(value: number): string {
  return new Intl.NumberFormat("en-US").format(value);
}

function displayCellValue(value: unknown): string {
  if (value === null || value === undefined || value === "") {
    return "—";
  }
  return String(value);
}

function extractDestinationId(row: Record<string, unknown>): string {
  const candidates = ["id", "value", "code", "key", "destination_id"];
  for (const key of candidates) {
    const current = row[key];
    if (typeof current === "string" && current.trim()) {
      return current.trim();
    }
  }
  return "";
}

function extractDestinationLabel(row: Record<string, unknown>): string {
  const candidates = ["label", "name", "title", "description"];
  for (const key of candidates) {
    const current = row[key];
    if (typeof current === "string" && current.trim()) {
      return current.trim();
    }
  }
  const fallback = extractDestinationId(row);
  return fallback || "Untitled row";
}

function parseDestinationTable(raw: string): Array<Record<string, unknown>> {
  const trimmed = raw.trim();
  if (!trimmed) {
    return [];
  }

  if (trimmed.startsWith("[")) {
    const parsed = JSON.parse(trimmed) as unknown;
    if (!Array.isArray(parsed)) {
      throw new Error("Destination table JSON must be an array.");
    }
    return parsed.map((entry) => {
      if (!entry || typeof entry !== "object" || Array.isArray(entry)) {
        throw new Error("Destination table rows must be objects.");
      }
      return entry as Record<string, unknown>;
    });
  }

  const lines = trimmed.split(/\r?\n/).filter((line) => line.trim().length > 0);
  if (lines.length === 0) {
    return [];
  }

  const headers = lines[0].split(",").map((value) => value.trim());
  if (headers.length === 0) {
    throw new Error("Destination table CSV must include headers.");
  }

  return lines.slice(1).map((line) => {
    const cells = line.split(",").map((value) => value.trim());
    const entry: Record<string, unknown> = {};
    headers.forEach((header, index) => {
      entry[header] = cells[index] ?? "";
    });
    return entry;
  });
}

function valueCountEntries(valueCounts: Record<string, number>): Array<[string, number]> {
  return Object.entries(valueCounts).sort((left, right) => {
    const countDelta = right[1] - left[1];
    if (countDelta !== 0) {
      return countDelta;
    }
    return left[0].localeCompare(right[0]);
  });
}

function lookupTabsFromMappingSnapshot(snapshot: MappingSnapshotRecord | null): LookupTab[] {
  if (!snapshot) {
    return [];
  }

  const tabs: LookupTab[] = [];
  const seen = new Set<string>();
  for (const binding of snapshot.fieldBindings) {
    if (!binding.lookupName || seen.has(binding.lookupName)) {
      continue;
    }
    seen.add(binding.lookupName);
    tabs.push({
      lookupName: binding.lookupName,
      sourceField: binding.sourceField,
    });
  }
  return tabs;
}

function latestLookupMapForField(
  lookupMaps: LookupValueMapRecord[],
  lookupName: string,
): LookupValueMapRecord | null {
  const matches = lookupMaps.filter((record) => record.lookupName === lookupName);
  if (matches.length === 0) {
    return null;
  }

  return [...matches].sort((left, right) => right.createdAt.localeCompare(left.createdAt))[0] ?? null;
}

export default function LookupPage({ params }: { params: Promise<{ id: string; sourceId: string }> }) {
  const router = useRouter();
  const [routeParams, setRouteParams] = useState<{ id: string; sourceId: string } | null>(null);
  const [session, setSession] = useState<UiSession | null>(null);
  const [source, setSource] = useState<FeedContractRecord | null>(null);
  const [schemaColumns, setSchemaColumns] = useState<FeedSchemaColumnRecord[]>([]);
  const [summaries, setSummaries] = useState<FeedValueSummaryRecord[]>([]);
  const [mappingSnapshot, setMappingSnapshot] = useState<MappingSnapshotRecord | null>(null);
  const [lookupMaps, setLookupMaps] = useState<LookupValueMapRecord[]>([]);
  const [fieldStates, setFieldStates] = useState<Record<string, LookupFieldState>>({});
  const [activeField, setActiveField] = useState<string>("");
  const [loading, setLoading] = useState(true);
  const [pageError, setPageError] = useState<string | null>(null);
  const [actionLoading, setActionLoading] = useState(false);

  useEffect(() => {
    setSession(loadUiSession());
  }, []);

  useEffect(() => {
    let active = true;
    void Promise.resolve(params).then((resolved) => {
      if (active) {
        setRouteParams(resolved);
      }
    });

    return () => {
      active = false;
    };
  }, [params]);

  useEffect(() => {
    if (!session || !routeParams) {
      setLoading(true);
      return;
    }

    let active = true;
    setLoading(true);
    setPageError(null);

    void Promise.all([
      getFeedContract(session.accessToken, routeParams.id, routeParams.sourceId),
      listFeedSchema(session.accessToken, routeParams.id, routeParams.sourceId),
      listFeedValueSummaries(session.accessToken, routeParams.id, routeParams.sourceId),
      getLatestApprovedMappingSnapshot(session.accessToken, routeParams.id, routeParams.sourceId),
      listLookupValueMaps(session.accessToken, routeParams.id, routeParams.sourceId),
    ])
      .then(([sourceResponse, schemaResponse, summaryResponse, mappingResponse, lookupMapResponse]) => {
        if (!active) {
          return;
        }

        const tabs = lookupTabsFromMappingSnapshot(mappingResponse);
        const nextStates: Record<string, LookupFieldState> = {};
        for (const tab of tabs) {
          const latestMap = latestLookupMapForField(lookupMapResponse, tab.lookupName);
          const destinationRows = latestMap?.destinationTable ?? [];
          nextStates[tab.lookupName] = {
            lookupName: latestMap?.lookupName ?? tab.lookupName,
            sourceField: tab.sourceField,
            draftText: JSON.stringify(destinationRows, null, 2),
            destinationRows,
            valueMap: latestMap?.sourceValueMap ?? {},
            draftRecord: latestMap,
            snapshotRecord: null,
            noticeMessage: latestMap
              ? `Loaded draft lookup table updated ${formatDate(latestMap.createdAt)}.`
              : null,
            errorMessage: null,
          };
        }

        setSource(sourceResponse);
        setSchemaColumns(schemaResponse);
        setSummaries(summaryResponse);
        setMappingSnapshot(mappingResponse);
        setLookupMaps(lookupMapResponse);
        setFieldStates(nextStates);
        setActiveField(tabs[0]?.lookupName ?? "");
      })
      .catch((error: unknown) => {
        if (active) {
          setPageError(error instanceof Error ? error.message : "Unable to load lookup mapping.");
        }
      })
      .finally(() => {
        if (active) {
          setLoading(false);
        }
      });

    return () => {
      active = false;
    };
  }, [routeParams, session]);

  const role: SessionRole = session?.role ?? "read_only_auditor";
  const lookupTabs = useMemo(() => lookupTabsFromMappingSnapshot(mappingSnapshot), [mappingSnapshot]);
  const activeState = activeField ? fieldStates[activeField] : null;

  const updateFieldState = (
    fieldName: string,
    updater: (current: LookupFieldState) => LookupFieldState,
  ) => {
    if (!fieldName) {
      return;
    }
    setFieldStates((current) => {
      const next = current[fieldName];
      if (!next) {
        return current;
      }
      return {
        ...current,
        [fieldName]: updater(next),
      };
    });
  };

  const setTabError = (fieldName: string, message: string | null) => {
    updateFieldState(fieldName, (current) => ({
      ...current,
      errorMessage: message,
      noticeMessage: message ? null : current.noticeMessage,
    }));
  };

  const applyParsedDestinationRows = () => {
    if (!activeState) {
      return;
    }

    const fieldName = activeField;
    try {
      const parsedRows = parseDestinationTable(activeState.draftText);
      const validIds = new Set(parsedRows.map((row) => extractDestinationId(row)).filter(Boolean));
      updateFieldState(activeField, (current) => ({
        ...current,
        destinationRows: parsedRows,
        valueMap: Object.fromEntries(
          Object.entries(current.valueMap).filter(([, value]) => validIds.has(value)),
        ),
        draftText: JSON.stringify(parsedRows, null, 2),
        errorMessage: null,
      }));
    } catch (error) {
      setTabError(fieldName, error instanceof Error ? error.message : "Unable to parse destination table.");
    }
  };

  const persistDraft = async () => {
    if (!session || !routeParams || !activeState || !activeField) {
      return;
    }

    const fieldName = activeField;
    try {
      setActionLoading(true);
      setTabError(fieldName, null);
      const parsedRows = parseDestinationTable(activeState.draftText);
      const lookupName = activeState.lookupName.trim() || fieldName;
      const response = await createLookupValueMap(session.accessToken, routeParams.id, routeParams.sourceId, {
        lookupName,
        destinationTable: parsedRows,
        sourceValueMap: activeState.valueMap,
      });

      updateFieldState(fieldName, (current) => ({
        ...current,
        lookupName: response.lookupName,
        draftRecord: response,
        destinationRows: response.destinationTable,
        draftText: JSON.stringify(response.destinationTable, null, 2),
        valueMap: response.sourceValueMap,
        noticeMessage: `Saved draft for ${response.lookupName}.`,
        errorMessage: null,
      }));
      setLookupMaps((current) => [...current, response]);
    } catch (error) {
      setTabError(fieldName, error instanceof Error ? error.message : "Unable to save lookup draft.");
    } finally {
      setActionLoading(false);
    }
  };

  const generateSnapshot = async () => {
    if (!session || !routeParams || !activeState || !activeField) {
      return;
    }

    const fieldName = activeField;
    try {
      setActionLoading(true);
      setTabError(fieldName, null);
      const parsedRows = parseDestinationTable(activeState.draftText);
      const lookupName = activeState.lookupName.trim() || fieldName;
      const savedDraft = await createLookupValueMap(session.accessToken, routeParams.id, routeParams.sourceId, {
        lookupName,
        destinationTable: parsedRows,
        sourceValueMap: activeState.valueMap,
      });
      const snapshot = await generateLookupSnapshot(session.accessToken, routeParams.id, routeParams.sourceId, {
        lookupName,
      });
      updateFieldState(fieldName, (current) => ({
        ...current,
        lookupName,
        draftRecord: savedDraft,
        destinationRows: savedDraft.destinationTable,
        draftText: JSON.stringify(savedDraft.destinationTable, null, 2),
        valueMap: savedDraft.sourceValueMap,
        snapshotRecord: snapshot,
        noticeMessage: `Generated snapshot ${snapshot.lookupSnapshotVersion}.`,
        errorMessage: null,
      }));
      setLookupMaps((current) => [...current, savedDraft]);
    } catch (error) {
      setTabError(fieldName, error instanceof Error ? error.message : "Unable to generate lookup snapshot.");
    } finally {
      setActionLoading(false);
    }
  };

  const approveSnapshot = async () => {
    if (!session || !routeParams || !activeState || !activeField || !activeState.snapshotRecord) {
      return;
    }

    const fieldName = activeField;
    try {
      setActionLoading(true);
      setTabError(fieldName, null);
      const snapshot = await approveLookupSnapshot(
        session.accessToken,
        routeParams.id,
        activeState.snapshotRecord.lookupSnapshotId,
      );
      updateFieldState(fieldName, (current) => ({
        ...current,
        snapshotRecord: snapshot,
        noticeMessage: `Approved snapshot ${snapshot.lookupSnapshotVersion}.`,
        errorMessage: null,
      }));
    } catch (error) {
      setTabError(fieldName, error instanceof Error ? error.message : "Unable to approve lookup snapshot.");
    } finally {
      setActionLoading(false);
    }
  };

  const currentSummaries = summaries.filter((summary) => summary.fieldName === activeState?.sourceField);
  const destinationRows = activeState?.destinationRows ?? [];
  const destinationIds = useMemo(
    () => destinationRows.map((row) => extractDestinationId(row)).filter(Boolean),
    [destinationRows],
  );

  const onSelectDestination = (fieldValue: string, destinationId: string) => {
    if (!activeField) {
      return;
    }

    updateFieldState(activeField, (current) => ({
      ...current,
      valueMap: {
        ...current.valueMap,
        [fieldValue]: destinationId,
      },
      errorMessage: null,
    }));
  };

  return (
    <main className="flex min-h-screen flex-col bg-surface text-slate-800">
      <Topbar role={role} />
      <section className="mx-auto flex w-full max-w-[1600px] flex-1 flex-col gap-4 px-6 py-6">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <button
            className="rounded-md border border-outline-variant bg-surface-container px-3 py-2 text-sm font-medium text-slate-700 hover:bg-outline-variant"
            onClick={() => router.push(`/projects/${routeParams?.id ?? ""}`)}
            type="button"
          >
            Back to project
          </button>
          {source ? (
            <div className="flex flex-wrap items-center gap-2 text-sm text-slate-600">
              <span className="rounded-full border border-outline-variant bg-surface-container px-3 py-1 font-medium text-slate-700">
                {source.label}
              </span>
              <span className="mono-id">{source.sourceDefinitionId}</span>
            </div>
          ) : null}
        </div>

        {loading ? (
          <div className="rounded-2xl border border-outline-variant bg-surface-container p-8 text-sm text-slate-600">
            Loading lookup mappings...
          </div>
        ) : pageError ? (
          <div role="alert" className="rounded-2xl border border-error/30 bg-error/10 px-4 py-3 text-sm text-error">
            {pageError}
          </div>
        ) : lookupTabs.length === 0 ? (
          <div className="rounded-2xl border border-dashed border-outline-variant bg-surface-container p-8 text-sm text-slate-600">
            No lookup fields were found in the approved mapping snapshot.
          </div>
        ) : (
          <div className="space-y-4">
            <div className="flex flex-wrap gap-2">
              {lookupTabs.map((tab) => {
                const state = fieldStates[tab.lookupName];
                const active = tab.lookupName === activeField;
                return (
                  <button
                    key={tab.lookupName}
                    className={`rounded-full px-4 py-2 text-sm font-semibold ${
                      active
                        ? "bg-primary text-white"
                        : "border border-outline-variant bg-surface-container text-slate-700"
                    }`}
                    onClick={() => setActiveField(tab.lookupName)}
                    type="button"
                  >
                    {state?.lookupName ?? tab.lookupName}
                  </button>
                );
              })}
            </div>

            <div className="grid gap-4 xl:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)]">
              <section className="space-y-4 rounded-2xl border border-outline-variant bg-surface-container p-6 shadow-sm">
                <div className="space-y-2">
                  <h1 className="text-2xl font-semibold text-slate-900">Lookup mapping</h1>
                  <p className="text-sm text-slate-600">
                    Source values for <span className="font-semibold text-slate-900">{activeState?.sourceField ?? "—"}</span>
                    {" "}with a draft destination table and approval flow.
                  </p>
                </div>

                <div className="grid gap-3 sm:grid-cols-3">
                  <div className="rounded-xl border border-outline-variant bg-surface px-4 py-3">
                    <div className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">Source</div>
                    <div className="mt-1 text-sm text-slate-900">{source?.label ?? "—"}</div>
                  </div>
                  <div className="rounded-xl border border-outline-variant bg-surface px-4 py-3">
                    <div className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">Lookup</div>
                    <div className="mt-1 text-sm text-slate-900">{activeState?.lookupName ?? "—"}</div>
                  </div>
                  <div className="rounded-xl border border-outline-variant bg-surface px-4 py-3">
                    <div className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">Source slice</div>
                    <div className="mt-1 text-sm text-slate-900">
                      {currentSummaries[0]?.sourceSliceVersion ?? "—"}
                    </div>
                  </div>
                </div>

                <div>
                  <div className="mb-3 flex items-center justify-between">
                    <h2 className="text-lg font-semibold text-slate-900">Observed values</h2>
                    <span className="text-sm text-slate-500">
                      {currentSummaries.reduce((total, summary) => total + Object.keys(summary.valueCounts).length, 0)} distinct values
                    </span>
                  </div>

                  <div className="overflow-hidden rounded-xl border border-outline-variant">
                    <table className="w-full border-collapse text-left">
                      <thead className="bg-surface">
                        <tr className="text-xs uppercase tracking-[0.16em] text-slate-500">
                          <th className="px-4 py-3">Source value</th>
                          <th className="px-4 py-3">Count</th>
                          <th className="px-4 py-3">Mapped to</th>
                        </tr>
                      </thead>
                      <tbody>
                        {currentSummaries.length === 0 ? (
                          <tr className="border-t border-outline-variant">
                            <td className="px-4 py-4 text-sm text-slate-600" colSpan={3}>
                              No value summary is available for this field.
                            </td>
                          </tr>
                        ) : (
                          currentSummaries.flatMap((summary) =>
                            valueCountEntries(summary.valueCounts).map(([value, count]) => (
                              <tr key={`${summary.summaryId}-${value}`} className="border-t border-outline-variant">
                                <td
                                  className={`px-4 py-3 text-sm ${
                                    activeState?.valueMap[value] ? "text-slate-900" : "text-rose-700"
                                  }`}
                                >
                                  {value}
                                </td>
                                <td className="px-4 py-3 text-sm text-slate-700">{formatCount(count)}</td>
                                <td className="px-4 py-3">
                                  <select
                                    className={`w-full rounded-md bg-white px-3 py-2 text-sm text-slate-900 ${
                                      activeState?.valueMap[value]
                                        ? "border border-outline-variant"
                                        : "border border-rose-300"
                                    }`}
                                    disabled={!role || role !== "central_team" || actionLoading}
                                    onChange={(event) => onSelectDestination(value, event.currentTarget.value)}
                                    value={activeState?.valueMap[value] ?? ""}
                                  >
                                    <option value="">Unmapped</option>
                                    {destinationIds.map((destinationId) => (
                                      <option key={destinationId} value={destinationId}>
                                        {destinationId}
                                      </option>
                                    ))}
                                  </select>
                                </td>
                              </tr>
                            )),
                          )
                        )}
                      </tbody>
                    </table>
                  </div>
                </div>
              </section>

              <section className="space-y-4 rounded-2xl border border-outline-variant bg-surface-container p-6 shadow-sm">
                <div className="space-y-2">
                  <h2 className="text-lg font-semibold text-slate-900">Destination table</h2>
                  <p className="text-sm text-slate-600">
                    Paste JSON or CSV rows with an `id` or `destination_id` column, then generate the lookup snapshot.
                  </p>
                </div>

                <div className="space-y-2">
                  <label
                    className="block text-xs font-semibold uppercase tracking-[0.16em] text-slate-500"
                    htmlFor="lookup-name"
                  >
                    Lookup name
                  </label>
                  <input
                    className="w-full rounded-md border border-outline-variant bg-white px-3 py-3 text-sm text-slate-900"
                    id="lookup-name"
                    onChange={(event) => {
                      const value = event.currentTarget.value;
                      updateFieldState(activeField, (current) => ({
                        ...current,
                        lookupName: value,
                      }));
                    }}
                    value={activeState?.lookupName ?? ""}
                  />
                </div>

                <div className="space-y-2">
                  <label
                    className="block text-xs font-semibold uppercase tracking-[0.16em] text-slate-500"
                    htmlFor="lookup-table"
                  >
                    Draft destination table
                  </label>
                  <textarea
                    className="min-h-48 w-full rounded-md border border-outline-variant bg-white px-3 py-3 font-mono text-sm text-slate-900"
                    id="lookup-table"
                    onChange={(event) => {
                      const value = event.currentTarget.value;
                      updateFieldState(activeField, (current) => ({
                        ...current,
                        draftText: value,
                        errorMessage: null,
                      }));
                    }}
                    value={activeState?.draftText ?? "[]"}
                  />
                  <div className="flex flex-wrap gap-2">
                    <button
                      className="rounded-md border border-outline-variant px-3 py-2 text-sm font-semibold text-slate-700 disabled:opacity-60"
                      disabled={actionLoading || role !== "central_team"}
                      onClick={() => applyParsedDestinationRows()}
                      type="button"
                    >
                      Apply table
                    </button>
                    <button
                      className="rounded-md border border-outline-variant px-3 py-2 text-sm font-semibold text-slate-700 disabled:opacity-60"
                      disabled={actionLoading || role !== "central_team"}
                      onClick={() => void persistDraft()}
                      type="button"
                    >
                      Save draft
                    </button>
                    <button
                      className="rounded-md bg-primary px-3 py-2 text-sm font-semibold text-white disabled:opacity-60"
                      disabled={actionLoading || role !== "central_team"}
                      onClick={() => void generateSnapshot()}
                      type="button"
                    >
                      Generate snapshot
                    </button>
                    <button
                      className="rounded-md bg-emerald-600 px-3 py-2 text-sm font-semibold text-white disabled:opacity-60"
                      disabled={actionLoading || role !== "central_team" || !activeState?.snapshotRecord}
                      onClick={() => void approveSnapshot()}
                      type="button"
                    >
                      Approve snapshot
                    </button>
                  </div>
                </div>

                <div className="space-y-3">
                  <div className="flex items-center justify-between">
                    <h3 className="text-sm font-semibold uppercase tracking-[0.16em] text-slate-500">
                      Draft preview
                    </h3>
                    {activeState?.draftRecord ? (
                      <span className="rounded-full bg-primary-container px-3 py-1 text-xs font-semibold text-on-primary-container">
                        {activeState.draftRecord.status}
                      </span>
                    ) : null}
                  </div>

                  <div className="overflow-hidden rounded-xl border border-outline-variant">
                    <table className="w-full border-collapse text-left">
                      <thead className="bg-surface">
                        <tr className="text-xs uppercase tracking-[0.16em] text-slate-500">
                          <th className="px-4 py-3">ID</th>
                          <th className="px-4 py-3">Label</th>
                          <th className="px-4 py-3">Status</th>
                        </tr>
                      </thead>
                      <tbody>
                        {destinationRows.length === 0 ? (
                          <tr className="border-t border-outline-variant">
                            <td className="px-4 py-4 text-sm text-slate-600" colSpan={3}>
                              No destination rows loaded.
                            </td>
                          </tr>
                        ) : (
                          destinationRows.map((row, index) => {
                            const destinationId = extractDestinationId(row);
                            const label = extractDestinationLabel(row);
                            return (
                              <tr key={`${destinationId}-${index}`} className="border-t border-outline-variant">
                                <td className="px-4 py-3 text-sm text-slate-900">{displayCellValue(destinationId)}</td>
                                <td className="px-4 py-3 text-sm text-slate-700">{displayCellValue(label)}</td>
                                <td className="px-4 py-3 text-sm text-slate-700">
                                  {destinationId ? "ready" : "missing id"}
                                </td>
                              </tr>
                            );
                          })
                        )}
                      </tbody>
                    </table>
                  </div>
                </div>

                <div className="rounded-xl border border-outline-variant bg-surface px-4 py-4">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div className="text-sm font-semibold text-slate-900">
                      Snapshot status: {activeState?.snapshotRecord?.status ?? "not generated"}
                    </div>
                    {activeState?.snapshotRecord ? (
                      <div className="mono-id text-xs">
                        {activeState.snapshotRecord.lookupSnapshotVersion}
                      </div>
                    ) : null}
                  </div>
                  {activeState?.snapshotRecord ? (
                    <div className="mt-3 text-sm text-slate-700">
                      Generated {formatDate(activeState.snapshotRecord.createdAt)}
                    </div>
                  ) : (
                    <div className="mt-3 text-sm text-slate-600">
                      The generated snapshot will appear here once the destination table is complete.
                    </div>
                  )}
                </div>

                {activeState?.noticeMessage ? (
                  <div className="rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-900">
                    {activeState.noticeMessage}
                  </div>
                ) : null}
                {activeState?.errorMessage ? (
                  <div role="alert" className="rounded-xl border border-error/30 bg-error/10 px-4 py-3 text-sm text-error">
                    {activeState.errorMessage}
                  </div>
                ) : null}
              </section>
            </div>

            <section className="rounded-2xl border border-outline-variant bg-surface-container p-6 shadow-sm">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <h2 className="text-lg font-semibold text-slate-900">Source analysis context</h2>
                  <p className="text-sm text-slate-600">
                    Schema columns and summary fields for this source.
                  </p>
                </div>
                <div className="text-sm text-slate-600">
                  {schemaColumns.length} schema columns · {lookupMaps.length} saved lookup tables
                </div>
              </div>
              <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
                {schemaColumns.map((column) => (
                  <div key={column.name} className="rounded-xl border border-outline-variant bg-surface px-4 py-3">
                    <div className="text-sm font-semibold text-slate-900">{column.name}</div>
                    <div className="mt-1 text-xs text-slate-500">
                      {column.inferredType} · {column.nullable ? "nullable" : "required"}
                      {column.maxLength ? ` · max ${column.maxLength}` : ""}
                    </div>
                  </div>
                ))}
              </div>
            </section>
          </div>
        )}
      </section>
    </main>
  );
}
