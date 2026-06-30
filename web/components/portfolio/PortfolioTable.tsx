"use client";

import { useMemo, useState } from "react";
import type { ProjectRecord } from "../../lib/projects-api";
import type { SessionRole } from "../../lib/session";

export interface PortfolioTableProps {
  projects: ProjectRecord[];
  role: SessionRole;
  onInitiate?: () => void;
}

type SortKey = "name" | "updatedAt";
type SortDirection = "asc" | "desc";
type StatusFilter = "all" | "active" | "archived";

function formatDate(value: string): string {
  return value.slice(0, 10);
}

function truncate(value: string | null | undefined, maxLength: number): string {
  if (!value) {
    return "—";
  }
  if (value.length <= maxLength) {
    return value;
  }
  return `${value.slice(0, maxLength - 1)}…`;
}

function statusClassName(status: ProjectRecord["status"]): string {
  return status === "archived"
    ? "bg-surface-dim text-neutral"
    : "bg-primary-container text-on-primary-container";
}

export function PortfolioTable({ projects, role, onInitiate }: PortfolioTableProps) {
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("active");
  const [environmentFilter, setEnvironmentFilter] = useState("");
  const [sortKey, setSortKey] = useState<SortKey>("name");
  const [sortDirection, setSortDirection] = useState<SortDirection>("asc");

  const environmentOptions = useMemo(() => {
    const values = new Set<string>();
    for (const project of projects) {
      for (const environment of project.executionEnvironments ?? []) {
        values.add(environment);
      }
    }
    return [...values].sort((left, right) => left.localeCompare(right));
  }, [projects]);

  const filteredProjects = useMemo(() => {
    const query = search.trim().toLowerCase();
    return projects.filter((project) => {
      const searchable = `${project.name} ${project.projectId}`.toLowerCase();
      if (query && !searchable.includes(query)) {
        return false;
      }
      if (statusFilter !== "all" && project.status !== statusFilter) {
        return false;
      }
      if (
        environmentFilter &&
        !(project.executionEnvironments ?? []).includes(environmentFilter)
      ) {
        return false;
      }
      return true;
    });
  }, [environmentFilter, projects, search, statusFilter]);

  const sortedProjects = useMemo(() => {
    const next = [...filteredProjects].sort((left, right) => {
      const comparison =
        sortKey === "updatedAt"
          ? left.updatedAt.localeCompare(right.updatedAt)
          : left.name.localeCompare(right.name);
      return comparison;
    });
    return sortDirection === "asc" ? next : next.reverse();
  }, [filteredProjects, sortDirection, sortKey]);

  const canCreate = role !== "read_only_auditor";

  const toggleSort = (nextKey: SortKey) => {
    if (sortKey === nextKey) {
      setSortDirection((current) => (current === "asc" ? "desc" : "asc"));
      return;
    }

    setSortKey(nextKey);
    setSortDirection(nextKey === "updatedAt" ? "desc" : "asc");
  };

  return (
    <section className="space-y-4 rounded-2xl border border-outline-variant bg-surface-container p-6 shadow-sm">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold text-slate-900">Projects</h1>
          <p className="text-sm text-slate-600">Migration projects visible to your role.</p>
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

      <div className="flex flex-wrap items-center gap-3">
        <label className="block">
          <span className="sr-only">Search projects</span>
          <input
            aria-label="Search projects"
            className="min-w-56 rounded-md border border-outline-variant bg-surface px-3 py-2 text-sm text-slate-900 placeholder:text-slate-400 focus:outline-none focus:ring-1 focus:ring-primary"
            onChange={(event) => setSearch(event.currentTarget.value)}
            placeholder="Search by name or ID"
            type="search"
            value={search}
          />
        </label>

        <label className="block">
          <span className="sr-only">Filter by status</span>
          <select
            aria-label="Filter by status"
            className="rounded-md border border-outline-variant bg-surface px-3 py-2 text-sm text-slate-900 focus:outline-none focus:ring-1 focus:ring-primary"
            onChange={(event) => setStatusFilter(event.currentTarget.value as StatusFilter)}
            value={statusFilter}
          >
            <option value="all">All statuses</option>
            <option value="active">Active</option>
            <option value="archived">Archived</option>
          </select>
        </label>

        <label className="block">
          <span className="sr-only">Filter by environment</span>
          <select
            aria-label="Filter by environment"
            className="rounded-md border border-outline-variant bg-surface px-3 py-2 text-sm text-slate-900 focus:outline-none focus:ring-1 focus:ring-primary"
            onChange={(event) => setEnvironmentFilter(event.currentTarget.value)}
            value={environmentFilter}
          >
            <option value="">All environments</option>
            {environmentOptions.map((environment) => (
              <option key={environment} value={environment}>
                {environment}
              </option>
            ))}
          </select>
        </label>
      </div>

      {sortedProjects.length === 0 ? (
        <div className="rounded-xl border border-dashed border-outline-variant bg-surface px-4 py-10 text-sm text-slate-500">
          No matching projects.
        </div>
      ) : (
        <div className="overflow-hidden rounded-xl border border-outline-variant">
          <table className="w-full border-collapse">
            <thead className="bg-surface">
              <tr className="text-left text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">
                <th className="px-4 py-3">
                  <button
                    className="inline-flex items-center gap-1"
                    onClick={() => toggleSort("name")}
                    type="button"
                  >
                    Project
                  </button>
                </th>
                <th className="px-4 py-3">Goal</th>
                <th className="px-4 py-3">Target DB</th>
                <th className="px-4 py-3">Environments</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3">
                  <button
                    className="inline-flex items-center gap-1"
                    onClick={() => toggleSort("updatedAt")}
                    type="button"
                  >
                    Last Updated
                  </button>
                </th>
                <th className="px-4 py-3">Open Details</th>
              </tr>
            </thead>
            <tbody>
              {sortedProjects.map((project) => (
                <tr key={project.projectId} className="border-t border-outline-variant hover:bg-surface-container-lowest">
                  <td className="px-4 py-3 align-top">
                    <div className="space-y-0.5">
                      <a
                        className="font-semibold text-slate-900 hover:text-primary hover:underline"
                        href={`/projects/${project.projectId}`}
                      >
                        {project.name}
                      </a>
                      <div className="mono-id">{project.projectId}</div>
                    </div>
                  </td>
                  <td className="px-4 py-3 align-top text-sm text-slate-700">
                    {truncate(project.goal, 60)}
                  </td>
                  <td className="px-4 py-3 align-top text-sm text-slate-700">
                    {project.domainConfig?.targetDbEngine ?? "—"}
                  </td>
                  <td className="px-4 py-3 align-top text-sm text-slate-700">
                    {project.executionEnvironments && project.executionEnvironments.length > 0 ? (
                      <div className="flex flex-wrap gap-1.5">
                        {project.executionEnvironments.map((environment) => (
                          <span
                            key={environment}
                            className="rounded-full border border-outline-variant bg-surface px-2 py-0.5 text-xs text-slate-600"
                          >
                            {environment}
                          </span>
                        ))}
                      </div>
                    ) : (
                      "—"
                    )}
                  </td>
                  <td className="px-4 py-3 align-top">
                    <span className={`status-chip inline-flex items-center ${statusClassName(project.status)}`}>
                      {project.status}
                    </span>
                  </td>
                  <td className="px-4 py-3 align-top text-sm text-slate-700">
                    {formatDate(project.updatedAt)}
                  </td>
                  <td className="px-4 py-3 align-top">
                    <a
                      className="text-sm font-semibold text-primary hover:underline"
                      href={`/projects/${project.projectId}`}
                    >
                      Open
                    </a>
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
