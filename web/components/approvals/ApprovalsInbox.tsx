"use client";

import { useEffect, useState } from "react";
import {
  approveFeedSlice,
  listPendingApprovals,
  rejectFeedSlice,
  type FeedSliceApprovalItem,
} from "../../lib/feed-slice-approval-api";
import type { SessionRole } from "../../lib/session";

export interface ApprovalsInboxProps {
  token: string;
  role: SessionRole;
}

function formatDate(value: string): string {
  return value.slice(0, 16).replace("T", " ");
}

export function ApprovalsInbox({ token, role }: ApprovalsInboxProps) {
  const [items, setItems] = useState<FeedSliceApprovalItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [rejectTarget, setRejectTarget] = useState<FeedSliceApprovalItem | null>(null);
  const [rejectReason, setRejectReason] = useState("");
  const [actionLoading, setActionLoading] = useState(false);

  const loadApprovals = async (activeRef: { active: boolean }) => {
    setLoading(true);
    setErrorMessage(null);
    try {
      const response = await listPendingApprovals(token);
      if (activeRef.active) {
        setItems(response);
      }
    } catch (error) {
      if (activeRef.active) {
        setErrorMessage(error instanceof Error ? error.message : "Unable to load approvals.");
      }
    } finally {
      if (activeRef.active) {
        setLoading(false);
      }
    }
  };

  useEffect(() => {
    const activeRef = { active: true };
    void loadApprovals(activeRef);
    return () => {
      activeRef.active = false;
    };
  }, [token]);

  const runAction = async (action: () => Promise<void>): Promise<boolean> => {
    setActionLoading(true);
    setErrorMessage(null);
    try {
      await action();
      const activeRef = { active: true };
      await loadApprovals(activeRef);
      return true;
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Unable to update approval.");
      return false;
    } finally {
      setActionLoading(false);
    }
  };

  return (
    <section className="space-y-4 rounded-2xl border border-outline-variant bg-surface-container p-6 shadow-sm">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold text-slate-900">Approvals</h1>
          <p className="text-sm text-slate-600">Pending source slices that need a decision.</p>
        </div>
        <div className="text-sm text-slate-500">
          {role === "central_team" ? "Central team inbox" : "Read-only view"}
        </div>
      </div>

      {loading ? (
        <div className="rounded-xl border border-outline-variant bg-surface px-4 py-3 text-sm text-slate-600">
          Loading approvals...
        </div>
      ) : errorMessage ? (
        <div role="alert" className="rounded-xl border border-error/30 bg-error/10 px-4 py-3 text-sm text-error">
          {errorMessage}
        </div>
      ) : items.length === 0 ? (
        <div className="rounded-xl border border-dashed border-outline-variant bg-surface px-4 py-8 text-sm text-slate-500">
          No pending approvals
        </div>
      ) : (
        <div className="overflow-hidden rounded-xl border border-outline-variant">
          <table className="w-full border-collapse text-left">
            <thead className="bg-surface">
              <tr className="text-xs uppercase tracking-[0.16em] text-slate-500">
                <th className="px-4 py-3">Project</th>
                <th className="px-4 py-3">Source label</th>
                <th className="px-4 py-3">Source type</th>
                <th className="px-4 py-3">Rows</th>
                <th className="px-4 py-3">Uploaded</th>
                <th className="px-4 py-3">Warnings</th>
                <th className="px-4 py-3">Actions</th>
              </tr>
            </thead>
            <tbody>
              {items.map((item) => (
                <tr key={item.sourceSliceId} className="border-t border-outline-variant">
                  <td className="px-4 py-3">
                    <div className="text-sm font-semibold text-slate-900">{item.projectName}</div>
                    <div className="mono-id mt-1">{item.projectId}</div>
                  </td>
                  <td className="px-4 py-3 text-sm text-slate-700">
                    <div className="font-semibold text-slate-900">{item.sourceLabel}</div>
                    <div className="mono-id mt-1">{item.sourceSliceVersion}</div>
                  </td>
                  <td className="px-4 py-3 text-sm text-slate-700">{item.sourceType}</td>
                  <td className="px-4 py-3 text-sm text-slate-700">{item.rowCount}</td>
                  <td className="px-4 py-3 text-sm text-slate-700">{formatDate(item.createdAt)}</td>
                  <td className="px-4 py-3 text-sm text-slate-700">
                    {item.parseWarnings && item.parseWarnings.length > 0 ? item.parseWarnings.join("; ") : "—"}
                  </td>
                  <td className="px-4 py-3">
                    {role === "central_team" ? (
                      <div className="flex flex-wrap gap-2">
                        <button
                          className="rounded-md bg-emerald-600 px-3 py-2 text-sm font-semibold text-white disabled:opacity-60"
                          disabled={actionLoading}
                          onClick={() =>
                            void runAction(() =>
                              approveFeedSlice(
                                token,
                                item.projectId,
                                item.sourceDefinitionId,
                                item.sourceSliceId,
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
                            setRejectTarget(item);
                            setRejectReason("");
                          }}
                          type="button"
                        >
                          Reject
                        </button>
                      </div>
                    ) : (
                      <span className="text-sm text-slate-500">Read only</span>
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
            <p className="mt-1 text-sm text-slate-600">
              {rejectTarget.sourceLabel} in {rejectTarget.projectName}
            </p>
            <div className="mt-4 space-y-2">
              <label className="block text-xs font-semibold uppercase tracking-[0.16em] text-slate-500" htmlFor="reject-reason">
                Reason
              </label>
              <textarea
                className="min-h-32 w-full rounded-md border border-outline-variant bg-white px-3 py-3 text-sm text-slate-900"
                id="reject-reason"
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
                      rejectTarget.projectId,
                      rejectTarget.sourceDefinitionId,
                      rejectTarget.sourceSliceId,
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
    </section>
  );
}
