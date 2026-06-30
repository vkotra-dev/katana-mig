"use client";

import { useState } from "react";
import type { UserRole, UserStatus } from "./UserForm";

export interface ProjectMember {
  projectId: string;
  userId: string;
  displayName: string | null;
  email: string;
  role: UserRole;
  status: UserStatus;
  warning?: string | null;
}

export interface ProjectMembersPanelProps {
  projectId: string;
  members: ProjectMember[];
  warning?: string;
  loading?: boolean;
  onAdd: (userId: string) => Promise<void> | void;
  onRemove: (userId: string) => Promise<void> | void;
}

export function ProjectMembersPanel({
  projectId,
  members,
  warning,
  loading = false,
  onAdd,
  onRemove,
}: ProjectMembersPanelProps) {
  const [userId, setUserId] = useState("");

  return (
    <section className="space-y-4 rounded-2xl border border-outline-variant bg-surface-container p-6 shadow-sm">
      <div className="space-y-1">
        <h2 className="text-lg font-semibold text-slate-900">Project members</h2>
        <p className="text-sm text-slate-600">Manage stakeholders for project {projectId}.</p>
      </div>

      <form
        className="flex gap-3"
        onSubmit={(event) => {
          event.preventDefault();
          void onAdd(userId);
          setUserId("");
        }}
      >
        <input
          className="flex-1 rounded-md border border-outline-variant bg-white px-3 py-3 text-sm text-slate-900"
          name="userId"
          onChange={(event) => setUserId(event.target.value)}
          placeholder="User ID"
          value={userId}
        />
        <button
          className="rounded-md bg-primary px-4 py-3 text-sm font-semibold text-white disabled:opacity-60"
          disabled={loading}
          type="submit"
        >
          Add member
        </button>
      </form>

      {warning ? (
        <p className="rounded-md border border-warning/30 bg-warning/10 px-3 py-2 text-sm text-slate-800" role="status">
          {warning}
        </p>
      ) : null}

      <ul className="space-y-2">
        {members.map((member) => (
          <li key={`${member.projectId}:${member.userId}`} className="flex items-center justify-between rounded-md border border-outline-variant px-4 py-3">
            <div>
              <div className="text-sm font-semibold text-slate-900">{member.email}</div>
              <div className="text-xs text-slate-500">
                {member.displayName ?? "No display name"} · {member.role} · {member.status}
              </div>
            </div>
            <button
              className="rounded-md border border-outline-variant px-3 py-2 text-sm text-slate-700"
              onClick={() => void onRemove(member.userId)}
              type="button"
            >
              Remove
            </button>
          </li>
        ))}
      </ul>
    </section>
  );
}
