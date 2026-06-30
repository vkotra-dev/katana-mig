import { API_BASE_URL } from "./api-base";

export type SourceType = "csv" | "fixed_length_file";

export interface SourceContractRecord {
  sourceDefinitionId: string;
  projectId: string;
  sourceType: SourceType;
  label: string;
  encoding: string;
  destinationObjectReferences: string[] | null;
  layoutInformation: Array<Record<string, unknown>> | null;
  copybookText: string | null;
  status: string;
  createdAt: string;
}

export interface SourceSchemaColumnRecord {
  name: string;
  inferredType: "text" | "integer" | "decimal" | "date" | "boolean" | "uuid";
  nullable: boolean;
  maxLength: number | null;
}

export interface SourceValueSummaryRecord {
  summaryId: string;
  sourceDefinitionId: string;
  sourceSliceVersion: string;
  fieldName: string;
  valueCounts: Record<string, number>;
  createdAt: string;
}

export interface SourceSliceRecord {
  sourceSliceId: string;
  sourceDefinitionId: string;
  sourceSliceVersion: string;
  headerCsv: string | null;
  rowCount: number;
  status: string;
  approvalRejectionReason: string | null;
  parseWarnings: string[] | null;
  previewRows: string[];
  createdAt: string;
}

export interface SourceContractCreateInput {
  sourceType: SourceType;
  label: string;
  encoding: string;
}

export interface SourceFileUploadInput {
  content: string;
}

export class SourceApiError extends Error {
  code: string;
  status: number;

  constructor(code: string, message: string, status: number) {
    super(message || code);
    this.name = "SourceApiError";
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
  return (await response.json()) as T;
}

async function parseApiError(response: Response): Promise<SourceApiError> {
  try {
    const body = (await response.json()) as { error?: { code?: string; message?: string } };
    const code = body.error?.code ?? "api_error";
    const message = body.error?.message ?? code;
    return new SourceApiError(code, message, response.status);
  } catch {
    const message = await response.text();
    return new SourceApiError("api_error", message || "api_error", response.status);
  }
}

function mapSourceContractResponse(response: {
  source_definition_id: string;
  project_id: string;
  source_type: SourceType;
  label: string;
  encoding: string;
  destination_object_references: string[] | null;
  layout_information: Array<Record<string, unknown>> | null;
  copybook_text: string | null;
  status: string;
  created_at: string;
}): SourceContractRecord {
  return {
    sourceDefinitionId: response.source_definition_id,
    projectId: response.project_id,
    sourceType: response.source_type,
    label: response.label,
    encoding: response.encoding,
    destinationObjectReferences: response.destination_object_references,
    layoutInformation: response.layout_information,
    copybookText: response.copybook_text,
    status: response.status,
    createdAt: response.created_at,
  };
}

function mapSourceSliceResponse(response: {
  source_slice_id: string;
  source_definition_id: string;
  source_slice_version: string;
  header_csv: string | null;
  row_count: number;
  status: string;
  approval_rejection_reason: string | null;
  parse_warnings: string[] | null;
  preview_rows: string[];
  created_at: string;
}): SourceSliceRecord {
  return {
    sourceSliceId: response.source_slice_id,
    sourceDefinitionId: response.source_definition_id,
    sourceSliceVersion: response.source_slice_version,
    headerCsv: response.header_csv,
    rowCount: response.row_count,
    status: response.status,
    approvalRejectionReason: response.approval_rejection_reason,
    parseWarnings: response.parse_warnings,
    previewRows: response.preview_rows,
    createdAt: response.created_at,
  };
}

function mapSourceSchemaColumnResponse(response: {
  name: string;
  inferred_type: "text" | "integer" | "decimal" | "date" | "boolean" | "uuid";
  nullable: boolean;
  max_length: number | null;
}): SourceSchemaColumnRecord {
  return {
    name: response.name,
    inferredType: response.inferred_type,
    nullable: response.nullable,
    maxLength: response.max_length,
  };
}

function mapSourceValueSummaryResponse(response: {
  summary_id: string;
  source_definition_id: string;
  source_slice_version: string;
  field_name: string;
  value_counts: Record<string, number>;
  created_at: string;
}): SourceValueSummaryRecord {
  return {
    summaryId: response.summary_id,
    sourceDefinitionId: response.source_definition_id,
    sourceSliceVersion: response.source_slice_version,
    fieldName: response.field_name,
    valueCounts: response.value_counts,
    createdAt: response.created_at,
  };
}

export async function listSourceContracts(
  token: string,
  projectId: string,
): Promise<SourceContractRecord[]> {
  const response = await requestJson<Array<Parameters<typeof mapSourceContractResponse>[0]>>(
    `/projects/${projectId}/sources`,
    { method: "GET", token },
  );
  return response.map(mapSourceContractResponse);
}

export async function getSourceContract(
  token: string,
  projectId: string,
  sourceDefinitionId: string,
): Promise<SourceContractRecord> {
  const response = await requestJson<Parameters<typeof mapSourceContractResponse>[0]>(
    `/projects/${projectId}/sources/${sourceDefinitionId}`,
    { method: "GET", token },
  );
  return mapSourceContractResponse(response);
}

export async function createSourceContract(
  token: string,
  projectId: string,
  input: SourceContractCreateInput,
): Promise<SourceContractRecord> {
  const response = await requestJson<Parameters<typeof mapSourceContractResponse>[0]>(
    `/projects/${projectId}/sources`,
    {
      method: "POST",
      token,
      body: JSON.stringify({
        source_type: input.sourceType,
        label: input.label,
        encoding: input.encoding,
      }),
    },
  );
  return mapSourceContractResponse(response);
}

export async function uploadSourceCopybook(
  token: string,
  projectId: string,
  sourceDefinitionId: string,
  input: SourceFileUploadInput,
): Promise<SourceContractRecord> {
  const response = await requestJson<Parameters<typeof mapSourceContractResponse>[0]>(
    `/projects/${projectId}/sources/${sourceDefinitionId}/copybook`,
    {
      method: "POST",
      token,
      body: JSON.stringify(input),
    },
  );
  return mapSourceContractResponse(response);
}

export async function uploadSourceSlice(
  token: string,
  projectId: string,
  sourceDefinitionId: string,
  input: SourceFileUploadInput,
): Promise<SourceSliceRecord> {
  const response = await requestJson<Parameters<typeof mapSourceSliceResponse>[0]>(
    `/projects/${projectId}/sources/${sourceDefinitionId}/slices`,
    {
      method: "POST",
      token,
      body: JSON.stringify(input),
    },
  );
  return mapSourceSliceResponse(response);
}

export async function listSourceSlices(
  token: string,
  projectId: string,
  sourceDefinitionId: string,
): Promise<SourceSliceRecord[]> {
  const response = await requestJson<Array<Parameters<typeof mapSourceSliceResponse>[0]>>(
    `/projects/${projectId}/sources/${sourceDefinitionId}/slices`,
    { method: "GET", token },
  );
  return response.map(mapSourceSliceResponse);
}

export async function getSourceSlice(
  token: string,
  projectId: string,
  sourceDefinitionId: string,
  sourceSliceId: string,
): Promise<SourceSliceRecord> {
  const response = await requestJson<Parameters<typeof mapSourceSliceResponse>[0]>(
    `/projects/${projectId}/sources/${sourceDefinitionId}/slices/${sourceSliceId}`,
    { method: "GET", token },
  );
  return mapSourceSliceResponse(response);
}

export async function listSourceSchema(
  token: string,
  projectId: string,
  sourceDefinitionId: string,
): Promise<SourceSchemaColumnRecord[]> {
  const response = await requestJson<Array<Parameters<typeof mapSourceSchemaColumnResponse>[0]>>(
    `/projects/${projectId}/sources/${sourceDefinitionId}/schema`,
    { method: "GET", token },
  );
  return response.map(mapSourceSchemaColumnResponse);
}

export async function listSourceValueSummaries(
  token: string,
  projectId: string,
  sourceDefinitionId: string,
  field?: string,
): Promise<SourceValueSummaryRecord[]> {
  const query = field ? `?field=${encodeURIComponent(field)}` : "";
  const response = await requestJson<Array<Parameters<typeof mapSourceValueSummaryResponse>[0]>>(
    `/projects/${projectId}/sources/${sourceDefinitionId}/value-summary${query}`,
    { method: "GET", token },
  );
  return response.map(mapSourceValueSummaryResponse);
}
