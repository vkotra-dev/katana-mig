"use client";

import { use, useEffect, useMemo, useState } from "react";
import { Topbar } from "../../../../components/Topbar";
import {
  downloadCodegenDeliveryBundle,
  listCodegenArtifacts,
  triggerCodegen,
  type CodegenArtifactRecord,
} from "../../../../lib/codegen-api";
import { listSourceContracts, type SourceContractRecord } from "../../../../lib/sources-api";
import { loadUiSession, type SessionRole, type UiSession } from "../../../../lib/session";

function formatDate(value: string): string {
  return value.slice(0, 16).replace("T", " ");
}

function statusClassName(status: string): string {
  if (status === "active") {
    return "bg-emerald-100 text-emerald-900";
  }
  return "bg-slate-100 text-slate-700";
}

function latestActiveArtifact(artifacts: CodegenArtifactRecord[]): CodegenArtifactRecord | null {
  const active = artifacts.filter((artifact) => artifact.status === "active");
  const source = active.length > 0 ? active : artifacts;
  if (source.length === 0) {
    return null;
  }
  return [...source].sort((left, right) => right.createdAt.localeCompare(left.createdAt))[0] ?? null;
}

function sourceDestinationLabel(source: SourceContractRecord): string {
  const refs = source.destinationObjectReferences ?? [];
  return refs.length > 0 ? refs.join(", ") : "Unassigned";
}

export default function CodegenPage({ params }: { params: Promise<{ id: string }> }) {
  const [routeParams, setRouteParams] = useState<{ id: string } | null>(null);
  const [session, setSession] = useState<UiSession | null>(null);
  const [sources, setSources] = useState<SourceContractRecord[]>([]);
  const [artifacts, setArtifacts] = useState<CodegenArtifactRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [pageError, setPageError] = useState<string | null>(null);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);
  const [actionLoading, setActionLoading] = useState<string | null>(null);

  useEffect(() => {
    setSession(loadUiSession());
  }, []);

  useEffect(() => {
    let active = true;
    void Promise.resolve(params).then((resolved) => {
      if (active) {
        setRouteParams(resolved);
      }
    });
    return () => {
      active = false;
    };
  }, [params]);

  useEffect(() => {
    if (!session || !routeParams) {
      setLoading(true);
      return;
    }

    let active = true;
    setLoading(true);
    setPageError(null);
    setStatusMessage(null);

    void Promise.all([
      listSourceContracts(session.accessToken, routeParams.id),
      listCodegenArtifacts(session.accessToken, routeParams.id),
    ])
      .then(([sourceResponse, artifactResponse]) => {
        if (!active) {
          return;
        }
        setSources(sourceResponse);
        setArtifacts(artifactResponse);
      })
      .catch((error: unknown) => {
        if (active) {
          setPageError(error instanceof Error ? error.message : "Unable to load code generation.");
        }
      })
      .finally(() => {
        if (active) {
          setLoading(false);
        }
      });

    return () => {
      active = false;
    };
  }, [routeParams, session]);

  const role: SessionRole = session?.role ?? "read_only_auditor";
  const latestArtifact = useMemo(() => latestActiveArtifact(artifacts), [artifacts]);
  const activeCount = useMemo(() => artifacts.filter((artifact) => artifact.status === "active").length, [artifacts]);

  const refreshArtifacts = async (): Promise<void> => {
    if (!session || !routeParams) {
      return;
    }
    const response = await listCodegenArtifacts(session.accessToken, routeParams.id);
    setArtifacts(response);
  };

  const handleGenerate = async (sourceDefinitionId: string): Promise<void> => {
    if (!session || !routeParams) {
      return;
    }
    setActionLoading(sourceDefinitionId);
    setPageError(null);
    setStatusMessage(null);
    try {
      await triggerCodegen(session.accessToken, routeParams.id, sourceDefinitionId);
      await refreshArtifacts();
      setStatusMessage("Code generation completed.");
    } catch (error) {
      setPageError(error instanceof Error ? error.message : "Unable to generate code.");
    } finally {
      setActionLoading(null);
    }
  };

  const handleDownloadBundle = async (): Promise<void> => {
    if (!session || !routeParams) {
      return;
    }
    setPageError(null);
    setStatusMessage(null);
    try {
      const sqlBundle = await downloadCodegenDeliveryBundle(session.accessToken, routeParams.id);
      const blob = new Blob([sqlBundle], { type: "text/plain" });
      const href = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = href;
      anchor.download = "delivery-bundle.sql";
      anchor.click();
      URL.revokeObjectURL(href);
      setStatusMessage("Delivery bundle downloaded.");
    } catch (error) {
      setPageError(error instanceof Error ? error.message : "Unable to download delivery bundle.");
    }
  };

  return (
    <main className="flex min-h-screen flex-col bg-surface text-slate-800">
      <Topbar role={role} />
      <section className="mx-auto flex w-full max-w-[1600px] flex-1 flex-col gap-6 px-6 py-6">
        <div className="space-y-2">
          <p className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-500">Code Generation</p>
          <h1 className="text-3xl font-semibold text-slate-900">SQL bundle delivery</h1>
          <p className="max-w-3xl text-sm text-slate-600">
            Generate SQL from the approved mapping and source contract, review the latest active artifact, and
            download the delivery bundle for the project.
          </p>
        </div>

        {loading ? (
          <div className="rounded-2xl border border-outline-variant bg-surface-container p-8 text-sm text-slate-600">
            Loading code generation...
          </div>
        ) : pageError ? (
          <div role="alert" className="rounded-2xl border border-error/30 bg-error/10 px-4 py-3 text-sm text-error">
            {pageError}
          </div>
        ) : session && routeParams ? (
          <>
            {statusMessage ? (
              <div className="rounded-2xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-900">
                {statusMessage}
              </div>
            ) : null}

            <section className="space-y-4 rounded-2xl border border-outline-variant bg-surface-container p-6 shadow-sm">
              <div>
                <h2 className="text-xl font-semibold text-slate-900">Sources</h2>
                <p className="text-sm text-slate-600">Generate SQL from each source contract.</p>
              </div>

              {sources.length === 0 ? (
                <div className="rounded-xl border border-dashed border-outline-variant bg-surface px-4 py-8 text-sm text-slate-500">
                  No source contracts available.
                </div>
              ) : (
                <div className="overflow-hidden rounded-xl border border-outline-variant">
                  <table className="w-full border-collapse text-left">
                    <thead className="bg-surface">
                      <tr className="text-xs uppercase tracking-[0.16em] text-slate-500">
                        <th className="px-4 py-3">Source</th>
                        <th className="px-4 py-3">Destination</th>
                        <th className="px-4 py-3">Encoding</th>
                        <th className="px-4 py-3">Status</th>
                        <th className="px-4 py-3">Action</th>
                      </tr>
                    </thead>
                    <tbody>
                      {sources.map((source) => (
                        <tr key={source.sourceDefinitionId} className="border-t border-outline-variant">
                          <td className="px-4 py-3">
                            <div className="text-sm font-semibold text-slate-900">{source.label}</div>
                            <div className="mono-id mt-1">{source.sourceDefinitionId}</div>
                          </td>
                          <td className="px-4 py-3 text-sm text-slate-700">{sourceDestinationLabel(source)}</td>
                          <td className="px-4 py-3 text-sm text-slate-700">{source.encoding}</td>
                          <td className="px-4 py-3 text-sm text-slate-700">{source.status}</td>
                          <td className="px-4 py-3">
                            {role === "central_team" ? (
                              <button
                                className="rounded-md bg-primary px-4 py-2 text-sm font-semibold text-white disabled:opacity-60"
                                disabled={actionLoading === source.sourceDefinitionId}
                                onClick={() => void handleGenerate(source.sourceDefinitionId)}
                                type="button"
                              >
                                Generate SQL
                              </button>
                            ) : (
                              <span className="text-sm text-slate-500">No action</span>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </section>

            <section className="grid gap-6 lg:grid-cols-[1.35fr_0.85fr]">
              <div className="space-y-4 rounded-2xl border border-outline-variant bg-surface-container p-6 shadow-sm">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <h2 className="text-xl font-semibold text-slate-900">Latest active artifact</h2>
                    <p className="text-sm text-slate-600">{activeCount} active artifact(s) in the project.</p>
                  </div>
                  {latestArtifact ? (
                    <span className={`rounded-full px-3 py-1 text-xs font-semibold ${statusClassName(latestArtifact.status)}`}>
                      {latestArtifact.status}
                    </span>
                  ) : null}
                </div>

                {latestArtifact ? (
                  <>
                    <div className="grid gap-3 text-sm text-slate-700 sm:grid-cols-2">
                      <div>
                        <div className="text-xs uppercase tracking-[0.16em] text-slate-500">Destination</div>
                        <div className="font-semibold text-slate-900">{latestArtifact.destinationObjectName}</div>
                      </div>
                      <div>
                        <div className="text-xs uppercase tracking-[0.16em] text-slate-500">Artifact ID</div>
                        <div className="mono-id">{latestArtifact.codegenArtifactId}</div>
                      </div>
                      <div>
                        <div className="text-xs uppercase tracking-[0.16em] text-slate-500">Created</div>
                        <div>{formatDate(latestArtifact.createdAt)}</div>
                      </div>
                      <div>
                        <div className="text-xs uppercase tracking-[0.16em] text-slate-500">Source slice</div>
                        <div>{latestArtifact.sourceSliceVersion ?? "—"}</div>
                      </div>
                    </div>

                    <div className="flex flex-wrap gap-2">
                      <button
                        className="rounded-md border border-outline-variant px-3 py-2 text-sm font-semibold text-slate-700"
                        onClick={async () => {
                          await navigator.clipboard.writeText(latestArtifact.sqlBundle ?? "");
                          setStatusMessage("SQL bundle copied to clipboard.");
                        }}
                        type="button"
                      >
                        Copy SQL
                      </button>
                      <button
                        className="rounded-md border border-outline-variant px-3 py-2 text-sm font-semibold text-slate-700"
                        onClick={() => void handleDownloadBundle()}
                        type="button"
                      >
                        Download delivery bundle
                      </button>
                    </div>

                    <div className="rounded-xl border border-outline-variant bg-surface px-4 py-4">
                      <div className="mb-3 text-xs uppercase tracking-[0.16em] text-slate-500">SQL preview</div>
                      <pre className="max-h-[420px] overflow-auto whitespace-pre-wrap rounded-lg bg-slate-950 px-4 py-4 text-xs leading-6 text-slate-100">
                        {latestArtifact.sqlBundle ?? "No SQL bundle stored."}
                      </pre>
                    </div>
                  </>
                ) : (
                  <div className="rounded-xl border border-dashed border-outline-variant bg-surface px-4 py-8 text-sm text-slate-500">
                    No active code generation artifact yet.
                  </div>
                )}
              </div>

              <div className="space-y-4 rounded-2xl border border-outline-variant bg-surface-container p-6 shadow-sm">
                <div>
                  <h2 className="text-xl font-semibold text-slate-900">Delivery bundle</h2>
                  <p className="text-sm text-slate-600">
                    Concatenated SQL for the active artifacts in this project.
                  </p>
                </div>

                <div className="rounded-xl border border-outline-variant bg-surface px-4 py-4 text-sm text-slate-700">
                  <div className="text-xs uppercase tracking-[0.16em] text-slate-500">Active artifacts</div>
                  <div className="mt-2 text-2xl font-semibold text-slate-900">{activeCount}</div>
                </div>

                <div className="rounded-xl border border-dashed border-outline-variant bg-surface px-4 py-4 text-sm text-slate-600">
                  The download button above saves the bundle as <span className="font-mono">delivery-bundle.sql</span>.
                </div>
              </div>
            </section>

            <section className="space-y-4 rounded-2xl border border-outline-variant bg-surface-container p-6 shadow-sm">
              <div>
                <h2 className="text-xl font-semibold text-slate-900">Artifact history</h2>
                <p className="text-sm text-slate-600">Active and superseded artifacts for the project.</p>
              </div>

              {artifacts.length === 0 ? (
                <div className="rounded-xl border border-dashed border-outline-variant bg-surface px-4 py-8 text-sm text-slate-500">
                  No artifacts yet.
                </div>
              ) : (
                <div className="overflow-hidden rounded-xl border border-outline-variant">
                  <table className="w-full border-collapse text-left">
                    <thead className="bg-surface">
                      <tr className="text-xs uppercase tracking-[0.16em] text-slate-500">
                        <th className="px-4 py-3">Destination</th>
                        <th className="px-4 py-3">Status</th>
                        <th className="px-4 py-3">Version</th>
                        <th className="px-4 py-3">Created</th>
                      </tr>
                    </thead>
                    <tbody>
                      {artifacts.map((artifact) => (
                        <tr key={artifact.codegenArtifactId} className="border-t border-outline-variant">
                          <td className="px-4 py-3 text-sm text-slate-900">{artifact.destinationObjectName}</td>
                          <td className="px-4 py-3">
                            <span className={`rounded-full px-2.5 py-1 text-xs font-semibold ${statusClassName(artifact.status)}`}>
                              {artifact.status}
                            </span>
                          </td>
                          <td className="px-4 py-3 text-sm text-slate-700">
                            {artifact.sourceSliceVersion ?? "—"} / {artifact.mappingSnapshotVersion ?? "—"}
                          </td>
                          <td className="px-4 py-3 text-sm text-slate-700">{formatDate(artifact.createdAt)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </section>
          </>
        ) : null}
      </section>
    </main>
  );
}
