import { API_BASE_URL } from "./api-base";

export interface ReconciliationCheckResult {
  checkName: string;
  status: "pass" | "fail";
  detail: string;
}

export interface RowCountSummary {
  sourceRows: number;
  destinationRows: number;
  rejected: number;
  duplicated: number;
  partiallyMapped: number;
}

export interface ReconciliationReport {
  reportId: string;
  runId: string;
  checks: ReconciliationCheckResult[];
  overallStatus: "in_progress" | "pass" | "fail";
  rowCountSummary: RowCountSummary | null;
  createdAt: string;
  completedAt: string | null;
}

export interface LineageRow {
  lineageRowId: string;
  sourceRowIndex: number | null;
  sourceRowKey: string | null;
  destinationRowId: string | null;
  mappingRulesApplied: string[] | null;
  outcome: "confirmed" | "rejected" | "duplicated" | "partially_mapped";
  outcomeDetail: string | null;
}

export interface LineageResponse {
  rows: LineageRow[];
  total: number;
  offset: number;
  limit: number;
}

export interface ReconciliationExport extends ReconciliationReport {
  exportedAt: string;
  lineageRows: LineageRow[];
}

export class ReconciliationApiError extends Error {
  code: string;
  status: number;

  constructor(code: string, message: string, status: number) {
    super(message || code);
    this.name = "ReconciliationApiError";
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

async function parseApiError(response: Response): Promise<ReconciliationApiError> {
  try {
    const body = (await response.json()) as { error?: { code?: string; message?: string } };
    return new ReconciliationApiError(body.error?.code ?? "api_error", body.error?.message ?? "api_error", response.status);
  } catch {
    return new ReconciliationApiError("api_error", await response.text(), response.status);
  }
}

async function requestJson<T>(path: string, init: RequestInit & { token: string }): Promise<T> {
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

function mapReport(record: {
  report_id: string;
  run_id: string;
  checks: Array<{ check_name: string; status: "pass" | "fail"; detail: string }>;
  overall_status: "in_progress" | "pass" | "fail";
  row_count_summary: {
    source_rows: number;
    destination_rows: number;
    rejected: number;
    duplicated: number;
    partially_mapped: number;
  } | null;
  created_at: string;
  completed_at: string | null;
}): ReconciliationReport {
  return {
    reportId: record.report_id,
    runId: record.run_id,
    checks: record.checks.map((check) => ({
      checkName: check.check_name,
      status: check.status,
      detail: check.detail,
    })),
    overallStatus: record.overall_status,
    rowCountSummary: record.row_count_summary
      ? {
          sourceRows: record.row_count_summary.source_rows,
          destinationRows: record.row_count_summary.destination_rows,
          rejected: record.row_count_summary.rejected,
          duplicated: record.row_count_summary.duplicated,
          partiallyMapped: record.row_count_summary.partially_mapped,
        }
      : null,
    createdAt: record.created_at,
    completedAt: record.completed_at,
  };
}

function mapLineageRow(record: {
  lineage_row_id: string;
  source_row_index: number | null;
  source_row_key: string | null;
  destination_row_id: string | null;
  mapping_rules_applied: string[] | null;
  outcome: "confirmed" | "rejected" | "duplicated" | "partially_mapped";
  outcome_detail: string | null;
}): LineageRow {
  return {
    lineageRowId: record.lineage_row_id,
    sourceRowIndex: record.source_row_index,
    sourceRowKey: record.source_row_key,
    destinationRowId: record.destination_row_id,
    mappingRulesApplied: record.mapping_rules_applied,
    outcome: record.outcome,
    outcomeDetail: record.outcome_detail,
  };
}

export async function triggerReconciliation(token: string, projectId: string, runId: string): Promise<ReconciliationReport> {
  const response = await requestJson<Parameters<typeof mapReport>[0]>(
    `/projects/${projectId}/runs/${runId}/reconciliation`,
    { method: "POST", token },
  );
  return mapReport(response);
}

export async function getLatestReport(token: string, projectId: string, runId: string): Promise<ReconciliationReport> {
  const response = await requestJson<Parameters<typeof mapReport>[0]>(
    `/projects/${projectId}/runs/${runId}/reconciliation`,
    { method: "GET", token },
  );
  return mapReport(response);
}

export async function listReports(token: string, projectId: string, runId: string): Promise<ReconciliationReport[]> {
  const response = await requestJson<Array<Parameters<typeof mapReport>[0]>>(
    `/projects/${projectId}/runs/${runId}/reconciliation/history`,
    { method: "GET", token },
  );
  return response.map(mapReport);
}

export async function getLineage(
  token: string,
  projectId: string,
  runId: string,
  reportId: string,
  options: {
    offset?: number;
    limit?: number;
    outcome?: string;
    sourceRowIndex?: number;
    destinationRowId?: string;
  } = {},
): Promise<LineageResponse> {
  const params = new URLSearchParams();
  if (options.offset !== undefined) {
    params.set("offset", String(options.offset));
  }
  if (options.limit !== undefined) {
    params.set("limit", String(options.limit));
  }
  if (options.outcome) {
    params.set("outcome", options.outcome);
  }
  if (options.sourceRowIndex !== undefined) {
    params.set("source_row_index", String(options.sourceRowIndex));
  }
  if (options.destinationRowId) {
    params.set("destination_row_id", options.destinationRowId);
  }

  const suffix = params.toString().length > 0 ? `?${params.toString()}` : "";
  const response = await requestJson<{
    rows: Array<Parameters<typeof mapLineageRow>[0]>;
    total: number;
    offset: number;
    limit: number;
  }>(`/projects/${projectId}/runs/${runId}/reconciliation/${reportId}/lineage${suffix}`, {
    method: "GET",
    token,
  });
  return {
    rows: response.rows.map(mapLineageRow),
    total: response.total,
    offset: response.offset,
    limit: response.limit,
  };
}

export async function exportReport(token: string, projectId: string, runId: string, reportId: string): Promise<ReconciliationExport> {
  const response = await requestJson<
    Parameters<typeof mapReport>[0] & { exported_at: string; lineage_rows: Array<Parameters<typeof mapLineageRow>[0]> }
  >(`/projects/${projectId}/runs/${runId}/reconciliation/${reportId}/export`, {
    method: "GET",
    token,
  });
  const report = mapReport(response);
  return {
    ...report,
    exportedAt: response.exported_at,
    lineageRows: response.lineage_rows.map(mapLineageRow),
  };
}
