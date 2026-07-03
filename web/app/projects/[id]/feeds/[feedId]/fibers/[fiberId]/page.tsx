"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { Topbar } from "../../../../../../../components/Topbar";
import { FeedCommentThread } from "../../../../../../../components/feeds/FeedCommentThread";
import {
  approveFiber,
  assignFiber,
  getFiber,
  triggerFiber,
  type FiberRecord,
} from "../../../../../../../lib/feeds-api";
import { loadUiSession, type SessionRole, type UiSession } from "../../../../../../../lib/session";

type ActionState = "idle" | "assigning" | "approving" | "triggering";

function statusBadgeClass(status: string): string {
  if (status === "operator_triggered" || status === "codegen_complete") {
    return "border-emerald-500/20 bg-emerald-500/10 text-emerald-700";
  }
  if (status === "business_approved") {
    return "border-blue-500/20 bg-blue-500/10 text-blue-700";
  }
  if (status === "operator_assigned") {
    return "border-amber-500/20 bg-amber-500/10 text-amber-700";
  }
  return "border-slate-200 bg-slate-50 text-slate-600";
}

function formatError(error: unknown, fallback: string): string {
  if (error instanceof Error && error.message.trim()) {
    return error.message;
  }
  return fallback;
}

export default function FiberDetailPage() {
  const router = useRouter();
  const params = useParams<{ id: string; feedId: string; fiberId: string }>();
  const projectId = params.id;
  const feedId = params.feedId;
  const fiberId = params.fiberId;

  const [session, setSession] = useState<UiSession | null>(null);
  const [fiber, setFiber] = useState<FiberRecord | null>(null);
  const [loading, setLoading] = useState(true);
  const [actionState, setActionState] = useState<ActionState>("idle");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  useEffect(() => {
    setSession(loadUiSession());
  }, []);

  useEffect(() => {
    if (!session) {
      setLoading(false);
      setErrorMessage("Sign in to view fiber details.");
      return;
    }

    let active = true;
    setLoading(true);
    setErrorMessage(null);

    void getFiber(session.accessToken, projectId, feedId, fiberId)
      .then((nextFiber) => {
        if (!active) {
          return;
        }
        setFiber(nextFiber);
      })
      .catch((error: unknown) => {
        if (!active) {
          return;
        }
        setFiber(null);
        setErrorMessage(formatError(error, "Unable to load fiber details."));
      })
      .finally(() => {
        if (active) {
          setLoading(false);
        }
      });

    return () => {
      active = false;
    };
  }, [feedId, fiberId, projectId, session]);

  async function runAction(kind: Exclude<ActionState, "idle">): Promise<void> {
    if (!session || !fiber) {
      return;
    }

    setActionState(kind);
    setErrorMessage(null);
    try {
      const nextFiber =
        kind === "assigning"
          ? await assignFiber(session.accessToken, projectId, feedId, fiberId)
          : kind === "approving"
            ? await approveFiber(session.accessToken, projectId, feedId, fiberId)
            : await triggerFiber(session.accessToken, projectId, feedId, fiberId);
      setFiber(nextFiber);
    } catch (error: unknown) {
      setErrorMessage(formatError(error, "Unable to update fiber."));
    } finally {
      setActionState("idle");
    }
  }

  const role: SessionRole = session?.role ?? "read_only_auditor";
  const canAssign = role === "central_team" && fiber?.status === "mapped";
  const canApprove = role === "project_stakeholder" && fiber?.status === "operator_assigned";
  const canTrigger = role === "central_team" && fiber?.status === "business_approved";
  const actionBusy = actionState !== "idle";

  return (
    <main className="flex min-h-screen flex-col bg-slate-50 text-slate-900">
      <Topbar role={role} />
      <section className="mx-auto flex w-full max-w-6xl flex-1 flex-col gap-6 px-6 py-6">
        <div className="flex items-center gap-2 text-xs text-slate-500">
          <button className="hover:text-slate-900 hover:underline" onClick={() => router.back()} type="button">
            ← Back
          </button>
          <span className="text-slate-300">|</span>
          <span className="font-mono uppercase tracking-[0.2em]">Fiber Detail</span>
        </div>

        {errorMessage && (
          <div role="alert" className="rounded-2xl border border-red-500/20 bg-red-500/10 px-4 py-3 text-sm text-red-700">
            {errorMessage}
          </div>
        )}

        {loading && (
          <div className="rounded-2xl border border-slate-200 bg-white p-8 text-sm text-slate-600">
            Loading fiber details...
          </div>
        )}

        {!loading && fiber && (
          <>
            <div className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
              <div className="flex flex-wrap items-start justify-between gap-4">
                <div className="space-y-2">
                  <p className="font-mono text-xs uppercase tracking-[0.2em] text-slate-500">{fiber.fiberType}</p>
                  <h1 className="text-2xl font-semibold text-slate-950">{fiber.fiberKey}</h1>
                </div>
                <span
                  className={`inline-flex rounded-full border px-3 py-1 font-mono text-xs uppercase ${statusBadgeClass(fiber.status)}`}
                >
                  {fiber.status}
                </span>
              </div>

              <dl className="mt-6 grid gap-4 sm:grid-cols-3">
                <div className="rounded-2xl bg-slate-50 p-4">
                  <dt className="font-mono text-xs uppercase tracking-[0.2em] text-slate-500">Source</dt>
                  <dd className="mt-2 text-sm text-slate-900">{fiber.source}</dd>
                </div>
                <div className="rounded-2xl bg-slate-50 p-4">
                  <dt className="font-mono text-xs uppercase tracking-[0.2em] text-slate-500">Feed</dt>
                  <dd className="mt-2 text-sm text-slate-900">{fiber.feedId}</dd>
                </div>
                <div className="rounded-2xl bg-slate-50 p-4">
                  <dt className="font-mono text-xs uppercase tracking-[0.2em] text-slate-500">Project</dt>
                  <dd className="mt-2 text-sm text-slate-900">{fiber.projectId}</dd>
                </div>
              </dl>

              {(canAssign || canApprove || canTrigger) && (
                <div className="mt-6 flex flex-wrap gap-3">
                  {canAssign && (
                    <button
                      className="rounded-xl bg-slate-900 px-5 py-2.5 text-sm font-semibold text-white hover:bg-slate-800 disabled:opacity-60"
                      disabled={actionBusy}
                      onClick={() => void runAction("assigning")}
                      type="button"
                    >
                      {actionState === "assigning" ? "Assigning..." : "Assign for Review"}
                    </button>
                  )}
                  {canApprove && (
                    <button
                      className="rounded-xl bg-slate-900 px-5 py-2.5 text-sm font-semibold text-white hover:bg-slate-800 disabled:opacity-60"
                      disabled={actionBusy}
                      onClick={() => void runAction("approving")}
                      type="button"
                    >
                      {actionState === "approving" ? "Approving..." : "Approve"}
                    </button>
                  )}
                  {canTrigger && (
                    <button
                      className="rounded-xl bg-slate-900 px-5 py-2.5 text-sm font-semibold text-white hover:bg-slate-800 disabled:opacity-60"
                      disabled={actionBusy}
                      onClick={() => void runAction("triggering")}
                      type="button"
                    >
                      {actionState === "triggering" ? "Triggering..." : "Trigger"}
                    </button>
                  )}
                </div>
              )}
            </div>

            {fiber.fiberType === "domain_object" && fiber.fieldBindings && (
              <section className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
                <div className="mb-4">
                  <h2 className="text-lg font-semibold text-slate-950">Field Bindings</h2>
                  <p className="text-sm text-slate-500">domain_object field_bindings</p>
                </div>
                <div className="overflow-hidden rounded-2xl border border-slate-200">
                  <table className="min-w-full divide-y divide-slate-200 text-sm">
                    <thead className="bg-slate-50 text-left text-slate-500">
                      <tr>
                        <th className="px-4 py-3 font-medium">Source Field</th>
                        <th className="px-4 py-3 font-medium">Destination Field</th>
                        <th className="px-4 py-3 font-medium">Lookup</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100 bg-white text-slate-900">
                      {fiber.fieldBindings.map((binding) => (
                        <tr key={`${binding.sourceField}-${binding.destinationField}`}>
                          <td className="px-4 py-3 font-mono text-xs">{binding.sourceField}</td>
                          <td className="px-4 py-3 font-mono text-xs">{binding.destinationField}</td>
                          <td className="px-4 py-3 text-xs text-slate-600">{binding.lookupName ?? "—"}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </section>
            )}

            {fiber.fiberType === "lookup" && fiber.proposedMappings && (
              <section className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
                <div className="mb-4">
                  <h2 className="text-lg font-semibold text-slate-950">Proposed Mappings</h2>
                  <p className="text-sm text-slate-500">lookup proposed-mappings</p>
                </div>
                <div className="rounded-2xl bg-slate-950 p-4 text-sm text-slate-100">
                  <pre className="overflow-x-auto whitespace-pre-wrap">
                    {JSON.stringify(fiber.proposedMappings, null, 2)}
                  </pre>
                </div>
              </section>
            )}

            {session && fiber && (
              <FeedCommentThread
                feedId={feedId}
                projectId={projectId}
                token={session.accessToken}
              />
            )}
          </>
        )}
      </section>
    </main>
  );
}
