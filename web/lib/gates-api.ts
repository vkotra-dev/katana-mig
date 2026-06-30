import { API_BASE_URL } from "./api-base";

export interface GateRecord {
  gate: "gate_1" | "gate_2";
  decision: "approved" | "rejected";
  approverUserId: string | null;
  decidedAt: string;
  notes: string | null;
  affectedObjects: string[] | null;
  requiredChanges: string | null;
}

export interface GateStatusRecord {
  runId: string;
  gate1: GateRecord | null;
  gate2: GateRecord | null;
}

export interface GateFieldBindingRecord {
  sourceField: string;
  destinationField: string;
  lookupName: string | null;
}

export interface Gate1EvidenceRecord {
  runId: string;
  destinationObjectName: string;
  mappingSnapshotVersion: string | null;
  fieldBindings: GateFieldBindingRecord[];
  piiFields: string[];
  coverageGaps: string[];
}

export interface GateLookupRowRecord {
  sourceValue: string;
  destinationValue: string | null;
  state: "confirmed" | "low_confidence" | "unmapped" | "overridden";
}

export interface Gate2EvidenceRecord {
  runId: string;
  lookupName: string;
  rows: GateLookupRowRecord[];
  confirmedCount: number;
  unmappedCount: number;
}

export class GateApiError extends Error {
  code: string;
  status: number;

  constructor(code: string, message: string, status: number) {
    super(message || code);
    this.name = "GateApiError";
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

async function parseApiError(response: Response): Promise<GateApiError> {
  try {
    const body = (await response.json()) as { error?: { code?: string; message?: string } };
    return new GateApiError(body.error?.code ?? "api_error", body.error?.message ?? "api_error", response.status);
  } catch {
    return new GateApiError("api_error", await response.text(), response.status);
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

function mapGateRecord(record: {
  gate: "gate_1" | "gate_2";
  decision: "approved" | "rejected";
  approver_user_id: string | null;
  decided_at: string;
  notes: string | null;
  affected_objects: string[] | null;
  required_changes: string | null;
}): GateRecord {
  return {
    gate: record.gate,
    decision: record.decision,
    approverUserId: record.approver_user_id,
    decidedAt: record.decided_at,
    notes: record.notes,
    affectedObjects: record.affected_objects,
    requiredChanges: record.required_changes,
  };
}

export async function getGateStatus(token: string, projectId: string, runId: string): Promise<GateStatusRecord> {
  const response = await requestJson<{
    run_id: string;
    gate_1: Parameters<typeof mapGateRecord>[0] | null;
    gate_2: Parameters<typeof mapGateRecord>[0] | null;
  }>(`/projects/${projectId}/runs/${runId}/gates`, { method: "GET", token });
  return {
    runId: response.run_id,
    gate1: response.gate_1 ? mapGateRecord(response.gate_1) : null,
    gate2: response.gate_2 ? mapGateRecord(response.gate_2) : null,
  };
}

export async function getGate1Evidence(token: string, projectId: string, runId: string): Promise<Gate1EvidenceRecord> {
  const response = await requestJson<{
    run_id: string;
    destination_object_name: string;
    mapping_snapshot_version: string | null;
    field_bindings: Array<{
      source_field: string;
      destination_field: string;
      lookup_name: string | null;
    }>;
    pii_fields: string[];
    coverage_gaps: string[];
  }>(`/projects/${projectId}/runs/${runId}/gates/gate-1/evidence`, { method: "GET", token });
  return {
    runId: response.run_id,
    destinationObjectName: response.destination_object_name,
    mappingSnapshotVersion: response.mapping_snapshot_version,
    fieldBindings: response.field_bindings.map((binding) => ({
      sourceField: binding.source_field,
      destinationField: binding.destination_field,
      lookupName: binding.lookup_name,
    })),
    piiFields: response.pii_fields,
    coverageGaps: response.coverage_gaps,
  };
}

export async function getGate2Evidence(token: string, projectId: string, runId: string): Promise<Gate2EvidenceRecord> {
  const response = await requestJson<{
    run_id: string;
    lookup_name: string;
    rows: Array<{
      source_value: string;
      destination_value: string | null;
      state: "confirmed" | "low_confidence" | "unmapped" | "overridden";
    }>;
    confirmed_count: number;
    unmapped_count: number;
  }>(`/projects/${projectId}/runs/${runId}/gates/gate-2/evidence`, { method: "GET", token });
  return {
    runId: response.run_id,
    lookupName: response.lookup_name,
    rows: response.rows.map((row) => ({
      sourceValue: row.source_value,
      destinationValue: row.destination_value,
      state: row.state,
    })),
    confirmedCount: response.confirmed_count,
    unmappedCount: response.unmapped_count,
  };
}

export async function approveGate(
  token: string,
  projectId: string,
  runId: string,
  gate: "gate_1" | "gate_2",
  input: { notes?: string | null },
): Promise<GateStatusRecord> {
  const response = await requestJson<{
    run_id: string;
    gate_1: Parameters<typeof mapGateRecord>[0] | null;
    gate_2: Parameters<typeof mapGateRecord>[0] | null;
  }>(`/projects/${projectId}/runs/${runId}/gates/${gate.replace("_", "-")}/approve`, {
    method: "POST",
    token,
    body: JSON.stringify({ notes: input.notes ?? null }),
  });
  return {
    runId: response.run_id,
    gate1: response.gate_1 ? mapGateRecord(response.gate_1) : null,
    gate2: response.gate_2 ? mapGateRecord(response.gate_2) : null,
  };
}

export async function rejectGate(
  token: string,
  projectId: string,
  runId: string,
  gate: "gate_1" | "gate_2",
  input: { affectedObjects: string[]; requiredChanges: string; notes?: string | null },
): Promise<GateStatusRecord> {
  const response = await requestJson<{
    run_id: string;
    gate_1: Parameters<typeof mapGateRecord>[0] | null;
    gate_2: Parameters<typeof mapGateRecord>[0] | null;
  }>(`/projects/${projectId}/runs/${runId}/gates/${gate.replace("_", "-")}/reject`, {
    method: "POST",
    token,
    body: JSON.stringify({
      affected_objects: input.affectedObjects,
      required_changes: input.requiredChanges,
      notes: input.notes ?? null,
    }),
  });
  return {
    runId: response.run_id,
    gate1: response.gate_1 ? mapGateRecord(response.gate_1) : null,
    gate2: response.gate_2 ? mapGateRecord(response.gate_2) : null,
  };
}
