"use client";

import { useMemo, useState } from "react";
import type { SessionRole } from "../../lib/session";
import type { ProjectRecord } from "../../lib/projects-api";

export interface ProjectTableProps {
  projects: ProjectRecord[];
  role: SessionRole;
  onInitiate?: () => void;
}

type SortKey = "name" | "createdAt" | "status";
type SortDirection = "asc" | "desc";

function formatDate(value: string): string {
  return value.slice(0, 10);
}

function statusClassName(status: ProjectRecord["status"]): string {
  return status === "archived"
    ? "bg-surface-dim text-neutral"
    : "bg-primary-container text-on-primary-container";
}

function compareValues(
  left: ProjectRecord,
  right: ProjectRecord,
  key: SortKey,
): number {
  switch (key) {
    case "createdAt":
      return left.createdAt.localeCompare(right.createdAt);
    case "status":
      return left.status.localeCompare(right.status);
    case "name":
    default:
      return left.name.localeCompare(right.name);
  }
}

export function ProjectTable({ projects, role, onInitiate }: ProjectTableProps) {
  const [sortKey, setSortKey] = useState<SortKey>("name");
  const [sortDirection, setSortDirection] = useState<SortDirection>("asc");

  const sortedProjects = useMemo(() => {
    const next = [...projects].sort((left, right) => compareValues(left, right, sortKey));
    return sortDirection === "asc" ? next : next.reverse();
  }, [projects, sortDirection, sortKey]);

  const canCreate = role !== "read_only_auditor";

  return (
    <section className="space-y-4 rounded-2xl border border-outline-variant bg-surface-container p-6 shadow-sm">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold text-slate-900">Projects</h1>
          <p className="text-sm text-slate-600">Browse active and archived migration projects.</p>
        </div>
        {canCreate && onInitiate ? (
          <button
            className="rounded-md bg-primary px-4 py-2 text-sm font-semibold text-white hover:opacity-95"
            onClick={onInitiate}
            type="button"
          >
            Initiate project
          </button>
        ) : null}
      </div>

      {projects.length === 0 ? (
        <div className="rounded-xl border border-dashed border-outline-variant px-6 py-12 text-center text-sm text-slate-600">
          No projects found.
        </div>
      ) : (
        <div className="overflow-hidden rounded-xl border border-outline-variant">
          <table className="w-full border-collapse">
            <thead className="bg-surface">
              <tr className="text-left text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">
                <th className="px-4 py-3">
                  <button
                    className="inline-flex items-center gap-1"
                    onClick={() => {
                      if (sortKey === "name") {
                        setSortDirection((current) => (current === "asc" ? "desc" : "asc"));
                      } else {
                        setSortKey("name");
                        setSortDirection("asc");
                      }
                    }}
                    type="button"
                  >
                    Name
                  </button>
                </th>
                <th className="px-4 py-3">Goal</th>
                <th className="px-4 py-3">Constraints</th>
                <th className="px-4 py-3">Environments</th>
                <th className="px-4 py-3">
                  <button
                    className="inline-flex items-center gap-1"
                    onClick={() => {
                      if (sortKey === "status") {
                        setSortDirection((current) => (current === "asc" ? "desc" : "asc"));
                      } else {
                        setSortKey("status");
                        setSortDirection("asc");
                      }
                    }}
                    type="button"
                  >
                    Status
                  </button>
                </th>
                <th className="px-4 py-3">
                  <button
                    className="inline-flex items-center gap-1"
                    onClick={() => {
                      if (sortKey === "createdAt") {
                        setSortDirection((current) => (current === "asc" ? "desc" : "asc"));
                      } else {
                        setSortKey("createdAt");
                        setSortDirection("desc");
                      }
                    }}
                    type="button"
                  >
                    Created
                  </button>
                </th>
              </tr>
            </thead>
            <tbody>
              {sortedProjects.map((project) => (
                <tr key={project.projectId} className="border-t border-outline-variant">
                  <td className="px-4 py-4 align-top">
                    <div className="space-y-1">
                      <a
                        className="font-semibold text-slate-900 hover:underline"
                        href={`/projects/${project.projectId}`}
                      >
                        {project.name}
                      </a>
                      <div className="mono-id text-xs">{project.projectId}</div>
                    </div>
                  </td>
                  <td className="px-4 py-4 align-top text-sm text-slate-700">
                    {project.goal ?? "—"}
                  </td>
                  <td className="px-4 py-4 align-top text-sm text-slate-700">
                    {project.constraints?.join(", ") ?? "—"}
                  </td>
                  <td className="px-4 py-4 align-top text-sm text-slate-700">
                    {project.executionEnvironments?.join(" → ") ?? "—"}
                  </td>
                  <td className="px-4 py-4 align-top">
                    <span
                      className={`status-chip inline-flex items-center ${statusClassName(project.status)}`}
                    >
                      {project.status}
                    </span>
                  </td>
                  <td className="px-4 py-4 align-top text-sm text-slate-700">
                    {formatDate(project.createdAt)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
