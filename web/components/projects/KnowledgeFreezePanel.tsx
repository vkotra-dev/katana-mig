"use client";

import { useEffect, useState } from "react";
import { listKnowledgeFreezes, type KnowledgeFreezeRecord } from "../../lib/runs-api";

export interface KnowledgeFreezePanelProps {
  projectId: string;
  token: string;
}

function formatDate(value: string | null): string {
  return value ? value.slice(0, 10) : "—";
}

function formatDateTime(value: string | null): string {
  return value ? value.slice(0, 16).replace("T", " ") : "—";
}

export function KnowledgeFreezePanel({ projectId, token }: KnowledgeFreezePanelProps) {
  const [rows, setRows] = useState<KnowledgeFreezeRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    setLoading(true);
    setErrorMessage(null);
    void listKnowledgeFreezes(token, projectId)
      .then((response) => {
        if (active) {
          setRows(response);
        }
      })
      .catch((error: unknown) => {
        if (active) {
          setErrorMessage(error instanceof Error ? error.message : "Unable to load knowledge freezes.");
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
  }, [projectId, token]);

  return (
    <section className="space-y-4 rounded-2xl border border-outline-variant bg-surface-container p-6 shadow-sm">
      <div>
        <h2 className="text-xl font-semibold text-slate-900">Knowledge-freeze history</h2>
        <p className="text-sm text-slate-600">Read-only history of runs where a freeze was recorded.</p>
      </div>

      {loading ? (
        <div className="rounded-xl border border-outline-variant bg-surface px-4 py-3 text-sm text-slate-600">
          Loading knowledge freezes...
        </div>
      ) : errorMessage ? (
        <div role="alert" className="rounded-xl border border-error/30 bg-error/10 px-4 py-3 text-sm text-error">
          {errorMessage}
        </div>
      ) : rows.length === 0 ? (
        <div className="rounded-xl border border-dashed border-outline-variant bg-surface px-4 py-8 text-sm text-slate-500">
          No knowledge freezes yet.
        </div>
      ) : (
        <div className="overflow-hidden rounded-xl border border-outline-variant">
          <table className="w-full border-collapse text-left">
            <thead className="bg-surface">
              <tr className="text-xs uppercase tracking-[0.16em] text-slate-500">
                <th className="px-4 py-3">Date</th>
                <th className="px-4 py-3">Run ID</th>
                <th className="px-4 py-3">Destination object</th>
                <th className="px-4 py-3">Environment</th>
                <th className="px-4 py-3">Frozen artifact ID</th>
                <th className="px-4 py-3">Status</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.run_id} className="border-t border-outline-variant">
                  <td className="px-4 py-3 text-sm text-slate-700">
                    <div className="font-medium text-slate-900">{formatDate(row.started_at ?? row.created_at)}</div>
                    <div className="text-xs text-slate-500">{formatDateTime(row.started_at)}</div>
                  </td>
                  <td className="px-4 py-3">
                    <span className="mono-id">{row.run_id}</span>
                  </td>
                  <td className="px-4 py-3 text-sm text-slate-700">{row.destination_object_name}</td>
                  <td className="px-4 py-3 text-sm text-slate-700">{row.environment ?? "—"}</td>
                  <td className="px-4 py-3">
                    <span className="mono-id">{row.knowledge_freeze_version}</span>
                  </td>
                  <td className="px-4 py-3 text-sm text-slate-700">{row.status}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
