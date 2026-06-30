"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { Topbar } from "../../../../../../components/Topbar";
import {
  approveMappingSnapshot,
  getMappingSnapshot,
  patchMappingSnapshot,
  proposeMappingSnapshot,
  rejectMappingSnapshot,
  type MappingApiError,
  type MappingFieldBindingRecord,
  type MappingReviewRecord,
} from "../../../../../../lib/mapping-api";
import { listSourceSchema, type SourceSchemaColumnRecord } from "../../../../../../lib/sources-api";
import { loadUiSession, type SessionRole, type UiSession } from "../../../../../../lib/session";

type PageState = "loading" | "no_snapshot" | "draft" | "approved" | "rejected";

function statusClass(status: string): string {
  if (status === "approved") {
    return "border-emerald-500/20 bg-emerald-500/10 text-emerald-700";
  }
  if (status === "rejected") {
    return "border-red-500/20 bg-red-500/10 text-red-700";
  }
  return "border-amber-500/20 bg-amber-500/10 text-amber-700";
}

function isMappingApiError(error: unknown): error is MappingApiError {
  return Boolean(error && typeof error === "object" && "status" in error && "code" in error);
}

export default function MappingPage() {
  const router = useRouter();
  const params = useParams<{ id: string; sourceId: string }>();
  const projectId = params.id;
  const sourceDefinitionId = params.sourceId;

  const [session, setSession] = useState<UiSession | null>(null);
  const [pageState, setPageState] = useState<PageState>("loading");
  const [snapshot, setSnapshot] = useState<MappingReviewRecord | null>(null);
  const [sourceColumns, setSourceColumns] = useState<SourceSchemaColumnRecord[]>([]);
  const [editedBindings, setEditedBindings] = useState<MappingFieldBindingRecord[]>([]);
  const [isDirty, setIsDirty] = useState(false);
  const [decision, setDecision] = useState<"approved" | "rejected" | null>(null);
  const [rejectionReason, setRejectionReason] = useState("");
  const [loadingAction, setLoadingAction] = useState(false);
  const [proposing, setProposing] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);

  useEffect(() => {
    setSession(loadUiSession());
  }, []);

  useEffect(() => {
    if (!session) {
      setPageState("no_snapshot");
      setErrorMessage("Sign in to review mappings.");
      return;
    }

    let active = true;
    setPageState("loading");
    setErrorMessage(null);

    void Promise.allSettled([
      getMappingSnapshot(session.accessToken, projectId, sourceDefinitionId),
      listSourceSchema(session.accessToken, projectId, sourceDefinitionId),
    ]).then(([mappingResult, schemaResult]) => {
      if (!active) {
        return;
      }

      if (schemaResult.status === "fulfilled") {
        setSourceColumns(schemaResult.value);
      } else {
        setSourceColumns([]);
      }

      if (mappingResult.status === "fulfilled") {
        const nextSnapshot = mappingResult.value;
        setSnapshot(nextSnapshot);
        setEditedBindings(nextSnapshot.fieldBindings.map((binding) => ({ ...binding })));
        setIsDirty(false);
        setDecision(null);
        setRejectionReason("");
        setPageState(nextSnapshot.status as PageState);
        return;
      }

      if (isMappingApiError(mappingResult.reason) && mappingResult.reason.status === 404) {
        setSnapshot(null);
        setEditedBindings([]);
        setIsDirty(false);
        setDecision(null);
        setRejectionReason("");
        setPageState("no_snapshot");
        return;
      }

      setErrorMessage(mappingResult.reason instanceof Error ? mappingResult.reason.message : "Unable to load mapping review.");
      setPageState("no_snapshot");
    });

    return () => {
      active = false;
    };
  }, [projectId, session, sourceDefinitionId]);

  async function handlePropose(): Promise<void> {
    if (!session) {
      return;
    }

    setProposing(true);
    setErrorMessage(null);
    try {
      const next = await proposeMappingSnapshot(session.accessToken, projectId, sourceDefinitionId);
      setSnapshot(next);
      setEditedBindings(next.fieldBindings.map((binding) => ({ ...binding })));
      setIsDirty(false);
      setDecision(null);
      setRejectionReason("");
      setPageState("draft");
      setStatusMessage("Mapping proposal generated.");
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Unable to propose a mapping.");
    } finally {
      setProposing(false);
    }
  }

  async function handleSaveDraft(): Promise<void> {
    if (!session || !snapshot) {
      return;
    }

    setLoadingAction(true);
    setErrorMessage(null);
    try {
      const next = await patchMappingSnapshot(
        session.accessToken,
        projectId,
        sourceDefinitionId,
        editedBindings,
      );
      setSnapshot(next);
      setEditedBindings(next.fieldBindings.map((binding) => ({ ...binding })));
      setIsDirty(false);
      setStatusMessage("Draft bindings saved.");
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Unable to save draft bindings.");
    } finally {
      setLoadingAction(false);
    }
  }

  async function handleSubmitDecision(): Promise<void> {
    if (!session || !snapshot) {
      return;
    }
    if (!decision) {
      setErrorMessage("Choose Approve or Push Back first.");
      return;
    }
    if (decision === "rejected" && !rejectionReason.trim()) {
      setErrorMessage("A rejection comment is required.");
      return;
    }

    setLoadingAction(true);
    setErrorMessage(null);
    try {
      const next =
        decision === "approved"
          ? await approveMappingSnapshot(session.accessToken, projectId, sourceDefinitionId)
          : await rejectMappingSnapshot(session.accessToken, projectId, sourceDefinitionId, rejectionReason.trim());
      setSnapshot(next);
      setEditedBindings(next.fieldBindings.map((binding) => ({ ...binding })));
      setDecision(null);
      setRejectionReason("");
      setIsDirty(false);
      setPageState(next.status as PageState);
      setStatusMessage(
        decision === "approved"
          ? "Mapping approved and source reference updated."
          : "Mapping rejected. You can propose a new mapping.",
      );
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Unable to submit the decision.");
    } finally {
      setLoadingAction(false);
    }
  }

  const role: SessionRole = session?.role ?? "read_only_auditor";
  const canAct = role === "central_team";
  const sourceFieldCount = sourceColumns.length;

  return (
    <main className="flex min-h-screen flex-col bg-slate-50 text-slate-900">
      <Topbar role={role} />
      <section className="mx-auto flex w-full max-w-[1600px] flex-1 flex-col gap-6 px-6 py-6">
        <div className="flex items-center gap-2 text-xs text-slate-500">
          <button className="hover:text-slate-900 hover:underline" onClick={() => router.back()} type="button">
            ← Back
          </button>
          <span className="text-slate-300">|</span>
          <span className="font-mono uppercase tracking-[0.2em]">Mapping Review</span>
          {snapshot && (
            <>
              <span className="text-slate-300">•</span>
              <span className={`inline-flex rounded-full border px-2 py-0.5 font-mono text-[10px] uppercase ${statusClass(snapshot.status)}`}>
                {snapshot.status}
              </span>
            </>
          )}
        </div>

        {errorMessage && (
          <div role="alert" className="rounded-2xl border border-red-500/20 bg-red-500/10 px-4 py-3 text-sm text-red-700">
            {errorMessage}
          </div>
        )}
        {statusMessage && !errorMessage && (
          <div className="rounded-2xl border border-emerald-500/20 bg-emerald-500/10 px-4 py-3 text-sm text-emerald-700">
            {statusMessage}
          </div>
        )}

        {pageState === "loading" && (
          <div className="rounded-2xl border border-slate-200 bg-white p-8 text-sm text-slate-600">
            Loading mapping review...
          </div>
        )}

        {pageState === "no_snapshot" && (
          <div className="flex flex-col items-center gap-4 rounded-3xl border border-dashed border-slate-300 bg-white p-12 text-center shadow-sm">
            <p className="font-mono text-sm uppercase tracking-[0.2em] text-slate-500">
              No mapping has been proposed yet.
            </p>
            {canAct ? (
              <button
                className="rounded-xl bg-slate-900 px-5 py-2.5 text-sm font-semibold text-white hover:bg-slate-800 disabled:opacity-60"
                disabled={proposing}
                onClick={() => void handlePropose()}
                type="button"
              >
                {proposing ? "Proposing..." : "Propose Mapping via AI"}
              </button>
            ) : (
              <p className="text-sm text-slate-500">Only central_team users can propose a mapping.</p>
            )}
          </div>
        )}

        {(pageState === "draft" || pageState === "approved" || pageState === "rejected") && snapshot && (
          <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
            <div className="space-y-4 rounded-3xl border border-slate-200 bg-white p-6 shadow-sm lg:col-span-2">
              <div className="flex items-start justify-between gap-4 border-b border-slate-200 pb-4">
                <div>
                  <p className="text-[10px] font-semibold uppercase tracking-[0.25em] text-slate-500">
                    Auditable Evidence Panel
                  </p>
                  <h1 className="mt-1 text-xl font-semibold text-slate-900">
                    {snapshot.destinationObjectName} bindings
                  </h1>
                </div>
                <div className="rounded-full border border-slate-200 bg-slate-50 px-3 py-1 text-[10px] font-mono uppercase tracking-[0.2em] text-slate-500">
                  Version {snapshot.mappingSnapshotVersion}
                </div>
              </div>

              {pageState === "draft" && canAct && (
                <div className="flex justify-end">
                  <button
                    className="rounded-xl border border-slate-300 bg-white px-4 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-50 disabled:opacity-60"
                    disabled={!isDirty || loadingAction}
                    onClick={() => void handleSaveDraft()}
                    type="button"
                  >
                    {loadingAction ? "Saving..." : "Save draft"}
                  </button>
                </div>
              )}

              <div className="overflow-hidden rounded-2xl border border-slate-200">
                <table className="w-full border-collapse text-sm">
                  <thead className="bg-slate-50">
                    <tr className="text-left text-[10px] font-semibold uppercase tracking-[0.2em] text-slate-500">
                      <th className="px-4 py-3">Source field</th>
                      <th className="px-4 py-3">Destination field</th>
                      <th className="px-4 py-3">Lookup</th>
                    </tr>
                  </thead>
                  <tbody>
                    {editedBindings.map((binding, index) => (
                      <tr key={`${binding.sourceField}-${index}`} className="border-t border-slate-200">
                        <td className="px-4 py-3 font-mono text-xs font-semibold text-slate-700">
                          {binding.sourceField}
                        </td>
                        <td className="px-4 py-3">
                          {pageState === "draft" && canAct ? (
                            <select
                              aria-label={`Destination field for ${binding.sourceField}`}
                              className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-xs text-slate-700 focus:border-slate-900 focus:outline-none"
                              onChange={(event) => {
                                const nextBindings = editedBindings.map((item, itemIndex) =>
                                  itemIndex === index
                                    ? { ...item, destinationField: event.target.value }
                                    : item,
                                );
                                setEditedBindings(nextBindings);
                                setIsDirty(true);
                              }}
                              value={binding.destinationField}
                            >
                              {snapshot.destinationFields.map((field) => (
                                <option key={field} value={field}>
                                  {field}
                                </option>
                              ))}
                            </select>
                          ) : (
                            <span className="font-mono text-xs font-semibold text-slate-900">
                              {binding.destinationField}
                            </span>
                          )}
                        </td>
                        <td className="px-4 py-3">
                          {pageState === "draft" && canAct ? (
                            <input
                              aria-label={`Lookup name for ${binding.sourceField}`}
                              className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-xs text-slate-700 focus:border-slate-900 focus:outline-none"
                              onChange={(event) => {
                                const nextBindings = editedBindings.map((item, itemIndex) =>
                                  itemIndex === index
                                    ? { ...item, lookupName: event.target.value.trim() ? event.target.value.trim() : null }
                                    : item,
                                );
                                setEditedBindings(nextBindings);
                                setIsDirty(true);
                              }}
                              placeholder="optional"
                              type="text"
                              value={binding.lookupName ?? ""}
                            />
                          ) : binding.lookupName ? (
                            <span className="inline-flex rounded-full border border-amber-500/20 bg-amber-500/10 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-[0.2em] text-amber-700">
                              {binding.lookupName}
                            </span>
                          ) : (
                            <span className="text-slate-400">—</span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              <div className="grid gap-4 rounded-2xl border border-slate-200 bg-slate-50 p-4 md:grid-cols-2">
                <div>
                  <p className="text-[10px] font-semibold uppercase tracking-[0.2em] text-slate-500">
                    Source schema
                  </p>
                  <p className="mt-1 text-sm text-slate-700">
                    {sourceFieldCount > 0 ? `${sourceFieldCount} columns loaded from source analysis.` : "No source schema rows loaded."}
                  </p>
                </div>
                <div>
                  <p className="text-[10px] font-semibold uppercase tracking-[0.2em] text-slate-500">
                    Snapshot metadata
                  </p>
                  <p className="mt-1 text-sm text-slate-700">
                    Created {snapshot.createdAt.slice(0, 10)}
                    {snapshot.approvedAt ? ` • Approved ${snapshot.approvedAt.slice(0, 10)}` : ""}
                  </p>
                </div>
              </div>

              {sourceColumns.length > 0 && (
                <div className="space-y-3 rounded-2xl border border-slate-200 p-4">
                  <p className="text-[10px] font-semibold uppercase tracking-[0.2em] text-slate-500">
                    Source fields
                  </p>
                  <div className="flex flex-wrap gap-2">
                    {sourceColumns.map((column) => (
                      <span
                        key={column.name}
                        className="rounded-full border border-slate-200 bg-white px-3 py-1 text-xs font-mono text-slate-700"
                      >
                        {column.name}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>

            <aside className="space-y-4 rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
              <div className="border-b border-slate-200 pb-4">
                <p className="text-[10px] font-semibold uppercase tracking-[0.25em] text-slate-500">
                  Governed Audit Panel
                </p>
                <h2 className="mt-1 text-lg font-semibold text-slate-900">Decision matrix</h2>
              </div>

              {pageState === "draft" && canAct && (
                <div className="space-y-4">
                  <div className="grid grid-cols-2 gap-2">
                    <button
                      className={`rounded-xl border px-3 py-2 text-sm font-semibold transition ${
                        decision === "approved"
                          ? "border-emerald-600 bg-emerald-600 text-white"
                          : "border-slate-300 bg-white text-slate-700 hover:bg-slate-50"
                      }`}
                      onClick={() => {
                        setDecision("approved");
                        setErrorMessage(null);
                      }}
                      type="button"
                    >
                      Approve
                    </button>
                    <button
                      className={`rounded-xl border px-3 py-2 text-sm font-semibold transition ${
                        decision === "rejected"
                          ? "border-red-600 bg-red-600 text-white"
                          : "border-slate-300 bg-white text-slate-700 hover:bg-slate-50"
                      }`}
                      onClick={() => {
                        setDecision("rejected");
                        setErrorMessage(null);
                      }}
                      type="button"
                    >
                      Push back
                    </button>
                  </div>

                  <label className="block">
                    <span className="mb-1 block text-[10px] font-semibold uppercase tracking-[0.2em] text-slate-500">
                      Rejection comment
                    </span>
                    <textarea
                      className="min-h-28 w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm text-slate-700 focus:border-slate-900 focus:outline-none"
                      onChange={(event) => setRejectionReason(event.target.value)}
                      placeholder="Required if you push back"
                      value={rejectionReason}
                    />
                  </label>

                  <button
                    className="w-full rounded-xl bg-slate-900 px-4 py-2.5 text-sm font-semibold text-white hover:bg-slate-800 disabled:opacity-60"
                    disabled={loadingAction || decision === null}
                    onClick={() => void handleSubmitDecision()}
                    type="button"
                  >
                    {loadingAction ? "Submitting..." : "Submit decision"}
                  </button>
                </div>
              )}

              {pageState === "draft" && !canAct && (
                <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4 text-sm text-slate-600">
                  Auditor accounts cannot change the review state.
                </div>
              )}

              {(pageState === "approved" || pageState === "rejected") && (
                <div className="space-y-4">
                  <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4 text-sm text-slate-600">
                    This mapping is <strong className="uppercase">{pageState}</strong> and locked for review.
                  </div>
                  {pageState === "rejected" && canAct && (
                    <button
                      className="w-full rounded-xl border border-slate-300 bg-white px-4 py-2.5 text-sm font-semibold text-slate-700 hover:bg-slate-50 disabled:opacity-60"
                      disabled={proposing}
                      onClick={() => void handlePropose()}
                      type="button"
                    >
                      {proposing ? "Proposing..." : "Propose New Mapping"}
                    </button>
                  )}
                </div>
              )}
            </aside>
          </div>
        )}
      </section>
    </main>
  );
}
