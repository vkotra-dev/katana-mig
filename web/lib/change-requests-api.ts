import { jsonRequest } from "./api-base";

export type ChangeRequestStatus = "open" | "resolved" | "closed";
export type ChangeRequestType = "lookup_delta" | string;

export interface ChangeRequestPayloadRecord {
  runId: string;
  lookupName: string;
  unmappedValue: string;
  destinationObjectName: string;
}

export interface ChangeRequestSummaryRecord {
  changeRequestId: string;
  projectId: string;
  changeRequestType: ChangeRequestType;
  status: ChangeRequestStatus | string;
  title: string;
  createdAt: string;
}

export interface ChangeRequestRecord extends ChangeRequestSummaryRecord {
  payload: ChangeRequestPayloadRecord | null;
  updatedAt: string;
}

export interface ChangeRequestResolveInput {
  acceptedValue: string;
}

export interface ChangeRequestResolveResult {
  changeRequestId: string;
  status: "resolved";
}

type RawPayload = {
  run_id: string;
  lookup_name: string;
  unmapped_value: string;
  destination_object_name: string;
} | null;

type RawSummary = {
  change_request_id: string;
  project_id: string;
  change_request_type: string;
  status: string;
  title: string;
  created_at: string;
};

type RawDetail = RawSummary & {
  payload: RawPayload;
  updated_at: string;
};

type RawResolveResponse = {
  change_request_id: string;
  status: "resolved";
};

function mapSummary(raw: RawSummary): ChangeRequestSummaryRecord {
  return {
    changeRequestId: raw.change_request_id,
    projectId: raw.project_id,
    changeRequestType: raw.change_request_type,
    status: raw.status,
    title: raw.title,
    createdAt: raw.created_at,
  };
}

function mapPayload(raw: RawPayload): ChangeRequestPayloadRecord | null {
  if (!raw) {
    return null;
  }
  return {
    runId: raw.run_id,
    lookupName: raw.lookup_name,
    unmappedValue: raw.unmapped_value,
    destinationObjectName: raw.destination_object_name,
  };
}

function mapDetail(raw: RawDetail): ChangeRequestRecord {
  return {
    ...mapSummary(raw),
    payload: mapPayload(raw.payload),
    updatedAt: raw.updated_at,
  };
}

export async function listChangeRequests(
  token: string,
  projectId: string,
): Promise<ChangeRequestSummaryRecord[]> {
  const response = await jsonRequest<RawSummary[]>(
    `/projects/${projectId}/change-requests`,
    { method: "GET", token },
  );
  return response.map(mapSummary);
}

export async function getChangeRequest(
  token: string,
  projectId: string,
  crId: string,
): Promise<ChangeRequestRecord> {
  const response = await jsonRequest<RawDetail>(
    `/projects/${projectId}/change-requests/${crId}`,
    { method: "GET", token },
  );
  return mapDetail(response);
}

export async function resolveChangeRequest(
  token: string,
  projectId: string,
  crId: string,
  input: ChangeRequestResolveInput,
): Promise<ChangeRequestResolveResult> {
  const response = await jsonRequest<RawResolveResponse>(
    `/projects/${projectId}/change-requests/${crId}/resolve`,
    {
      method: "POST",
      token,
      body: JSON.stringify({ accepted_value: input.acceptedValue }),
    },
  );
  return {
    changeRequestId: response.change_request_id,
    status: response.status,
  };
}
