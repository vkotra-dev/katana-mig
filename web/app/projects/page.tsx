"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Topbar } from "../../components/Topbar";
import { CreateProjectDialog } from "../../components/projects/CreateProjectDialog";
import { ProjectTable } from "../../components/projects/ProjectTable";
import { listProjects, projectErrorMessage, type ProjectRecord } from "../../lib/projects-api";
import { loadUiSession, type SessionRole, type UiSession } from "../../lib/session";

export default function ProjectsPage() {
  const router = useRouter();
  const [session, setSession] = useState<UiSession | null>(null);
  const [projects, setProjects] = useState<ProjectRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [dialogOpen, setDialogOpen] = useState(false);

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
    </main>
  );
}
