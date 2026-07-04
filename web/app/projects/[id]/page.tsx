"use client";

import { use, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Topbar } from "../../../components/Topbar";
import { ProjectNavigationTabs } from "../../../components/projects/ProjectNavigationTabs";
import { KnowledgeFreezePanel } from "../../../components/projects/KnowledgeFreezePanel";
import { ProjectDetailView } from "../../../components/projects/ProjectDetailView";
import { SourceArtifactsPanel } from "../../../components/projects/SourceArtifactsPanel";
import { SourceList } from "../../../components/projects/SourceList";
import { getAiModelDefaults, type AIModelDefaultsRecord } from "../../../lib/ai-model-defaults-api";
import { getProject, projectErrorMessage, type ProjectRecord } from "../../../lib/projects-api";
import { loadUiSession, type SessionRole, type UiSession } from "../../../lib/session";

export default function ProjectDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { id } = use(params);
  const initialTab = searchParams.get("tab");
  const [session, setSession] = useState<UiSession | null>(null);
  const [project, setProject] = useState<ProjectRecord | null>(null);
  const [modelDefaults, setModelDefaults] = useState<AIModelDefaultsRecord["migrationModels"] | null>(null);
  const [activeTab, setActiveTab] = useState<"overview" | "sources" | "artifacts">(
    initialTab === "sources" || initialTab === "artifacts" ? initialTab : "overview",
  );
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

  useEffect(() => {
    if (!session) {
      setModelDefaults(null);
      return;
    }

    let active = true;

    void getAiModelDefaults(session.accessToken)
      .then((response) => {
        if (active) {
          setModelDefaults(response.migrationModels);
        }
      })
      .catch(() => {
        if (active) {
          setModelDefaults(null);
        }
      });

    return () => {
      active = false;
    };
  }, [session]);

  const role: SessionRole = session?.role ?? "read_only_auditor";
  const navigationActiveTab = activeTab === "overview" || activeTab === "sources" || activeTab === "artifacts" ? activeTab : "overview";

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

          {role === "central_team" ? (
            <Link
              className="rounded-md bg-primary px-4 py-2 text-sm font-semibold text-white"
              href={`/projects/${id}/edit`}
            >
              Edit
            </Link>
          ) : null}
        </div>

        <ProjectNavigationTabs
          activeTab={navigationActiveTab}
          mode="detail"
          onTabChange={setActiveTab}
          projectId={id}
        />

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
            <div className="space-y-4">
              <ProjectDetailView modelDefaults={modelDefaults} project={project} />
              <KnowledgeFreezePanel projectId={id} token={session.accessToken} />
            </div>
          ) : activeTab === "sources" ? (
            <SourceList
              projectId={id}
              role={role}
              token={session.accessToken}
              destinationSchemaDdl={project?.domainConfig?.destinationSchemaDdl ?? null}
            />
          ) : (
            <SourceArtifactsPanel projectId={id} role={role} token={session.accessToken} />
          )
        ) : null}
      </section>
    </main>
  );
}
