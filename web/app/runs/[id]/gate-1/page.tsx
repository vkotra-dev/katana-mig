"use client";

import { useEffect, useState } from "react";
import { useParams, useSearchParams } from "next/navigation";
import { Topbar } from "../../../../components/Topbar";
import { approveGate, getGate1Evidence, rejectGate, type Gate1EvidenceRecord } from "../../../../lib/gates-api";
import { loadUiSession, type SessionRole, type UiSession } from "../../../../lib/session";

function splitCsv(value: string): string[] {
  return value
    .split(",")
    .map((entry) => entry.trim())
    .filter((entry) => entry.length > 0);
}

function chipClassName(kind: "approved" | "rejected" | "neutral"): string {
  if (kind === "approved") {
    return "bg-emerald-100 text-emerald-700";
  }
  if (kind === "rejected") {
    return "bg-red-100 text-red-700";
  }
  return "bg-slate-100 text-slate-600";
}

export default function Gate1Page() {
  const params = useParams<{ id: string }>();
  const searchParams = useSearchParams();
  const projectId = searchParams.get("projectId");
  const runId = params.id;
  const [session, setSession] = useState<UiSession | null>(null);
  const [evidence, setEvidence] = useState<Gate1EvidenceRecord | null>(null);
  const [loading, setLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [notes, setNotes] = useState("");
  const [pushBackOpen, setPushBackOpen] = useState(false);
  const [affectedObjectsText, setAffectedObjectsText] = useState("");
  const [requiredChanges, setRequiredChanges] = useState("");
  const [pushBackNotes, setPushBackNotes] = useState("");
  const [submissionMessage, setSubmissionMessage] = useState<string | null>(null);

  useEffect(() => {
    setSession(loadUiSession());
  }, []);

  useEffect(() => {
    if (!session || !projectId || !runId) {
      setLoading(false);
      return;
    }

    let active = true;
    setLoading(true);
    setErrorMessage(null);

    void getGate1Evidence(session.accessToken, projectId, runId)
      .then((nextEvidence) => {
        if (active) {
          setEvidence(nextEvidence);
        }
      })
      .catch((error: unknown) => {
        if (active) {
          setErrorMessage(error instanceof Error ? error.message : "Unable to load Gate 1.");
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
  }, [projectId, runId, session]);

  const role: SessionRole = session?.role ?? "read_only_auditor";
  const canAct = role === "central_team";

  const handleApprove = async () => {
    if (!session || !projectId || !runId) {
      return;
    }

    setErrorMessage(null);
    setSubmissionMessage(null);
    try {
      await approveGate(session.accessToken, projectId, runId, "gate_1", { notes });
      setSubmissionMessage("Approval submitted.");
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Approval failed.");
    }
  };

  const handlePushBack = async () => {
    if (!session || !projectId || !runId) {
      return;
    }
    const affectedObjects = splitCsv(affectedObjectsText);
    if (affectedObjects.length === 0 || requiredChanges.trim().length === 0) {
      setErrorMessage("Affected objects and required changes are required.");
      return;
    }

    setErrorMessage(null);
    setSubmissionMessage(null);
    try {
      await rejectGate(session.accessToken, projectId, runId, "gate_1", {
        affectedObjects,
        requiredChanges: requiredChanges.trim(),
        notes: pushBackNotes.trim() || null,
      });
      setSubmissionMessage("Push back submitted.");
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Push back failed.");
    }
  };

  return (
    <main className="flex min-h-screen flex-col bg-surface text-slate-800">
      <Topbar role={role} />
      <section className="mx-auto flex w-full max-w-[1600px] flex-1 flex-col gap-4 px-6 py-6">
        <div className="rounded-2xl border border-outline-variant bg-surface-container p-6 shadow-sm">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">Runs / Gate 1</p>
              <h1 className="text-3xl font-semibold tracking-tight text-slate-900">Gate 1 Review</h1>
              <p className="mt-1 text-sm text-slate-600">
                Domain object map, PII classification, and coverage gaps for run <span className="font-mono">{runId}</span>.
              </p>
            </div>
            {canAct ? (
              <div className="flex items-center gap-3">
                <label className="space-y-2">
                  <span className="block text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">Notes</span>
                  <input
                    className="w-72 rounded-md border border-outline-variant bg-white px-3 py-2 text-sm text-slate-900"
                    onChange={(event) => setNotes(event.currentTarget.value)}
                    placeholder="Optional notes"
                    value={notes}
                  />
                </label>
                <button className="rounded-md bg-primary px-4 py-3 text-sm font-semibold text-white" onClick={() => void handleApprove()} type="button">
                  Approve
                </button>
                <button
                  className="rounded-md border border-outline-variant bg-white px-4 py-3 text-sm font-semibold text-slate-700"
                  onClick={() => setPushBackOpen((current) => !current)}
                  type="button"
                >
                  Push back
                </button>
              </div>
            ) : null}
          </div>

          {errorMessage ? (
            <div role="alert" className="mt-4 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
              {errorMessage}
            </div>
          ) : null}
          {submissionMessage ? (
            <div className="mt-4 rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-700">
              {submissionMessage}
            </div>
          ) : null}

          <div className="mt-6 grid gap-4 lg:grid-cols-[1.35fr_0.9fr]">
            <div className="space-y-4">
              <div className="rounded-2xl border border-outline-variant bg-white p-4">
                <div className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">Domain object map</div>
                <table className="mt-3 w-full border-collapse text-left">
                  <thead>
                    <tr className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">
                      <th className="px-3 py-2">Source field</th>
                      <th className="px-3 py-2">Destination field</th>
                      <th className="px-3 py-2">Lookup</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(evidence?.fieldBindings ?? []).map((binding) => (
                      <tr key={`${binding.sourceField}-${binding.destinationField}`} className="border-t border-outline-variant">
                        <td className="px-3 py-2 font-mono text-sm">{binding.sourceField}</td>
                        <td className="px-3 py-2 text-sm">{binding.destinationField}</td>
                        <td className="px-3 py-2 font-mono text-sm text-slate-600">{binding.lookupName ?? "—"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              <div className="rounded-2xl border border-outline-variant bg-white p-4">
                <div className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">PII classification</div>
                <div className="mt-3 flex flex-wrap gap-2">
                  {(evidence?.piiFields ?? []).length === 0 ? (
                    <span className="rounded-full bg-slate-100 px-3 py-1 text-sm text-slate-600">No PII fields detected</span>
                  ) : (
                    (evidence?.piiFields ?? []).map((field) => (
                      <span key={field} className="rounded-full bg-amber-100 px-3 py-1 font-mono text-sm text-amber-900">
                        {field}
                      </span>
                    ))
                  )}
                </div>
              </div>

              <div className="rounded-2xl border border-outline-variant bg-white p-4">
                <div className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">Coverage gaps</div>
                <div className="mt-3 space-y-2">
                  {(evidence?.coverageGaps ?? []).length === 0 ? (
                    <div className="rounded-xl bg-emerald-50 px-3 py-2 text-sm text-emerald-700">No coverage gaps.</div>
                  ) : (
                    (evidence?.coverageGaps ?? []).map((gap) => (
                      <div key={gap} className="rounded-xl bg-amber-50 px-3 py-2 font-mono text-sm text-amber-900">
                        {gap}
                      </div>
                    ))
                  )}
                </div>
              </div>
            </div>

            <aside className="rounded-2xl border border-outline-variant bg-white p-4">
              <div className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">Decision panel</div>
              <div className="mt-3 space-y-3 text-sm text-slate-700">
                <p>Submitting records an approval. It does not call execution directly.</p>
                <div className="flex items-center gap-2">
                  <span className={`rounded-full px-3 py-1 text-xs font-semibold uppercase tracking-[0.16em] ${chipClassName("approved")}`}>
                    Ready
                  </span>
                  <span className="font-mono">{evidence?.mappingSnapshotVersion ?? "—"}</span>
                </div>
              </div>

              {pushBackOpen && canAct ? (
                <div className="mt-4 space-y-3 rounded-xl border border-outline-variant bg-surface px-4 py-4">
                  <label className="space-y-2">
                    <span className="block text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">Affected objects</span>
                    <input
                      aria-label="Affected objects"
                      className="w-full rounded-md border border-outline-variant bg-white px-3 py-2 text-sm text-slate-900"
                      onChange={(event) => setAffectedObjectsText(event.currentTarget.value)}
                      placeholder="Customer, Address"
                      value={affectedObjectsText}
                    />
                  </label>
                  <label className="space-y-2">
                    <span className="block text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">Required changes</span>
                    <textarea
                      aria-label="Required changes"
                      className="min-h-28 w-full rounded-md border border-outline-variant bg-white px-3 py-2 text-sm text-slate-900"
                      onChange={(event) => setRequiredChanges(event.currentTarget.value)}
                      value={requiredChanges}
                    />
                  </label>
                  <label className="space-y-2">
                    <span className="block text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">Notes</span>
                    <textarea
                      aria-label="Push back notes"
                      className="min-h-20 w-full rounded-md border border-outline-variant bg-white px-3 py-2 text-sm text-slate-900"
                      onChange={(event) => setPushBackNotes(event.currentTarget.value)}
                      value={pushBackNotes}
                    />
                  </label>
                  <button className="rounded-md bg-primary px-4 py-3 text-sm font-semibold text-white" onClick={() => void handlePushBack()} type="button">
                    Submit push back
                  </button>
                </div>
              ) : null}
            </aside>
          </div>
        </div>
      </section>
    </main>
  );
}
