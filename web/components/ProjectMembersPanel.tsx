"use client";

import { useState, useRef, useEffect } from "react";
import type { UserRole, UserStatus } from "./UserForm";
import type { UserResponse } from "../lib/management-api";

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
  availableUsers: UserResponse[];
  warning?: string;
  loading?: boolean;
  onAdd: (userId: string) => Promise<void> | void;
  onRemove: (userId: string) => Promise<void> | void;
}

export function ProjectMembersPanel({
  projectId,
  members,
  availableUsers,
  warning,
  loading = false,
  onAdd,
  onRemove,
}: ProjectMembersPanelProps) {
  const [query, setQuery] = useState("");
  const [isOpen, setIsOpen] = useState(false);
  const [highlightedIndex, setHighlightedIndex] = useState(0);
  const containerRef = useRef<HTMLDivElement>(null);

  const filtered = availableUsers.filter((user) => {
    const q = query.toLowerCase();
    return (
      user.email.toLowerCase().includes(q) ||
      (user.displayName ?? "").toLowerCase().includes(q)
    );
  });

  const selectUser = (userId: string) => {
    void onAdd(userId);
    setQuery("");
    setIsOpen(false);
  };

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const handleKeyDown = (event: React.KeyboardEvent<HTMLInputElement>) => {
    if (!isOpen) {
      if (event.key === "ArrowDown" || event.key === "ArrowUp") {
        setIsOpen(true);
        setHighlightedIndex(0);
        event.preventDefault();
      }
      return;
    }

    switch (event.key) {
      case "ArrowDown":
        setHighlightedIndex((prev) => (filtered.length > 0 ? (prev + 1) % filtered.length : 0));
        event.preventDefault();
        break;
      case "ArrowUp":
        setHighlightedIndex((prev) => (filtered.length > 0 ? (prev - 1 + filtered.length) % filtered.length : 0));
        event.preventDefault();
        break;
      case "Enter":
        if (filtered.length > 0 && highlightedIndex >= 0 && highlightedIndex < filtered.length) {
          selectUser(filtered[highlightedIndex].userId);
          event.preventDefault();
        }
        break;
      case "Escape":
        setIsOpen(false);
        event.preventDefault();
        break;
    }
  };

  return (
    <section className="space-y-4 rounded-2xl border border-outline-variant bg-surface-container p-6 shadow-sm">
      <div className="space-y-1">
        <h2 className="text-lg font-semibold text-slate-900">Project members</h2>
        <p className="text-sm text-slate-600">Manage stakeholders for project {projectId}.</p>
      </div>

      <div ref={containerRef} className="relative flex gap-3">
        <div className="relative flex-1">
          <input
            className="w-full rounded-md border border-outline-variant bg-white px-3 py-3 text-sm text-slate-900 focus:outline-none focus:ring-2 focus:ring-primary/20"
            name="userId"
            onBlur={() => {
              // Delay slightly so click events on list items fire before blur closes it
              setTimeout(() => setIsOpen(false), 200);
            }}
            onChange={(event) => {
              setQuery(event.target.value);
              setIsOpen(true);
              setHighlightedIndex(0);
            }}
            onFocus={() => setIsOpen(true)}
            onKeyDown={handleKeyDown}
            placeholder="Search users by email or name..."
            type="text"
            value={query}
          />
          {isOpen && filtered.length > 0 && (
            <ul className="absolute left-0 right-0 z-50 mt-1 max-h-60 overflow-auto rounded-md border border-outline-variant bg-white py-1 shadow-lg">
              {filtered.map((user, index) => {
                const label = `${user.email} — ${user.displayName ?? "No display name"} (${user.role})`;
                const isHighlighted = index === highlightedIndex;
                return (
                  <li
                    key={user.userId}
                    className={`cursor-pointer px-4 py-2 text-sm text-slate-900 ${
                      isHighlighted ? "bg-primary/10 font-semibold" : "hover:bg-slate-50"
                    }`}
                    onClick={() => selectUser(user.userId)}
                  >
                    {label}
                  </li>
                );
              })}
            </ul>
          )}
        </div>
      </div>

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
