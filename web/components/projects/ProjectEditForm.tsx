"use client";

import { useState } from "react";
import type { ProjectRecord, ProjectUpdateInput, TargetDbEngine } from "../../lib/projects-api";
import { PROJECT_RESOURCES_TEMPLATE } from "./projectResourcesTemplate";

export interface ProjectEditFormProps {
  project: ProjectRecord;
  loading?: boolean;
  errorMessage?: string;
  onSubmit: (value: ProjectUpdateInput) => Promise<void> | void;
}

function normalizeOptionalText(value: string): string | null {
  const trimmed = value.trim();
  return trimmed.length > 0 ? trimmed : null;
}

function parseList(value: string): string[] | null {
  const items = value
    .split(/[\n,]/)
    .map((item) => item.trim())
    .filter((item) => item.length > 0);

  return items.length > 0 ? items : null;
}

function parseSamplePolicy(value: string): Record<string, unknown> | null {
  const trimmed = value.trim();
  if (!trimmed) {
    return null;
  }

  return JSON.parse(trimmed) as Record<string, unknown>;
}

function initialProjectResources(value: string | null | undefined): string {
  const trimmed = value?.trim();
  if (!trimmed) {
    return PROJECT_RESOURCES_TEMPLATE;
  }
  return value ?? PROJECT_RESOURCES_TEMPLATE;
}

export function ProjectEditForm({
  project,
  loading = false,
  errorMessage,
  onSubmit,
}: ProjectEditFormProps) {
  const [name, setName] = useState(project.name);
  const [goal, setGoal] = useState(project.goal ?? "");
  const [projectResources, setProjectResources] = useState(
    initialProjectResources(project.projectResources),
  );
  const [executionEnvironments, setExecutionEnvironments] = useState(
    project.executionEnvironments?.join(", ") ?? "",
  );
  const [targetDbEngine, setTargetDbEngine] = useState<TargetDbEngine | "">(
    project.domainConfig?.targetDbEngine ?? "",
  );
  const [stagingSchema, setStagingSchema] = useState(project.domainConfig?.stagingSchema ?? "");
  const [dryRun, setDryRun] = useState(project.domainConfig?.dryRun ?? false);
  const [destinationSchemaDdl, setDestinationSchemaDdl] = useState(
    project.domainConfig?.destinationSchemaDdl ?? "",
  );
  const [samplePolicy, setSamplePolicy] = useState(
    project.domainConfig?.samplePolicy ? JSON.stringify(project.domainConfig.samplePolicy, null, 2) : "",
  );
  const [formError, setFormError] = useState<string | null>(null);

  return (
    <form
    className="space-y-5 rounded-2xl border border-outline-variant bg-surface-container p-8 shadow-sm"
    onSubmit={(event) => {
      event.preventDefault();

      let parsedSamplePolicy: Record<string, unknown> | null;
      try {
        parsedSamplePolicy = parseSamplePolicy(samplePolicy);
      } catch {
        setFormError("Sample policy must be valid JSON.");
        return;
      }

      setFormError(null);
      void onSubmit({
        name: name.trim(),
        goal: normalizeOptionalText(goal),
        projectResources: normalizeOptionalText(projectResources),
        executionEnvironments: parseList(executionEnvironments),
        domainConfig: {
          targetDbEngine: targetDbEngine || null,
          stagingSchema: normalizeOptionalText(stagingSchema),
          dryRun,
          samplePolicy: parsedSamplePolicy,
          destinationSchemaDdl: normalizeOptionalText(destinationSchemaDdl),
          environments: project.domainConfig?.environments ?? null,
        },
      });
    }}
  >
      <div className="space-y-2">
        <h1 className="text-2xl font-semibold text-slate-900">Edit project</h1>
        <p className="text-sm text-slate-600">
          Update the project metadata and destination configuration without leaving the project shell.
        </p>
      </div>

      <div className="space-y-2">
        <label className="block text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">Project name</label>
        <input
          aria-label="Project name"
          className="w-full rounded-md border border-outline-variant bg-white px-3 py-3 text-sm text-slate-900"
          name="name"
          onChange={(event) => setName(event.target.value)}
          required
          type="text"
          value={name}
        />
      </div>

      <div className="space-y-2">
        <label className="block text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">Goal</label>
        <textarea
          aria-label="Goal"
          className="min-h-24 w-full rounded-md border border-outline-variant bg-white px-3 py-3 text-sm text-slate-900"
          name="goal"
          onChange={(event) => setGoal(event.target.value)}
          value={goal}
        />
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <div className="space-y-2">
          <label className="block text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">Project Resources</label>
          <textarea
            aria-label="Project Resources"
            className="min-h-32 w-full rounded-md border border-outline-variant bg-white px-3 py-3 text-sm text-slate-900"
            name="projectResources"
            onChange={(event) => setProjectResources(event.target.value)}
            value={projectResources}
          />
        </div>

        <div className="space-y-2">
          <label className="block text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">Target database engine</label>
          <select
            aria-label="Target database engine"
            className="w-full rounded-md border border-outline-variant bg-white px-3 py-3 text-sm text-slate-900"
            name="targetDbEngine"
            onChange={(event) => setTargetDbEngine(event.target.value as TargetDbEngine | "")}
            value={targetDbEngine}
          >
            <option value="">Select an engine</option>
            <option value="mssql">mssql</option>
            <option value="oracle">oracle</option>
            <option value="postgresql">postgresql</option>
            <option value="mysql">mysql</option>
          </select>
        </div>
      </div>

      <div className="space-y-2">
        <label className="block text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">Execution environments</label>
        <textarea
          aria-label="Execution environments"
          className="min-h-24 w-full rounded-md border border-outline-variant bg-white px-3 py-3 text-sm text-slate-900"
          name="executionEnvironments"
          onChange={(event) => setExecutionEnvironments(event.target.value)}
          value={executionEnvironments}
        />
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <div className="space-y-2">
          <label className="block text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">Staging schema</label>
          <input
            aria-label="Staging schema"
            className="w-full rounded-md border border-outline-variant bg-white px-3 py-3 text-sm text-slate-900"
            name="stagingSchema"
            onChange={(event) => setStagingSchema(event.target.value)}
            type="text"
            value={stagingSchema}
          />
        </div>

        <label className="flex items-center gap-3 rounded-md border border-outline-variant bg-white px-3 py-3 text-sm text-slate-900">
          <input
            aria-label="Dry run"
            checked={dryRun}
            name="dryRun"
            onChange={(event) => setDryRun(event.target.checked)}
            type="checkbox"
          />
          Dry run
        </label>
      </div>

      <div className="space-y-2">
        <label className="block text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">Destination schema DDL</label>
        <textarea
          aria-label="Destination schema DDL"
          className="min-h-32 w-full rounded-md border border-outline-variant bg-white px-3 py-3 text-sm text-slate-900"
          name="destinationSchemaDdl"
          onChange={(event) => setDestinationSchemaDdl(event.target.value)}
          value={destinationSchemaDdl}
        />
      </div>

      <div className="space-y-2">
        <label className="block text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">Sample policy</label>
        <textarea
          aria-label="Sample policy"
          className="min-h-24 w-full rounded-md border border-outline-variant bg-white px-3 py-3 font-mono text-sm text-slate-900"
          name="samplePolicy"
          onChange={(event) => setSamplePolicy(event.target.value)}
          value={samplePolicy}
        />
      </div>

      {formError || errorMessage ? (
        <p className="rounded-md border border-error/30 bg-error/10 px-3 py-2 text-sm text-error" role="alert">
          {formError ?? errorMessage}
        </p>
      ) : null}

      <button
        className="rounded-md bg-primary px-4 py-3 text-sm font-semibold text-white disabled:opacity-60"
        disabled={loading}
        type="submit"
      >
        {loading ? "Saving..." : "Save changes"}
      </button>
    </form>
  );
}
