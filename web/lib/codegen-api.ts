import { API_BASE_URL } from "./api-base";

export interface CodegenTriggerRecord {
  codegenArtifactId: string;
  projectId: string;
  destinationObjectName: string;
  status: "active" | "superseded";
  sqlBundlePreview: string;
  sourceSliceVersion: string | null;
  mappingSnapshotVersion: string | null;
  lookupSnapshotVersion: string | null;
  createdAt: string;
}

export interface CodegenArtifactRecord {
  codegenArtifactId: string;
  projectId: string;
  destinationObjectName: string;
  runId: string | null;
  sourceSliceVersion: string | null;
  mappingSnapshotVersion: string | null;
  lookupSnapshotVersion: string | null;
  sqlBundle: string | null;
  status: "active" | "superseded";
  createdAt: string;
  supersededAt: string | null;
}

export interface DeliveryBundleRecord {
  filename: string;
  sqlBundle: string;
  artifactCount: number;
}

export class CodegenApiError extends Error {
  code: string;
  status: number;

  constructor(code: string, message: string, status: number) {
    super(message || code);
    this.name = "CodegenApiError";
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

async function requestText(
  path: string,
  init: RequestInit & { token: string },
): Promise<{ text: string; headers: Headers }> {
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

  return {
    text: await response.text(),
    headers: response.headers,
  };
}

async function parseApiError(response: Response): Promise<CodegenApiError> {
  try {
    const body = (await response.json()) as { error?: { code?: string; message?: string } };
    const code = body.error?.code ?? "api_error";
    const message = body.error?.message ?? code;
    return new CodegenApiError(code, message, response.status);
  } catch {
    const message = await response.text();
    return new CodegenApiError("api_error", message || "api_error", response.status);
  }
}

function mapTriggerResponse(response: {
  codegen_artifact_id: string;
  project_id: string;
  destination_object_name: string;
  status: "active" | "superseded";
  sql_bundle_preview: string;
  source_slice_version: string | null;
  mapping_snapshot_version: string | null;
  lookup_snapshot_version: string | null;
  created_at: string;
}): CodegenTriggerRecord {
  return {
    codegenArtifactId: response.codegen_artifact_id,
    projectId: response.project_id,
    destinationObjectName: response.destination_object_name,
    status: response.status,
    sqlBundlePreview: response.sql_bundle_preview,
    sourceSliceVersion: response.source_slice_version,
    mappingSnapshotVersion: response.mapping_snapshot_version,
    lookupSnapshotVersion: response.lookup_snapshot_version,
    createdAt: response.created_at,
  };
}

function mapArtifactResponse(response: {
  codegen_artifact_id: string;
  project_id: string;
  destination_object_name: string;
  run_id: string | null;
  source_slice_version: string | null;
  mapping_snapshot_version: string | null;
  lookup_snapshot_version: string | null;
  sql_bundle: string | null;
  status: "active" | "superseded";
  created_at: string;
  superseded_at: string | null;
}): CodegenArtifactRecord {
  return {
    codegenArtifactId: response.codegen_artifact_id,
    projectId: response.project_id,
    destinationObjectName: response.destination_object_name,
    runId: response.run_id,
    sourceSliceVersion: response.source_slice_version,
    mappingSnapshotVersion: response.mapping_snapshot_version,
    lookupSnapshotVersion: response.lookup_snapshot_version,
    sqlBundle: response.sql_bundle,
    status: response.status,
    createdAt: response.created_at,
    supersededAt: response.superseded_at,
  };
}

export async function triggerCodegen(
  token: string,
  projectId: string,
  sourceDefinitionId: string,
): Promise<CodegenTriggerRecord> {
  const response = await requestJson<Parameters<typeof mapTriggerResponse>[0]>(
    `/projects/${projectId}/sources/${sourceDefinitionId}/codegen`,
    { method: "POST", token },
  );
  return mapTriggerResponse(response);
}

export async function listCodegenArtifacts(
  token: string,
  projectId: string,
): Promise<CodegenArtifactRecord[]> {
  const response = await requestJson<Array<Parameters<typeof mapArtifactResponse>[0]>>(
    `/projects/${projectId}/codegen-artifacts`,
    { method: "GET", token },
  );
  return response.map(mapArtifactResponse);
}

export async function getCodegenArtifact(
  token: string,
  projectId: string,
  codegenArtifactId: string,
): Promise<CodegenArtifactRecord> {
  const response = await requestJson<Parameters<typeof mapArtifactResponse>[0]>(
    `/projects/${projectId}/codegen-artifacts/${codegenArtifactId}`,
    { method: "GET", token },
  );
  return mapArtifactResponse(response);
}

export async function downloadCodegenDeliveryBundle(
  token: string,
  projectId: string,
): Promise<string> {
  const response = await requestText(`/projects/${projectId}/delivery-bundle`, {
    method: "GET",
    token,
  });
  return response.text;
}
