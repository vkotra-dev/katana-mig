"use client";

import { useEffect, useState } from "react";
import { AddSourceDialog } from "./AddSourceDialog";
import {
  getSchemaAnalysis,
  triggerSchemaAnalysis,
  type SchemaAnalysisRecord,
} from "../../lib/codegen-api";
import { listFeedContracts, type FeedContractRecord } from "../../lib/feeds-api";
import type { SessionRole } from "../../lib/session";

export interface SourceListProps {
  projectId: string;
  token: string;
  role: SessionRole;
  destinationSchemaDdl?: string | null;
  onFeedClick: (sourceDefinitionId: string) => void;
}

function formatDate(value: string): string {
  return value.slice(0, 10);
}

function sourceTypeLabel(sourceType: FeedContractRecord["sourceType"]): string {
  return sourceType === "csv" ? "CSV" : "Fixed-Length";
}

export function SourceList({ projectId, token, role, destinationSchemaDdl = null, onFeedClick }: SourceListProps) {
  const [sources, setSources] = useState<FeedContractRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [analysis, setAnalysis] = useState<SchemaAnalysisRecord | null | undefined>(undefined);
  const [analysisLoading, setAnalysisLoading] = useState(false);
  const [analysisErrorMessage, setAnalysisErrorMessage] = useState<string | null>(null);
  const [analysisActionLoading, setAnalysisActionLoading] = useState(false);

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

  useEffect(() => {
    if (sources.length === 0) {
      setAnalysis(undefined);
      setAnalysisErrorMessage(null);
      setAnalysisLoading(false);
      return;
    }

    let active = true;
    setAnalysisLoading(true);
    setAnalysisErrorMessage(null);
    void getSchemaAnalysis(token, projectId)
      .then((response) => {
        if (active) {
          setAnalysis(response);
        }
      })
      .catch((error: unknown) => {
        if (active) {
          setAnalysisErrorMessage(error instanceof Error ? error.message : "Unable to load schema analysis.");
        }
      })
      .finally(() => {
        if (active) {
          setAnalysisLoading(false);
        }
      });

    return () => {
      active = false;
    };
  }, [projectId, token, sources.length]);

  const handleAnalyze = async (): Promise<void> => {
    if (!destinationSchemaDdl) {
      return;
    }
    setAnalysisErrorMessage(null);
    setAnalysisActionLoading(true);
    try {
      const response = await triggerSchemaAnalysis(token, projectId);
      setAnalysis(response);
    } catch (error) {
      setAnalysisErrorMessage(error instanceof Error ? error.message : "Unable to analyze the destination schema.");
    } finally {
      setAnalysisActionLoading(false);
    }
  };

  return (
    <section className="space-y-4 rounded-2xl border border-outline-variant bg-surface-container p-6 shadow-sm">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-xl font-semibold text-slate-900">Feeds</h2>
          <p className="text-sm text-slate-600">Declared feed contracts and uploaded slices.</p>
        </div>
        {role === "central_team" ? (
          <button
            className="rounded-md bg-primary px-4 py-3 text-sm font-semibold text-white"
            onClick={() => setDialogOpen(true)}
            type="button"
          >
            Add Feed
          </button>
        ) : null}
      </div>

      {analysisErrorMessage ? (
        <div role="alert" className="rounded-xl border border-error/30 bg-error/10 px-4 py-3 text-sm text-error">
          {analysisErrorMessage}
        </div>
      ) : null}

      {sources.length > 0 && analysisLoading ? (
        <div className="rounded-xl border border-outline-variant bg-surface px-4 py-3 text-sm text-slate-600">
          Checking schema analysis...
        </div>
      ) : null}

      {sources.length > 0 && analysis !== undefined ? (
        <div className="rounded-xl border border-primary/30 bg-primary/5 px-4 py-3">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="space-y-1">
              <div className="text-sm font-semibold text-slate-900">
                {analysis === null
                  ? "Analyze your destination schema to enable dependency-ordered SQL delivery."
                  : `Destination schema was last analyzed at ${formatDate(analysis.analyzedAt)}.`}
              </div>
              <div className="text-xs text-slate-600">
                Destination schema analysis sorts delivery bundles by foreign-key dependency.
              </div>
            </div>
            <button
              className="rounded-full bg-primary px-4 py-2 text-sm font-semibold text-white disabled:opacity-60"
              disabled={analysisActionLoading || !destinationSchemaDdl}
              onClick={() => void handleAnalyze()}
              title={destinationSchemaDdl ? undefined : "Set destination_schema_ddl on the project first"}
              type="button"
            >
              {analysis === null ? "Analyze DDL" : "Re-analyze DDL"}
            </button>
          </div>
        </div>
      ) : null}

      {loading ? (
        <div className="rounded-xl border border-outline-variant bg-surface px-4 py-3 text-sm text-slate-600">
          Loading feeds...
        </div>
      ) : errorMessage ? (
        <div role="alert" className="rounded-xl border border-error/30 bg-error/10 px-4 py-3 text-sm text-error">
          {errorMessage}
        </div>
      ) : sources.length === 0 ? (
        <div className="rounded-xl border border-dashed border-outline-variant bg-surface px-4 py-8 text-sm text-slate-500">
          No feed contracts yet.
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
                <th className="px-4 py-3">Actions</th>
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
                    <button
                      className="inline-flex rounded-md border border-outline-variant px-3 py-2 text-sm font-semibold text-slate-700 hover:bg-outline-variant/40"
                      onClick={() => onFeedClick(source.sourceDefinitionId)}
                      type="button"
                    >
                      Open feed
                    </button>
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
