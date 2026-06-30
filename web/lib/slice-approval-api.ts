import { API_BASE_URL } from "./api-base";

export interface SourceSliceApprovalItem {
  projectId: string;
  projectName: string;
  sourceDefinitionId: string;
  sourceLabel: string;
  sourceType: string;
  sourceSliceId: string;
  sourceSliceVersion: string;
  rowCount: number;
  status: string;
  parseWarnings: string[] | null;
  createdAt: string;
}

export interface SourceSliceApprovalCount {
  pendingCount: number;
}

export class SourceSliceApprovalApiError extends Error {
  code: string;
  status: number;

  constructor(code: string, message: string, status: number) {
    super(message || code);
    this.name = "SourceSliceApprovalApiError";
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

async function parseApiError(response: Response): Promise<SourceSliceApprovalApiError> {
  try {
    const body = (await response.json()) as { error?: { code?: string; message?: string } };
    const code = body.error?.code ?? "api_error";
    const message = body.error?.message ?? code;
    return new SourceSliceApprovalApiError(code, message, response.status);
  } catch {
    const message = await response.text();
    return new SourceSliceApprovalApiError("api_error", message || "api_error", response.status);
  }
}

function mapApprovalItem(response: {
  project_id: string;
  project_name: string;
  source_definition_id: string;
  source_label: string;
  source_type: string;
  source_slice_id: string;
  source_slice_version: string;
  row_count: number;
  status: string;
  parse_warnings: string[] | null;
  created_at: string;
}): SourceSliceApprovalItem {
  return {
    projectId: response.project_id,
    projectName: response.project_name,
    sourceDefinitionId: response.source_definition_id,
    sourceLabel: response.source_label,
    sourceType: response.source_type,
    sourceSliceId: response.source_slice_id,
    sourceSliceVersion: response.source_slice_version,
    rowCount: response.row_count,
    status: response.status,
    parseWarnings: response.parse_warnings,
    createdAt: response.created_at,
  };
}

export async function listPendingApprovals(token: string): Promise<SourceSliceApprovalItem[]> {
  const response = await requestJson<Array<Parameters<typeof mapApprovalItem>[0]>>("/approvals", {
    method: "GET",
    token,
  });
  return response.map(mapApprovalItem);
}

export async function getPendingApprovalCount(token: string): Promise<number> {
  const response = await requestJson<SourceSliceApprovalCount>("/approvals/count", {
    method: "GET",
    token,
  });
  return response.pendingCount;
}

export async function approveSourceSlice(
  token: string,
  projectId: string,
  sourceDefinitionId: string,
  sourceSliceId: string,
): Promise<void> {
  await requestJson<void>(
    `/projects/${projectId}/sources/${sourceDefinitionId}/slices/${sourceSliceId}/approve`,
    { method: "POST", token },
  );
}

export async function rejectSourceSlice(
  token: string,
  projectId: string,
  sourceDefinitionId: string,
  sourceSliceId: string,
  reason: string,
): Promise<void> {
  await requestJson<void>(
    `/projects/${projectId}/sources/${sourceDefinitionId}/slices/${sourceSliceId}/reject`,
    {
      method: "POST",
      token,
      body: JSON.stringify({ reason }),
    },
  );
}

export async function resubmitSourceSlice(
  token: string,
  projectId: string,
  sourceDefinitionId: string,
  sourceSliceId: string,
  input: { encoding?: string | null; parseSettings?: Record<string, unknown> | null },
): Promise<void> {
  await requestJson<void>(
    `/projects/${projectId}/sources/${sourceDefinitionId}/slices/${sourceSliceId}/resubmit`,
    {
      method: "POST",
      token,
      body: JSON.stringify({
        encoding: input.encoding ?? null,
        parse_settings: input.parseSettings ?? null,
      }),
    },
  );
}
