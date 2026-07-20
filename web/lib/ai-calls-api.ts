import { API_BASE_URL } from "./api-base";

export interface AICallLogRecord {
  callId: string;
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
  options?: { callType?: string; artifactId?: string }
): Promise<AICallLogRecord[]> {
  const params = new URLSearchParams();
  if (options?.callType) params.set("call_type", options.callType);
  if (options?.artifactId) params.set("artifact_id", options.artifactId);
  const qs = params.toString();
  const url = `${API_BASE_URL}/projects/${projectId}/ai-calls${qs ? `?${qs}` : ""}`;
  const res = await fetch(url, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) throw new Error(`Failed to fetch AI call logs: ${res.status}`);
  const data: Array<{
    call_id: string;
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
