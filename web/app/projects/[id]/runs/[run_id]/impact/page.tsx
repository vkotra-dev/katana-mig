"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Topbar } from "../../../../../../components/Topbar";
import { acknowledgeImpact, getImpactReport, type ImpactReport } from "../../../../../../lib/runs-api";
import { loadUiSession, type SessionRole, type UiSession } from "../../../../../../lib/session";

export default function ImpactPage({
  params,
}: {
  params: Promise<{ id: string; run_id: string }>;
}) {
  const router = useRouter();
  const [routeParams, setRouteParams] = useState<{ id: string; run_id: string } | null>(null);
  const [session, setSession] = useState<UiSession | null>(null);
  const [report, setReport] = useState<ImpactReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
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
    setErrorMessage(null);

    void getImpactReport(session.accessToken, routeParams.id, routeParams.run_id)
      .then((nextReport) => {
        if (active) {
          setReport(nextReport);
        }
      })
      .catch((error: unknown) => {
        if (active) {
          setErrorMessage(error instanceof Error ? error.message : "Unable to load impact report.");
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

  const handleAcknowledge = async (): Promise<void> => {
    if (!session || !routeParams) {
      return;
    }
    setActionLoading(true);
    setErrorMessage(null);
    try {
      await acknowledgeImpact(session.accessToken, routeParams.id, routeParams.run_id);
      router.push(`/runs/${routeParams.run_id}?projectId=${routeParams.id}`);
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Acknowledge failed.");
    } finally {
      setActionLoading(false);
    }
  };

  return (
    <main className="flex min-h-screen flex-col bg-surface text-slate-800">
      <Topbar role={role} />
      <section className="mx-auto flex w-full max-w-[1600px] flex-1 flex-col gap-4 px-6 py-6">
        <div className="rounded-2xl border border-outline-variant bg-surface-container p-6 shadow-sm">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">
                Runs / Impact Review
              </p>
              <h1 className="text-3xl font-semibold tracking-tight text-slate-900">Impact Review</h1>
              <p className="mt-1 text-sm text-slate-600">
                Gate 1 rejection analysis and remediation plan for run{" "}
                <span className="font-mono">{routeParams?.run_id}</span>.
              </p>
            </div>

            <div className="flex items-center gap-3">
              <button
                className="rounded-md bg-primary px-4 py-3 text-sm font-semibold text-white disabled:opacity-60"
                disabled={actionLoading || loading || report === null}
                onClick={() => void handleAcknowledge()}
                type="button"
              >
                Acknowledge and fix
              </button>
              <button
                className="rounded-md border border-outline-variant bg-white px-4 py-3 text-sm font-semibold text-slate-400 disabled:cursor-not-allowed"
                disabled
                title="Use the Change Request system to request clarification"
                type="button"
              >
                Request clarification
              </button>
            </div>
          </div>

          {errorMessage ? (
            <div role="alert" className="mt-4 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
              {errorMessage}
            </div>
          ) : null}

          {loading ? (
            <div className="mt-6 text-sm text-slate-500">Loading impact report…</div>
          ) : (
            <div className="mt-6 grid gap-4 lg:grid-cols-3">
              <div className="rounded-2xl border border-outline-variant bg-white p-4">
                <div className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">
                  Gate 1 Pushback
                </div>
                {report ? (
                  <div className="mt-3 space-y-3 text-sm text-slate-700">
                    <div>
                      <p className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-400">
                        Required changes
                      </p>
                      <p className="mt-1">{report.gateRejection.requiredChanges}</p>
                    </div>
                    <div>
                      <p className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-400">
                        Affected objects
                      </p>
                      <div className="mt-1 flex flex-wrap gap-1">
                        {report.gateRejection.affectedObjects.map((obj) => (
                          <span
                            key={obj}
                            className="rounded-full bg-amber-100 px-3 py-1 font-mono text-xs text-amber-900"
                          >
                            {obj}
                          </span>
                        ))}
                      </div>
                    </div>
                    <div className="grid grid-cols-2 gap-2 text-xs text-slate-500">
                      <div>
                        <span className="font-semibold uppercase tracking-[0.14em]">Rejected by</span>
                        <p className="mt-0.5 font-mono">{report.gateRejection.rejectedBy ?? "—"}</p>
                      </div>
                      <div>
                        <span className="font-semibold uppercase tracking-[0.14em]">Rejected at</span>
                        <p className="mt-0.5 font-mono">{report.gateRejection.rejectedAt.slice(0, 16).replace("T", " ")}</p>
                      </div>
                    </div>
                    {report.gateRejection.notes ? (
                      <div>
                        <p className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-400">Notes</p>
                        <p className="mt-1">{report.gateRejection.notes}</p>
                      </div>
                    ) : null}
                  </div>
                ) : (
                  <p className="mt-3 text-sm text-slate-500">No rejection data.</p>
                )}
              </div>

              <div className="rounded-2xl border border-outline-variant bg-white p-4">
                <div className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">
                  Replay Scope
                </div>
                <div className="mt-3 space-y-2">
                  {report === null || report.replayScope.length === 0 ? (
                    <p className="text-sm text-slate-500">No other runs are affected.</p>
                  ) : (
                    report.replayScope.map((runId) => (
                      <div
                        key={runId}
                        className="rounded-xl border border-outline-variant bg-surface px-3 py-2 font-mono text-sm text-slate-700"
                      >
                        {runId}
                      </div>
                    ))
                  )}
                </div>
              </div>

              <div className="rounded-2xl border border-outline-variant bg-white p-4">
                <div className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">
                  AI Recommendation
                </div>
                {report ? (
                  <div className="mt-3 space-y-3 text-sm text-slate-700">
                    <div>
                      <p className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-400">
                        Recommendation
                      </p>
                      <p className="mt-1">{report.aiRecommendation.recommendation}</p>
                    </div>
                    <div>
                      <p className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-400">
                        Suggested fix
                      </p>
                      <p className="mt-1 whitespace-pre-line">{report.aiRecommendation.suggestedFix}</p>
                    </div>
                    {report.aiRecommendation.minimalReplayScope.length > 0 ? (
                      <div>
                        <p className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-400">
                          Minimal replay scope
                        </p>
                        <div className="mt-1 flex flex-wrap gap-1">
                          {report.aiRecommendation.minimalReplayScope.map((obj) => (
                            <span
                              key={obj}
                              className="rounded-full bg-slate-100 px-3 py-1 font-mono text-xs text-slate-700"
                            >
                              {obj}
                            </span>
                          ))}
                        </div>
                      </div>
                    ) : null}
                  </div>
                ) : (
                  <p className="mt-3 text-sm text-slate-500">No recommendation available.</p>
                )}
              </div>
            </div>
          )}
        </div>
      </section>
    </main>
  );
}
