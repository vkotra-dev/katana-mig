"use client";

import { useEffect, useMemo, useState } from "react";
import { useParams, useSearchParams } from "next/navigation";
import { Topbar } from "../../../../components/Topbar";
import {
  approveGate,
  getGate2Evidence,
  type Gate2EvidenceRecord,
  type GateLookupRowRecord,
} from "../../../../lib/gates-api";
import { loadUiSession, type SessionRole, type UiSession } from "../../../../lib/session";

type RowFilter = "all" | "confirmed" | "low_confidence" | "unmapped" | "overridden";

function chipClassName(state: GateLookupRowRecord["state"]): string {
  if (state === "confirmed") {
    return "bg-emerald-100 text-emerald-700";
  }
  if (state === "low_confidence") {
    return "bg-amber-100 text-amber-800";
  }
  if (state === "overridden") {
    return "bg-blue-100 text-blue-700";
  }
  return "bg-red-100 text-red-700";
}

export default function Gate2Page() {
  const params = useParams<{ id: string }>();
  const searchParams = useSearchParams();
  const projectId = searchParams.get("projectId");
  const runId = params.id;
  const [session, setSession] = useState<UiSession | null>(null);
  const [evidence, setEvidence] = useState<Gate2EvidenceRecord | null>(null);
  const [rows, setRows] = useState<GateLookupRowRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [filter, setFilter] = useState<RowFilter>("all");
  const [overrideRowIndex, setOverrideRowIndex] = useState<number | null>(null);
  const [overrideValue, setOverrideValue] = useState("");
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

    void getGate2Evidence(session.accessToken, projectId, runId)
      .then((nextEvidence) => {
        if (!active) {
          return;
        }
        setEvidence(nextEvidence);
        setRows(nextEvidence.rows);
      })
      .catch((error: unknown) => {
        if (active) {
          setErrorMessage(error instanceof Error ? error.message : "Unable to load Gate 2.");
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

  const visibleRows = useMemo(
    () => rows.filter((row) => filter === "all" || row.state === filter),
    [filter, rows],
  );

  const unmappedCount = rows.filter((row) => row.state === "unmapped").length;

  const saveOverride = () => {
    if (overrideRowIndex === null) {
      return;
    }
    setRows((current) =>
      current.map((row, index) =>
        index === overrideRowIndex
          ? { ...row, destinationValue: overrideValue.trim(), state: "overridden" }
          : row,
      ),
    );
    setSubmissionMessage("Override saved.");
    setOverrideRowIndex(null);
    setOverrideValue("");
  };

  const bulkApprove = () => {
    setRows((current) => current.map((row) => ({ ...row, state: "confirmed" })));
    setSubmissionMessage("Bulk approval applied.");
  };

  const resolveUnmapped = (rowIndex: number) => {
    setRows((current) =>
      current.map((row, index) =>
        index === rowIndex
          ? { ...row, destinationValue: row.destinationValue ?? "resolved", state: "confirmed" }
          : row,
      ),
    );
    setSubmissionMessage("Unmapped value resolved.");
  };

  const submitForApproval = async () => {
    if (!session || !projectId || !runId || unmappedCount > 0) {
      return;
    }
    setErrorMessage(null);
    try {
      await approveGate(session.accessToken, projectId, runId, "gate_2", { notes: "Gate 2 approved." });
      setSubmissionMessage("Approval submitted.");
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Approval failed.");
    }
  };

  return (
    <main className="flex min-h-screen flex-col bg-surface text-slate-800">
      <Topbar role={role} />
      <section className="mx-auto flex w-full max-w-[1600px] flex-1 flex-col gap-4 px-6 py-6">
        <div className="rounded-2xl border border-outline-variant bg-surface-container p-6 shadow-sm">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">Runs / Gate 2</p>
              <h1 className="text-3xl font-semibold tracking-tight text-slate-900">Gate 2 Review</h1>
              <p className="mt-1 text-sm text-slate-600">
                Lookup Inventory versus Lookup Map for run <span className="font-mono">{runId}</span>.
              </p>
            </div>
            {canAct ? (
              <div className="flex items-center gap-3">
                <button className="rounded-md border border-outline-variant bg-white px-4 py-3 text-sm font-semibold text-slate-700" onClick={bulkApprove} type="button">
                  Bulk approve
                </button>
                <label className="space-y-2">
                  <span className="block text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">State</span>
                  <select
                    className="rounded-md border border-outline-variant bg-white px-3 py-2 text-sm text-slate-900"
                    onChange={(event) => setFilter(event.currentTarget.value as RowFilter)}
                    value={filter}
                  >
                    <option value="all">All states</option>
                    <option value="confirmed">confirmed</option>
                    <option value="low_confidence">low confidence</option>
                    <option value="unmapped">unmapped</option>
                    <option value="overridden">overridden</option>
                  </select>
                </label>
                <button
                  className="rounded-md bg-primary px-4 py-3 text-sm font-semibold text-white disabled:opacity-50"
                  disabled={unmappedCount > 0}
                  onClick={() => void submitForApproval()}
                  type="button"
                >
                  Submit for approval
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
            <div className="rounded-2xl border border-outline-variant bg-white p-4">
              <div className="flex items-center justify-between gap-4">
                <div>
                  <div className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">Lookup rows</div>
                  <div className="mt-1 text-sm text-slate-600">
                    {unmappedCount > 0 ? `${unmappedCount} unmapped values must be resolved.` : "All rows are ready for approval."}
                  </div>
                </div>
                <span className="rounded-full bg-slate-100 px-3 py-1 font-mono text-sm text-slate-700">
                  {evidence?.lookupName ?? "—"}
                </span>
              </div>

              <table className="mt-4 w-full border-collapse text-left">
                <thead>
                  <tr className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">
                    <th className="px-3 py-3">Source value</th>
                    <th className="px-3 py-3">Destination value</th>
                    <th className="px-3 py-3">State</th>
                    <th className="px-3 py-3">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {visibleRows.map((row, index) => (
                    <tr key={`${row.sourceValue}-${index}`} className="border-t border-outline-variant">
                      <td className="px-3 py-3 font-mono text-sm">{row.sourceValue}</td>
                      <td className="px-3 py-3 font-mono text-sm">{row.destinationValue ?? "—"}</td>
                      <td className="px-3 py-3">
                        <span className={`rounded-full px-3 py-1 text-xs font-semibold uppercase tracking-[0.16em] ${chipClassName(row.state)}`}>
                          {row.state.replace("_", " ")}
                        </span>
                      </td>
                      <td className="px-3 py-3">
                        <div className="flex flex-wrap items-center gap-2">
                          <button
                            className="text-sm font-semibold text-primary hover:underline"
                            onClick={() => {
                              setOverrideRowIndex(index);
                              setOverrideValue(row.destinationValue ?? "");
                            }}
                            type="button"
                          >
                            Override
                          </button>
                          <button
                            className="text-sm font-semibold text-primary hover:underline"
                            onClick={() => resolveUnmapped(index)}
                            type="button"
                          >
                            Resolve unmapped
                          </button>
                        </div>
                        {overrideRowIndex === index ? (
                          <div className="mt-3 rounded-xl border border-outline-variant bg-surface px-3 py-3">
                            <label className="space-y-2">
                              <span className="block text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">Override value</span>
                              <input
                                aria-label="Override value"
                                className="w-full rounded-md border border-outline-variant bg-white px-3 py-2 text-sm text-slate-900"
                                onChange={(event) => setOverrideValue(event.currentTarget.value)}
                                value={overrideValue}
                              />
                            </label>
                            <button className="mt-3 rounded-md bg-primary px-4 py-2 text-sm font-semibold text-white" onClick={saveOverride} type="button">
                              Save override
                            </button>
                          </div>
                        ) : null}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <aside className="rounded-2xl border border-outline-variant bg-white p-4">
              <div className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">Decision summary</div>
              <div className="mt-3 space-y-3 text-sm text-slate-700">
                <div className="rounded-xl bg-slate-50 px-3 py-3">
                  Confirmed: <span className="font-mono">{evidence?.confirmedCount ?? 0}</span>
                </div>
                <div className="rounded-xl bg-slate-50 px-3 py-3">
                  Unmapped: <span className="font-mono">{unmappedCount}</span>
                </div>
                <div className="rounded-xl bg-slate-50 px-3 py-3">
                  Submitted gate status is recorded when all rows are mapped.
                </div>
              </div>
            </aside>
          </div>
        </div>
      </section>
    </main>
  );
}
