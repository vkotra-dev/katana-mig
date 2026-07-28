import { API_BASE_URL } from "./api-base";

export type FeedType = "csv" | "fixed_length_file";

export interface MappingOwnershipRecord {
  sourceDefinitionId: string | null;
  feedLabel: string | null;
  feedSourceType: string | null;
  status: string;
  destinationObjectName: string;
  mappingSnapshotId: string;
}

export interface FeedContractRecord {
  sourceDefinitionId: string;
  projectId: string;
  sourceType: FeedType;
  label: string;
  encoding: string;
  destinationObjectReferences: string[] | null;
  layoutInformation: Array<Record<string, unknown>> | null;
  copybookText: string | null;
  status: string;
  createdAt: string;
  mappingStatus: "draft" | "partial" | "approved" | null;
  mappingOwnershipWarnings: Record<string, MappingOwnershipRecord> | null;
  mappingHints?: string | null;
  transformationInstructions?: string | null;
}

export interface FeedSchemaColumnRecord {
  name: string;
  inferredType: "text" | "integer" | "decimal" | "date" | "boolean" | "uuid";
  nullable: boolean;
  maxLength: number | null;
}

export interface FeedValueSummaryRecord {
  summaryId: string;
  sourceDefinitionId: string;
  sourceSliceVersion: string;
  fieldName: string;
  valueCounts: Record<string, number>;
  createdAt: string;
}

export interface FiberFieldBindingRecord {
  sourceField: string;
  destinationField: string;
  lookupName: string | null;
}

export interface FiberProposedMappingRecord {
  sourceValue: string;
  destEntryId: string | null;
  destRow: Record<string, unknown> | null;
  confidenceScore: number | null;
}

export interface FiberRecord {
  fiberId: string;
  feedId: string;
  projectId: string;
  fiberType: "lookup" | "domain_object";
  fiberKey: string;
  status: string;
  source: "auto" | "manual";
  proposedMappings: FiberProposedMappingRecord[] | null;
  fieldBindings: FiberFieldBindingRecord[] | null;
  outputSql: string | null;
  createdAt: string;
  updatedAt: string;
}

export interface FeedSliceRecord {
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

export interface FeedContractCreateInput {
  sourceType: FeedType;
  label: string;
  encoding: string;
}

export interface FeedFileUploadInput {
  content: string;
}

export class FeedApiError extends Error {
  code: string;
  status: number;

  constructor(code: string, message: string, status: number) {
    super(message || code);
    this.name = "FeedApiError";
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

async function parseApiError(response: Response): Promise<FeedApiError> {
  try {
    const body = (await response.json()) as {
      error?: { code?: string; message?: string };
      detail?: string | { code?: string; message?: string };
    };
    let code = "api_error";
    let message = "api_error";

    if (body.error) {
      code = body.error.code ?? "api_error";
      message = body.error.message ?? code;
    } else if (body.detail) {
      if (typeof body.detail === "string") {
        message = body.detail;
      } else {
        code = body.detail.code ?? "api_error";
        message = body.detail.message ?? code;
      }
    }

    return new FeedApiError(code, message, response.status);
  } catch {
    const message = await response.text();
    return new FeedApiError("api_error", message || "api_error", response.status);
  }
}

function mapFeedContractResponse(response: {
  source_definition_id: string;
  project_id: string;
  source_type: FeedType;
  label: string;
  encoding: string;
  destination_object_references: string[] | null;
  layout_information: Array<Record<string, unknown>> | null;
  copybook_text: string | null;
  status: string;
  created_at: string;
  mapping_status?: "draft" | "partial" | "approved" | null;
  mapping_ownership_warnings?: Record<string, {
    source_definition_id: string | null;
    feed_label: string | null;
    feed_source_type: string | null;
    status: string;
    destination_object_name: string;
    mapping_snapshot_id: string;
  }> | null;
  mapping_hints?: string | null;
  transformation_instructions?: string | null;
}): FeedContractRecord {
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
    mappingStatus: response.mapping_status ?? null,
    mappingOwnershipWarnings: (() => {
      const raw = response.mapping_ownership_warnings;
      if (!raw) return null;
      const result: Record<string, MappingOwnershipRecord> = {};
      for (const [key, val] of Object.entries(raw)) {
        result[key] = {
          sourceDefinitionId: val.source_definition_id,
          feedLabel: val.feed_label,
          feedSourceType: val.feed_source_type,
          status: val.status,
          destinationObjectName: val.destination_object_name,
          mappingSnapshotId: val.mapping_snapshot_id,
        };
      }
      return result;
    })(),
    mappingHints: response.mapping_hints ?? null,
    transformationInstructions: response.transformation_instructions ?? null,
  };
}

function mapFeedSliceResponse(response: {
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
}): FeedSliceRecord {
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

function mapFeedSchemaColumnResponse(response: {
  name: string;
  inferred_type: "text" | "integer" | "decimal" | "date" | "boolean" | "uuid";
  nullable: boolean;
  max_length: number | null;
}): FeedSchemaColumnRecord {
  return {
    name: response.name,
    inferredType: response.inferred_type,
    nullable: response.nullable,
    maxLength: response.max_length,
  };
}

function mapFeedValueSummaryResponse(response: {
  summary_id: string;
  source_definition_id: string;
  source_slice_version: string;
  field_name: string;
  value_counts: Record<string, number>;
  created_at: string;
}): FeedValueSummaryRecord {
  return {
    summaryId: response.summary_id,
    sourceDefinitionId: response.source_definition_id,
    sourceSliceVersion: response.source_slice_version,
    fieldName: response.field_name,
    valueCounts: response.value_counts,
    createdAt: response.created_at,
  };
}

function mapFiberResponse(response: {
  fiber_id: string;
  feed_id: string;
  project_id: string;
  fiber_type: "lookup" | "domain_object";
  fiber_key: string;
  status: string;
  source: "auto" | "manual";
  proposed_mappings: Array<{
    source_value: string;
    dest_entry_id: string | null;
    dest_row: Record<string, unknown> | null;
    confidence_score: number | null;
  }> | null;
  field_bindings: Array<{
    source_field: string;
    destination_field: string;
    lookup_name: string | null;
  }> | null;
  output_sql: string | null;
  created_at: string;
  updated_at: string;
}): FiberRecord {
  return {
    fiberId: response.fiber_id,
    feedId: response.feed_id,
    projectId: response.project_id,
    fiberType: response.fiber_type,
    fiberKey: response.fiber_key,
    status: response.status,
    source: response.source,
    proposedMappings: response.proposed_mappings?.map((mapping) => ({
      sourceValue: mapping.source_value,
      destEntryId: mapping.dest_entry_id,
      destRow: mapping.dest_row,
      confidenceScore: mapping.confidence_score,
    })) ?? null,
    fieldBindings: response.field_bindings?.map((binding) => ({
      sourceField: binding.source_field,
      destinationField: binding.destination_field,
      lookupName: binding.lookup_name,
    })) ?? null,
    outputSql: response.output_sql,
    createdAt: response.created_at,
    updatedAt: response.updated_at,
  };
}

export async function listFeedContracts(
  token: string,
  projectId: string,
  { includeDiscarded = false }: { includeDiscarded?: boolean } = {},
): Promise<FeedContractRecord[]> {
  const url = includeDiscarded
    ? `/projects/${projectId}/sources?include_discarded=true`
    : `/projects/${projectId}/sources`;
  const response = await requestJson<Array<Parameters<typeof mapFeedContractResponse>[0]>>(
    url,
    { method: "GET", token },
  );
  return response.map(mapFeedContractResponse);
}

export async function discardFeed(
  token: string,
  projectId: string,
  sourceDefinitionId: string,
): Promise<FeedContractRecord> {
  const response = await requestJson<Parameters<typeof mapFeedContractResponse>[0]>(
    `/projects/${projectId}/sources/${sourceDefinitionId}`,
    { method: "DELETE", token },
  );
  return mapFeedContractResponse(response);
}

export async function getFeedContract(
  token: string,
  projectId: string,
  sourceDefinitionId: string,
): Promise<FeedContractRecord> {
  const response = await requestJson<Parameters<typeof mapFeedContractResponse>[0]>(
    `/projects/${projectId}/sources/${sourceDefinitionId}`,
    { method: "GET", token },
  );
  return mapFeedContractResponse(response);
}

export async function createFeedContract(
  token: string,
  projectId: string,
  input: FeedContractCreateInput,
): Promise<FeedContractRecord> {
  const response = await requestJson<Parameters<typeof mapFeedContractResponse>[0]>(
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
  return mapFeedContractResponse(response);
}

export async function uploadFeedCopybook(
  token: string,
  projectId: string,
  sourceDefinitionId: string,
  input: FeedFileUploadInput,
): Promise<FeedContractRecord> {
  const response = await requestJson<Parameters<typeof mapFeedContractResponse>[0]>(
    `/projects/${projectId}/sources/${sourceDefinitionId}/copybook`,
    {
      method: "POST",
      token,
      body: JSON.stringify(input),
    },
  );
  return mapFeedContractResponse(response);
}

export async function uploadFeedSlice(
  token: string,
  projectId: string,
  sourceDefinitionId: string,
  input: FeedFileUploadInput,
): Promise<FeedSliceRecord> {
  const response = await requestJson<Parameters<typeof mapFeedSliceResponse>[0]>(
    `/projects/${projectId}/sources/${sourceDefinitionId}/slices`,
    {
      method: "POST",
      token,
      body: JSON.stringify(input),
    },
  );
  return mapFeedSliceResponse(response);
}

export async function listFeedSlices(
  token: string,
  projectId: string,
  sourceDefinitionId: string,
  masked?: boolean,
): Promise<FeedSliceRecord[]> {
  const query = masked !== undefined ? `?masked=${masked}` : "";
  const response = await requestJson<Array<Parameters<typeof mapFeedSliceResponse>[0]>>(
    `/projects/${projectId}/sources/${sourceDefinitionId}/slices${query}`,
    { method: "GET", token },
  );
  return response.map(mapFeedSliceResponse);
}

export async function getFeedSlice(
  token: string,
  projectId: string,
  sourceDefinitionId: string,
  sourceSliceId: string,
): Promise<FeedSliceRecord> {
  const response = await requestJson<Parameters<typeof mapFeedSliceResponse>[0]>(
    `/projects/${projectId}/sources/${sourceDefinitionId}/slices/${sourceSliceId}`,
    { method: "GET", token },
  );
  return mapFeedSliceResponse(response);
}

export async function listFeedSchema(
  token: string,
  projectId: string,
  sourceDefinitionId: string,
): Promise<FeedSchemaColumnRecord[]> {
  const response = await requestJson<Array<Parameters<typeof mapFeedSchemaColumnResponse>[0]>>(
    `/projects/${projectId}/sources/${sourceDefinitionId}/schema`,
    { method: "GET", token },
  );
  return response.map(mapFeedSchemaColumnResponse);
}

export async function listFeedValueSummaries(
  token: string,
  projectId: string,
  sourceDefinitionId: string,
  field?: string,
): Promise<FeedValueSummaryRecord[]> {
  const query = field ? `?field=${encodeURIComponent(field)}` : "";
  const response = await requestJson<Array<Parameters<typeof mapFeedValueSummaryResponse>[0]>>(
    `/projects/${projectId}/sources/${sourceDefinitionId}/value-summary${query}`,
    { method: "GET", token },
  );
  return response.map(mapFeedValueSummaryResponse);
}

export async function listFeedFibers(
  token: string,
  projectId: string,
  feedId: string,
): Promise<FiberRecord[]> {
  const response = await requestJson<Array<Parameters<typeof mapFiberResponse>[0]>>(
    `/projects/${projectId}/feeds/${feedId}/fibers`,
    { method: "GET", token },
  );
  return response.map(mapFiberResponse);
}

export interface FiberCreateInput {
  fiberType: "lookup" | "domain_object";
  fiberKey: string;
  source: "auto" | "manual";
}

export async function createFiber(
  token: string,
  projectId: string,
  feedId: string,
  input: FiberCreateInput,
): Promise<FiberRecord> {
  const response = await requestJson<Parameters<typeof mapFiberResponse>[0]>(
    `/projects/${projectId}/feeds/${feedId}/fibers`,
    {
      method: "POST",
      token,
      body: JSON.stringify({
        fiber_type: input.fiberType,
        fiber_key: input.fiberKey,
        source: input.source,
      }),
    },
  );
  return mapFiberResponse(response);
}

export async function getFiber(
  token: string,
  projectId: string,
  feedId: string,
  fiberId: string,
): Promise<FiberRecord> {
  const response = await requestJson<Parameters<typeof mapFiberResponse>[0]>(
    `/projects/${projectId}/feeds/${feedId}/fibers/${fiberId}`,
    { method: "GET", token },
  );
  return mapFiberResponse(response);
}

export async function assignFiber(
  token: string,
  projectId: string,
  feedId: string,
  fiberId: string,
): Promise<FiberRecord> {
  const response = await requestJson<Parameters<typeof mapFiberResponse>[0]>(
    `/projects/${projectId}/feeds/${feedId}/fibers/${fiberId}/assign`,
    { method: "POST", token, body: JSON.stringify({}) },
  );
  return mapFiberResponse(response);
}

export async function approveFiber(
  token: string,
  projectId: string,
  feedId: string,
  fiberId: string,
): Promise<FiberRecord> {
  const response = await requestJson<Parameters<typeof mapFiberResponse>[0]>(
    `/projects/${projectId}/feeds/${feedId}/fibers/${fiberId}/approve`,
    { method: "POST", token, body: JSON.stringify({}) },
  );
  return mapFiberResponse(response);
}

export async function triggerFiber(
  token: string,
  projectId: string,
  feedId: string,
  fiberId: string,
): Promise<FiberRecord> {
  const response = await requestJson<Parameters<typeof mapFiberResponse>[0]>(
    `/projects/${projectId}/feeds/${feedId}/fibers/${fiberId}/trigger`,
    { method: "POST", token, body: JSON.stringify({}) },
  );
  return mapFiberResponse(response);
}

export interface FeedCommentRecord {
  commentId: string;
  feedId: string;
  userId: string;
  displayName: string | null;
  role: string;
  body: string;
  createdAt: string;
  sourceSliceId?: string | null;
  sourceSliceVersion?: string | null;
}

function mapFeedCommentResponse(response: {
  comment_id: string;
  feed_id: string;
  user_id: string;
  display_name: string | null;
  role: string;
  body: string;
  created_at: string;
  source_slice_id?: string | null;
  source_slice_version?: string | null;
}): FeedCommentRecord {
  return {
    commentId: response.comment_id,
    feedId: response.feed_id,
    userId: response.user_id,
    displayName: response.display_name,
    role: response.role,
    body: response.body,
    createdAt: response.created_at,
    sourceSliceId: response.source_slice_id,
    sourceSliceVersion: response.source_slice_version,
  };
}

export async function listFeedComments(
  token: string,
  projectId: string,
  feedId: string,
): Promise<FeedCommentRecord[]> {
  const response = await requestJson<Array<Parameters<typeof mapFeedCommentResponse>[0]>>(
    `/projects/${projectId}/feeds/${feedId}/comments`,
    { method: "GET", token },
  );
  return response.map(mapFeedCommentResponse);
}

export async function createFeedComment(
  token: string,
  projectId: string,
  feedId: string,
  body: string,
  sourceSliceId?: string,
): Promise<FeedCommentRecord> {
  const response = await requestJson<Parameters<typeof mapFeedCommentResponse>[0]>(
    `/projects/${projectId}/feeds/${feedId}/comments`,
    {
      method: "POST",
      token,
      body: JSON.stringify({ body, source_slice_id: sourceSliceId }),
    },
  );
  return mapFeedCommentResponse(response);
}

export async function analyzeFeedSource(
  token: string,
  projectId: string,
  sourceDefinitionId: string,
): Promise<{ status: string; schemaArtifactId: string; destinationDDL: string | null }> {
  const response = await requestJson<{ status: string; schema_artifact_id: string; destination_ddl: string | null }>(
    `/projects/${projectId}/sources/${sourceDefinitionId}/analyze`,
    {
      method: "POST",
      token,
    },
  );
  return {
    status: response.status,
    schemaArtifactId: response.schema_artifact_id,
    destinationDDL: response.destination_ddl ?? null,
  };
}

export async function getSourceSchemaArtifact(
  token: string,
  projectId: string,
  sourceDefinitionId: string,
): Promise<{ schemaArtifactId: string; destinationDDL: string | null }> {
  const response = await requestJson<{ schema_artifact_id: string; destination_ddl: string | null }>(
    `/projects/${projectId}/sources/${sourceDefinitionId}/schema-artifact`,
    { method: "GET", token },
  );
  return {
    schemaArtifactId: response.schema_artifact_id,
    destinationDDL: response.destination_ddl ?? null,
  };
}

export async function approveFeedSlice(
  token: string,
  projectId: string,
  sourceDefinitionId: string,
  sourceSliceId: string,
): Promise<FeedSliceRecord> {
  const response = await requestJson<Parameters<typeof mapFeedSliceResponse>[0]>(
    `/projects/${projectId}/sources/${sourceDefinitionId}/slices/${sourceSliceId}/approve`,
    { method: "POST", token },
  );
  return mapFeedSliceResponse(response);
}

export async function rejectFeedSlice(
  token: string,
  projectId: string,
  sourceDefinitionId: string,
  sourceSliceId: string,
  reason: string,
): Promise<FeedSliceRecord> {
  const response = await requestJson<Parameters<typeof mapFeedSliceResponse>[0]>(
    `/projects/${projectId}/sources/${sourceDefinitionId}/slices/${sourceSliceId}/reject`,
    {
      method: "POST",
      token,
      body: JSON.stringify({ reason }),
    },
  );
  return mapFeedSliceResponse(response);
}

export async function patchFeedMappingHints(
  token: string,
  projectId: string,
  sourceDefinitionId: string,
  hints: string | null,
): Promise<FeedContractRecord> {
  const response = await requestJson<Parameters<typeof mapFeedContractResponse>[0]>(
    `/projects/${projectId}/sources/${sourceDefinitionId}/hints`,
    {
      method: "PATCH",
      token,
      body: JSON.stringify({ mapping_hints: hints }),
    },
  );
  return mapFeedContractResponse(response);
}

export async function resubmitFeedSlice(
  token: string,
  projectId: string,
  sourceDefinitionId: string,
  sourceSliceId: string,
  encoding?: string,
): Promise<FeedSliceRecord> {
  const response = await requestJson<Parameters<typeof mapFeedSliceResponse>[0]>(
    `/projects/${projectId}/sources/${sourceDefinitionId}/slices/${sourceSliceId}/resubmit`,
    {
      method: "POST",
      token,
      body: JSON.stringify({ encoding: encoding ?? null }),
    },
  );
  return mapFeedSliceResponse(response);
}

export async function saveTransformationInstructions(
  token: string,
  projectId: string,
  sourceDefinitionId: string,
  instructions: string | null,
): Promise<FeedContractRecord> {
  const response = await requestJson<Parameters<typeof mapFeedContractResponse>[0]>(
    `/projects/${projectId}/sources/${sourceDefinitionId}/transformation-instructions`,
    {
      method: "PATCH",
      token,
      body: JSON.stringify({ transformation_instructions: instructions }),
    },
  );
  return mapFeedContractResponse(response);
}

export interface VersionHistoryEntry {
  versionId: string;
  fieldName: string;
  oldValue: string | null;
  newValue: string | null;
  changedBy: string | null;
  changedAt: string;
}

export async function listVersionHistory(
  token: string,
  projectId: string,
  entityType: "hints" | "transformation",
): Promise<VersionHistoryEntry[]> {
  const raw = await requestJson<{ version_id: string; field_name: string; old_value: string | null; new_value: string | null; changed_by: string | null; changed_at: string }[]>(
    `/projects/${projectId}/versions/${entityType}/versions`,
    { method: "GET", token },
  );
  return raw.map((r) => ({
    versionId: r.version_id,
    fieldName: r.field_name,
    oldValue: r.old_value ?? null,
    newValue: r.new_value ?? null,
    changedBy: r.changed_by ?? null,
    changedAt: r.changed_at,
  }));
}
