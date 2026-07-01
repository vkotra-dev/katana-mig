"use client";

import { useEffect, useState } from "react";
import { AddSourceDialog } from "./AddSourceDialog";
import {
  listFeedContracts,
  type FeedContractRecord,
} from "../../lib/feeds-api";
import type { SessionRole } from "../../lib/session";

export interface SourceListProps {
  projectId: string;
  token: string;
  role: SessionRole;
}

function formatDate(value: string): string {
  return value.slice(0, 10);
}

function sourceTypeLabel(sourceType: FeedContractRecord["sourceType"]): string {
  return sourceType === "csv" ? "CSV" : "Fixed-Length";
}

export function SourceList({ projectId, token, role }: SourceListProps) {
  const [sources, setSources] = useState<FeedContractRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [dialogOpen, setDialogOpen] = useState(false);

  useEffect(() => {
    let active = true;
    setLoading(true);
    setErrorMessage(null);
    void listFeedContracts(token, projectId)
      .then((response) => {
        if (active) {
          setSources(response);
        }
      })
      .catch((error: unknown) => {
        if (active) {
          setErrorMessage(error instanceof Error ? error.message : "Unable to load sources.");
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
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-xl font-semibold text-slate-900">Sources</h2>
          <p className="text-sm text-slate-600">Declared source contracts and uploaded slices.</p>
        </div>
        {role === "central_team" ? (
          <button
            className="rounded-md bg-primary px-4 py-3 text-sm font-semibold text-white"
            onClick={() => setDialogOpen(true)}
            type="button"
          >
            Add Source
          </button>
        ) : null}
      </div>

      {loading ? (
        <div className="rounded-xl border border-outline-variant bg-surface px-4 py-3 text-sm text-slate-600">
          Loading sources...
        </div>
      ) : errorMessage ? (
        <div role="alert" className="rounded-xl border border-error/30 bg-error/10 px-4 py-3 text-sm text-error">
          {errorMessage}
        </div>
      ) : sources.length === 0 ? (
        <div className="rounded-xl border border-dashed border-outline-variant bg-surface px-4 py-8 text-sm text-slate-500">
          No source contracts yet.
        </div>
      ) : (
        <div className="overflow-hidden rounded-xl border border-outline-variant">
          <table className="w-full border-collapse text-left">
            <thead className="bg-surface">
              <tr className="text-xs uppercase tracking-[0.16em] text-slate-500">
                <th className="px-4 py-3">Label</th>
                <th className="px-4 py-3">Type</th>
                <th className="px-4 py-3">Encoding</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3">Created</th>
                <th className="px-4 py-3">Lookup</th>
              </tr>
            </thead>
            <tbody>
              {sources.map((source) => (
                <tr key={source.sourceDefinitionId} className="border-t border-outline-variant">
                  <td className="px-4 py-3">
                    <div className="text-sm font-semibold text-slate-900">{source.label}</div>
                    <div className="mono-id mt-1">{source.sourceDefinitionId}</div>
                  </td>
                  <td className="px-4 py-3 text-sm text-slate-700">{sourceTypeLabel(source.sourceType)}</td>
                  <td className="px-4 py-3 text-sm text-slate-700">{source.encoding}</td>
                  <td className="px-4 py-3 text-sm text-slate-700">{source.status}</td>
                  <td className="px-4 py-3 text-sm text-slate-700">{formatDate(source.createdAt)}</td>
                  <td className="px-4 py-3">
                    <a
                      className="inline-flex rounded-md border border-outline-variant px-3 py-2 text-sm font-semibold text-slate-700 hover:bg-outline-variant/40"
                      href={`/projects/${projectId}/sources/${source.sourceDefinitionId}/lookup`}
                    >
                      Open lookup
                    </a>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <AddSourceDialog
        open={dialogOpen}
        onClose={() => setDialogOpen(false)}
        onCreated={async () => {
          const response = await listFeedContracts(token, projectId);
          setSources(response);
        }}
        projectId={projectId}
        token={token}
      />
    </section>
  );
}
