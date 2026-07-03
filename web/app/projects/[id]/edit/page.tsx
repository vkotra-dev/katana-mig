"use client";

import { use, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { Topbar } from "../../../../components/Topbar";
import { ProjectEditForm } from "../../../../components/projects/ProjectEditForm";
import {
  getProject,
  projectErrorMessage,
  updateProject,
  type ProjectRecord,
  type ProjectUpdateInput,
} from "../../../../lib/projects-api";
import { loadUiSession, type SessionRole } from "../../../../lib/session";

export default function ProjectEditPage({ params }: { params: Promise<{ id: string }> }) {
  const router = useRouter();
  const session = useMemo(() => loadUiSession(), []);
  const { id } = use(params);
  const [project, setProject] = useState<ProjectRecord | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

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

  const handleSubmit = async (value: ProjectUpdateInput) => {
    if (!session) {
      return;
    }

    setSaving(true);
    setErrorMessage(null);

    try {
      const next = await updateProject(session.accessToken, id, value);
      router.push(`/projects/${next.projectId}`);
    } catch (error) {
      setErrorMessage(projectErrorMessage(error));
    } finally {
      setSaving(false);
    }
  };

  const role: SessionRole = session?.role ?? "read_only_auditor";

  return (
    <main className="flex min-h-screen flex-col bg-surface text-slate-800">
      <Topbar role={role} />
      <section className="mx-auto flex w-full max-w-[1600px] flex-1 flex-col gap-4 px-6 py-6">
        <div className="flex items-center justify-between">
          <button
            className="rounded-md border border-outline-variant bg-surface-container px-3 py-2 text-sm font-medium text-slate-700 hover:bg-outline-variant"
            onClick={() => router.push(`/projects/${id}`)}
            type="button"
          >
            Back to project
          </button>
        </div>

        {loading ? (
          <div className="rounded-2xl border border-outline-variant bg-surface-container p-8 text-sm text-slate-600">
            Loading project...
          </div>
        ) : project ? (
          <ProjectEditForm
            errorMessage={errorMessage ?? undefined}
            loading={saving}
            onSubmit={handleSubmit}
            project={project}
          />
        ) : errorMessage ? (
          <div role="alert" className="rounded-2xl border border-error/30 bg-error/10 px-4 py-3 text-sm text-error">
            {errorMessage}
          </div>
        ) : null}
      </section>
    </main>
  );
}
