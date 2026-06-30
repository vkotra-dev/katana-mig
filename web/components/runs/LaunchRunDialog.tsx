"use client";

import { useEffect, useMemo, useState, type FormEvent } from "react";
import {
  createRun,
  launchRun,
  listCheckpoints,
  listRuns,
  type RunRecord,
} from "../../lib/runs-api";
import { listProjects, type ProjectRecord } from "../../lib/projects-api";
import { listSourceContracts, listSourceSlices, type SourceContractRecord, type SourceSliceRecord } from "../../lib/sources-api";
import { getUiSession } from "../../lib/session";

type WizardStep = 1 | 2 | 3;

export interface LaunchRunDialogProps {
  open: boolean;
  onClose: () => void;
  onSuccess: (run: RunRecord) => Promise<void> | void;
  initialProjectId?: string | null;
}

interface SnapshotPreview {
  sourceSliceVersion: string | null;
  mappingSnapshotVersion: string | null;
  lookupSnapshotVersion: string | null;
  codegenInputSnapshotVersion: string | null;
  knowledgeFreezeVersion: string | null;
}

function copyText(value: string): void {
  void navigator.clipboard?.writeText(value);
}

function latestApprovedSlice(slices: SourceSliceRecord[]): SourceSliceRecord | null {
  return slices.find((slice) => slice.status === "approved") ?? null;
}

function latestRunForDestination(runs: RunRecord[], destinationObjectName: string): RunRecord | null {
  return (
    runs.find((run) => run.destination_object_name === destinationObjectName) ?? null
  );
}

export function LaunchRunDialog({
  open,
  onClose,
  onSuccess,
  initialProjectId = null,
}: LaunchRunDialogProps) {
  const session = getUiSession();
  const [step, setStep] = useState<WizardStep>(1);
  const [loading, setLoading] = useState(false);
  const [loadingProjects, setLoadingProjects] = useState(false);
  const [projects, setProjects] = useState<ProjectRecord[]>([]);
  const [contracts, setContracts] = useState<SourceContractRecord[]>([]);
  const [projectRuns, setProjectRuns] = useState<RunRecord[]>([]);
  const [sourceSlices, setSourceSlices] = useState<SourceSliceRecord[]>([]);
  const [selectedProjectId, setSelectedProjectId] = useState<string | null>(initialProjectId);
  const [selectedSourceDefinitionId, setSelectedSourceDefinitionId] = useState<string>("");
  const [destinationObjectName, setDestinationObjectName] = useState<string>("");
  const [environment, setEnvironment] = useState<string>("");
  const [snapshotPreview, setSnapshotPreview] = useState<SnapshotPreview>({
    sourceSliceVersion: null,
    mappingSnapshotVersion: null,
    lookupSnapshotVersion: null,
    codegenInputSnapshotVersion: null,
    knowledgeFreezeVersion: null,
  });
  const [createdRun, setCreatedRun] = useState<RunRecord | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  useEffect(() => {
    if (!open) {
      return;
    }

    let active = true;

    const loadProjects = async () => {
      if (!session) {
        setErrorMessage("Sign in to launch runs.");
        return;
      }

      setLoadingProjects(true);
      setErrorMessage(null);
      try {
        const nextProjects = await listProjects(session.accessToken);
        if (!active) {
          return;
        }
        setProjects(nextProjects);
        setSelectedProjectId((current) => current ?? initialProjectId ?? nextProjects[0]?.projectId ?? null);
      } catch (error) {
        if (active) {
          setErrorMessage(error instanceof Error ? error.message : "Unable to load projects.");
        }
      } finally {
        if (active) {
          setLoadingProjects(false);
        }
      }
    };

    void loadProjects();

    return () => {
      active = false;
    };
  }, [initialProjectId, open, session]);

  useEffect(() => {
    if (!open || !session || !selectedProjectId) {
      return;
    }

    let active = true;
    setLoading(true);
    setErrorMessage(null);

    const loadProjectData = async () => {
      try {
        const [nextContracts, nextRuns] = await Promise.all([
          listSourceContracts(session.accessToken, selectedProjectId),
          listRuns(session.accessToken, selectedProjectId),
        ]);
        if (!active) {
          return;
        }
        setContracts(nextContracts);
        setProjectRuns(nextRuns);
        const nextSourceDefinitionId = selectedSourceDefinitionId || nextContracts[0]?.sourceDefinitionId || "";
        setSelectedSourceDefinitionId(nextSourceDefinitionId);
      } catch (error) {
        if (active) {
          setErrorMessage(error instanceof Error ? error.message : "Unable to load project details.");
        }
      } finally {
        if (active) {
          setLoading(false);
        }
      }
    };

    void loadProjectData();

    return () => {
      active = false;
    };
  }, [open, selectedProjectId, session, selectedSourceDefinitionId]);

  useEffect(() => {
    if (!open || !session || !selectedProjectId || !selectedSourceDefinitionId) {
      return;
    }

    let active = true;

    const loadSlices = async () => {
      try {
        const nextSlices = await listSourceSlices(
          session.accessToken,
          selectedProjectId,
          selectedSourceDefinitionId,
        );
        if (!active) {
          return;
        }
        setSourceSlices(nextSlices);
      } catch (error) {
        if (active) {
          setErrorMessage(error instanceof Error ? error.message : "Unable to load source slices.");
        }
      }
    };

    void loadSlices();

    return () => {
      active = false;
    };
  }, [open, selectedProjectId, selectedSourceDefinitionId, session]);

  const selectedProject = useMemo(
    () => projects.find((project) => project.projectId === selectedProjectId) ?? null,
    [projects, selectedProjectId],
  );

  const selectedContract = useMemo(
    () => contracts.find((contract) => contract.sourceDefinitionId === selectedSourceDefinitionId) ?? null,
    [contracts, selectedSourceDefinitionId],
  );

  const selectedSourceSlice = useMemo(
    () => latestApprovedSlice(sourceSlices),
    [sourceSlices],
  );

  const selectedRun = useMemo(() => {
    if (!destinationObjectName) {
      return null;
    }
    return latestRunForDestination(projectRuns, destinationObjectName);
  }, [destinationObjectName, projectRuns]);

  useEffect(() => {
    if (!selectedProject || !selectedContract) {
      return;
    }

    const nextDestinationObjectName =
      destinationObjectName ||
      selectedContract.destinationObjectReferences?.[0] ||
      selectedContract.label;
    if (nextDestinationObjectName !== destinationObjectName) {
      setDestinationObjectName(nextDestinationObjectName);
    }
  }, [destinationObjectName, selectedContract, selectedProject]);

  useEffect(() => {
    if (!selectedProjectId) {
      return;
    }

    const sourceSliceVersion = selectedSourceSlice?.sourceSliceVersion ?? selectedRun?.source_slice_version ?? null;
    const mappingSnapshotVersion = selectedRun?.mapping_snapshot_version ?? sourceSliceVersion;
    const lookupSnapshotVersion = selectedRun?.lookup_snapshot_version ?? sourceSliceVersion;
    const codegenInputSnapshotVersion =
      selectedRun?.code_generation_input_snapshot_version ?? selectedRun?.source_slice_version ?? sourceSliceVersion;
    const knowledgeFreezeVersion = selectedRun?.knowledge_freeze_version ?? sourceSliceVersion;

    setSnapshotPreview({
      sourceSliceVersion,
      mappingSnapshotVersion,
      lookupSnapshotVersion,
      codegenInputSnapshotVersion,
      knowledgeFreezeVersion,
    });
  }, [selectedProjectId, selectedRun, selectedSourceSlice]);

  const objectAlreadyRunning = useMemo(() => {
    if (!destinationObjectName) {
      return false;
    }

    return projectRuns.some(
      (run) =>
        run.destination_object_name === destinationObjectName &&
        run.environment === (environment || null) &&
        ["running", "paused", "awaiting_approval"].includes(run.status),
    );
  }, [destinationObjectName, environment, projectRuns]);

  const frozenProjectDefinitionPresent = Boolean(selectedProject);
  const requiredSourceSlicePresent = Boolean(selectedSourceSlice);
  const requiredDownstreamSnapshotsApproved = Boolean(
    snapshotPreview.sourceSliceVersion &&
      snapshotPreview.mappingSnapshotVersion &&
      snapshotPreview.lookupSnapshotVersion &&
      snapshotPreview.codegenInputSnapshotVersion,
  );
  const preflightPassed =
    frozenProjectDefinitionPresent &&
    requiredSourceSlicePresent &&
    requiredDownstreamSnapshotsApproved &&
    !objectAlreadyRunning &&
    Boolean(selectedProjectId) &&
    Boolean(selectedSourceDefinitionId) &&
    Boolean(destinationObjectName);

  const close = () => {
    setStep(1);
    setLoading(false);
    setLoadingProjects(false);
    setProjects([]);
    setContracts([]);
    setProjectRuns([]);
    setSourceSlices([]);
    setSelectedProjectId(initialProjectId);
    setSelectedSourceDefinitionId("");
    setDestinationObjectName("");
    setEnvironment("");
    setSnapshotPreview({
      sourceSliceVersion: null,
      mappingSnapshotVersion: null,
      lookupSnapshotVersion: null,
      codegenInputSnapshotVersion: null,
      knowledgeFreezeVersion: null,
    });
    setCreatedRun(null);
    setErrorMessage(null);
    onClose();
  };

  const submitLaunch = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!session || !selectedProjectId || !selectedSourceDefinitionId || !destinationObjectName || !preflightPassed) {
      return;
    }

    setLoading(true);
    setErrorMessage(null);
    try {
      const queuedRun = await createRun(session.accessToken, selectedProjectId, {
        destination_object_name: destinationObjectName,
        source_definition_id: selectedSourceDefinitionId,
        environment: environment || null,
      });
      await launchRun(session.accessToken, selectedProjectId, queuedRun.run_id);
      setCreatedRun(queuedRun);
      await onSuccess(queuedRun);
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Unable to launch run.");
    } finally {
      setLoading(false);
    }
  };

  if (!open) {
    return null;
  }

  const selectedObjectSuggestions = selectedContract?.destinationObjectReferences ?? [];

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/50 px-4 py-8">
      <div className="max-h-[92vh] w-full max-w-4xl overflow-y-auto rounded-2xl border border-outline-variant bg-surface-container p-6 shadow-2xl">
        <div className="flex items-start justify-between gap-4">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">Launch Run</p>
            <h2 className="text-2xl font-semibold tracking-tight text-slate-900">Initiate project run</h2>
            <p className="text-sm text-slate-600">
              Multi-environment work creates separate runs in declared order.
            </p>
          </div>
          <button
            className="rounded-md border border-outline-variant px-3 py-2 text-sm text-slate-700"
            onClick={close}
            type="button"
          >
            Close
          </button>
        </div>

        <div className="mt-4 flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">
          <span className={step === 1 ? "text-slate-900" : ""}>1. Target</span>
          <span>•</span>
          <span className={step === 2 ? "text-slate-900" : ""}>2. Snapshot set</span>
          <span>•</span>
          <span className={step === 3 ? "text-slate-900" : ""}>3. Preflight</span>
        </div>

        {createdRun ? (
          <div className="mt-6 rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-4">
            <p className="text-sm font-semibold text-emerald-800">Run queued</p>
            <p className="mt-2 font-mono text-sm text-emerald-900">{createdRun.run_id}</p>
            <div className="mt-4 flex gap-3">
              <a
                className="rounded-md bg-primary px-4 py-2 text-sm font-semibold text-white"
                href={`/runs/${createdRun.run_id}?projectId=${createdRun.project_id}`}
              >
                View run
              </a>
              <button
                className="rounded-md border border-outline-variant px-4 py-2 text-sm text-slate-700"
                onClick={close}
                type="button"
              >
                Close
              </button>
            </div>
          </div>
        ) : null}

        {!createdRun ? (
          <form className="mt-6 space-y-6" onSubmit={submitLaunch}>
            {step === 1 ? (
              <section className="space-y-4 rounded-xl border border-outline-variant bg-surface px-4 py-4">
                <div className="grid gap-4 md:grid-cols-2">
                  <div className="space-y-2">
                    <label
                      className="block text-xs font-semibold uppercase tracking-[0.16em] text-slate-500"
                      htmlFor="launch-run-project"
                    >
                      Project
                    </label>
                    <select
                      id="launch-run-project"
                      className="w-full rounded-md border border-outline-variant bg-white px-3 py-3 text-sm text-slate-900"
                      value={selectedProjectId ?? ""}
                      onChange={(event) => {
                        setSelectedProjectId(event.currentTarget.value);
                        setSelectedSourceDefinitionId("");
                        setSourceSlices([]);
                        setDestinationObjectName("");
                        setStep(1);
                      }}
                    >
                      <option value="">Select project</option>
                      {projects.map((project) => (
                        <option key={project.projectId} value={project.projectId}>
                          {project.name}
                        </option>
                      ))}
                    </select>
                  </div>

                  <div className="space-y-2">
                    <label
                      className="block text-xs font-semibold uppercase tracking-[0.16em] text-slate-500"
                      htmlFor="launch-run-source-contract"
                    >
                      Source contract
                    </label>
                    <select
                      id="launch-run-source-contract"
                      className="w-full rounded-md border border-outline-variant bg-white px-3 py-3 text-sm text-slate-900"
                      value={selectedSourceDefinitionId}
                      onChange={(event) => setSelectedSourceDefinitionId(event.currentTarget.value)}
                    >
                      <option value="">Select source contract</option>
                      {contracts.map((contract) => (
                        <option key={contract.sourceDefinitionId} value={contract.sourceDefinitionId}>
                          {contract.label}
                        </option>
                      ))}
                    </select>
                  </div>
                </div>

                <div className="grid gap-4 md:grid-cols-2">
                  <div className="space-y-2">
                    <label
                      className="block text-xs font-semibold uppercase tracking-[0.16em] text-slate-500"
                      htmlFor="launch-run-destination-object"
                    >
                      Destination object
                    </label>
                    <input
                      id="launch-run-destination-object"
                      className="w-full rounded-md border border-outline-variant bg-white px-3 py-3 text-sm text-slate-900"
                      list="runs-destination-objects"
                      onChange={(event) => setDestinationObjectName(event.currentTarget.value)}
                      placeholder="Customer"
                      value={destinationObjectName}
                    />
                    <datalist id="runs-destination-objects">
                      {selectedObjectSuggestions.map((reference) => (
                        <option key={reference} value={reference} />
                      ))}
                    </datalist>
                  </div>

                  <div className="space-y-2">
                    <label
                      className="block text-xs font-semibold uppercase tracking-[0.16em] text-slate-500"
                      htmlFor="launch-run-environment"
                    >
                      Environment
                    </label>
                    <input
                      id="launch-run-environment"
                      className="w-full rounded-md border border-outline-variant bg-white px-3 py-3 text-sm text-slate-900"
                      onChange={(event) => setEnvironment(event.currentTarget.value)}
                      placeholder="dev"
                      value={environment}
                    />
                  </div>
                </div>
              </section>
            ) : null}

            {step === 2 ? (
              <section className="space-y-4 rounded-xl border border-outline-variant bg-surface px-4 py-4">
                <div className="grid gap-3 md:grid-cols-2">
                  {[
                    ["Source slice", snapshotPreview.sourceSliceVersion],
                    ["Mapping snapshot", snapshotPreview.mappingSnapshotVersion],
                    ["Lookup snapshot", snapshotPreview.lookupSnapshotVersion],
                    ["Codegen input", snapshotPreview.codegenInputSnapshotVersion],
                    ["Knowledge freeze", snapshotPreview.knowledgeFreezeVersion],
                  ].map(([label, value]) => (
                    <div key={label} className="rounded-lg border border-outline-variant bg-white px-3 py-3">
                      <div className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">{label}</div>
                      <div className="mt-2 flex items-center gap-2">
                        <span className="rounded-full bg-slate-100 px-3 py-1 font-mono text-sm text-slate-700">
                          {value ?? "—"}
                        </span>
                        {value ? (
                          <button
                            className="text-xs font-semibold text-primary"
                            onClick={() => copyText(String(value))}
                            type="button"
                          >
                            Copy
                          </button>
                        ) : null}
                      </div>
                    </div>
                  ))}
                </div>
                <p className="text-sm text-slate-600">
                  These versions are pinned to the run and reused on resume.
                </p>
              </section>
            ) : null}

            {step === 3 ? (
              <section className="space-y-4 rounded-xl border border-outline-variant bg-surface px-4 py-4">
                <div className="space-y-3">
                  {[
                    {
                      label: "Frozen project definition present",
                      ok: frozenProjectDefinitionPresent,
                      reason: selectedProject ? null : "Select a project before launching.",
                    },
                    {
                      label: "Required source slice approved & present",
                      ok: requiredSourceSlicePresent,
                      reason: selectedSourceDefinitionId ? "No approved slice found for this source contract." : "Select a source contract.",
                    },
                    {
                      label: "Required downstream snapshots approved",
                      ok: requiredDownstreamSnapshotsApproved,
                      reason: "Select a source contract with pinned snapshots available.",
                    },
                    {
                      label: "Object not already running for this environment",
                      ok: !objectAlreadyRunning,
                      reason: objectAlreadyRunning
                        ? "A run with this destination object and environment is already active."
                        : null,
                    },
                  ].map((item) => (
                    <div
                      key={item.label}
                      className="flex items-start justify-between gap-4 rounded-lg border border-outline-variant bg-white px-3 py-3"
                    >
                      <div>
                        <p className="text-sm font-medium text-slate-900">{item.label}</p>
                        {item.reason ? <p className="mt-1 text-sm text-slate-600">{item.reason}</p> : null}
                      </div>
                      <span className={`status-chip ${item.ok ? "bg-emerald-100 text-emerald-700" : "bg-red-100 text-red-700"}`}>
                        {item.ok ? "pass" : "fail"}
                      </span>
                    </div>
                  ))}
                </div>

                <div className="rounded-lg border border-outline-variant bg-white px-3 py-3">
                  <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">Summary</p>
                  <div className="mt-2 grid gap-2 text-sm text-slate-700 md:grid-cols-2">
                    <div>
                      <span className="font-semibold text-slate-900">Project:</span>{" "}
                      {selectedProject?.name ?? "—"}
                    </div>
                    <div>
                      <span className="font-semibold text-slate-900">Destination object:</span>{" "}
                      {destinationObjectName || "—"}
                    </div>
                    <div>
                      <span className="font-semibold text-slate-900">Source contract:</span>{" "}
                      {selectedContract?.label ?? "—"}
                    </div>
                    <div>
                      <span className="font-semibold text-slate-900">Environment:</span>{" "}
                      {environment || "—"}
                    </div>
                  </div>
                </div>

                <div className="flex items-center justify-between gap-3">
                  <button
                    className="rounded-md border border-outline-variant px-4 py-2 text-sm text-slate-700"
                    onClick={() => setStep(2)}
                    type="button"
                  >
                    Back
                  </button>
                  <button
                    className="rounded-md bg-primary px-4 py-2 text-sm font-semibold text-white disabled:opacity-60"
                    disabled={!preflightPassed || loading}
                    type="submit"
                  >
                    {loading ? "Launching..." : "Launch run"}
                  </button>
                </div>
              </section>
            ) : null}

            <div className="flex items-center justify-between gap-3">
              <button
                className="rounded-md border border-outline-variant px-4 py-2 text-sm text-slate-700 disabled:opacity-50"
                disabled={step === 1 || loading || loadingProjects}
                onClick={() => setStep((current) => Math.max(1, current - 1) as WizardStep)}
                type="button"
              >
                Back
              </button>
              {step < 3 ? (
                <button
                  className="rounded-md bg-primary px-4 py-2 text-sm font-semibold text-white disabled:opacity-60"
                  disabled={
                    (step === 1 && (!selectedProjectId || !selectedSourceDefinitionId || !destinationObjectName)) ||
                    loading ||
                    loadingProjects
                  }
                  onClick={() => setStep((current) => (current + 1) as WizardStep)}
                  type="button"
                >
                  Next
                </button>
              ) : null}
            </div>

            {errorMessage ? (
              <p className="rounded-md border border-error/30 bg-error/10 px-3 py-2 text-sm text-error" role="alert">
                {errorMessage}
              </p>
            ) : null}
          </form>
        ) : null}
      </div>
    </div>
  );
}
