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
import { addProjectMember, listProjectMembers, listUsers, removeProjectMember, type ProjectMemberResponse, type UserResponse } from "../../../lib/management-api";
import { getProject, projectErrorMessage, type ProjectRecord } from "../../../lib/projects-api";
import { loadUiSession, type SessionRole, type UiSession } from "../../../lib/session";
import { ProjectMembersPanel, type ProjectMember } from "../../../components/ProjectMembersPanel";

export default function ProjectDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { id } = use(params);
  const initialTab = searchParams.get("tab");
  const [session, setSession] = useState<UiSession | null>(null);
  const [project, setProject] = useState<ProjectRecord | null>(null);
  const [modelDefaults, setModelDefaults] = useState<(AIModelDefaultsRecord["migrationModels"] & AIModelDefaultsRecord["platformModels"]) | null>(null);
  const [activeTab, setActiveTab] = useState<"overview" | "feeds" | "artifacts" | "members">(
    initialTab === "feeds" || initialTab === "sources" ? "feeds" : initialTab === "artifacts" ? "artifacts" : "overview",
  );
  const [loading, setLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [members, setMembers] = useState<ProjectMember[]>([]);
  const [memberWarning, setMemberWarning] = useState<string | undefined>();
  const [allUsers, setAllUsers] = useState<UserResponse[]>([]);

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
          setModelDefaults({ ...response.migrationModels, ...response.platformModels });
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

  function joinMembers(memberRows: ProjectMemberResponse[], users: UserResponse[]): ProjectMember[] {
    return memberRows.map((m) => {
      const user = users.find((u) => u.userId === m.userId);
      return {
        projectId: m.projectId,
        userId: m.userId,
        displayName: user?.displayName ?? null,
        email: user?.email ?? m.userId,
        role: user?.role ?? "project_stakeholder",
        status: user?.status ?? "active",
      };
    });
  }

  async function refreshMembers(token: string) {
    const [memberRows, users] = await Promise.all([
      listProjectMembers(token, id),
      listUsers(token),
    ]);
    setAllUsers(users);
    setMembers(joinMembers(memberRows, users));
  }

  useEffect(() => {
    if (!session || activeTab !== "members") return;
    void refreshMembers(session.accessToken);
  }, [session, activeTab]); // eslint-disable-line react-hooks/exhaustive-deps

  const role: SessionRole = session?.role ?? "read_only_auditor";
  const navigationActiveTab = activeTab === "overview" || activeTab === "feeds" || activeTab === "artifacts" || activeTab === "members" ? activeTab : "overview";

  const handleMemberAdd = async (userId: string) => {
    if (!session) return;
    const response = await addProjectMember(session.accessToken, id, userId);
    setMemberWarning(response.warning ?? undefined);
    await refreshMembers(session.accessToken);
  };

  const handleMemberRemove = async (userId: string) => {
    if (!session) return;
    await removeProjectMember(session.accessToken, id, userId);
    await refreshMembers(session.accessToken);
  };

  const handleFeedClick = (sourceDefinitionId: string) => {
    if (!session) return;
    if (session.role === "project_stakeholder") {
      router.push(`/projects/${id}/feeds/${sourceDefinitionId}/review`);
    } else {
      router.push(`/projects/${id}/feeds/${sourceDefinitionId}`);
    }
  };

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

          {role === "admin" ? (
            <Link
              className="rounded-md bg-primary px-4 py-2 text-sm font-semibold text-white"
              href={`/admin/projects/${id}/members`}
            >
              Manage Members & PM
            </Link>
          ) : null}
        </div>

        <ProjectNavigationTabs
          activeTab={navigationActiveTab}
          mode="detail"
          onTabChange={setActiveTab}
          projectId={id}
          role={role}
        />

        {activeTab === "members" && session ? (
          <ProjectMembersPanel
            availableUsers={allUsers.filter((u) => !members.some((m) => m.userId === u.userId))}
            members={members}
            onAdd={handleMemberAdd}
            onRemove={handleMemberRemove}
            projectId={id}
            warning={memberWarning}
          />
        ) : loading ? (
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
          ) : activeTab === "feeds" ? (
            <SourceList
              projectId={id}
              role={role}
              token={session.accessToken}
              onFeedClick={handleFeedClick}
            />
          ) : (
            <SourceArtifactsPanel projectId={id} role={role} token={session.accessToken} />
          )
        ) : null}
      </section>
    </main>
  );
}
