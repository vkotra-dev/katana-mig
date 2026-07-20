import { API_BASE_URL } from "./api-base";

export interface AICallLogRecord {
  callId: string;
  feature: string;
  callType: string;
  artifactId: string | null;
  modelId: string;
  systemPrompt: string;
  userPrompt: string;
  rawResponse: string | null;
  errorDetail: string | null;
  calledAt: string;
}

export async function listAiCallLogs(
  token: string,
  projectId: string,
  options?: { feature?: string; callType?: string; artifactId?: string; limit?: number; offset?: number }
): Promise<AICallLogRecord[]> {
  const params = new URLSearchParams();
  if (options?.feature) params.set("feature", options.feature);
  if (options?.callType) params.set("call_type", options.callType);
  if (options?.artifactId) params.set("artifact_id", options.artifactId);
  if (options?.limit !== undefined) params.set("limit", options.limit.toString());
  if (options?.offset !== undefined) params.set("offset", options.offset.toString());
  const qs = params.toString();
  const url = `${API_BASE_URL}/projects/${projectId}/ai-calls${qs ? `?${qs}` : ""}`;
  const res = await fetch(url, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) throw new Error(`Failed to fetch AI call logs: ${res.status}`);
  const data: Array<{
    call_id: string;
    feature: string;
    call_type: string;
    artifact_id: string | null;
    model_id: string;
    system_prompt: string;
    user_prompt: string;
    raw_response: string | null;
    error_detail: string | null;
    called_at: string;
  }> = await res.json();
  return data.map((r) => ({
    callId: r.call_id,
    feature: r.feature,
    callType: r.call_type,
    artifactId: r.artifact_id,
    modelId: r.model_id,
    systemPrompt: r.system_prompt,
    userPrompt: r.user_prompt,
    rawResponse: r.raw_response,
    errorDetail: r.error_detail,
    calledAt: r.called_at,
  }));
}
