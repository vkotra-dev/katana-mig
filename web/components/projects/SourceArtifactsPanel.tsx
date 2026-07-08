"use client";

import { useEffect, useState, Fragment } from "react";
import { useRouter } from "next/navigation";
import {
  listFeedContracts,
  listFeedSlices,
  type FeedSliceRecord,
} from "../../lib/feeds-api";
import {
  approveFeedSlice,
  rejectFeedSlice,
  resubmitFeedSlice,
} from "../../lib/feed-slice-approval-api";
import type { SessionRole } from "../../lib/session";
import { splitCsvRow } from "../../lib/csv-utils";

export interface SourceArtifactsPanelProps {
  projectId: string;
  token: string;
  role: SessionRole;
}

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
const SSN_RE = /^\d{3}-?\d{2}-?\d{4}$/;
const CARD_RE = /^\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}$/;
const PHONE_RE = /^\+?[\d\s\-().]{7,15}$/;
const DATE_RE = /^\d{4}-\d{2}-\d{2}$|^\d{2}\/\d{2}\/\d{4}$/;

type PiiLevel = "pii" | "possible" | "clean";

function scanColumnPii(values: string[]): PiiLevel {
  const filled = values.filter((v) => v.trim().length > 0);
  if (filled.length === 0) return "clean";

  const strongHits = filled.filter(
    (v) => EMAIL_RE.test(v) || SSN_RE.test(v) || CARD_RE.test(v)
  ).length;
  if (strongHits / filled.length > 0.6) return "pii";

  const softHits = filled.filter(
    (v) => PHONE_RE.test(v) || DATE_RE.test(v)
  ).length;
  if (softHits / filled.length > 0.3) return "possible";

  return "clean";
}

function piiLabel(level: PiiLevel): { icon: string; className: string; text: string } {
  if (level === "pii") return { icon: "🔴", className: "text-red-600", text: "PII" };
  if (level === "possible") return { icon: "⚠️", className: "text-amber-600", text: "Possible PII" };
  return { icon: "✅", className: "text-emerald-600", text: "Clean" };
}

interface ArtifactRow {
  sourceDefinitionId: string;
  sourceLabel: string;
  sourceType: string;
  slice: FeedSliceRecord;
}

function formatDate(value: string): string {
  return value.slice(0, 16).replace("T", " ");
}

function statusClassName(status: string): string {
  if (status === "approved") {
    return "bg-emerald-100 text-emerald-900";
  }
  if (status === "rejected") {
    return "bg-rose-100 text-rose-900";
  }
  return "bg-amber-100 text-amber-900";
}

export function SourceArtifactsPanel({ projectId, token, role }: SourceArtifactsPanelProps) {
  const router = useRouter();
  const [rows, setRows] = useState<ArtifactRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [rejectTarget, setRejectTarget] = useState<ArtifactRow | null>(null);
  const [resubmitTarget, setResubmitTarget] = useState<ArtifactRow | null>(null);
  const [rejectReason, setRejectReason] = useState("");
  const [resubmitEncoding, setResubmitEncoding] = useState("utf-8");
  const [resubmitParseSettings, setResubmitParseSettings] = useState("{}");
  const [actionLoading, setActionLoading] = useState(false);

  // Expanded detail and inline approval states
  const [expandedSliceId, setExpandedSliceId] = useState<string | null>(null);
  const [unmaskedSlices, setUnmaskedSlices] = useState<Record<string, FeedSliceRecord>>({});
  const [globalShowOriginal, setGlobalShowOriginal] = useState(false);
  const [rejectionReason, setRejectionReason] = useState("");
  const [approvalError, setApprovalError] = useState<string | null>(null);
  const [inlineApprovalLoading, setInlineApprovalLoading] = useState<"approve" | "reject" | null>(null);

  useEffect(() => {
    if (globalShowOriginal && expandedSliceId && !unmaskedSlices[expandedSliceId]) {
      const targetRow = rows.find((r) => r.slice.sourceSliceId === expandedSliceId);
      if (targetRow) {
        listFeedSlices(token, projectId, targetRow.sourceDefinitionId, false)
          .then((fetchedSlices) => {
            const target = fetchedSlices.find((s) => s.sourceSliceId === expandedSliceId);
            if (target) {
              setUnmaskedSlices((prev) => ({ ...prev, [expandedSliceId]: target }));
            }
          })
          .catch((e: unknown) => {
            setErrorMessage(e instanceof Error ? e.message : "Failed to load unmasked data.");
          });
      }
    }
  }, [globalShowOriginal, expandedSliceId, rows, token, projectId, unmaskedSlices]);

  const loadRows = async (): Promise<ArtifactRow[]> => {
    const contracts = await listFeedContracts(token, projectId);
    const slicesByContract = await Promise.all(
      contracts.map(async (contract) => ({
        contract,
        slices: await listFeedSlices(token, projectId, contract.sourceDefinitionId),
      })),
    );
    return slicesByContract.flatMap(({ contract, slices }) =>
      slices.map((slice) => ({
        sourceDefinitionId: contract.sourceDefinitionId,
        sourceLabel: contract.label,
        sourceType: contract.sourceType,
        slice,
      })),
    );
  };

  useEffect(() => {
    let active = true;
    setLoading(true);
    setErrorMessage(null);
    void loadRows()
      .then((data) => {
        if (active) {
          setRows(data);
        }
      })
      .catch((error: unknown) => {
        if (active) {
          setErrorMessage(error instanceof Error ? error.message : "Unable to load artifacts.");
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
  }, [projectId, token]);

  const refresh = async () => {
    const data = await loadRows();
    setRows(data);
  };

  const runAction = async (action: () => Promise<void>): Promise<boolean> => {
    setActionLoading(true);
    setErrorMessage(null);
    try {
      await action();
      await refresh();
      return true;
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Unable to update artifact.");
      return false;
    } finally {
      setActionLoading(false);
    }
  };

  return (
    <section className="space-y-4 rounded-2xl border border-outline-variant bg-surface-container p-6 shadow-sm">
      <div>
        <h2 className="text-xl font-semibold text-slate-900">Artifacts</h2>
        <p className="text-sm text-slate-600">Feed slice versions and approval status.</p>
      </div>

      {loading ? (
        <div className="rounded-xl border border-outline-variant bg-surface px-4 py-3 text-sm text-slate-600">
          Loading artifacts...
        </div>
      ) : errorMessage ? (
        <div role="alert" className="rounded-xl border border-error/30 bg-error/10 px-4 py-3 text-sm text-error">
          {errorMessage}
        </div>
      ) : rows.length === 0 ? (
        <div className="rounded-xl border border-dashed border-outline-variant bg-surface px-4 py-8 text-sm text-slate-500">
          No feed slices yet.
        </div>
      ) : (
        <div className="space-y-3">
          {(role === "admin" || role === "pm" || role === "central_team") && (
            <div className="flex items-center gap-2 self-start pb-1">
              <label htmlFor="global-toggle-switch" className="relative inline-flex items-center cursor-pointer select-none">
                <input
                  id="global-toggle-switch"
                  type="checkbox"
                  checked={globalShowOriginal}
                  onChange={(e) => setGlobalShowOriginal(e.target.checked)}
                  className="sr-only peer"
                />
                <div className="w-9 h-5 bg-slate-200 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-slate-300 after:border after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:bg-primary"></div>
                <span className="ml-2.5 text-xs font-semibold text-slate-700">
                  {globalShowOriginal ? "Showing original data" : "Showing masked data"}
                </span>
              </label>
            </div>
          )}
          <div className="overflow-x-auto rounded-xl border border-outline-variant max-w-full">
            <table className="w-full border-collapse text-left">
            <thead className="bg-surface">
              <tr className="text-xs uppercase tracking-[0.16em] text-slate-500">
                <th className="px-4 py-3">Artifact</th>
                <th className="px-4 py-3">Stage</th>
                <th className="px-4 py-3">Version</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3">Produced</th>
                <th className="px-4 py-3">Actions</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => {
                const isExpanded = expandedSliceId === row.slice.sourceSliceId;
                const activeSlice = globalShowOriginal && unmaskedSlices[row.slice.sourceSliceId]
                  ? unmaskedSlices[row.slice.sourceSliceId]
                  : row.slice;

                const headers = activeSlice.headerCsv ? splitCsvRow(activeSlice.headerCsv) : [];
                const previewLines = activeSlice.previewRows || [];
                const parsedRows = previewLines.map((r) => splitCsvRow(r));

                const blankColumns = headers.filter((_, colIdx) =>
                  parsedRows.every((r) => !r[colIdx]?.trim())
                );

                const columnPii = headers.map((_, colIdx) =>
                  scanColumnPii(parsedRows.map((r) => r[colIdx] ?? ""))
                );

                const isNonAuditor = role !== "read_only_auditor";

                return (
                  <Fragment key={row.slice.sourceSliceId}>
                    <tr
                      className="border-t border-outline-variant hover:bg-slate-50/50 cursor-pointer"
                      onClick={(e) => {
                        const target = e.target as HTMLElement;
                        if (target.closest("button") || target.closest("input") || target.closest("textarea")) {
                          return;
                        }
                        setExpandedSliceId(isExpanded ? null : row.slice.sourceSliceId);
                        setApprovalError(null);
                        setRejectionReason("");
                      }}
                    >
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-2">
                          <span className="text-xs text-slate-400 font-mono w-4 text-center">
                            {isExpanded ? "▼" : "▶"}
                          </span>
                          <div>
                            <div className="text-sm font-semibold text-slate-900">{row.sourceLabel}</div>
                            <div className="text-xs text-slate-500">
                              {row.sourceType} · Feed slice
                            </div>
                          </div>
                        </div>
                      </td>
                      <td className="px-4 py-3 text-sm text-slate-700">Feed intake</td>
                      <td className="px-4 py-3 text-sm text-slate-700">{row.slice.sourceSliceVersion ?? "—"}</td>
                      <td className="px-4 py-3">
                        <span className={`rounded-full px-2.5 py-1 text-xs font-semibold ${statusClassName(row.slice.status)}`}>
                          {row.slice.status}
                        </span>
                        {row.slice.status === "rejected" && row.slice.approvalRejectionReason ? (
                          <div className="mt-2 text-xs text-rose-700">{row.slice.approvalRejectionReason}</div>
                        ) : null}
                      </td>
                      <td className="px-4 py-3 text-sm text-slate-700">{formatDate(row.slice.createdAt)}</td>
                      <td className="px-4 py-3">
                        <div className="flex flex-wrap gap-2 items-center">
                          <button
                            className="rounded-md border border-outline-variant px-3 py-2 text-sm font-semibold text-slate-700 hover:bg-outline-variant/40"
                            onClick={() => setExpandedSliceId(isExpanded ? null : row.slice.sourceSliceId)}
                            type="button"
                          >
                            {isExpanded ? "Hide details" : "View details"}
                          </button>
                          {isNonAuditor && row.slice.status === "pending_approval" ? (
                            <>
                              <button
                                className="rounded-md bg-emerald-600 px-3 py-2 text-sm font-semibold text-white disabled:opacity-60"
                                disabled={actionLoading}
                                onClick={() =>
                                  void runAction(() =>
                                    approveFeedSlice(
                                      token,
                                      projectId,
                                      row.sourceDefinitionId,
                                      row.slice.sourceSliceId,
                                    ),
                                  )
                                }
                                type="button"
                              >
                                Approve
                              </button>
                              <button
                                className="rounded-md border border-error px-3 py-2 text-sm font-semibold text-error disabled:opacity-60"
                                disabled={actionLoading}
                                onClick={() => {
                                  setRejectTarget(row);
                                  setRejectReason("");
                                }}
                                type="button"
                              >
                                Reject
                              </button>
                            </>
                          ) : role === "central_team" && row.slice.status === "rejected" ? (
                            <button
                              className="rounded-md border border-outline-variant px-3 py-2 text-sm font-semibold text-slate-700 disabled:opacity-60"
                              disabled={actionLoading}
                              onClick={() => {
                                setResubmitTarget(row);
                                setResubmitEncoding("utf-8");
                                setResubmitParseSettings("{}");
                              }}
                              type="button"
                            >
                              Resubmit
                            </button>
                          ) : null}
                        </div>
                      </td>
                    </tr>

                    {isExpanded && (
                      <tr className="bg-slate-50/50">
                        <td colSpan={6} className="px-6 py-4 border-t border-outline-variant">
                          <div className="space-y-4 max-w-[calc(100vw-8rem)]">
                            <div className="flex items-center justify-between">
                              <h4 className="text-sm font-bold text-slate-800">
                                Feed Data Profile & Sample Preview ({previewLines.length} rows shown)
                              </h4>
                            </div>

                            {/* Stats Cards */}
                            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                              {[
                                { label: "Columns", value: headers.length },
                                { label: "Total Rows", value: activeSlice.rowCount },
                                { label: "Preview Rows", value: previewLines.length },
                                { label: "Blank Columns", value: blankColumns.length, alert: blankColumns.length > 0 },
                              ].map(({ label, value, alert }) => (
                                <div key={label} className={`rounded-xl border p-3 text-center ${alert ? "border-amber-300 bg-amber-50" : "border-outline-variant bg-white"}`}>
                                  <div className={`text-lg font-bold ${alert ? "text-amber-700" : "text-slate-900"}`}>{value}</div>
                                  <div className="text-[9px] uppercase tracking-wider text-slate-500 mt-0.5">{label}</div>
                                </div>
                              ))}
                            </div>

                            {/* PII badges */}
                            {headers.length > 0 && (
                              <div>
                                <div className="text-[10px] font-semibold uppercase tracking-wider text-slate-500 mb-1.5">PII Scan</div>
                                <div className="flex flex-wrap gap-1.5 max-w-[calc(100vw-10rem)]">
                                  {headers.map((col, i) => {
                                    const badge = piiLabel(columnPii[i]);
                                    return (
                                      <span key={col} className={`inline-flex items-center gap-1 rounded-full border px-2.5 py-0.5 text-[10px] font-medium bg-white break-all ${badge.className}`}>
                                        {badge.icon} {col}
                                      </span>
                                    );
                                  })}
                                </div>
                                {blankColumns.length > 0 && (
                                  <p className="mt-2 text-[10px] text-amber-700">
                                    Blank columns: {blankColumns.join(", ")}
                                  </p>
                                )}
                              </div>
                            )}

                            {/* Preview data table */}
                            {previewLines.length > 0 ? (
                              <div className="max-h-60 max-w-[calc(100vw-8rem)] md:max-w-full overflow-auto rounded-lg border border-outline-variant bg-white">
                                <table className="text-left text-[10px] border-collapse font-mono w-full">
                                  <thead className="bg-slate-50 border-b border-outline-variant sticky top-0">
                                    <tr>
                                      {headers.map((col, i) => {
                                        const badge = piiLabel(columnPii[i]);
                                        return (
                                          <th key={i} className="px-3 py-2 font-bold text-slate-700 whitespace-nowrap">
                                            <span className={badge.className}>{badge.icon}</span> {col}
                                          </th>
                                        );
                                      })}
                                    </tr>
                                  </thead>
                                  <tbody className="divide-y divide-slate-100">
                                    {parsedRows.map((cells, rowIdx) => (
                                      <tr key={rowIdx} className="hover:bg-slate-50/50">
                                        {headers.map((_, colIdx) => {
                                          const val = cells[colIdx] ?? "";
                                          const blank = !val.trim();
                                          return (
                                            <td key={colIdx} className={`px-3 py-1.5 whitespace-nowrap ${blank ? "bg-amber-50/50 text-amber-400 italic" : "text-slate-600"}`}>
                                              {blank ? "—" : val}
                                            </td>
                                          );
                                        })}
                                      </tr>
                                    ))}
                                  </tbody>
                                </table>
                              </div>
                            ) : (
                              <div className="rounded-lg border border-dashed border-outline-variant bg-white px-4 py-6 text-center text-xs text-slate-500">
                                No preview data available for this slice.
                              </div>
                            )}

                            {/* Inline Approval for non-auditors */}
                            {isNonAuditor && activeSlice.status === "pending_approval" && (
                              <div className="border-t border-outline-variant pt-4 space-y-2">
                                <div className="text-xs font-semibold text-slate-800">Decide on this slice version</div>
                                {approvalError && <p className="text-xs text-red-600">{approvalError}</p>}
                                <div className="flex flex-col gap-3 sm:flex-row sm:items-end">
                                  <button
                                    type="button"
                                    disabled={inlineApprovalLoading !== null}
                                    onClick={async () => {
                                      setInlineApprovalLoading("approve");
                                      setApprovalError(null);
                                      try {
                                        await approveFeedSlice(token, projectId, row.sourceDefinitionId, activeSlice.sourceSliceId);
                                        await refresh();
                                        setExpandedSliceId(null);
                                      } catch (e) {
                                        setApprovalError(e instanceof Error ? e.message : "Approval failed.");
                                      } finally {
                                        setInlineApprovalLoading(null);
                                      }
                                    }}
                                    className="rounded-lg bg-emerald-600 px-4 py-2 text-xs font-semibold text-white hover:bg-emerald-700 disabled:opacity-50"
                                  >
                                    {inlineApprovalLoading === "approve" ? "Approving…" : "Approve"}
                                  </button>
                                  <div className="flex flex-1 flex-col gap-1.5">
                                    <input
                                      type="text"
                                      placeholder="Rejection reason (required to reject)"
                                      value={rejectionReason}
                                      onChange={(e) => setRejectionReason(e.target.value)}
                                      className="rounded-lg border border-outline-variant px-3 py-1.5 text-xs text-slate-700 placeholder:text-slate-400 bg-white"
                                    />
                                    <button
                                      type="button"
                                      disabled={!rejectionReason.trim() || inlineApprovalLoading !== null}
                                      onClick={async () => {
                                        setInlineApprovalLoading("reject");
                                        setApprovalError(null);
                                        try {
                                          await rejectFeedSlice(token, projectId, row.sourceDefinitionId, activeSlice.sourceSliceId, rejectionReason.trim());
                                          await refresh();
                                          setExpandedSliceId(null);
                                          setRejectionReason("");
                                        } catch (e) {
                                          setApprovalError(e instanceof Error ? e.message : "Rejection failed.");
                                        } finally {
                                          setInlineApprovalLoading(null);
                                        }
                                      }}
                                      className="rounded-lg border border-red-300 px-4 py-1.5 text-xs font-semibold text-red-600 hover:bg-red-50 disabled:opacity-40 self-start"
                                    >
                                      {inlineApprovalLoading === "reject" ? "Rejecting…" : "Reject"}
                                    </button>
                                  </div>
                                </div>
                              </div>
                            )}
                          </div>
                        </td>
                      </tr>
                    )}
                  </Fragment>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
      )}

      {rejectTarget ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/50 px-4 py-8">
          <div className="w-full max-w-lg rounded-2xl border border-outline-variant bg-surface-container p-6 shadow-2xl">
            <h2 className="text-xl font-semibold text-slate-900">Reject feed slice</h2>
            <div className="mt-4 space-y-2">
              <label className="block text-xs font-semibold uppercase tracking-[0.16em] text-slate-500" htmlFor="artifact-reject-reason">
                Reason
              </label>
              <textarea
                className="min-h-32 w-full rounded-md border border-outline-variant bg-white px-3 py-3 text-sm text-slate-900"
                id="artifact-reject-reason"
                onChange={(event) => setRejectReason(event.currentTarget.value)}
                value={rejectReason}
              />
            </div>
            <div className="mt-6 flex justify-end gap-3">
              <button
                className="rounded-md border border-outline-variant px-4 py-3 text-sm font-semibold text-slate-700"
                onClick={() => setRejectTarget(null)}
                type="button"
              >
                Cancel
              </button>
              <button
                className="rounded-md bg-error px-4 py-3 text-sm font-semibold text-white disabled:opacity-60"
                disabled={actionLoading || rejectReason.trim().length === 0}
                onClick={() => {
                  void runAction(() =>
                    rejectFeedSlice(
                      token,
                      projectId,
                      rejectTarget.sourceDefinitionId,
                      rejectTarget.slice.sourceSliceId,
                      rejectReason.trim(),
                    ),
                  ).then((success) => {
                    if (success) {
                      setRejectTarget(null);
                    }
                  });
                }}
                type="button"
              >
                Reject feed slice
              </button>
            </div>
          </div>
        </div>
      ) : null}

      {resubmitTarget ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/50 px-4 py-8">
          <div className="w-full max-w-2xl rounded-2xl border border-outline-variant bg-surface-container p-6 shadow-2xl">
            <h2 className="text-xl font-semibold text-slate-900">Resubmit feed slice</h2>
            <p className="mt-1 text-sm text-slate-600">
              {resubmitTarget.sourceLabel} · {resubmitTarget.slice.sourceSliceVersion}
            </p>
            <div className="mt-4 grid gap-4 sm:grid-cols-2">
              <div className="space-y-2">
                <label className="block text-xs font-semibold uppercase tracking-[0.16em] text-slate-500" htmlFor="resubmit-encoding">
                  Encoding
                </label>
                <input
                  className="w-full rounded-md border border-outline-variant bg-white px-3 py-3 text-sm text-slate-900"
                  id="resubmit-encoding"
                  onChange={(event) => setResubmitEncoding(event.currentTarget.value)}
                  value={resubmitEncoding}
                />
              </div>
              <div className="space-y-2 sm:col-span-2">
                <label className="block text-xs font-semibold uppercase tracking-[0.16em] text-slate-500" htmlFor="resubmit-settings">
                  Parse settings JSON
                </label>
                <textarea
                  className="min-h-40 w-full rounded-md border border-outline-variant bg-white px-3 py-3 text-sm text-slate-900"
                  id="resubmit-settings"
                  onChange={(event) => setResubmitParseSettings(event.currentTarget.value)}
                  value={resubmitParseSettings}
                />
              </div>
            </div>
            <div className="mt-6 flex justify-end gap-3">
              <button
                className="rounded-md border border-outline-variant px-4 py-3 text-sm font-semibold text-slate-700"
                onClick={() => setResubmitTarget(null)}
                type="button"
              >
                Cancel
              </button>
              <button
                className="rounded-md bg-primary px-4 py-3 text-sm font-semibold text-white disabled:opacity-60"
                disabled={actionLoading}
                onClick={() => {
                  let parsedSettings: Record<string, unknown> | null = null;
                  try {
                    parsedSettings = resubmitParseSettings.trim() ? (JSON.parse(resubmitParseSettings) as Record<string, unknown>) : null;
                  } catch {
                    setErrorMessage("Parse settings must be valid JSON.");
                    return;
                  }
                  void runAction(() =>
                    resubmitFeedSlice(token, projectId, resubmitTarget.sourceDefinitionId, resubmitTarget.slice.sourceSliceId, {
                      encoding: resubmitEncoding.trim() || null,
                      parseSettings: parsedSettings,
                    }),
                  ).then((success) => {
                    if (success) {
                      setResubmitTarget(null);
                    }
                  });
                }}
                type="button"
              >
                Resubmit feed slice
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </section>
  );
}
