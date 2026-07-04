"use client";

import { useState } from "react";
import type {
  AIModelDefaultsRecord,
  ModelPolicy,
  SamplePolicy,
  SamplePolicyStrategy,
  ProjectRecord,
  ProjectUpdateInput,
  TargetDbEngine,
} from "../../lib/projects-api";
import { ProjectResourcesEditor } from "./ProjectResourcesEditor";
import { MODEL_POLICY_FIELDS } from "./modelPolicyCatalog";

export interface ProjectEditFormProps {
  project: ProjectRecord;
  loading?: boolean;
  errorMessage?: string;
  modelDefaults?: AIModelDefaultsRecord["migrationModels"] | null;
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

type SamplePolicyDraft = {
  strategy: SamplePolicyStrategy | "";
  maxRows: string;
  stratifiedColumn: string;
};

const SAMPLE_POLICY_STRATEGIES: Array<{ value: SamplePolicyStrategy; label: string }> = [
  { value: "random", label: "Random" },
  { value: "top_n", label: "Top N" },
  { value: "full", label: "Full" },
  { value: "stratified", label: "Stratified" },
];

function initializeSamplePolicyDraft(policy: SamplePolicy | null | undefined): SamplePolicyDraft {
  return {
    strategy: policy?.strategy ?? "",
    maxRows: policy?.maxRows?.toString() ?? "",
    stratifiedColumn: policy?.stratifiedColumn ?? "",
  };
}

function buildSamplePolicyPayload(draft: SamplePolicyDraft): SamplePolicy | null {
  const maxRows = draft.maxRows.trim();
  const stratifiedColumn = draft.stratifiedColumn.trim();
  const inferredStrategy: SamplePolicyStrategy | null =
    draft.strategy || stratifiedColumn.length > 0 || maxRows.length > 0 ? draft.strategy || "random" : null;

  if (!inferredStrategy && stratifiedColumn.length === 0 && maxRows.length === 0) {
    return null;
  }

  if (inferredStrategy === "stratified" && stratifiedColumn.length === 0) {
    throw new Error("Sample policy stratified column is required for stratified sampling.");
  }

  if (maxRows.length > 0) {
    const parsedMaxRows = Number(maxRows);
    if (!Number.isInteger(parsedMaxRows) || parsedMaxRows <= 0) {
      throw new Error("Sample policy max rows must be a positive integer.");
    }

    return {
      strategy: inferredStrategy ?? "random",
      maxRows: parsedMaxRows,
      stratifiedColumn: inferredStrategy === "stratified" ? stratifiedColumn || null : null,
    };
  }

  if (inferredStrategy === "stratified") {
    return {
      strategy: inferredStrategy,
      maxRows: null,
      stratifiedColumn,
    };
  }

  return {
    strategy: inferredStrategy,
    maxRows: null,
    stratifiedColumn: null,
  };
}

function initializeModelPolicyDraft(policy: ModelPolicy | null | undefined): Record<keyof ModelPolicy, string> {
  return {
    piiReview: policy?.piiReview ?? "",
    fieldMapping: policy?.fieldMapping ?? "",
    lookupMapping: policy?.lookupMapping ?? "",
    scriptGeneration: policy?.scriptGeneration ?? "",
    scriptCorrection: policy?.scriptCorrection ?? "",
    schemaDependency: policy?.schemaDependency ?? "",
    impactAnalysis: policy?.impactAnalysis ?? "",
    feedAnalysis: policy?.feedAnalysis ?? "",
    planning: policy?.planning ?? "",
    review: policy?.review ?? "",
    implementation: policy?.implementation ?? "",
  };
}

function buildModelPolicyPayload(draft: Record<keyof ModelPolicy, string>): ModelPolicy | null {
  const entries = MODEL_POLICY_FIELDS.map(({ key }) => [key, draft[key].trim()] as const).filter(
    ([, value]) => value.length > 0,
  );

  if (entries.length === 0) {
    return null;
  }

  return entries.reduce<ModelPolicy>((acc, [key, value]) => {
    acc[key] = value;
    return acc;
  }, {});
}

export function ProjectEditForm({
  project,
  loading = false,
  errorMessage,
  modelDefaults = null,
  onSubmit,
}: ProjectEditFormProps) {
  const [name, setName] = useState(project.name);
  const [goal, setGoal] = useState(project.goal ?? "");
  const [projectResources, setProjectResources] = useState(project.projectResources ?? "");
  const [modelPolicy, setModelPolicy] = useState(() => initializeModelPolicyDraft(project.modelPolicy));
  const [executionEnvironments] = useState(project.executionEnvironments?.join(", ") ?? "");
  const [targetDbEngine, setTargetDbEngine] = useState<TargetDbEngine | "">(
    project.domainConfig?.targetDbEngine ?? "",
  );
  const [stagingSchema, setStagingSchema] = useState(project.domainConfig?.stagingSchema ?? "");
  const [destinationSchema, setDestinationSchema] = useState(
    project.domainConfig?.destinationSchema ?? "",
  );
  const [dryRun, setDryRun] = useState(project.domainConfig?.dryRun ?? false);
  const [destinationSchemaDdl, setDestinationSchemaDdl] = useState(
    project.domainConfig?.destinationSchemaDdl ?? "",
  );
  const [samplePolicy, setSamplePolicy] = useState(() =>
    initializeSamplePolicyDraft(project.domainConfig?.samplePolicy),
  );
  const [formError, setFormError] = useState<string | null>(null);
  const [modelPolicyOpen, setModelPolicyOpen] = useState(false);

  return (
    <form
      className="space-y-5 rounded-2xl border border-outline-variant bg-surface-container p-8 shadow-sm"
      onSubmit={(event) => {
        event.preventDefault();

        try {
          const parsedSamplePolicy = buildSamplePolicyPayload(samplePolicy);
          setFormError(null);
          const nextModelPolicy = buildModelPolicyPayload(modelPolicy);
          void onSubmit({
            name: name.trim(),
            goal: normalizeOptionalText(goal),
            projectResources: normalizeOptionalText(projectResources),
            executionEnvironments: parseList(executionEnvironments),
            modelPolicy: nextModelPolicy,
            domainConfig: {
              targetDbEngine: targetDbEngine || null,
              stagingSchema: normalizeOptionalText(stagingSchema),
              destinationSchema: normalizeOptionalText(destinationSchema),
              dryRun,
              samplePolicy: parsedSamplePolicy,
              destinationSchemaDdl: normalizeOptionalText(destinationSchemaDdl),
              environments: project.domainConfig?.environments ?? null,
            },
          });
        } catch (error) {
          setFormError(error instanceof Error ? error.message : "Sample policy is invalid.");
        }
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

      <div className="grid gap-4 lg:grid-cols-3">
        <div className="space-y-2 lg:col-span-1">
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

        <div className="space-y-2 lg:col-span-1">
          <label className="block text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">
            Staging schema
          </label>
          <input
            aria-label="Staging schema"
            className="w-full rounded-md border border-outline-variant bg-white px-3 py-3 text-sm text-slate-900"
            name="stagingSchema"
            onChange={(event) => setStagingSchema(event.target.value)}
            type="text"
            value={stagingSchema}
          />
        </div>

        <div className="space-y-2 lg:col-span-1">
          <label className="block text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">
            Destination schema
          </label>
          <input
            aria-label="Destination schema"
            className="w-full rounded-md border border-outline-variant bg-white px-3 py-3 text-sm text-slate-900"
            name="destinationSchema"
            onChange={(event) => setDestinationSchema(event.target.value)}
            type="text"
            value={destinationSchema}
          />
        </div>

        <div className="flex items-end lg:col-span-3">
          <label className="flex items-center gap-3 rounded-md border border-outline-variant bg-white px-3 py-3 text-sm text-slate-900 w-full lg:w-auto">
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

        <div className="space-y-2 lg:col-span-3">
          <label className="block text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">Destination schema DDL</label>
          <textarea
            aria-label="Destination schema DDL"
            className="min-h-32 w-full rounded-md border border-outline-variant bg-white px-3 py-3 text-sm text-slate-900"
            name="destinationSchemaDdl"
            onChange={(event) => setDestinationSchemaDdl(event.target.value)}
            value={destinationSchemaDdl}
          />
        </div>

        <div className="space-y-2 lg:col-span-3">
          <label className="block text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">Sample policy</label>
          <p className="text-xs text-slate-400">Leave the fields blank to keep sample policy unset.</p>
          <div className="grid gap-4 lg:grid-cols-3">
            <div className="space-y-2">
              <label className="block text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">
                Strategy
              </label>
              <select
                aria-label="Sample policy strategy"
                className="w-full rounded-md border border-outline-variant bg-white px-3 py-3 text-sm text-slate-900"
                name="samplePolicyStrategy"
                onChange={(event) =>
                  setSamplePolicy((current) => ({
                    ...current,
                    strategy: event.target.value as SamplePolicyStrategy | "",
                    stratifiedColumn:
                      event.target.value === "stratified" ? current.stratifiedColumn : "",
                  }))
                }
                value={samplePolicy.strategy}
              >
                <option value="">Select a strategy</option>
                {SAMPLE_POLICY_STRATEGIES.map(({ value, label }) => (
                  <option key={value} value={value}>
                    {label}
                  </option>
                ))}
              </select>
            </div>

            <div className="space-y-2">
              <label className="block text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">
                Max rows
              </label>
              <input
                aria-label="Sample policy max rows"
                className="w-full rounded-md border border-outline-variant bg-white px-3 py-3 text-sm text-slate-900"
                min={1}
                name="samplePolicyMaxRows"
                onChange={(event) =>
                  setSamplePolicy((current) => ({
                    ...current,
                    maxRows: event.target.value,
                  }))
                }
                placeholder="Optional"
                type="number"
                value={samplePolicy.maxRows}
              />
            </div>

            {samplePolicy.strategy === "stratified" ? (
              <div className="space-y-2">
                <label className="block text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">
                  Stratified column
                </label>
                <input
                  aria-label="Sample policy stratified column"
                  className="w-full rounded-md border border-outline-variant bg-white px-3 py-3 text-sm text-slate-900"
                  name="samplePolicyStratifiedColumn"
                  onChange={(event) =>
                    setSamplePolicy((current) => ({
                      ...current,
                      stratifiedColumn: event.target.value,
                    }))
                  }
                  placeholder="region"
                  type="text"
                  value={samplePolicy.stratifiedColumn}
                />
              </div>
            ) : null}
          </div>
        </div>

        <div className="space-y-2 lg:col-span-3">
          <button
            className="flex w-full items-center justify-between rounded-xl border border-outline-variant bg-surface px-4 py-4 text-left"
            onClick={() => setModelPolicyOpen((value) => !value)}
            type="button"
          >
            <span className="text-sm font-semibold text-slate-900">Model Policy</span>
            <span className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">
              {modelPolicyOpen ? "Collapse" : "Expand"}
            </span>
          </button>
        </div>

        {modelPolicyOpen
          ? MODEL_POLICY_FIELDS.map(({ key, label }) => (
              <div className="space-y-2" key={key}>
                <label className="block text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">
                  {label}
                </label>
                <input
                  aria-label={label}
                  className="w-full rounded-md border border-outline-variant bg-white px-3 py-3 text-sm text-slate-900"
                  onChange={(event) => setModelPolicy((current) => ({ ...current, [key]: event.target.value }))}
                  placeholder="Global default"
                  type="text"
                  value={modelPolicy[key]}
                />
                <p className="text-xs text-slate-500">
                  {modelDefaults?.[key] ? `Global default: ${modelDefaults[key]}` : "Global default unavailable"}
                </p>
              </div>
            ))
          : null}

        <div className="space-y-2 lg:col-span-3">
          <label className="block text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">Project Resources</label>
          <ProjectResourcesEditor value={projectResources} onChange={setProjectResources} />
        </div>
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
