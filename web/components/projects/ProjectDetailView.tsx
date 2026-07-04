"use client";

import type { AIModelDefaultsRecord } from "../../lib/ai-model-defaults-api";
import type { ProjectRecord, SamplePolicy } from "../../lib/projects-api";
import { StageTimeline } from "./StageTimeline";
import { MODEL_POLICY_FIELDS } from "./modelPolicyCatalog";

export interface ProjectDetailViewProps {
  project: ProjectRecord;
  modelDefaults?: AIModelDefaultsRecord["migrationModels"] | null;
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

function formatSamplePolicy(policy: SamplePolicy | null | undefined): string {
  if (!policy) {
    return "—";
  }

  const strategyLabels: Record<SamplePolicy["strategy"], string> = {
    random: "Random",
    top_n: "Top N",
    full: "Full",
    stratified: "Stratified",
  };

  const lines = [
    `Strategy: ${strategyLabels[policy.strategy]}`,
    `Max rows: ${policy.maxRows ?? "—"}`,
  ];

  if (policy.strategy === "stratified") {
    lines.push(`Stratified column: ${policy.stratifiedColumn ?? "—"}`);
  }

  return lines.join("\n");
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

export function ProjectDetailView({ project, modelDefaults = null }: ProjectDetailViewProps) {
  const domainConfig = project.domainConfig;
  const projectResources = project.projectResources ?? "";

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

      <StageTimeline latestRunSummary={project.latestRunSummary ?? null} />

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
        <KeyValue
          label="Destination schema"
          value={domainConfig?.destinationSchema ?? "—"}
        />
        <KeyValue label="Dry run" value={displayValue(domainConfig?.dryRun)} />
        <KeyValue
          label="Destination schema DDL"
          value={domainConfig?.destinationSchemaDdl ?? "—"}
        />
        <KeyValue
          label="Sample policy"
          value={formatSamplePolicy(domainConfig?.samplePolicy)}
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
      </div>

      <div className="space-y-3">
        <div className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">Model Policy</div>
        <div className="grid gap-4 lg:grid-cols-3">
          {MODEL_POLICY_FIELDS.map(({ key, label }) => {
            const overrideModel = project.modelPolicy?.[key];
            const effectiveModel = overrideModel ?? modelDefaults?.[key] ?? "Global default unavailable";
            const sourceLabel = overrideModel ? "Source: project override" : "Source: engine.yaml";

            return (
              <div className="space-y-1 rounded-xl border border-outline-variant bg-surface px-4 py-3" key={key}>
                <div className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">{label}</div>
                <div className="text-sm text-slate-900">{effectiveModel}</div>
                <div className="text-xs text-slate-500">{sourceLabel}</div>
              </div>
            );
          })}
        </div>
      </div>

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        <label className="space-y-1 rounded-xl border border-outline-variant bg-surface px-4 py-3 md:col-span-2 xl:col-span-3">
          <div className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">
            Project Resources
          </div>
          <textarea
            aria-label="Project Resources"
            className="mt-2 min-h-32 w-full rounded-md border border-outline-variant bg-surface px-3 py-2 text-sm text-slate-800"
            readOnly
            value={projectResources}
          />
        </label>
      </div>
    </section>
  );
}
