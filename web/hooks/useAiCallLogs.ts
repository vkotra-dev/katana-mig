import { useState, useEffect, useCallback } from "react";
import { listAiCallLogs, type AICallLogRecord } from "../lib/ai-calls-api";

export interface UseAiCallLogsOptions {
  feature: "feed_mapping" | "codegen" | "feed_analysis" | "lookup_fiber";
  callType?: string;
  artifactId?: string;
}

export interface UseAiCallLogsResult {
  logs: AICallLogRecord[];
  loading: boolean;
  error: string | null;
  hasMore: boolean;
  loadMore: () => Promise<void>;
}

export function useAiCallLogs(
  token: string | null | undefined,
  projectId: string,
  options: UseAiCallLogsOptions
): UseAiCallLogsResult {
  const [logs, setLogs] = useState<AICallLogRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [hasMore, setHasMore] = useState(true);
  const [offset, setOffset] = useState(0);
  const LIMIT = 50;

  const fetchLogs = useCallback(
    async (currentOffset: number, isInitial: boolean) => {
      if (!token) return;
      try {
        const response = await listAiCallLogs(token, projectId, {
          feature: options.feature,
          callType: options.callType,
          artifactId: options.artifactId,
          limit: LIMIT,
          offset: currentOffset,
        });

        if (isInitial) {
          setLogs(response);
        } else {
          setLogs((prev) => [...prev, ...response]);
        }

        setHasMore(response.length === LIMIT);
        setError(null);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to fetch logs");
      } finally {
        setLoading(false);
      }
    },
    [token, projectId, options.feature, options.callType, options.artifactId]
  );

  useEffect(() => {
    setOffset(0);
    setLoading(true);
    fetchLogs(0, true);
  }, [fetchLogs]);

  const loadMore = async () => {
    if (loading || !hasMore) return;
    const nextOffset = offset + LIMIT;
    setOffset(nextOffset);
    await fetchLogs(nextOffset, false);
  };

  return { logs, loading, error, hasMore, loadMore };
}
