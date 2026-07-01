"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { Topbar } from "../../components/Topbar";
import { CreateProjectDialog } from "../../components/projects/CreateProjectDialog";
import { PortfolioTable } from "../../components/portfolio/PortfolioTable";
import { SummaryStrip } from "../../components/portfolio/SummaryStrip";
import { getPendingApprovalCount } from "../../lib/feed-slice-approval-api";
import { listProjects, projectErrorMessage, type ProjectRecord } from "../../lib/projects-api";
import { loadUiSession, type SessionRole, type UiSession } from "../../lib/session";

export default function DashboardPage() {
  const router = useRouter();
  const [session, setSession] = useState<UiSession | null>(null);
  const [projects, setProjects] = useState<ProjectRecord[]>([]);
  const [pendingApprovals, setPendingApprovals] = useState(0);
  const [loading, setLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [dialogOpen, setDialogOpen] = useState(false);

  useEffect(() => {
    const current = loadUiSession();
    if (!current) {
      router.replace("/");
      return;
    }
    setSession(current);
  }, [router]);

  useEffect(() => {
    if (!session) {
      return;
    }

    let active = true;
    setLoading(true);
    setErrorMessage(null);

    void Promise.all([
      listProjects(session.accessToken, { includeArchived: true }),
      getPendingApprovalCount(session.accessToken),
    ])
      .then(([allProjects, count]) => {
        if (!active) {
          return;
        }
        setProjects(allProjects);
        setPendingApprovals(count);
      })
      .catch((error: unknown) => {
        if (!active) {
          return;
        }
        setErrorMessage(projectErrorMessage(error));
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

  const summary = useMemo(() => {
    const activeProjects = projects.filter((project) => project.status === "active").length;
    const archivedProjects = projects.filter((project) => project.status === "archived").length;
    return {
      activeProjects,
      archivedProjects,
      total: projects.length,
    };
  }, [projects]);

  if (!session) {
    return null;
  }

  return (
    <main className="flex min-h-screen flex-col bg-surface text-slate-800">
      <Topbar role={role} />
      <section className="mx-auto flex w-full max-w-[1600px] flex-1 flex-col gap-6 px-6 py-6">
        {loading ? (
          <div className="rounded-2xl border border-outline-variant bg-surface-container p-8 text-sm text-slate-600">
            Loading portfolio...
          </div>
        ) : errorMessage ? (
          <div
            role="alert"
            className="rounded-2xl border border-error/30 bg-error/10 px-4 py-3 text-sm text-error"
          >
            {errorMessage}
          </div>
        ) : (
          <>
            <SummaryStrip
              active={summary.activeProjects}
              archived={summary.archivedProjects}
              pendingApprovals={pendingApprovals}
              total={summary.total}
            />
            <PortfolioTable
              onInitiate={() => {
                setDialogOpen(true);
              }}
              projects={projects}
              role={role}
            />
          </>
        )}
      </section>
      <CreateProjectDialog
        onClose={() => {
          setDialogOpen(false);
        }}
        onCreated={(project) => {
          setProjects((current) => [project, ...current]);
          setDialogOpen(false);
          router.push(`/projects/${project.projectId}`);
        }}
        open={dialogOpen}
        token={session.accessToken}
      />
    </main>
  );
}
