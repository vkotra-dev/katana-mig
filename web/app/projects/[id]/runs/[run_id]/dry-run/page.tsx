"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { Topbar } from "../../../../../../components/Topbar";
import {
  approveDryRun,
  getDryRunArtifact,
  pushBackDryRun,
  type DryRunArtifactRecord,
} from "../../../../../../lib/runs-api";
import { loadUiSession, type SessionRole, type UiSession } from "../../../../../../lib/session";

function formatCount(value: number): string {
  return new Intl.NumberFormat("en-US").format(value);
}

function formatPct(value: number | null): string {
  if (value === null) {
    return "—";
  }
  return `${value.toFixed(1)}%`;
}

export default function DryRunPage() {
  const router = useRouter();
  const params = useParams<{ id: string; run_id: string }>();
  const projectId = params.id;
  const runId = params.run_id;

  const [session, setSession] = useState<UiSession | null>(null);
  const [artifact, setArtifact] = useState<DryRunArtifactRecord | null>(null);
  const [loading, setLoading] = useState(true);
  const [pageError, setPageError] = useState<string | null>(null);
  const [actionLoading, setActionLoading] = useState(false);
  const [pushBackComment, setPushBackComment] = useState("");

  const role: SessionRole = session?.role ?? "read_only_auditor";

  useEffect(() => {
    setSession(loadUiSession());
  }, []);

  useEffect(() => {
    if (!session) {
      return;
    }

    let active = true;
    setLoading(true);
    setPageError(null);

    void getDryRunArtifact(session.accessToken, projectId, runId)
      .then((result) => {
        if (active) {
          setArtifact(result);
        }
      })
      .catch((error: unknown) => {
        if (active) {
          setPageError(error instanceof Error ? error.message : "Unable to load dry-run results.");
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
  }, [session, projectId, runId]);

  const handleApprove = async (): Promise<void> => {
    if (!session) {
      return;
    }
    setActionLoading(true);
    setPageError(null);
    try {
      await approveDryRun(session.accessToken, projectId, runId);
      router.push(`/projects/${projectId}`);
    } catch (error: unknown) {
      setPageError(error instanceof Error ? error.message : "Approve failed.");
      setActionLoading(false);
    }
  };

  const handlePushBack = async (): Promise<void> => {
    if (!session || !pushBackComment.trim()) {
      return;
    }
    setActionLoading(true);
    setPageError(null);
    try {
      await pushBackDryRun(session.accessToken, projectId, runId, pushBackComment.trim());
      router.push(`/projects/${projectId}`);
    } catch (error: unknown) {
      setPageError(error instanceof Error ? error.message : "Push-back failed.");
      setActionLoading(false);
    }
  };

  return (
    <main className="flex min-h-screen flex-col bg-surface text-slate-800">
      <Topbar role={role} />
      <section className="mx-auto flex w-full max-w-[1600px] flex-1 flex-col gap-6 px-6 py-6">
        <div className="space-y-2">
          <p className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-500">Dry-Run Review</p>
          <h1 className="text-3xl font-semibold text-slate-900">Dry-run results</h1>
          <p className="max-w-3xl text-sm text-slate-600">
            Review the mapping pass results before allowing the engine to write to the destination.
          </p>
        </div>

        {pageError ? (
          <div role="alert" className="rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
            {pageError}
          </div>
        ) : null}

        {loading ? (
          <div className="rounded-2xl border border-outline-variant bg-surface-container p-8 text-sm text-slate-600">
            Loading dry-run results...
          </div>
        ) : artifact ? (
          <>
            <section className="rounded-2xl border border-outline-variant bg-surface-container p-6 shadow-sm">
              <h2 className="mb-4 text-xl font-semibold text-slate-900">
                Target object summary - {artifact.destinationObjectName}
              </h2>
              <div className="grid gap-4 sm:grid-cols-3">
                <div className="rounded-xl border border-outline-variant bg-surface px-4 py-4">
                  <div className="text-xs uppercase tracking-[0.16em] text-slate-500">Success rows</div>
                  <div className="mt-1 text-2xl font-semibold text-emerald-700">
                    {formatCount(artifact.successCount)}
                  </div>
                </div>
                <div className="rounded-xl border border-outline-variant bg-surface px-4 py-4">
                  <div className="text-xs uppercase tracking-[0.16em] text-slate-500">Failure rows</div>
                  <div className="mt-1 text-2xl font-semibold text-red-700">
                    {formatCount(artifact.failureCount)}
                  </div>
                </div>
                <div className="rounded-xl border border-outline-variant bg-surface px-4 py-4">
                  <div className="text-xs uppercase tracking-[0.16em] text-slate-500">Field coverage</div>
                  <div className="mt-1 text-2xl font-semibold text-slate-900">
                    {formatPct(artifact.fieldCoveragePct)}
                  </div>
                </div>
              </div>
            </section>

            <section className="rounded-2xl border border-outline-variant bg-surface-container p-6 shadow-sm">
              <h2 className="mb-4 text-xl font-semibold text-slate-900">Sample rows</h2>
              {artifact.sampleRows.length === 0 ? (
                <div className="rounded-xl border border-dashed border-outline-variant bg-surface px-4 py-8 text-sm text-slate-500">
                  No sample rows available.
                </div>
              ) : (
                <div className="overflow-x-auto rounded-xl border border-outline-variant">
                  <table className="w-full border-collapse text-left text-sm">
                    <thead className="bg-surface">
                      <tr className="text-xs uppercase tracking-[0.16em] text-slate-500">
                        <th className="px-4 py-3">Source field</th>
                        <th className="px-4 py-3">Source value</th>
                        <th className="px-4 py-3">Mapped field</th>
                        <th className="px-4 py-3">Mapped value</th>
                      </tr>
                    </thead>
                    <tbody>
                      {artifact.sampleRows.map((row, rowIndex) =>
                        Object.entries(row.source).map(([sourceField, sourceValue], fieldIndex) => (
                          <tr key={`${rowIndex}-${fieldIndex}`} className="border-t border-outline-variant">
                            <td className="px-4 py-2 font-mono text-xs text-slate-700">{sourceField}</td>
                            <td className="px-4 py-2 text-slate-900">{String(sourceValue)}</td>
                            <td className="px-4 py-2 font-mono text-xs text-slate-700">
                              {Object.keys(row.mapped)[fieldIndex] ?? "—"}
                            </td>
                            <td className="px-4 py-2 text-slate-900">
                              {String(Object.values(row.mapped)[fieldIndex] ?? "—")}
                            </td>
                          </tr>
                        )),
                      )}
                    </tbody>
                  </table>
                </div>
              )}
            </section>

            <section className="rounded-2xl border border-outline-variant bg-surface-container p-6 shadow-sm">
              <h2 className="mb-4 text-xl font-semibold text-slate-900">PII masking status</h2>
              {artifact.piiFields.length === 0 ? (
                <div className="rounded-xl border border-dashed border-outline-variant bg-surface px-4 py-8 text-sm text-slate-500">
                  No PII fields detected.
                </div>
              ) : (
                <div className="overflow-hidden rounded-xl border border-outline-variant">
                  <table className="w-full border-collapse text-left text-sm">
                    <thead className="bg-surface">
                      <tr className="text-xs uppercase tracking-[0.16em] text-slate-500">
                        <th className="px-4 py-3">Source field</th>
                        <th className="px-4 py-3">Token applied</th>
                      </tr>
                    </thead>
                    <tbody>
                      {artifact.piiFields.map((entry) => (
                        <tr key={entry.field} className="border-t border-outline-variant">
                          <td className="px-4 py-3 font-mono text-xs text-slate-900">{entry.field}</td>
                          <td className="px-4 py-3 font-mono text-xs text-slate-600">{entry.token}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </section>

            <section className="rounded-2xl border border-outline-variant bg-surface-container p-6 shadow-sm">
              <h2 className="mb-4 text-xl font-semibold text-slate-900">
                Failures ({formatCount(artifact.failureCount)})
              </h2>
              {artifact.failures.length === 0 ? (
                <div className="rounded-xl border border-dashed border-outline-variant bg-surface px-4 py-8 text-sm text-slate-500">
                  No failures recorded.
                </div>
              ) : (
                <div className="overflow-hidden rounded-xl border border-outline-variant">
                  <table className="w-full border-collapse text-left text-sm">
                    <thead className="bg-surface">
                      <tr className="text-xs uppercase tracking-[0.16em] text-slate-500">
                        <th className="px-4 py-3">Row</th>
                        <th className="px-4 py-3">Reason</th>
                        <th className="px-4 py-3">Field</th>
                        <th className="px-4 py-3">Value</th>
                      </tr>
                    </thead>
                    <tbody>
                      {artifact.failures.map((failure, index) => (
                        <tr key={index} className="border-t border-outline-variant">
                          <td className="px-4 py-3 text-slate-900">Row {failure.rowIndex}</td>
                          <td className="px-4 py-3 font-mono text-xs text-red-700">{failure.reason}</td>
                          <td className="px-4 py-3 font-mono text-xs text-slate-700">{failure.field}</td>
                          <td className="px-4 py-3 text-slate-900">{failure.value}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </section>

            {role === "central_team" ? (
              <section className="rounded-2xl border border-outline-variant bg-surface-container p-6 shadow-sm">
                <h2 className="mb-4 text-xl font-semibold text-slate-900">Decision</h2>

                {artifact.status !== "pending" ? (
                  <div className="rounded-xl border border-outline-variant bg-surface px-4 py-4 text-sm text-slate-700">
                    This dry-run has already been <span className="font-semibold">{artifact.status}</span>.
                    {artifact.pushBackComment ? <p className="mt-2 text-slate-600">{artifact.pushBackComment}</p> : null}
                  </div>
                ) : (
                  <div className="space-y-4">
                    <button
                      className="rounded-md bg-primary px-5 py-2 text-sm font-semibold text-white disabled:opacity-60"
                      disabled={actionLoading}
                      onClick={() => void handleApprove()}
                      type="button"
                    >
                      Approve
                    </button>

                    <div className="border-t border-outline-variant pt-4">
                      <label className="mb-2 block text-sm font-semibold text-slate-700" htmlFor="push-back-comment">
                        Push-back comment
                      </label>
                      <textarea
                        className="w-full rounded-xl border border-outline-variant bg-surface px-4 py-3 text-sm text-slate-900 focus:outline-none focus:ring-2 focus:ring-primary"
                        disabled={actionLoading}
                        id="push-back-comment"
                        onChange={(event) => {
                          setPushBackComment(event.target.value);
                        }}
                        placeholder="Explain what needs to change before the migration can proceed..."
                        rows={4}
                        value={pushBackComment}
                      />
                      <button
                        className="mt-3 rounded-md border border-red-300 bg-red-50 px-5 py-2 text-sm font-semibold text-red-700 disabled:opacity-60"
                        disabled={actionLoading || !pushBackComment.trim()}
                        onClick={() => void handlePushBack()}
                        type="button"
                      >
                        Push back
                      </button>
                    </div>
                  </div>
                )}
              </section>
            ) : null}
          </>
        ) : null}
      </section>
    </main>
  );
}
