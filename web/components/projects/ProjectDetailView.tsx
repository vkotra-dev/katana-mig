"use client";

import { useState, useEffect } from "react";
import DOMPurify from "dompurify";
import type { AIModelDefaultsRecord } from "../../lib/ai-model-defaults-api";
import type { ProjectRecord, SamplePolicy } from "../../lib/projects-api";
import { StageTimeline } from "./StageTimeline";
import { MODEL_POLICY_FIELDS } from "./modelPolicyCatalog";

export interface ProjectDetailViewProps {
  project: ProjectRecord;
  modelDefaults?: (AIModelDefaultsRecord["migrationModels"] & AIModelDefaultsRecord["platformModels"]) | null;
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
  className = "",
}: {
  label: string;
  value: string;
  className?: string;
}) {
  return (
    <div className={`space-y-2 ${className}`}>
      <div className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">{label}</div>
      <div className="whitespace-pre-wrap text-sm text-slate-900">{value}</div>
    </div>
  );
}

export function ProjectDetailView({ project, modelDefaults = null }: ProjectDetailViewProps) {
  const domainConfig = project.domainConfig;
  const projectResources = project.projectResources ?? "";
  const [purifiedHtml, setPurifiedHtml] = useState("");

  useEffect(() => {
    setPurifiedHtml(DOMPurify.sanitize(projectResources));
  }, [projectResources]);

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

      <div className="space-y-2">
        <div className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">Goal</div>
        <div className="whitespace-pre-wrap text-sm text-slate-900">{project.goal ?? "—"}</div>
      </div>

      <div className="grid gap-x-6 gap-y-5 lg:grid-cols-3">
        <KeyValue
          label="Execution environments"
          value={project.executionEnvironments?.join(" → ") ?? "—"}
        />
        <KeyValue label="Target database engine" value={domainConfig?.targetDbEngine ?? "—"} />
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
          className="lg:col-span-3"
          label="Destination schema DDL"
          value={domainConfig?.destinationSchemaDdl ?? "—"}
        />
        <KeyValue
          className="lg:col-span-3"
          label="Sample policy"
          value={formatSamplePolicy(domainConfig?.samplePolicy)}
        />
        <KeyValue
          className="lg:col-span-3"
          label="Constraints"
          value={project.constraints?.join(", ") ?? "—"}
        />
        <KeyValue
          className="lg:col-span-3"
          label="Unresolved questions"
          value={project.unresolvedQuestions?.join("; ") ?? "—"}
        />
        <KeyValue className="lg:col-span-3" label="Assumptions" value={project.assumptions?.join("; ") ?? "—"} />
        <KeyValue
          className="lg:col-span-3"
          label="Lexicon scope"
          value={project.lexiconScope ?? "—"}
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

      {purifiedHtml && (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          <div className="space-y-1 rounded-xl border border-outline-variant bg-surface px-4 py-3 md:col-span-2 xl:col-span-3">
            <div className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">
              Project Resources
            </div>
            <div
              aria-label="Project Resources"
              className="prose prose-sm max-w-none mt-2 rounded-md border border-outline-variant bg-surface px-3 py-2 text-slate-800"
              dangerouslySetInnerHTML={{
                __html: purifiedHtml
              }}
            />
          </div>
        </div>
      )}
    </section>
  );
}
