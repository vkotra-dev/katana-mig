"use client";

import { useEffect, useState } from "react";
import {
  listSourceContracts,
  listSourceSlices,
  type SourceSliceRecord,
} from "../../lib/sources-api";
import {
  approveSourceSlice,
  rejectSourceSlice,
  resubmitSourceSlice,
} from "../../lib/slice-approval-api";
import type { SessionRole } from "../../lib/session";

export interface SourceArtifactsPanelProps {
  projectId: string;
  token: string;
  role: SessionRole;
}

interface ArtifactRow {
  sourceDefinitionId: string;
  sourceLabel: string;
  sourceType: string;
  slice: SourceSliceRecord;
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
  const [rows, setRows] = useState<ArtifactRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [rejectTarget, setRejectTarget] = useState<ArtifactRow | null>(null);
  const [resubmitTarget, setResubmitTarget] = useState<ArtifactRow | null>(null);
  const [rejectReason, setRejectReason] = useState("");
  const [resubmitEncoding, setResubmitEncoding] = useState("utf-8");
  const [resubmitParseSettings, setResubmitParseSettings] = useState("{}");
  const [actionLoading, setActionLoading] = useState(false);

  const loadRows = async (): Promise<ArtifactRow[]> => {
    const contracts = await listSourceContracts(token, projectId);
    const slicesByContract = await Promise.all(
      contracts.map(async (contract) => ({
        contract,
        slices: await listSourceSlices(token, projectId, contract.sourceDefinitionId),
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
        <p className="text-sm text-slate-600">Source slice versions and approval status.</p>
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
          No source slices yet.
        </div>
      ) : (
        <div className="overflow-hidden rounded-xl border border-outline-variant">
          <table className="w-full border-collapse text-left">
            <thead className="bg-surface">
              <tr className="text-xs uppercase tracking-[0.16em] text-slate-500">
                <th className="px-4 py-3">Stage</th>
                <th className="px-4 py-3">Artifact</th>
                <th className="px-4 py-3">Version</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3">Produced</th>
                <th className="px-4 py-3">Actions</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.slice.sourceSliceId} className="border-t border-outline-variant">
                  <td className="px-4 py-3 text-sm text-slate-700">Source intake</td>
                  <td className="px-4 py-3">
                    <div className="text-sm font-semibold text-slate-900">Source slice</div>
                    <div className="text-xs text-slate-500">
                      {row.sourceLabel} · {row.sourceType}
                    </div>
                  </td>
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
                    {role === "central_team" && row.slice.status === "pending_approval" ? (
                      <div className="flex flex-wrap gap-2">
                        <button
                          className="rounded-md bg-emerald-600 px-3 py-2 text-sm font-semibold text-white disabled:opacity-60"
                          disabled={actionLoading}
                          onClick={() =>
                            void runAction(() =>
                              approveSourceSlice(
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
                      </div>
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
                    ) : (
                      <span className="text-sm text-slate-500">No action</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {rejectTarget ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/50 px-4 py-8">
          <div className="w-full max-w-lg rounded-2xl border border-outline-variant bg-surface-container p-6 shadow-2xl">
            <h2 className="text-xl font-semibold text-slate-900">Reject slice</h2>
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
                    rejectSourceSlice(
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
                Reject slice
              </button>
            </div>
          </div>
        </div>
      ) : null}

      {resubmitTarget ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/50 px-4 py-8">
          <div className="w-full max-w-2xl rounded-2xl border border-outline-variant bg-surface-container p-6 shadow-2xl">
            <h2 className="text-xl font-semibold text-slate-900">Resubmit slice</h2>
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
                    resubmitSourceSlice(token, projectId, resubmitTarget.sourceDefinitionId, resubmitTarget.slice.sourceSliceId, {
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
                Resubmit slice
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </section>
  );
}
