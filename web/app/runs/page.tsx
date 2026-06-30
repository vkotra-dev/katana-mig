"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Topbar } from "../../components/Topbar";
import { LaunchRunDialog } from "../../components/runs/LaunchRunDialog";
import { RunStatusChip, runStatusLabel } from "../../components/runs/RunStatusChip";
import { listProjects, type ProjectRecord } from "../../lib/projects-api";
import { listRuns, resumeRun, type RunRecord } from "../../lib/runs-api";
import { getUiSession, type SessionRole, type UiSession } from "../../lib/session";

type ReconciliationStatus = "reconciled" | "failed" | "n/a";

function formatTimestamp(value: string | null): string {
  return value ? value.slice(0, 16).replace("T", " ") : "—";
}

function reconciliationStatusForRun(run: RunRecord): ReconciliationStatus {
  if (run.status === "completed") {
    return "reconciled";
  }
  if (run.status === "failed") {
    return "failed";
  }
  return "n/a";
}

function reconciliationChipClassName(status: ReconciliationStatus): string {
  if (status === "reconciled") {
    return "bg-emerald-100 text-emerald-700";
  }
  if (status === "failed") {
    return "bg-red-100 text-red-700";
  }
  return "bg-slate-100 text-slate-600";
}

export default function RunsPage() {
  const router = useRouter();
  const [session, setSession] = useState<UiSession | null>(null);
  const [projects, setProjects] = useState<ProjectRecord[]>([]);
  const [runs, setRuns] = useState<RunRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [projectFilter, setProjectFilter] = useState("all");
  const [environmentFilter, setEnvironmentFilter] = useState("all");
  const [statusFilter, setStatusFilter] = useState("all");
  const [objectFilter, setObjectFilter] = useState("");
  const [searchTerm, setSearchTerm] = useState("");
  const [resumingRunId, setResumingRunId] = useState<string | null>(null);

  useEffect(() => {
    setSession(getUiSession());
  }, []);

  useEffect(() => {
    if (!session) {
      setLoading(false);
      return;
    }

    let active = true;
    setLoading(true);
    setErrorMessage(null);

    const loadRuns = async () => {
      try {
        const nextProjects = await listProjects(session.accessToken);
        const nextRuns = (
          await Promise.all(
            nextProjects.map(async (project) => {
              return await listRuns(session.accessToken, project.projectId);
            }),
          )
        ).flat();
        if (!active) {
          return;
        }
        setProjects(nextProjects);
        setRuns(nextRuns);
      } catch (error) {
        if (active) {
          setErrorMessage(error instanceof Error ? error.message : "Unable to load runs.");
        }
      } finally {
        if (active) {
          setLoading(false);
        }
      }
    };

    void loadRuns();

    return () => {
      active = false;
    };
  }, [session]);

  const role: SessionRole = session?.role ?? "read_only_auditor";
  const canLaunch = role === "central_team";

  const projectById = useMemo(
    () => new Map(projects.map((project) => [project.projectId, project])),
    [projects],
  );

  const filteredRuns = useMemo(() => {
    const lowerSearch = searchTerm.trim().toLowerCase();
    return runs
      .filter((run) => projectFilter === "all" || run.project_id === projectFilter)
      .filter((run) => environmentFilter === "all" || (run.environment ?? "—") === environmentFilter)
      .filter((run) => statusFilter === "all" || run.status === statusFilter)
      .filter((run) => !objectFilter || run.destination_object_name.toLowerCase().includes(objectFilter.toLowerCase()))
      .filter((run) => {
        if (!lowerSearch) {
          return true;
        }
        const project = projectById.get(run.project_id);
        return [
          run.run_id,
          run.destination_object_name,
          run.current_stage ?? "",
          project?.name ?? "",
          run.status,
        ]
          .join(" ")
          .toLowerCase()
          .includes(lowerSearch);
      })
      .sort((left, right) => right.created_at.localeCompare(left.created_at));
  }, [environmentFilter, objectFilter, projectById, projectFilter, runs, searchTerm, statusFilter]);

  const distinctEnvironments = useMemo(
    () =>
      Array.from(
        new Set(runs.map((run) => run.environment).filter((value): value is string => Boolean(value))),
      ),
    [runs],
  );

  const handleResume = async (run: RunRecord) => {
    if (!session) {
      return;
    }

    setResumingRunId(run.run_id);
    try {
      const resumed = await resumeRun(session.accessToken, run.project_id, run.run_id);
      setRuns((current) => current.map((item) => (item.run_id === resumed.run_id ? resumed : item)));
    } finally {
      setResumingRunId(null);
    }
  };

  return (
    <main className="flex min-h-screen flex-col bg-surface text-slate-800">
      <Topbar role={role} />
      <section className="mx-auto flex w-full max-w-[1600px] flex-1 flex-col gap-4 px-6 py-6">
        <div className="rounded-2xl border border-outline-variant bg-surface-container p-6 shadow-sm">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">Runs</p>
              <h1 className="text-3xl font-semibold tracking-tight text-slate-900">Runs</h1>
              <p className="mt-1 text-sm text-slate-600">
                Cross-project run list with launch, pause, resume, and reconciliation status.
              </p>
            </div>
            {canLaunch ? (
              <button
                className="rounded-md bg-primary px-4 py-3 text-sm font-semibold text-white"
                onClick={() => setDialogOpen(true)}
                type="button"
              >
                Launch run
              </button>
            ) : null}
          </div>

          <div className="mt-5 flex items-center justify-between gap-4 rounded-xl border border-outline-variant bg-white px-4 py-3">
            <div className="space-y-1">
              <div className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">Context</div>
              <div className="text-sm text-slate-700">
                {projectFilter === "all"
                  ? "All accessible projects"
                  : `Project: ${projectById.get(projectFilter)?.name ?? projectFilter}`}
              </div>
            </div>
            <select
              className="min-w-56 rounded-md border border-outline-variant bg-surface px-3 py-2 text-sm text-slate-900"
              onChange={(event) => setProjectFilter(event.currentTarget.value)}
              value={projectFilter}
            >
              <option value="all">All projects</option>
              {projects.map((project) => (
                <option key={project.projectId} value={project.projectId}>
                  {project.name}
                </option>
              ))}
            </select>
          </div>

          <div className="mt-4 grid gap-3 lg:grid-cols-5">
            <label className="space-y-2">
              <span className="block text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">Project</span>
              <select
                className="w-full rounded-md border border-outline-variant bg-white px-3 py-2 text-sm text-slate-900"
                onChange={(event) => setProjectFilter(event.currentTarget.value)}
                value={projectFilter}
              >
                <option value="all">All projects</option>
                {projects.map((project) => (
                  <option key={project.projectId} value={project.projectId}>
                    {project.name}
                  </option>
                ))}
              </select>
            </label>
            <label className="space-y-2">
              <span className="block text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">Environment</span>
              <select
                className="w-full rounded-md border border-outline-variant bg-white px-3 py-2 text-sm text-slate-900"
                onChange={(event) => setEnvironmentFilter(event.currentTarget.value)}
                value={environmentFilter}
              >
                <option value="all">All environments</option>
                {distinctEnvironments.map((environmentValue) => (
                  <option key={environmentValue} value={environmentValue}>
                    {environmentValue}
                  </option>
                ))}
              </select>
            </label>
            <label className="space-y-2">
              <span className="block text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">Status</span>
              <select
                className="w-full rounded-md border border-outline-variant bg-white px-3 py-2 text-sm text-slate-900"
                onChange={(event) => setStatusFilter(event.currentTarget.value)}
                value={statusFilter}
              >
                <option value="all">All statuses</option>
                {(["queued", "running", "paused", "awaiting_approval", "completed", "failed"] as const).map(
                  (status) => (
                    <option key={status} value={status}>
                      {runStatusLabel(status)}
                    </option>
                  ),
                )}
              </select>
            </label>
            <label className="space-y-2">
              <span className="block text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">Object</span>
              <input
                className="w-full rounded-md border border-outline-variant bg-white px-3 py-2 text-sm text-slate-900"
                onChange={(event) => setObjectFilter(event.currentTarget.value)}
                placeholder="Customer"
                value={objectFilter}
              />
            </label>
            <label className="space-y-2">
              <span className="block text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">Search</span>
              <input
                className="w-full rounded-md border border-outline-variant bg-white px-3 py-2 text-sm text-slate-900"
                onChange={(event) => setSearchTerm(event.currentTarget.value)}
                placeholder="run id, project, stage"
                value={searchTerm}
              />
            </label>
          </div>
        </div>

        {loading ? (
          <div className="rounded-2xl border border-outline-variant bg-surface-container p-6 shadow-sm">
            <div className="space-y-3">
              <div className="h-4 w-40 animate-pulse rounded bg-slate-200" />
              <div className="h-10 w-full animate-pulse rounded bg-slate-100" />
              <div className="h-10 w-full animate-pulse rounded bg-slate-100" />
              <div className="h-10 w-full animate-pulse rounded bg-slate-100" />
            </div>
          </div>
        ) : errorMessage ? (
          <div role="alert" className="rounded-2xl border border-error/30 bg-error/10 px-4 py-3 text-sm text-error">
            {errorMessage}
          </div>
        ) : filteredRuns.length === 0 ? (
          <div className="rounded-2xl border border-dashed border-outline-variant bg-surface-container px-6 py-12 text-center text-sm text-slate-600">
            No runs yet.
          </div>
        ) : (
          <div className="overflow-hidden rounded-2xl border border-outline-variant bg-surface-container shadow-sm">
            <table className="w-full border-collapse text-left">
              <thead className="bg-surface">
                <tr className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">
                  <th className="px-4 py-3">Run ID</th>
                  <th className="px-4 py-3">Project</th>
                  <th className="px-4 py-3">Destination object</th>
                  <th className="px-4 py-3">Environment</th>
                  <th className="px-4 py-3">Status</th>
                  <th className="px-4 py-3">Current stage</th>
                  <th className="px-4 py-3">Started</th>
                  <th className="px-4 py-3">Last checkpoint</th>
                  <th className="px-4 py-3">Reconciliation status</th>
                </tr>
              </thead>
              <tbody>
                {filteredRuns.map((run) => {
                  const project = projectById.get(run.project_id);
                  const reconciliationStatus = reconciliationStatusForRun(run);
                  const canResume = canLaunch && ["paused", "awaiting_approval"].includes(run.status);

                  return (
                    <tr key={run.run_id} className="group border-t border-outline-variant hover:bg-slate-50">
                      <td className="px-4 py-4 align-top">
                        <div className="space-y-2">
                          <div className="font-mono text-sm text-slate-900">{run.run_id}</div>
                          <div className="flex items-center gap-3 text-xs text-slate-500 opacity-0 transition group-hover:opacity-100">
                            <Link className="font-semibold text-primary hover:underline" href={`/runs/${run.run_id}?projectId=${run.project_id}`}>
                              Open
                            </Link>
                            {canResume ? (
                              <button
                                className="font-semibold text-primary hover:underline disabled:opacity-50"
                                disabled={resumingRunId === run.run_id}
                                onClick={() => void handleResume(run)}
                                type="button"
                              >
                                {resumingRunId === run.run_id ? "Resuming..." : "Resume"}
                              </button>
                            ) : null}
                          </div>
                        </div>
                      </td>
                      <td className="px-4 py-4 align-top">
                        <Link className="text-sm font-semibold text-slate-900 hover:underline" href={`/projects/${run.project_id}`}>
                          {project?.name ?? run.project_id}
                        </Link>
                      </td>
                      <td className="px-4 py-4 align-top text-sm text-slate-700">{run.destination_object_name}</td>
                      <td className="px-4 py-4 align-top">
                        <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold uppercase tracking-[0.16em] text-slate-600">
                          {run.environment ?? "—"}
                        </span>
                      </td>
                      <td className="px-4 py-4 align-top">
                        <RunStatusChip status={run.status} />
                      </td>
                      <td className="px-4 py-4 align-top text-sm text-slate-700">{run.current_stage ?? "—"}</td>
                      <td className="px-4 py-4 align-top font-mono text-sm text-slate-700">
                        {formatTimestamp(run.started_at)}
                      </td>
                      <td className="px-4 py-4 align-top font-mono text-sm text-slate-700">
                        {formatTimestamp(run.last_checkpoint_at)}
                      </td>
                      <td className="px-4 py-4 align-top">
                        <span className={`status-chip inline-flex items-center ${reconciliationChipClassName(reconciliationStatus)}`}>
                          {reconciliationStatus}
                        </span>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <LaunchRunDialog
        initialProjectId={projectFilter !== "all" ? projectFilter : null}
        onClose={() => setDialogOpen(false)}
        onSuccess={async (run) => {
          setDialogOpen(false);
          router.push(`/runs/${run.run_id}?projectId=${run.project_id}`);
        }}
        open={dialogOpen}
      />
    </main>
  );
}
