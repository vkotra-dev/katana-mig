"use client";

import type { ProjectRecord } from "../../lib/projects-api";

export interface ProjectDetailViewProps {
  project: ProjectRecord;
}

function formatDate(value: string | null): string {
  return value ? value.slice(0, 10) : "—";
}

function displayValue(value: string | number | boolean | null | undefined): string {
  if (value === null || value === undefined) {
    return "—";
  }
  return String(value);
}

function getStatusClassName(status: ProjectRecord["status"]): string {
  return status === "archived"
    ? "bg-surface-dim text-neutral"
    : "bg-primary-container text-on-primary-container";
}

function KeyValue({
  label,
  value,
}: {
  label: string;
  value: string;
}) {
  return (
    <div className="space-y-1 rounded-xl border border-outline-variant bg-surface px-4 py-3">
      <div className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">{label}</div>
      <div className="whitespace-pre-wrap text-sm text-slate-900">{value}</div>
    </div>
  );
}

export function ProjectDetailView({ project }: ProjectDetailViewProps) {
  const domainConfig = project.domainConfig;

  return (
    <section className="space-y-6 rounded-2xl border border-outline-variant bg-surface-container p-6 shadow-sm">
      <div className="space-y-3">
        <div className="flex flex-wrap items-center gap-3">
          <h1 className="text-2xl font-semibold text-slate-900">{project.name}</h1>
          <span className="mono-id">{project.projectId}</span>
          <span className={`status-chip inline-flex items-center ${getStatusClassName(project.status)}`}>
            {project.status}
          </span>
        </div>
        <div className="text-sm text-slate-600">
          Created {formatDate(project.createdAt)} · Updated {formatDate(project.updatedAt)}
          {project.archivedAt ? ` · Archived ${formatDate(project.archivedAt)}` : ""}
        </div>
      </div>

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        <KeyValue label="Goal" value={project.goal ?? "—"} />
        <KeyValue
          label="Environments"
          value={project.executionEnvironments?.join(" → ") ?? "—"}
        />
        <KeyValue label="Target DB engine" value={domainConfig?.targetDbEngine ?? "—"} />
        <KeyValue
          label="Staging schema"
          value={domainConfig?.stagingSchema ?? "—"}
        />
        <KeyValue label="Dry run" value={displayValue(domainConfig?.dryRun)} />
        <KeyValue
          label="Destination schema DDL"
          value={domainConfig?.destinationSchemaDdl ?? "—"}
        />
        <KeyValue
          label="Sample policy"
          value={domainConfig?.samplePolicy ? JSON.stringify(domainConfig.samplePolicy) : "—"}
        />
        <KeyValue
          label="Constraints"
          value={project.constraints?.join(", ") ?? "—"}
        />
        <KeyValue
          label="Unresolved questions"
          value={project.unresolvedQuestions?.join("; ") ?? "—"}
        />
        <KeyValue label="Assumptions" value={project.assumptions?.join("; ") ?? "—"} />
        <KeyValue
          label="Lexicon scope"
          value={project.lexiconScope ? JSON.stringify(project.lexiconScope) : "—"}
        />
        <KeyValue
          label="Environment"
          value={project.environment ?? "—"}
        />
      </div>
    </section>
  );
}
