"use client";

import { useEffect, useMemo, useState } from "react";
import { ProjectMembersPanel, type ProjectMember } from "../../../../../components/ProjectMembersPanel";
import {
  addProjectMember,
  listProjectMembers,
  listUsers,
  removeProjectMember,
  type ProjectMemberResponse,
  type UserResponse,
} from "../../../../../lib/management-api";
import { loadUiSession } from "../../../../../lib/session";

function joinMembers(
  members: ProjectMemberResponse[],
  users: UserResponse[],
): ProjectMember[] {
  return members.map((member) => {
    const user = users.find((candidate) => candidate.userId === member.userId);
    return {
      projectId: member.projectId,
      userId: member.userId,
      displayName: user?.displayName ?? null,
      email: user?.email ?? member.userId,
      role: user?.role ?? "project_stakeholder",
      status: user?.status ?? "active",
    };
  });
}

export default function ProjectMembersPage({ params }: any) {
  const session = useMemo(() => loadUiSession(), []);
  const [members, setMembers] = useState<ProjectMember[]>([]);
  const [warning, setWarning] = useState<string | undefined>();

  useEffect(() => {
    if (!session) {
      return;
    }

    void Promise.all([
      listProjectMembers(session.accessToken, params.projectId),
      listUsers(session.accessToken),
    ]).then(([projectMembers, users]) => {
      setMembers(joinMembers(projectMembers, users));
    });
  }, [params.projectId, session]);

  const refresh = async () => {
    if (!session) {
      return;
    }

    const [projectMembers, users] = await Promise.all([
      listProjectMembers(session.accessToken, params.projectId),
      listUsers(session.accessToken),
    ]);
    setMembers(joinMembers(projectMembers, users));
  };

  const handleAdd = async (userId: string) => {
    if (!session) {
      return;
    }

    const response = await addProjectMember(session.accessToken, params.projectId, userId);
    setWarning(response.warning ?? undefined);
    await refresh();
  };

  const handleRemove = async (userId: string) => {
    if (!session) {
      return;
    }

    await removeProjectMember(session.accessToken, params.projectId, userId);
    await refresh();
  };

  return (
    <main className="min-h-screen bg-surface px-6 py-8 text-slate-800">
      <div className="mx-auto max-w-4xl">
        <ProjectMembersPanel
          members={members}
          onAdd={handleAdd}
          onRemove={handleRemove}
          projectId={params.projectId}
          warning={warning}
        />
      </div>
    </main>
  );
}
