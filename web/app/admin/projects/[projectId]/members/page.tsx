"use client";

import { useEffect, useRef, useState } from "react";
import { ProjectMembersPanel, type ProjectMember } from "../../../../../components/ProjectMembersPanel";
import {
  addProjectMember,
  listProjectMembers,
  listUsers,
  removeProjectMember,
  type ProjectMemberResponse,
  type UserResponse,
} from "../../../../../lib/management-api";
import { loadUiSession, type UiSession } from "../../../../../lib/session";
import { getProject, assignProjectManager, type ProjectRecord } from "../../../../../lib/projects-api";

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
  const [session, setSession] = useState<UiSession | null>(null);
  const [members, setMembers] = useState<ProjectMember[]>([]);
  const [warning, setWarning] = useState<string | undefined>();
  const [project, setProject] = useState<ProjectRecord | null>(null);
  const [allUsers, setAllUsers] = useState<UserResponse[]>([]);
  const [pmQuery, setPmQuery] = useState("");
  const [pmOpen, setPmOpen] = useState(false);
  const pmContainerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    setSession(loadUiSession());
  }, []);

  useEffect(() => {
    if (!session) {
      return;
    }

    void Promise.all([
      getProject(session.accessToken, params.projectId),
      listProjectMembers(session.accessToken, params.projectId),
      listUsers(session.accessToken),
    ]).then(([proj, projectMembers, users]) => {
      setProject(proj);
      setAllUsers(users);
      setMembers(joinMembers(projectMembers, users));
    });
  }, [params.projectId, session]);

  const refresh = async () => {
    if (!session) {
      return;
    }

    const [proj, projectMembers, users] = await Promise.all([
      getProject(session.accessToken, params.projectId),
      listProjectMembers(session.accessToken, params.projectId),
      listUsers(session.accessToken),
    ]);
    setProject(proj);
    setAllUsers(users);
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

  const handleAssignPm = async (pmUserId: string) => {
    if (!session) return;
    const updated = await assignProjectManager(session.accessToken, params.projectId, pmUserId);
    setProject(updated);
    setPmQuery("");
    setPmOpen(false);
  };

  const currentPm = allUsers.find((u) => u.userId === project?.pmUserId);
  const pms = allUsers.filter((u) => u.role === "pm");
  const filteredPms = pms.filter((pm) => {
    const q = pmQuery.toLowerCase();
    return pm.email.toLowerCase().includes(q) || (pm.displayName ?? "").toLowerCase().includes(q);
  });

  const memberUserIds = new Set(members.map((m) => m.userId));
  const availableUsers = allUsers.filter(
    (u) =>
      u.role !== "admin" &&
      u.role !== "pm" &&
      !memberUserIds.has(u.userId)
  );

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (pmContainerRef.current && !pmContainerRef.current.contains(event.target as Node)) {
        setPmOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  return (
    <main className="min-h-screen bg-surface px-6 py-8 text-slate-800">
      <div className="mx-auto max-w-4xl space-y-6">
        <div className="space-y-4 rounded-2xl border border-outline-variant bg-surface-container p-6 shadow-sm">
          <div className="space-y-1">
            <h2 className="text-lg font-semibold text-slate-900">Project Manager</h2>
            <p className="text-sm text-slate-600">Assign the Project Manager who owns this project.</p>
          </div>
          <div className="flex items-center gap-4">
            <div className="text-sm text-slate-800">
              Current Manager:{" "}
              <span className="font-semibold">
                {currentPm
                  ? `${currentPm.displayName ?? "No display name"} (${currentPm.email})`
                  : "Unassigned"}
              </span>
            </div>
          </div>
          <div ref={pmContainerRef} className="relative max-w-md">
            <input
              className="w-full rounded-md border border-outline-variant bg-white px-3 py-2 text-sm text-slate-900 focus:outline-none focus:ring-2 focus:ring-primary/20"
              onBlur={() => {
                setTimeout(() => setPmOpen(false), 200);
              }}
              onChange={(e) => {
                setPmQuery(e.target.value);
                setPmOpen(true);
              }}
              onFocus={() => setPmOpen(true)}
              placeholder="Search Project Managers..."
              type="text"
              value={pmQuery}
            />
            {pmOpen && filteredPms.length > 0 && (
              <ul className="absolute left-0 right-0 z-50 mt-1 max-h-60 overflow-auto rounded-md border border-outline-variant bg-white py-1 shadow-lg">
                {filteredPms.map((pm) => (
                  <li
                    key={pm.userId}
                    className="cursor-pointer px-4 py-2 text-sm text-slate-900 hover:bg-slate-50"
                    onClick={() => handleAssignPm(pm.userId)}
                  >
                    {pm.email} — {pm.displayName ?? "No display name"}
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>

        <ProjectMembersPanel
          availableUsers={availableUsers}
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
