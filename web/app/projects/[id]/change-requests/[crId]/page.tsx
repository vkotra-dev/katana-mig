"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Topbar } from "../../../../../components/Topbar";
import {
  getChangeRequest,
  resolveChangeRequest,
  type ChangeRequestRecord,
} from "../../../../../lib/change-requests-api";
import { loadUiSession, type SessionRole, type UiSession } from "../../../../../lib/session";

function normalizeErrorMessage(error: unknown, fallback: string): string {
  if (!(error instanceof Error)) {
    return fallback;
  }

  const message = error.message.trim();
  if (!message.startsWith("{")) {
    return message || fallback;
  }

  try {
    const parsed = JSON.parse(message) as { error?: { message?: string } };
    return parsed.error?.message ?? message;
  } catch {
    return message || fallback;
  }
}

export default function CrReviewPage({
  params,
}: {
  params: Promise<{ id: string; crId: string }>;
}) {
  const router = useRouter();
  const [routeParams, setRouteParams] = useState<{ id: string; crId: string } | null>(null);
  const [session, setSession] = useState<UiSession | null>(null);
  const [cr, setCr] = useState<ChangeRequestRecord | null>(null);
  const [acceptedValue, setAcceptedValue] = useState("");
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

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
      setLoading(false);
      return;
    }

    let active = true;
    setLoading(true);
    setLoadError(null);

    void getChangeRequest(session.accessToken, routeParams.id, routeParams.crId)
      .then((response) => {
        if (active) {
          setCr(response);
        }
      })
      .catch((error: unknown) => {
        if (active) {
          setLoadError(normalizeErrorMessage(error, "Unable to load change request."));
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

  const handleSubmit = async (): Promise<void> => {
    if (!session || !routeParams || !acceptedValue.trim()) {
      return;
    }

    setSubmitting(true);
    setSubmitError(null);

    try {
      await resolveChangeRequest(session.accessToken, routeParams.id, routeParams.crId, {
        acceptedValue: acceptedValue.trim(),
      });
      router.push(`/projects/${routeParams.id}`);
    } catch (error: unknown) {
      setSubmitError(normalizeErrorMessage(error, "Unable to resolve change request."));
    } finally {
      setSubmitting(false);
    }
  };

  const role: SessionRole = session?.role ?? "read_only_auditor";
  const payload = cr?.payload ?? null;

  return (
    <main className="flex min-h-screen flex-col bg-surface text-slate-800">
      <Topbar role={role} />
      <section className="mx-auto flex w-full max-w-[900px] flex-1 flex-col gap-4 px-6 py-6">
        <div className="flex items-center justify-between">
          <button
            className="rounded-md border border-outline-variant bg-surface-container px-3 py-2 text-sm font-medium text-slate-700 hover:bg-outline-variant"
            onClick={() => router.push(`/projects/${routeParams?.id ?? ""}`)}
            type="button"
          >
            Back to project
          </button>
        </div>

        {loading ? (
          <div className="rounded-2xl border border-outline-variant bg-surface-container p-8 text-sm text-slate-600">
            Loading change request...
          </div>
        ) : loadError ? (
          <div
            role="alert"
            className="rounded-2xl border border-error/30 bg-error/10 px-4 py-3 text-sm text-error"
          >
            {loadError}
          </div>
        ) : cr ? (
          <div className="space-y-6 rounded-2xl border border-outline-variant bg-surface-container p-6 shadow-sm">
            <div className="space-y-1">
              <h1 className="text-2xl font-semibold text-slate-900">{cr.title}</h1>
              <p className="text-sm text-slate-500">
                Change request ID: <span className="font-mono">{cr.changeRequestId}</span>
              </p>
            </div>

            <div className="grid gap-3 sm:grid-cols-2">
              <div className="rounded-xl border border-outline-variant bg-surface px-4 py-3">
                <div className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">
                  Destination object
                </div>
                <div className="mt-1 text-sm text-slate-900">{payload?.destinationObjectName ?? "—"}</div>
              </div>
              <div className="rounded-xl border border-outline-variant bg-surface px-4 py-3">
                <div className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">Run ID</div>
                <div className="mt-1 font-mono text-sm text-slate-900">{payload?.runId ?? "—"}</div>
              </div>
              <div className="rounded-xl border border-outline-variant bg-surface px-4 py-3">
                <div className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">
                  Lookup name
                </div>
                <div className="mt-1 text-sm text-slate-900">{payload?.lookupName ?? "—"}</div>
              </div>
              <div className="rounded-xl border border-outline-variant bg-surface px-4 py-3">
                <div className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">
                  Unmapped value found
                </div>
                <div className="mt-1 font-mono text-sm font-semibold text-rose-700">
                  {payload?.unmappedValue ?? "—"}
                </div>
              </div>
            </div>

            <div className="space-y-2">
              <label className="block text-sm font-semibold text-slate-900" htmlFor="accepted-value">
                Map this to:
              </label>
              <input
                className="w-full rounded-md border border-outline-variant bg-white px-3 py-2 text-sm text-slate-900 focus:outline-none focus:ring-2 focus:ring-primary/40"
                id="accepted-value"
                onChange={(event) => setAcceptedValue(event.currentTarget.value)}
                placeholder="e.g. RETIRED"
                type="text"
                value={acceptedValue}
              />
            </div>

            {submitError ? (
              <div
                role="alert"
                className="rounded-xl border border-error/30 bg-error/10 px-4 py-3 text-sm text-error"
              >
                {submitError}
              </div>
            ) : null}

            <div className="flex gap-3">
              <button
                className="rounded-md bg-primary px-4 py-2 text-sm font-semibold text-white disabled:opacity-60"
                disabled={submitting || !acceptedValue.trim()}
                onClick={() => void handleSubmit()}
                type="button"
              >
                Submit
              </button>
            </div>
          </div>
        ) : null}
      </section>
    </main>
  );
}
