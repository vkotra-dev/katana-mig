import { API_BASE_URL } from "./api-base";

export type RunStatus = "queued" | "running" | "paused" | "completed" | "failed" | "awaiting_approval";

export interface RunRecord {
  run_id: string;
  project_id: string;
  destination_object_name: string;
  source_definition_reference: string | null;
  environment: string | null;
  status: RunStatus;
  current_stage: string | null;
  source_slice_version: string | null;
  mapping_snapshot_version: string | null;
  lookup_snapshot_version: string | null;
  lookup_snapshot_versions: Record<string, string> | null;
  code_generation_input_snapshot_version: string | null;
  codegen_artifact_id: string | null;
  knowledge_freeze_version: string | null;
  start_metadata: Record<string, unknown> | null;
  pause_metadata: Record<string, unknown> | null;
  resume_metadata: Record<string, unknown> | null;
  completion_metadata: Record<string, unknown> | null;
  started_at: string | null;
  last_checkpoint_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface RunCheckpoint {
  checkpoint_id: string;
  run_id: string;
  stage: string | null;
  current_object: string | null;
  current_environment: string | null;
  approved_snapshots: Record<string, unknown> | null;
  last_completed_row: number | null;
  pause_reason: string | null;
  created_at: string;
}

export interface RunCreateInput {
  destination_object_name: string;
  source_definition_id: string;
  environment?: string | null;
}

export interface GateRejectionDetail {
  rejectedBy: string | null;
  rejectedAt: string;
  affectedObjects: string[];
  requiredChanges: string;
  notes: string | null;
}

export interface ImpactAIRecommendation {
  recommendation: string;
  suggestedFix: string;
  minimalReplayScope: string[];
}

export interface ImpactReport {
  runId: string;
  gateRejection: GateRejectionDetail;
  replayScope: string[];
  aiRecommendation: ImpactAIRecommendation;
}

export class RunApiError extends Error {
  code: string;
  status: number;

  constructor(code: string, message: string, status: number) {
    super(message || code);
    this.name = "RunApiError";
    this.code = code;
    this.status = status;
  }
}

function authHeaders(token: string): Record<string, string> {
  return {
    Authorization: `Bearer ${token}`,
    "Content-Type": "application/json",
  };
}

async function parseApiError(response: Response): Promise<RunApiError> {
  try {
    const body = (await response.json()) as { error?: { code?: string; message?: string } };
    const code = body.error?.code ?? "api_error";
    const message = body.error?.message ?? code;
    return new RunApiError(code, message, response.status);
  } catch {
    const message = await response.text();
    return new RunApiError("api_error", message || "api_error", response.status);
  }
}

async function requestJson<T>(
  path: string,
  init: RequestInit & { token: string },
): Promise<T> {
  const { token, headers, ...rest } = init;
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...rest,
    headers: {
      ...authHeaders(token),
      ...(headers ?? {}),
    },
  });

  if (!response.ok) {
    throw await parseApiError(response);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return (await response.json()) as T;
}

function mapRunRecord(record: {
  run_id: string;
  project_id: string;
  destination_object_name: string;
  source_definition_reference: string | null;
  environment: string | null;
  status: RunStatus;
  current_stage: string | null;
  source_slice_version: string | null;
  mapping_snapshot_version: string | null;
  lookup_snapshot_version: string | null;
  lookup_snapshot_versions: Record<string, string> | null;
  code_generation_input_snapshot_version: string | null;
  codegen_artifact_id: string | null;
  knowledge_freeze_version: string | null;
  start_metadata: Record<string, unknown> | null;
  pause_metadata: Record<string, unknown> | null;
  resume_metadata: Record<string, unknown> | null;
  completion_metadata: Record<string, unknown> | null;
  started_at: string | null;
  last_checkpoint_at: string | null;
  created_at: string;
  updated_at: string;
}): RunRecord {
  return record;
}

function mapRunCheckpoint(record: {
  run_checkpoint_id: string;
  run_id: string;
  current_stage: string | null;
  current_object: string | null;
  current_environment: string | null;
  approved_snapshots: Record<string, unknown> | null;
  last_completed_row: number | null;
  pause_reason: string | null;
  created_at: string;
}): RunCheckpoint {
  return {
    checkpoint_id: record.run_checkpoint_id,
    run_id: record.run_id,
    stage: record.current_stage,
    current_object: record.current_object,
    current_environment: record.current_environment,
    approved_snapshots: record.approved_snapshots,
    last_completed_row: record.last_completed_row,
    pause_reason: record.pause_reason,
    created_at: record.created_at,
  };
}

export async function listRuns(token: string, projectId: string): Promise<RunRecord[]> {
  const response = await requestJson<Array<Parameters<typeof mapRunRecord>[0]>>(
    `/projects/${projectId}/runs`,
    { method: "GET", token },
  );
  return response.map(mapRunRecord);
}

export async function getRun(token: string, projectId: string, runId: string): Promise<RunRecord> {
  const response = await requestJson<Parameters<typeof mapRunRecord>[0]>(
    `/projects/${projectId}/runs/${runId}`,
    { method: "GET", token },
  );
  return mapRunRecord(response);
}

export async function createRun(
  token: string,
  projectId: string,
  body: RunCreateInput,
): Promise<RunRecord> {
  const response = await requestJson<Parameters<typeof mapRunRecord>[0]>(
    `/projects/${projectId}/runs`,
    {
      method: "POST",
      token,
      body: JSON.stringify({
        destination_object_name: body.destination_object_name,
        source_definition_id: body.source_definition_id,
        environment: body.environment ?? null,
      }),
    },
  );
  return mapRunRecord(response);
}

export async function launchRun(token: string, projectId: string, runId: string): Promise<RunRecord> {
  const response = await requestJson<Parameters<typeof mapRunRecord>[0]>(
    `/projects/${projectId}/runs/${runId}/launch`,
    { method: "POST", token },
  );
  return mapRunRecord(response);
}

export async function pauseRun(token: string, projectId: string, runId: string): Promise<RunRecord> {
  const response = await requestJson<Parameters<typeof mapRunRecord>[0]>(
    `/projects/${projectId}/runs/${runId}/pause`,
    { method: "POST", token },
  );
  return mapRunRecord(response);
}

export async function resumeRun(token: string, projectId: string, runId: string): Promise<RunRecord> {
  const response = await requestJson<Parameters<typeof mapRunRecord>[0]>(
    `/projects/${projectId}/runs/${runId}/resume`,
    { method: "POST", token },
  );
  return mapRunRecord(response);
}

export async function listCheckpoints(token: string, projectId: string, runId: string): Promise<RunCheckpoint[]> {
  const response = await requestJson<Array<Parameters<typeof mapRunCheckpoint>[0]>>(
    `/projects/${projectId}/runs/${runId}/checkpoints`,
    { method: "GET", token },
  );
  return response.map(mapRunCheckpoint);
}

export async function getImpactReport(
  token: string,
  projectId: string,
  runId: string,
): Promise<ImpactReport> {
  const response = await requestJson<{
    run_id: string;
    gate_rejection: {
      rejected_by: string | null;
      rejected_at: string;
      affected_objects: string[];
      required_changes: string;
      notes: string | null;
    };
    replay_scope: string[];
    ai_recommendation: {
      recommendation: string;
      suggested_fix: string;
      minimal_replay_scope: string[];
    };
  }>(`/projects/${projectId}/runs/${runId}/impact`, { method: "GET", token });

  return {
    runId: response.run_id,
    gateRejection: {
      rejectedBy: response.gate_rejection.rejected_by,
      rejectedAt: response.gate_rejection.rejected_at,
      affectedObjects: response.gate_rejection.affected_objects,
      requiredChanges: response.gate_rejection.required_changes,
      notes: response.gate_rejection.notes,
    },
    replayScope: response.replay_scope,
    aiRecommendation: {
      recommendation: response.ai_recommendation.recommendation,
      suggestedFix: response.ai_recommendation.suggested_fix,
      minimalReplayScope: response.ai_recommendation.minimal_replay_scope,
    },
  };
}

export async function acknowledgeImpact(
  token: string,
  projectId: string,
  runId: string,
): Promise<RunRecord> {
  const response = await requestJson<Parameters<typeof mapRunRecord>[0]>(
    `/projects/${projectId}/runs/${runId}/impact/acknowledge`,
    { method: "POST", token },
  );
  return mapRunRecord(response);
}
