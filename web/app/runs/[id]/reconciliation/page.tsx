"use client";

import { useEffect, useMemo, useState } from "react";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import { Topbar } from "../../../../components/Topbar";
import { loadUiSession, type SessionRole, type UiSession } from "../../../../lib/session";
import {
  exportReport,
  getLatestReport,
  getLineage,
  triggerReconciliation,
  type LineageResponse,
  type ReconciliationReport,
} from "../../../../lib/reconciliation-api";

type SelectedRow =
  | { direction: "source"; sourceRowIndex: number }
  | { direction: "destination"; destinationRowId: string }
  | null;

function is404Error(error: unknown): boolean {
  if (typeof error !== "object" || error === null) {
    return false;
  }
  const status = (error as { status?: unknown }).status;
  return typeof status === "number" && status === 404;
}

function statusClassName(status: ReconciliationReport["overallStatus"]): string {
  if (status === "pass") {
    return "border-emerald-200 bg-emerald-50 text-emerald-800";
  }
  if (status === "fail") {
    return "border-red-200 bg-red-50 text-red-700";
  }
  return "border-slate-200 bg-slate-50 text-slate-700";
}

function checkClassName(status: "pass" | "fail"): string {
  return status === "fail"
    ? "border-red-200 bg-red-50 text-red-700"
    : "border-emerald-200 bg-emerald-50 text-emerald-700";
}

function outcomeClassName(outcome: LineageResponse["rows"][number]["outcome"]): string {
  if (outcome === "confirmed") {
    return "bg-emerald-50 text-emerald-700";
  }
  if (outcome === "duplicated") {
    return "bg-amber-50 text-amber-700";
  }
  if (outcome === "partially_mapped") {
    return "bg-indigo-50 text-indigo-700";
  }
  return "bg-red-50 text-red-700";
}

export default function ReconciliationPage() {
  const router = useRouter();
  const params = useParams<{ id: string }>();
  const searchParams = useSearchParams();
  const runId = params.id;
  const projectId = searchParams.get("projectId");

  const [session, setSession] = useState<UiSession | null>(null);
  const [report, setReport] = useState<ReconciliationReport | null>(null);
  const [lineage, setLineage] = useState<LineageResponse | null>(null);
  const [selectedRow, setSelectedRow] = useState<SelectedRow>(null);
  const [loading, setLoading] = useState(true);
  const [triggering, setTriggering] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [reportMissing, setReportMissing] = useState(false);

  useEffect(() => {
    const current = loadUiSession();
    if (!current) {
      router.replace("/");
      return;
    }
    setSession(current);
  }, [router]);

  useEffect(() => {
    if (!session) {
      return;
    }

    if (!projectId) {
      setLoading(false);
      setErrorMessage("Missing project context.");
      return;
    }

    let active = true;
    setLoading(true);
    setErrorMessage(null);
    setReportMissing(false);

    void getLatestReport(session.accessToken, projectId, runId)
      .then(async (latestReport) => {
        if (!active) {
          return;
        }
        setReport(latestReport);
        setSelectedRow(null);
        const nextLineage = await getLineage(session.accessToken, projectId, runId, latestReport.reportId, {
          limit: 100,
        });
        if (active) {
          setLineage(nextLineage);
        }
      })
      .catch((error: unknown) => {
        if (!active) {
          return;
        }
        if (is404Error(error)) {
          setReport(null);
          setLineage(null);
          setReportMissing(true);
          return;
        }
        setErrorMessage(error instanceof Error ? error.message : "Unable to load reconciliation.");
      })
      .finally(() => {
        if (active) {
          setLoading(false);
        }
      });

    return () => {
      active = false;
    };
  }, [projectId, runId, session]);

  const role: SessionRole = session?.role ?? "read_only_auditor";
  const canTrigger = role === "central_team";

  const sortedChecks = useMemo(() => {
    if (!report) {
      return [];
    }
    return [...report.checks].sort((left, right) => {
      if (left.status === right.status) {
        return 0;
      }
      return left.status === "fail" ? -1 : 1;
    });
  }, [report]);

  const rowCountCards = useMemo(() => {
    if (!report?.rowCountSummary) {
      return [];
    }
    return [
      { label: "Source Rows", value: report.rowCountSummary.sourceRows },
      { label: "Destination Rows", value: report.rowCountSummary.destinationRows },
      { label: "Rejected", value: report.rowCountSummary.rejected },
      { label: "Duplicated", value: report.rowCountSummary.duplicated },
      { label: "Partially Mapped", value: report.rowCountSummary.partiallyMapped },
    ];
  }, [report]);

  const handleRefresh = async (nextReportId: string) => {
    if (!session || !projectId) {
      return;
    }

    const nextLineage = await getLineage(session.accessToken, projectId, runId, nextReportId, {
      limit: 100,
    });
    setLineage(nextLineage);
  };

  const handleTrigger = async () => {
    if (!session || !projectId) {
      return;
    }

    setTriggering(true);
    setErrorMessage(null);
    try {
      const nextReport = await triggerReconciliation(session.accessToken, projectId, runId);
      setReport(nextReport);
      setReportMissing(false);
      setSelectedRow(null);
      await handleRefresh(nextReport.reportId);
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Unable to run reconciliation.");
    } finally {
      setTriggering(false);
    }
  };

  const handleSourceDrillDown = async (sourceRowIndex: number) => {
    if (!session || !projectId || !report) {
      return;
    }

    setSelectedRow({ direction: "source", sourceRowIndex });
    const nextLineage = await getLineage(session.accessToken, projectId, runId, report.reportId, {
      sourceRowIndex,
    });
    setLineage(nextLineage);
  };

  const handleDestinationDrillDown = async (destinationRowId: string) => {
    if (!session || !projectId || !report) {
      return;
    }

    setSelectedRow({ direction: "destination", destinationRowId });
    const nextLineage = await getLineage(session.accessToken, projectId, runId, report.reportId, {
      destinationRowId,
    });
    setLineage(nextLineage);
  };

  const handleClearSelection = async () => {
    if (!report) {
      return;
    }

    setSelectedRow(null);
    await handleRefresh(report.reportId);
  };

  const handleDownload = async () => {
    if (!session || !projectId || !report) {
      return;
    }

    const exported = await exportReport(session.accessToken, projectId, runId, report.reportId);
    const blob = new Blob([JSON.stringify(exported, null, 2)], { type: "application/json" });
    const url = window.URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `reconciliation-${report.reportId}.json`;
    anchor.click();
    window.URL.revokeObjectURL(url);
  };

  if (!session) {
    return null;
  }

  return (
    <main className="flex min-h-screen flex-col bg-surface text-slate-800">
      <Topbar role={role} />
      <section className="mx-auto flex w-full max-w-[1600px] flex-1 flex-col gap-4 px-6 py-6">
        <div className="rounded-2xl border border-outline-variant bg-surface-container p-6 shadow-sm">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">Runs / Reconciliation</p>
              <h1 className="text-3xl font-semibold tracking-tight text-slate-900">Reconciliation & Lineage</h1>
              <p className="mt-1 text-sm text-slate-600">
                Run <span className="font-mono">{runId}</span>
                {projectId ? (
                  <>
                    {" "}
                    for project <span className="font-mono">{projectId}</span>
                  </>
                ) : null}
              </p>
            </div>
            <div className="flex items-center gap-3">
              {report ? (
                <button
                  className="rounded-md border border-outline-variant bg-white px-4 py-3 text-sm font-semibold text-slate-700"
                  onClick={() => void handleDownload()}
                  type="button"
                >
                  Download
                </button>
              ) : null}
              {canTrigger ? (
                <button
                  className="rounded-md bg-primary px-4 py-3 text-sm font-semibold text-white disabled:opacity-50"
                  disabled={triggering}
                  onClick={() => void handleTrigger()}
                  type="button"
                >
                  {triggering ? "Running..." : report ? "Re-run reconciliation" : "Run reconciliation"}
                </button>
              ) : null}
            </div>
          </div>

          {errorMessage ? (
            <div role="alert" className="mt-4 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
              {errorMessage}
            </div>
          ) : null}
        </div>

        {!loading && !report && !errorMessage ? (
          <div className="rounded-2xl border border-outline-variant bg-surface-container p-6 text-sm text-slate-600 shadow-sm">
            {reportMissing
              ? canTrigger
                ? "No reconciliation report exists yet. Run reconciliation to create the evidence bundle."
                : "No reconciliation report exists yet."
              : "No reconciliation report available."}
          </div>
        ) : null}

        {loading ? (
          <div className="rounded-2xl border border-outline-variant bg-surface-container p-6 text-sm text-slate-600 shadow-sm">
            Loading reconciliation evidence...
          </div>
        ) : null}

        {report ? (
          <>
            <div className={`rounded-2xl border p-5 shadow-sm ${statusClassName(report.overallStatus)}`}>
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <div className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">Status</div>
                  <div className="mt-1 text-xl font-semibold tracking-tight">
                    {report.overallStatus === "pass"
                      ? "All checks passed"
                      : report.overallStatus === "fail"
                        ? "Reconciliation failed"
                        : "Reconciliation in progress"}
                  </div>
                  <p className="mt-2 text-sm text-slate-600">
                    Infrastructure success is not logical success. Each check must pass independently.
                  </p>
                </div>
                <div className="space-y-1 text-right text-xs text-slate-500">
                  <div>
                    Report <span className="font-mono text-slate-700">{report.reportId}</span>
                  </div>
                  <div>
                    Created <span className="font-mono text-slate-700">{report.createdAt}</span>
                  </div>
                  {report.completedAt ? (
                    <div>
                      Completed <span className="font-mono text-slate-700">{report.completedAt}</span>
                    </div>
                  ) : null}
                </div>
              </div>
            </div>

            <div className="rounded-2xl border border-outline-variant bg-surface-container p-5 shadow-sm">
              <div className="flex items-center justify-between gap-4">
                <div>
                  <h2 className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">Check Results</h2>
                  <p className="mt-1 text-sm text-slate-600">Failed checks are pinned to the top of the evidence list.</p>
                </div>
              </div>
              <ul className="mt-4 space-y-2">
                {sortedChecks.map((check) => (
                  <li key={check.checkName} className={`rounded-xl border px-4 py-3 ${checkClassName(check.status)}`}>
                    <div className="flex items-start gap-3">
                      <div className="min-w-0 flex-1">
                        <div className="text-xs font-semibold uppercase tracking-[0.16em]">{check.checkName.replace(/_/g, " ")}</div>
                        <div className="mt-1 text-sm">{check.detail}</div>
                      </div>
                      <span className="rounded-full bg-white/70 px-3 py-1 text-xs font-semibold uppercase tracking-[0.14em]">
                        {check.status}
                      </span>
                    </div>
                  </li>
                ))}
              </ul>
            </div>

            <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-5">
              {rowCountCards.map((card) => (
                <div key={card.label} className="rounded-2xl border border-outline-variant bg-surface-container p-4 text-center shadow-sm">
                  <div className="text-3xl font-semibold tracking-tight text-slate-900">{card.value.toLocaleString()}</div>
                  <div className="mt-1 text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">{card.label}</div>
                </div>
              ))}
            </div>

            <div className="rounded-2xl border border-outline-variant bg-surface-container p-5 shadow-sm">
              <div className="flex flex-wrap items-center justify-between gap-4">
                <div>
                  <h2 className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">Lineage Explorer</h2>
                  <p className="mt-1 text-sm text-slate-600">
                    Select a source row to see its destination rows, or select a destination row to trace it back to source.
                  </p>
                </div>
                {selectedRow ? (
                  <button className="text-sm font-semibold text-primary hover:underline" onClick={() => void handleClearSelection()} type="button">
                    Clear selection
                  </button>
                ) : null}
              </div>

              {selectedRow ? (
                <div className="mt-4 rounded-xl border border-indigo-200 bg-indigo-50 px-4 py-3 text-sm text-indigo-700">
                  {selectedRow.direction === "source"
                    ? `Showing destination row(s) for source row #${selectedRow.sourceRowIndex}.`
                    : `Showing source row for destination row ${selectedRow.destinationRowId}.`}
                </div>
              ) : null}

              <div className="mt-4 overflow-x-auto">
                <table className="min-w-full border-collapse text-left text-sm">
                  <thead>
                    <tr className="border-b border-outline-variant text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">
                      <th className="px-3 py-2">Src row</th>
                      <th className="px-3 py-2">Src key</th>
                      <th className="px-3 py-2">Dst row id</th>
                      <th className="px-3 py-2">Mapping rules</th>
                      <th className="px-3 py-2">Outcome</th>
                      <th className="px-3 py-2">Detail</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(lineage?.rows ?? []).map((row) => {
                      const isSelected =
                        (selectedRow?.direction === "source" && selectedRow.sourceRowIndex === row.sourceRowIndex) ||
                        (selectedRow?.direction === "destination" && selectedRow.destinationRowId === row.destinationRowId);
                      return (
                        <tr key={row.lineageRowId} className={`border-b border-outline-variant/60 ${isSelected ? "bg-indigo-50" : ""}`}>
                          <td className="px-3 py-2">
                            {row.sourceRowIndex !== null ? (
                              <button
                                className="font-mono text-primary hover:underline"
                                onClick={() => void handleSourceDrillDown(row.sourceRowIndex ?? 0)}
                                type="button"
                              >
                                {row.sourceRowIndex}
                              </button>
                            ) : (
                              <span className="font-mono italic text-slate-400">orphaned</span>
                            )}
                          </td>
                          <td className="px-3 py-2 font-mono text-slate-700">{row.sourceRowKey ?? "—"}</td>
                          <td className="px-3 py-2">
                            {row.destinationRowId ? (
                              <button
                                className="font-mono text-primary hover:underline"
                                onClick={() => void handleDestinationDrillDown(row.destinationRowId ?? "")}
                                type="button"
                              >
                                {row.destinationRowId}
                              </button>
                            ) : (
                              <span className="font-mono text-slate-500">—</span>
                            )}
                          </td>
                          <td className="px-3 py-2">
                            <div className="flex flex-wrap gap-1">
                              {(row.mappingRulesApplied ?? []).map((rule) => (
                                <span key={rule} className="rounded-full border border-outline-variant bg-white px-2 py-1 font-mono text-xs text-slate-600">
                                  {rule}
                                </span>
                              ))}
                              {(row.mappingRulesApplied ?? []).length === 0 ? (
                                <span className="text-sm text-slate-400">—</span>
                              ) : null}
                            </div>
                          </td>
                          <td className="px-3 py-2">
                            <span className={`rounded-full px-3 py-1 text-xs font-semibold uppercase tracking-[0.14em] ${outcomeClassName(row.outcome)}`}>
                              {row.outcome.replace(/_/g, " ")}
                            </span>
                          </td>
                          <td className="px-3 py-2 text-sm text-slate-600">{row.outcomeDetail ?? "—"}</td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
                {lineage && lineage.total > lineage.rows.length ? (
                  <p className="mt-3 text-sm text-slate-500">
                    Showing {lineage.rows.length} of {lineage.total} lineage rows.
                  </p>
                ) : null}
              </div>
            </div>
          </>
        ) : null}
      </section>
    </main>
  );
}
