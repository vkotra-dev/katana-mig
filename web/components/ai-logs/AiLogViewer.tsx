import { useState } from "react";
import { useAiCallLogs } from "../../hooks/useAiCallLogs";
import { type AICallLogRecord } from "../../lib/ai-calls-api";

export interface AiLogViewerProps {
  token: string | null | undefined;
  projectId: string;
  feature: "feed_mapping" | "codegen" | "feed_analysis" | "lookup_fiber";
  callType?: string;
  artifactId?: string;
  emptyLabel?: string;
  canViewLogs?: boolean;
}

interface InspectModalProps {
  callId: string;
  logs: AICallLogRecord[];
  onClose: () => void;
}

const InspectModal = ({ callId, logs, onClose }: InspectModalProps) => {
  const [activeTab, setActiveTab] = useState<"system" | "user" | "raw">("system");
  const [copyFeedback, setCopyFeedback] = useState<string | null>(null);

  const log = logs.find((l) => l.callId === callId);

  if (!log) return null;

  const handleCopy = async (text: string) => {
    try {
      await navigator.clipboard.writeText(text);
      setCopyFeedback("Copied!");
      setTimeout(() => setCopyFeedback(null), 2000);
    } catch (err) {
      setCopyFeedback("Copy failed");
      setTimeout(() => setCopyFeedback(null), 2000);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm p-4" onClick={onClose}>
      <div className="flex h-[80vh] w-full max-w-4xl flex-col rounded-2xl border border-outline bg-surface-container shadow-2xl overflow-hidden" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between border-b border-outline-variant px-6 py-4 bg-surface">
          <div className="flex flex-col">
            <h3 className="text-lg font-semibold text-slate-900">AI Call Log Details</h3>
            <p className="text-xs font-mono text-slate-500">{log.callType} · {log.modelId} · {new Date(log.calledAt).toLocaleString()}</p>
          </div>
          <button
            onClick={onClose}
            className="text-slate-500 hover:text-slate-700 text-xl"
          >
            ✕
          </button>
        </div>

        <div className="flex border-b border-outline-variant bg-surface px-6">
          {(["system", "user", "raw"] as const).map((tab) => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              className={`border-b-2 px-4 py-3 text-sm font-semibold transition ${
                activeTab === tab
                  ? "border-primary text-primary"
                  : "border-transparent text-slate-600 hover:text-slate-900"
              }`}
            >
              {tab === "system" ? "System Prompt" : tab === "user" ? "User Prompt" : "Raw JSON"}
            </button>
          ))}
        </div>

        <div className="flex-1 overflow-auto bg-surface-container-low p-6 font-mono text-sm text-slate-800 relative">
          <div className="absolute top-4 right-4 z-10 flex items-center gap-2">
            {copyFeedback && (
              <span className="text-xs font-sans text-emerald-600 animate-pulse">{copyFeedback}</span>
            )}
            <button
              onClick={() => handleCopy(
                activeTab === "system" ? log.systemPrompt :
                activeTab === "user" ? log.userPrompt :
                JSON.stringify(log, null, 2)
              )}
              className="rounded-lg border border-outline bg-surface px-3 py-1.5 text-xs font-semibold text-slate-700 hover:bg-slate-50"
            >
              Copy
            </button>
          </div>

          {log.errorDetail && (
            <div className="mb-4 rounded-xl border border-red-500/20 bg-red-50 p-4 text-xs text-red-700">
              <span className="font-bold uppercase tracking-wider block mb-1">Error</span>
              {log.errorDetail}
            </div>
          )}

          <pre className="whitespace-pre-wrap break-words rounded-lg bg-surface p-4 overflow-auto max-h-full">
            {activeTab === "system" ? log.systemPrompt :
             activeTab === "user" ? log.userPrompt :
             JSON.stringify(log, null, 2)}
          </pre>
        </div>
      </div>
    </div>
  );
};

export function AiLogViewer({
  token,
  projectId,
  feature,
  callType,
  artifactId,
  emptyLabel = "No AI logs found.",
  canViewLogs = false,
}: AiLogViewerProps) {
  const [inspectingCallId, setInspectingCallId] = useState<string | null>(null);

  const { logs, loading, error, hasMore, loadMore } = useAiCallLogs(token, projectId, {
    feature,
    callType,
    artifactId,
  });


  if (!canViewLogs) return null;
  if (error) return <div className="text-error text-sm p-4">{error}</div>;

  return (
    <div className="space-y-4">
      <div className="overflow-hidden rounded-xl border border-outline-variant">
        <table className="w-full border-collapse text-left text-sm">
          <thead className="bg-surface text-xs uppercase tracking-[0.16em] text-slate-500">
            <tr>
              <th className="px-4 py-3">Call Type</th>
              <th className="px-4 py-3">Model ID</th>
              <th className="px-4 py-3">Timestamp</th>
              <th className="px-4 py-3 text-right">Action</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-outline-variant">
            {logs.length === 0 && !loading ? (
              <tr>
                <td colSpan={4} className="px-4 py-8 text-center text-slate-500">{emptyLabel}</td>
              </tr>
            ) : (
              logs.map((log) => (
                <tr key={log.callId} className="hover:bg-slate-50/50 transition-colors">
                  <td className="px-4 py-3 font-medium">{log.callType || "N/A"}</td>
                  <td className="px-4 py-3 font-mono text-xs text-slate-600">{log.modelId}</td>
                  <td className="px-4 py-3 text-slate-600">
                    {new Date(log.calledAt).toLocaleString()}
                  </td>
                  <td className="px-4 py-3 text-right">
                    <button
                      onClick={() => setInspectingCallId(log.callId)}
                      className="text-primary font-semibold hover:underline"
                    >
                      Inspect
                    </button>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {loading && <div className="text-center py-4 text-sm text-slate-500">Loading logs...</div>}

      {!loading && hasMore && (
        <button
          onClick={loadMore}
          className="w-full rounded-lg border border-outline-variant bg-surface py-2 text-sm font-semibold text-slate-700 hover:bg-slate-50"
        >
          Load More
        </button>
      )}

      {inspectingCallId && (
        <InspectModal
          callId={inspectingCallId}
          logs={logs}
          onClose={() => setInspectingCallId(null)}
        />
      )}
    </div>
  );
};
