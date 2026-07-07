"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Topbar } from "../../components/Topbar";
import { CreateProjectDialog } from "../../components/projects/CreateProjectDialog";
import { ProjectTable } from "../../components/projects/ProjectTable";
import { listProjects, projectErrorMessage, copyProject, type ProjectRecord } from "../../lib/projects-api";
import { loadUiSession, type SessionRole, type UiSession } from "../../lib/session";

export default function ProjectsPage() {
  const router = useRouter();
  const [session, setSession] = useState<UiSession | null>(null);
  const [projects, setProjects] = useState<ProjectRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [dialogOpen, setDialogOpen] = useState(false);

  const [copyModalStep, setCopyModalStep] = useState<0 | 1 | 2>(0); // 0 = closed
  const [copySourceProject, setCopySourceProject] = useState<ProjectRecord | null>(null);
  const [copyName, setCopyName] = useState("");
  const [copySearch, setCopySearch] = useState("");
  const [copySubmitting, setCopySubmitting] = useState(false);
  const [copyStakeholders, setCopyStakeholders] = useState("");

  useEffect(() => {
    setSession(loadUiSession());
  }, []);

  useEffect(() => {
    if (!session) {
      setLoading(false);
      return;
    }

    let active = true;
    setLoading(true);
    setErrorMessage(null);

    void listProjects(session.accessToken)
      .then((response) => {
        if (active) {
          setProjects(response);
        }
      })
      .catch((error: unknown) => {
        if (active) {
          setErrorMessage(projectErrorMessage(error));
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
  }, [session]);

  const handleCopyProject = async () => {
    if (!copySourceProject || !copyName.trim() || !session?.accessToken) return;
    setCopySubmitting(true);
    setErrorMessage(null);
    try {
      const stakeholderIds = copyStakeholders
        ? copyStakeholders.split(",").map((s) => s.trim()).filter(Boolean)
        : [];
      const newProject = await copyProject(session.accessToken, copySourceProject.projectId, {
        name: copyName.trim(),
        stakeholderUserIds: stakeholderIds,
      });
      setCopyModalStep(0);
      setCopyStakeholders("");
      router.push(`/projects/${newProject.projectId}`);
    } catch (err) {
      setErrorMessage("Failed to copy project.");
      setCopySubmitting(false);
    }
  };

  const role: SessionRole = session?.role ?? "read_only_auditor";

  return (
    <main className="flex min-h-screen flex-col bg-surface text-slate-800">
      <Topbar role={role} />
      <section className="mx-auto flex w-full max-w-[1600px] flex-1 flex-col gap-4 px-6 py-6">
        {loading ? (
          <div className="rounded-2xl border border-outline-variant bg-surface-container p-8 text-sm text-slate-600">
            Loading projects...
          </div>
        ) : errorMessage ? (
          <div role="alert" className="rounded-2xl border border-error/30 bg-error/10 px-4 py-3 text-sm text-error">
            {errorMessage}
          </div>
        ) : (
          <ProjectTable
            onInitiate={() => setDialogOpen(true)}
            onCopyClick={() => setCopyModalStep(1)}
            projects={projects}
            role={role}
          />
        )}
      </section>

      <CreateProjectDialog
        onClose={() => setDialogOpen(false)}
        onCreated={(project) => {
          setProjects((current) => [project, ...current]);
          setDialogOpen(false);
          router.push(`/projects/${project.projectId}`);
        }}
        open={dialogOpen}
        token={session?.accessToken ?? ""}
      />

      {copyModalStep > 0 && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
          <div className="w-full max-w-md rounded-2xl bg-white p-6 shadow-xl space-y-4">
            {copyModalStep === 1 && (
              <>
                <h2 className="text-base font-bold text-slate-900">Copy from project</h2>
                <input
                  type="search"
                  placeholder="Search projects…"
                  value={copySearch}
                  onChange={(e) => setCopySearch(e.target.value)}
                  className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-800 placeholder-slate-400 focus:border-primary focus:ring-1 focus:ring-primary focus:outline-none"
                />
                <ul className="max-h-60 overflow-y-auto divide-y divide-outline-variant border border-outline-variant rounded-lg">
                  {projects
                    .filter(
                      (p) =>
                        p.status !== "archived" &&
                        p.name.toLowerCase().includes(copySearch.toLowerCase()),
                    )
                    .map((p) => (
                      <li key={p.projectId}>
                        <button
                          type="button"
                          onClick={() => {
                            setCopySourceProject(p);
                            setCopyName(`Copy of ${p.name}`);
                            setCopyModalStep(2);
                          }}
                          className="w-full px-4 py-2.5 text-left text-sm text-slate-700 hover:bg-slate-50 transition"
                        >
                          {p.name}
                        </button>
                      </li>
                    ))}
                </ul>
                <div className="flex justify-end">
                  <button
                    type="button"
                    onClick={() => setCopyModalStep(0)}
                    className="text-sm font-semibold text-slate-500 hover:text-slate-700"
                  >
                    Cancel
                  </button>
                </div>
              </>
            )}

            {copyModalStep === 2 && copySourceProject && (
              <>
                <h2 className="text-base font-bold text-slate-900">
                  Copy "{copySourceProject.name}"
                </h2>
                <div className="space-y-3">
                  <div>
                    <label className="text-xs font-semibold text-slate-600 block mb-1">New project name</label>
                    <input
                      type="text"
                      value={copyName}
                      onChange={(e) => setCopyName(e.target.value)}
                      className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-800 focus:border-primary focus:ring-1 focus:ring-primary focus:outline-none"
                    />
                  </div>
                  <div>
                    <label className="text-xs font-semibold text-slate-600 block mb-1">
                      Stakeholders (Optional, comma-separated User IDs)
                    </label>
                    <input
                      type="text"
                      placeholder="e.g. user-1, user-2"
                      value={copyStakeholders}
                      onChange={(e) => setCopyStakeholders(e.target.value)}
                      className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-800 focus:border-primary focus:ring-1 focus:ring-primary focus:outline-none"
                    />
                  </div>
                  <p className="text-xs text-slate-500 leading-normal">
                    💡 Stakeholders from the source project are not carried over automatically. Define new stakeholders above or assign them later.
                  </p>
                </div>
                <div className="flex justify-end gap-3 pt-2">
                  <button
                    type="button"
                    onClick={() => setCopyModalStep(1)}
                    className="rounded-lg border border-slate-200 px-4 py-2 text-sm font-semibold text-slate-600 hover:bg-slate-50 transition"
                  >
                    Back
                  </button>
                  <button
                    type="button"
                    disabled={!copyName.trim() || copySubmitting}
                    onClick={handleCopyProject}
                    className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white disabled:opacity-40 hover:bg-indigo-700 transition"
                  >
                    {copySubmitting ? "Copying…" : "Copy project"}
                  </button>
                </div>
              </>
            )}
          </div>
        </div>
      )}
    </main>
  );
}
