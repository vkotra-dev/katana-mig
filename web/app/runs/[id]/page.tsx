"use client";

import { useEffect, useState, type ReactNode } from "react";
import Link from "next/link";
import { useParams, useSearchParams } from "next/navigation";
import { Topbar } from "../../../components/Topbar";
import { RunStatusChip } from "../../../components/runs/RunStatusChip";
import { listProjects, type ProjectRecord } from "../../../lib/projects-api";
import { getRun, listCheckpoints, listRuns, resumeRun, type RunCheckpoint, type RunRecord } from "../../../lib/runs-api";
import { getUiSession, type SessionRole, type UiSession } from "../../../lib/session";

type DetailTab = "overview" | "snapshots" | "checkpoints" | "timeline" | "lineage";

function formatTimestamp(value: string | null): string {
  return value ? value.slice(0, 19).replace("T", " ") : "—";
}

function copyText(value: string): void {
  void navigator.clipboard?.writeText(value);
}

function keyValueLabel(label: string, value: ReactNode): ReactNode {
  return (
    <div className="rounded-xl border border-outline-variant bg-white px-4 py-3">
      <div className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">{label}</div>
      <div className="mt-2 text-sm text-slate-700">{value}</div>
    </div>
  );
}

function snapshotPill(label: string, value: string | null, href?: string): ReactNode {
  const content = (
    <span className="rounded-full bg-slate-100 px-3 py-1 font-mono text-sm text-slate-700">
      {value ?? "—"}
    </span>
  );

  return (
    <div className="rounded-xl border border-outline-variant bg-white px-4 py-4">
      <div className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">{label}</div>
      <div className="mt-2 flex items-center gap-2">
        {href && value ? <Link href={href}>{content}</Link> : content}
        {value ? (
          <button className="text-xs font-semibold text-primary" onClick={() => copyText(value)} type="button">
            Copy
          </button>
        ) : null}
      </div>
    </div>
  );
}

function reconciliationStatus(status: RunRecord["status"]): { label: string; className: string } {
  if (status === "completed") {
    return { label: "reconciled", className: "bg-emerald-100 text-emerald-700" };
  }
  if (status === "failed") {
    return { label: "failed", className: "bg-red-100 text-red-700" };
  }
  return { label: "n/a", className: "bg-slate-100 text-slate-600" };
}

function pausedReason(run: RunRecord): string | null {
  return (run.pause_metadata?.pause_reason as string | undefined) ?? null;
}

function failureReason(run: RunRecord): string | null {
  return (run.completion_metadata?.failure_reason as string | undefined) ?? null;
}

function isPausedLike(status: RunRecord["status"]): boolean {
  return status === "paused" || status === "awaiting_approval";
}

function timelineEvents(run: RunRecord, checkpoints: RunCheckpoint[]): Array<{ label: string; timestamp: string | null; detail?: string }> {
  const events: Array<{ label: string; timestamp: string | null; detail?: string }> = [
    { label: "Created", timestamp: run.created_at },
    { label: "Started", timestamp: run.started_at, detail: run.start_metadata ? JSON.stringify(run.start_metadata) : undefined },
    ...checkpoints.map((checkpoint) => ({
      label: `Checkpoint ${checkpoint.last_completed_row ?? "—"}`,
      timestamp: checkpoint.created_at,
      detail: checkpoint.pause_reason ?? undefined,
    })),
  ];

  if (run.pause_metadata) {
    events.push({
      label: "Paused",
      timestamp: (run.pause_metadata.paused_at as string | undefined) ?? null,
      detail: pausedReason(run) ?? undefined,
    });
  }

  if (run.resume_metadata) {
    events.push({
      label: "Resumed",
      timestamp: (run.resume_metadata.resumed_at as string | undefined) ?? null,
      detail: run.resume_metadata ? JSON.stringify(run.resume_metadata) : undefined,
    });
  }

  if (run.completion_metadata) {
    events.push({
      label: run.status === "failed" ? "Failed" : "Completed",
      timestamp: run.updated_at,
      detail: JSON.stringify(run.completion_metadata),
    });
  }

  return events.sort((left, right) => (left.timestamp ?? "").localeCompare(right.timestamp ?? ""));
}

export default function RunDetailPage() {
  const params = useParams<{ id: string }>();
  const searchParams = useSearchParams();
  const runId = params.id;
  const projectIdParam = searchParams.get("projectId");
  const [session, setSession] = useState<UiSession | null>(null);
  const [projects, setProjects] = useState<ProjectRecord[]>([]);
  const [projectId, setProjectId] = useState<string | null>(projectIdParam);
  const [projectName, setProjectName] = useState<string | null>(null);
  const [run, setRun] = useState<RunRecord | null>(null);
  const [checkpoints, setCheckpoints] = useState<RunCheckpoint[]>([]);
  const [tab, setTab] = useState<DetailTab>("overview");
  const [loading, setLoading] = useState(true);
  const [refreshNonce, setRefreshNonce] = useState(0);
  const [lastUpdated, setLastUpdated] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [resuming, setResuming] = useState(false);

  useEffect(() => {
    setSession(getUiSession());
  }, []);

  const role: SessionRole = session?.role ?? "read_only_auditor";
  const canResume = role === "central_team" && isPausedLike(run?.status ?? "queued");

  const load = async () => {
    if (!session || !runId) {
      return;
    }

    setLoading(true);
    setErrorMessage(null);
    try {
      const visibleProjects = await listProjects(session.accessToken);
      setProjects(visibleProjects);
      const projectSearchSpace = projectIdParam
        ? visibleProjects.filter((project) => project.projectId === projectIdParam)
        : visibleProjects;

      let resolvedProjectId = projectIdParam;
      let resolvedRun: RunRecord | null = null;

      if (resolvedProjectId) {
        resolvedRun = await getRun(session.accessToken, resolvedProjectId, runId);
      } else {
        for (const project of projectSearchSpace) {
          const projectRuns = await listRuns(session.accessToken, project.projectId);
          const found = projectRuns.find((item) => item.run_id === runId);
          if (found) {
            resolvedProjectId = project.projectId;
            resolvedRun = found;
            break;
          }
        }
      }

      if (!resolvedProjectId || !resolvedRun) {
        throw new Error("Run not found.");
      }

      const nextCheckpoints = await listCheckpoints(session.accessToken, resolvedProjectId, runId);
      if (!resolvedRun.last_checkpoint_at && nextCheckpoints.length > 0) {
        resolvedRun = {
          ...resolvedRun,
          last_checkpoint_at: nextCheckpoints[nextCheckpoints.length - 1]?.created_at ?? resolvedRun.last_checkpoint_at,
        };
      }
      setProjectId(resolvedProjectId);
      setProjectName(visibleProjects.find((project) => project.projectId === resolvedProjectId)?.name ?? resolvedProjectId);
      setRun(resolvedRun);
      setCheckpoints(nextCheckpoints);
      setLastUpdated(new Date().toISOString());
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Unable to load run.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [session, runId, projectIdParam, refreshNonce]);

  useEffect(() => {
    if (!run || run.status !== "running") {
      return;
    }

    const timer = window.setInterval(() => {
      setRefreshNonce((current) => current + 1);
    }, 10_000);

    return () => {
      window.clearInterval(timer);
    };
  }, [run?.status]);

  const refresh = () => setRefreshNonce((current) => current + 1);

  const handleResume = async () => {
    if (!session || !projectId || !run) {
      return;
    }

    setResuming(true);
    setErrorMessage(null);
    try {
      const resumed = await resumeRun(session.accessToken, projectId, run.run_id);
      setRun(resumed);
      setRefreshNonce((current) => current + 1);
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Resume failed.");
    } finally {
      setResuming(false);
    }
  };

  const activeCheckpoint = checkpoints[checkpoints.length - 1] ?? null;
  const reconciliation = run ? reconciliationStatus(run.status) : null;
  const pausedBannerReason = run ? pausedReason(run) : null;
  const failedBannerReason = run ? failureReason(run) : null;
  const budgetExhausted =
    run?.completion_metadata?.completion_reason === "budget_exhausted" ||
    run?.pause_metadata?.pause_reason === "budget_exhausted";

  return (
    <main className="flex min-h-screen flex-col bg-surface text-slate-800">
      <Topbar role={role} />
      <section className="mx-auto flex w-full max-w-[1600px] flex-1 flex-col gap-4 px-6 py-6">
        <div className="rounded-2xl border border-outline-variant bg-surface-container p-6 shadow-sm">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div className="space-y-3">
              <div className="flex flex-wrap items-center gap-3">
                <button
                  className="font-mono text-sm text-slate-600 hover:text-primary"
                  onClick={() => copyText(run?.run_id ?? runId)}
                  type="button"
                >
                  {run?.run_id ?? runId}
                </button>
                <RunStatusChip status={run?.status ?? "queued"} />
              </div>
              <div className="flex flex-wrap items-center gap-3 text-sm text-slate-700">
                <Link className="font-semibold text-primary hover:underline" href={`/projects/${projectId ?? projectIdParam ?? ""}`}>
                  {projectName ?? projectId ?? projectIdParam ?? "Project"}
                </Link>
                <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold uppercase tracking-[0.16em] text-slate-600">
                  {run?.destination_object_name ?? "—"}
                </span>
                <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold uppercase tracking-[0.16em] text-slate-600">
                  {run?.environment ?? "—"}
                </span>
              </div>
              <div className="flex flex-wrap items-center gap-3 text-sm text-slate-600">
                <span>
                  Started <span className="font-mono">{formatTimestamp(run?.started_at ?? null)}</span>
                </span>
                <span>
                  Last checkpoint <span className="font-mono">{formatTimestamp(run?.last_checkpoint_at ?? null)}</span>
                </span>
                {lastUpdated ? (
                  <span>
                    Last updated <span className="font-mono">{formatTimestamp(lastUpdated)}</span>
                  </span>
                ) : null}
                {run?.status === "running" ? (
                  <span className="rounded-full bg-blue-100 px-3 py-1 text-xs font-semibold uppercase tracking-[0.16em] text-blue-700">
                    Auto-refresh every 10s
                  </span>
                ) : null}
              </div>
            </div>
            {canResume ? (
              <button
                className="rounded-md bg-primary px-4 py-3 text-sm font-semibold text-white disabled:opacity-60"
                disabled={resuming}
                onClick={() => void handleResume()}
                type="button"
              >
                {resuming ? "Resuming..." : "Resume"}
              </button>
            ) : null}
          </div>

          <div className="mt-5">
            <div className="flex items-center gap-2 rounded-xl border border-outline-variant bg-white px-4 py-3">
              {[
                { label: "Queue state", active: run?.status === "queued" || !run, tone: "gray" },
                { label: "Active stage", active: Boolean(run?.current_stage), tone: "blue" },
                { label: "Completion", active: run?.status === "completed", tone: "green" },
              ].map((item) => (
                <div key={item.label} className="flex items-center gap-2">
                  <span
                    className={`rounded-full px-3 py-1 text-xs font-semibold uppercase tracking-[0.16em] ${
                      item.active ? "bg-slate-900 text-white" : "bg-slate-100 text-slate-500"
                    }`}
                  >
                    {item.label}
                  </span>
                  <span className="text-xs text-slate-500">{item.label === "Active stage" ? run?.current_stage ?? "—" : ""}</span>
                </div>
              ))}
            </div>
          </div>

          {run && isPausedLike(run.status) ? (
            <div className="mt-4 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <div className="text-sm font-semibold text-amber-900">
                    {run.status === "awaiting_approval" ? "Awaiting approval" : "Paused"}
                  </div>
                  <div className="mt-1 text-sm text-amber-900">
                    {pausedBannerReason ?? "Awaiting human approval."}
                  </div>
                </div>
                {canResume ? (
                  <button
                    className="rounded-md bg-primary px-4 py-2 text-sm font-semibold text-white disabled:opacity-60"
                    disabled={resuming}
                    onClick={() => void handleResume()}
                    type="button"
                  >
                    {resuming ? "Resuming..." : "Resume"}
                  </button>
                ) : null}
              </div>
            </div>
          ) : null}

          {run?.status === "failed" ? (
            <div className="mt-4 rounded-xl border border-red-200 bg-red-50 px-4 py-3">
              <div className="text-sm font-semibold text-red-900">Failed</div>
              <div className="mt-1 text-sm text-red-900">{failedBannerReason ?? "Execution failed."}</div>
            </div>
          ) : null}

          {budgetExhausted ? (
            <div className="mt-4 rounded-xl border border-slate-200 bg-slate-50 px-4 py-3">
              <div className="text-sm font-semibold text-slate-900">Budget exhausted</div>
              <div className="mt-1 text-sm text-slate-700">Execution stopped gracefully.</div>
            </div>
          ) : null}

          <div className="mt-5 flex flex-wrap gap-2 border-b border-outline-variant pb-3">
            {[
              ["overview", "Overview"],
              ["snapshots", "Pinned snapshots"],
              ["checkpoints", "Checkpoints"],
              ["timeline", "Timeline"],
              ["lineage", "Reconciliation & lineage"],
            ].map(([value, label]) => (
              <button
                key={value}
                className={`rounded-full px-4 py-2 text-sm font-semibold ${
                  tab === value ? "bg-primary text-white" : "bg-slate-100 text-slate-600"
                }`}
                onClick={() => setTab(value as DetailTab)}
                type="button"
              >
                {label}
              </button>
            ))}
            <button
              className="ml-auto rounded-md border border-outline-variant px-4 py-2 text-sm text-slate-700"
              onClick={refresh}
              type="button"
            >
              Refresh
            </button>
          </div>

          {loading ? (
            <div className="py-10 text-sm text-slate-600">Loading run...</div>
          ) : errorMessage ? (
            <div role="alert" className="mt-4 rounded-xl border border-error/30 bg-error/10 px-4 py-3 text-sm text-error">
              {errorMessage}
            </div>
          ) : run ? (
            <div className="mt-5">
              {tab === "overview" ? (
                <div className="grid gap-4 md:grid-cols-2">
                  {keyValueLabel("Status", <RunStatusChip status={run.status} />)}
                  {keyValueLabel("Current stage", run.current_stage ?? "—")}
                  {keyValueLabel("Current object", run.destination_object_name)}
                  {keyValueLabel("Environment", run.environment ?? "—")}
                  {keyValueLabel("Start metadata", <pre className="whitespace-pre-wrap font-mono text-xs text-slate-700">{run.start_metadata ? JSON.stringify(run.start_metadata, null, 2) : "—"}</pre>)}
                  {keyValueLabel("Pause metadata", <pre className="whitespace-pre-wrap font-mono text-xs text-slate-700">{run.pause_metadata ? JSON.stringify(run.pause_metadata, null, 2) : "—"}</pre>)}
                  {keyValueLabel("Resume metadata", <pre className="whitespace-pre-wrap font-mono text-xs text-slate-700">{run.resume_metadata ? JSON.stringify(run.resume_metadata, null, 2) : "—"}</pre>)}
                  {keyValueLabel("Completion metadata", <pre className="whitespace-pre-wrap font-mono text-xs text-slate-700">{run.completion_metadata ? JSON.stringify(run.completion_metadata, null, 2) : "—"}</pre>)}
                </div>
              ) : null}

              {tab === "snapshots" ? (
                <div className="grid gap-4 md:grid-cols-2">
                  {snapshotPill("Source slice", run.source_slice_version)}
                  {snapshotPill("Mapping", run.mapping_snapshot_version)}
                  {snapshotPill("Lookup", run.lookup_snapshot_version ?? (run.lookup_snapshot_versions ? "multiple" : null))}
                  {run.lookup_snapshot_versions ? (
                    <div className="rounded-xl border border-outline-variant bg-white px-4 py-4 md:col-span-2">
                      <div className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">Lookup versions</div>
                      <pre className="mt-2 whitespace-pre-wrap font-mono text-sm text-slate-700">
                        {JSON.stringify(run.lookup_snapshot_versions, null, 2)}
                      </pre>
                    </div>
                  ) : null}
                  {snapshotPill(
                    "Codegen artifact",
                    run.codegen_artifact_id ? `cga_${run.codegen_artifact_id.slice(0, 8)}` : null,
                    run.codegen_artifact_id && projectId
                      ? `/projects/${projectId}/codegen-artifacts/${run.codegen_artifact_id}`
                      : undefined,
                  )}
                  {snapshotPill("Knowledge freeze", run.knowledge_freeze_version)}
                  {snapshotPill("Codegen input", run.code_generation_input_snapshot_version)}
                </div>
              ) : null}

              {tab === "checkpoints" ? (
                <div className="overflow-hidden rounded-xl border border-outline-variant bg-white">
                  <table className="w-full border-collapse text-left">
                    <thead className="bg-surface">
                      <tr className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">
                        <th className="px-4 py-3">Stage</th>
                        <th className="px-4 py-3">Object</th>
                        <th className="px-4 py-3">Environment</th>
                        <th className="px-4 py-3">Selected snapshots</th>
                        <th className="px-4 py-3">Last completed boundary</th>
                        <th className="px-4 py-3">Pause reason</th>
                      </tr>
                    </thead>
                    <tbody>
                      {checkpoints.length === 0 ? (
                        <tr>
                          <td className="px-4 py-6 text-sm text-slate-600" colSpan={6}>
                            No checkpoints yet.
                          </td>
                        </tr>
                      ) : (
                        checkpoints.map((checkpoint) => {
                          const isResumePoint = activeCheckpoint?.checkpoint_id === checkpoint.checkpoint_id;
                          return (
                            <tr
                              key={checkpoint.checkpoint_id}
                              className={isResumePoint ? "border-t border-outline-variant bg-amber-50" : "border-t border-outline-variant"}
                            >
                              <td className="px-4 py-4 text-sm text-slate-700">{checkpoint.stage ?? "—"}</td>
                              <td className="px-4 py-4 text-sm text-slate-700">{checkpoint.current_object ?? "—"}</td>
                              <td className="px-4 py-4 text-sm text-slate-700">{checkpoint.current_environment ?? "—"}</td>
                              <td className="px-4 py-4 text-xs text-slate-700">
                                <pre className="whitespace-pre-wrap font-mono">{JSON.stringify(checkpoint.approved_snapshots ?? {}, null, 2)}</pre>
                              </td>
                              <td className="px-4 py-4 font-mono text-sm text-slate-700">
                                {checkpoint.last_completed_row ?? "—"}
                              </td>
                              <td className="px-4 py-4 text-sm text-slate-700">{checkpoint.pause_reason ?? "—"}</td>
                            </tr>
                          );
                        })
                      )}
                    </tbody>
                  </table>
                </div>
              ) : null}

              {tab === "timeline" ? (
                <div className="overflow-hidden rounded-xl border border-outline-variant bg-white">
                  <ul>
                    {timelineEvents(run, checkpoints).map((event, index) => (
                      <li key={`${event.label}-${index}`} className="border-t border-outline-variant px-4 py-4 first:border-t-0">
                        <div className="flex items-start justify-between gap-4">
                          <div>
                            <div className="text-sm font-semibold text-slate-900">{event.label}</div>
                            {event.detail ? <div className="mt-1 text-sm text-slate-600">{event.detail}</div> : null}
                          </div>
                          <div className="font-mono text-sm text-slate-600">{formatTimestamp(event.timestamp)}</div>
                        </div>
                      </li>
                    ))}
                  </ul>
                </div>
              ) : null}

              {tab === "lineage" ? (
                <div className="space-y-4 rounded-xl border border-outline-variant bg-white px-4 py-4">
                  <div className="flex items-center justify-between">
                    <div>
                      <div className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">
                        Reconciliation status
                      </div>
                      <RunStatusChip status={run.status} />
                    </div>
                    {reconciliation ? (
                      <span className={`status-chip inline-flex items-center ${reconciliation.className}`}>
                        {reconciliation.label}
                      </span>
                    ) : null}
                  </div>
                  <div>
                    <Link className="text-sm font-semibold text-primary hover:underline" href={`/runs/${run.run_id}/reconciliation?projectId=${projectId ?? projectIdParam ?? ""}`}>
                      Open reconciliation view
                    </Link>
                  </div>
                </div>
              ) : null}
            </div>
          ) : null}
        </div>
      </section>
    </main>
  );
}
