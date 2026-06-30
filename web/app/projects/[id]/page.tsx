"use client";

import { use, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Topbar } from "../../../components/Topbar";
import { ProjectDetailView } from "../../../components/projects/ProjectDetailView";
import { SourceArtifactsPanel } from "../../../components/projects/SourceArtifactsPanel";
import { SourceList } from "../../../components/projects/SourceList";
import { getProject, projectErrorMessage, type ProjectRecord } from "../../../lib/projects-api";
import { loadUiSession, type SessionRole, type UiSession } from "../../../lib/session";

export default function ProjectDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const router = useRouter();
  const { id } = use(params);
  const [session, setSession] = useState<UiSession | null>(null);
  const [project, setProject] = useState<ProjectRecord | null>(null);
  const [activeTab, setActiveTab] = useState<"overview" | "sources" | "artifacts">("overview");
  const [loading, setLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

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

    void getProject(session.accessToken, id)
      .then((response) => {
        if (active) {
          setProject(response);
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
  }, [id, session]);

  const role: SessionRole = session?.role ?? "read_only_auditor";

  return (
    <main className="flex min-h-screen flex-col bg-surface text-slate-800">
      <Topbar role={role} />
      <section className="mx-auto flex w-full max-w-[1600px] flex-1 flex-col gap-4 px-6 py-6">
        <div className="flex items-center justify-between">
          <button
            className="rounded-md border border-outline-variant bg-surface-container px-3 py-2 text-sm font-medium text-slate-700 hover:bg-outline-variant"
            onClick={() => router.push("/projects")}
            type="button"
          >
            Back to projects
          </button>
        </div>

        <div className="flex gap-2">
          <button
            className={`rounded-full px-4 py-2 text-sm font-semibold ${
              activeTab === "overview"
                ? "bg-primary text-white"
                : "border border-outline-variant bg-surface-container text-slate-700"
            }`}
            onClick={() => setActiveTab("overview")}
            type="button"
          >
            Overview
          </button>
          <button
            className={`rounded-full px-4 py-2 text-sm font-semibold ${
              activeTab === "sources"
                ? "bg-primary text-white"
                : "border border-outline-variant bg-surface-container text-slate-700"
            }`}
            onClick={() => setActiveTab("sources")}
            type="button"
            >
            Sources
          </button>
          <button
            className={`rounded-full px-4 py-2 text-sm font-semibold ${
              activeTab === "artifacts"
                ? "bg-primary text-white"
                : "border border-outline-variant bg-surface-container text-slate-700"
            }`}
            onClick={() => setActiveTab("artifacts")}
            type="button"
          >
            Artifacts
          </button>
        </div>

        {loading ? (
          <div className="rounded-2xl border border-outline-variant bg-surface-container p-8 text-sm text-slate-600">
            Loading project...
          </div>
        ) : errorMessage ? (
          <div role="alert" className="rounded-2xl border border-error/30 bg-error/10 px-4 py-3 text-sm text-error">
            {errorMessage}
          </div>
        ) : project && session ? (
          activeTab === "overview" ? (
            <ProjectDetailView project={project} />
          ) : activeTab === "sources" ? (
            <SourceList projectId={id} role={role} token={session.accessToken} />
          ) : (
            <SourceArtifactsPanel projectId={id} role={role} token={session.accessToken} />
          )
        ) : null}
      </section>
    </main>
  );
}
