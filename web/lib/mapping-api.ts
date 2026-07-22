import { API_BASE_URL } from "./api-base";

export interface MappingFieldBindingRecord {
  sourceField: string;
  destinationField: string;
  lookupName: string | null;
  bindingType?: "direct" | "detail_fk" | "lookup_fk";
  referenceTableName?: string | null;
  destinationTableName?: string | null;
  destinationDataType?: string | null;
  nullable?: boolean | null;
}

export interface LookupTableReference {
  lookupName: string;
  destinationTableName: string;
}

export interface MappingDestinationColumnRecord {
  name: string;
  destinationDataType: string | null;
  nullable: boolean | null;
}

export interface MappingSnapshotRecord {
  mappingSnapshotId: string;
  projectId: string;
  destinationObjectName: string;
  mappingSnapshotVersion: string;
  fieldBindings: MappingFieldBindingRecord[];
  status: string;
  approvedAt: string | null;
  approvedByUserId: string | null;
  createdAt: string;
  lookupTableReferences: LookupTableReference[];
  destinationFields: string[];
  destinationColumns?: MappingDestinationColumnRecord[] | null;
}

export interface MappingReviewRecord extends MappingSnapshotRecord {}

export class MappingApiError extends Error {
  code: string;
  status: number;

  constructor(code: string, message: string, status: number) {
    super(message || code);
    this.name = "MappingApiError";
    this.code = code;
    this.status = status;
  }
}

type MappingSnapshotRaw = {
  mapping_snapshot_id: string;
  project_id: string;
  destination_object_name: string;
  mapping_snapshot_version: string;
  field_bindings: Array<{
    source_field: string;
    destination_field: string;
    lookup_name: string | null;
    binding_type?: string | null;
    reference_table_name?: string | null;
    destination_table_name?: string | null;
    destination_data_type?: string | null;
    nullable?: boolean | null;
  }>;
  status: string;
  approved_at: string | null;
  approved_by_user_id: string | null;
  created_at: string;
  lookup_table_references?: Array<{
    lookup_name: string;
    destination_table_name: string;
  }>;
  destination_fields?: string[];
  destination_columns?: Array<{
    name: string;
    destination_data_type: string | null;
    nullable: boolean | null;
  }>;

};

type MappingReviewRaw = MappingSnapshotRaw;

function mapMappingSnapshotResponse(response: MappingSnapshotRaw): MappingSnapshotRecord {
  return {
    mappingSnapshotId: response.mapping_snapshot_id,
    projectId: response.project_id,
    destinationObjectName: response.destination_object_name,
    mappingSnapshotVersion: response.mapping_snapshot_version,
    fieldBindings: response.field_bindings.map((binding) => ({
      sourceField: binding.source_field,
      destinationField: binding.destination_field,
      lookupName: binding.lookup_name,
      bindingType: binding.binding_type as any,
      referenceTableName: binding.reference_table_name,
      destinationTableName: binding.destination_table_name,
      destinationDataType: binding.destination_data_type,
      nullable: binding.nullable,
    })),
    status: response.status,
    approvedAt: response.approved_at,
    approvedByUserId: response.approved_by_user_id,
    createdAt: response.created_at,
    lookupTableReferences: (response.lookup_table_references ?? []).map((ref) => ({
      lookupName: ref.lookup_name,
      destinationTableName: ref.destination_table_name,
    })),
    destinationFields: response.destination_fields ?? [],
    destinationColumns: response.destination_columns?.map((c) => ({
      name: c.name,
      destinationDataType: c.destination_data_type ?? null,
      nullable: c.nullable ?? null,
    })) ?? null,
  };
}

function mapMappingReviewResponse(response: MappingReviewRaw): MappingReviewRecord {
  return mapMappingSnapshotResponse(response);
}

async function requestMappingJson<T>(
  path: string,
  init: RequestInit & { token: string },
): Promise<T> {
  const { token, headers, ...rest } = init;
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...rest,
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
      ...(headers ?? {}),
    },
  });

  if (!response.ok) {
    try {
      const body = (await response.json()) as { error?: { code?: string; message?: string } };
      throw new MappingApiError(
        body.error?.code ?? "api_error",
        body.error?.message ?? "api_error",
        response.status,
      );
    } catch (error) {
      if (error instanceof MappingApiError) {
        throw error;
      }
      throw new MappingApiError("api_error", await response.text(), response.status);
    }
  }

  return (await response.json()) as T;
}

export async function getLatestApprovedMappingSnapshot(
  token: string,
  projectId: string,
  sourceDefinitionId: string,
): Promise<MappingSnapshotRecord> {
  const response = await requestMappingJson<MappingSnapshotRaw>(
    `/projects/${projectId}/sources/${sourceDefinitionId}/mapping-snapshot`,
    { method: "GET", token },
  );
  return mapMappingSnapshotResponse(response);
}

export async function getAllApprovedMappingSnapshots(
  token: string,
  projectId: string,
  sourceDefinitionId: string,
  anyStatus = false,
): Promise<MappingSnapshotRecord[]> {
  const qs = anyStatus ? "?any_status=true" : "";
  const response = await requestMappingJson<MappingSnapshotRaw[]>(
    `/projects/${projectId}/sources/${sourceDefinitionId}/mapping-snapshots${qs}`,
    { method: "GET", token },
  );
  return response.map(mapMappingSnapshotResponse);
}

export async function proposeMappingSnapshot(
  token: string,
  projectId: string,
  sourceDefinitionId: string,
): Promise<MappingReviewRecord> {
  const response = await requestMappingJson<MappingReviewRaw>(
    `/projects/${projectId}/sources/${sourceDefinitionId}/mapping/propose`,
    { method: "POST", token },
  );
  return mapMappingReviewResponse(response);
}

export async function unapproveMappingSnapshot(
  token: string,
  projectId: string,
  sourceDefinitionId: string,
): Promise<MappingReviewRecord> {
  const response = await requestMappingJson<MappingReviewRaw>(
    `/projects/${projectId}/sources/${sourceDefinitionId}/mapping/unapprove`,
    { method: "POST", token },
  );
  return mapMappingReviewResponse(response);
}

export async function getMappingSnapshot(
  token: string,
  projectId: string,
  sourceDefinitionId: string,
): Promise<MappingReviewRecord> {
  const response = await requestMappingJson<MappingReviewRaw>(
    `/projects/${projectId}/sources/${sourceDefinitionId}/mapping`,
    { method: "GET", token },
  );
  return mapMappingReviewResponse(response);
}

export async function patchMappingSnapshot(
  token: string,
  projectId: string,
  sourceDefinitionId: string,
  fieldBindings: Array<{ sourceField: string; destinationField: string; lookupName: string | null }>,
  destinationObjectName?: string,
): Promise<MappingReviewRecord> {
  const query = destinationObjectName ? `?destination_object_name=${encodeURIComponent(destinationObjectName)}` : "";
  const response = await requestMappingJson<MappingReviewRaw>(
    `/projects/${projectId}/sources/${sourceDefinitionId}/mapping${query}`,
    {
      method: "PATCH",
      token,
      body: JSON.stringify({
        field_bindings: fieldBindings.map((binding) => ({
          source_field: binding.sourceField,
          destination_field: binding.destinationField,
          lookup_name: binding.lookupName,
        })),
      }),
    },
  );
  return mapMappingReviewResponse(response);
}

export async function approveMappingSnapshot(
  token: string,
  projectId: string,
  sourceDefinitionId: string,
): Promise<MappingReviewRecord> {
  const response = await requestMappingJson<MappingReviewRaw>(
    `/projects/${projectId}/sources/${sourceDefinitionId}/mapping/approve`,
    { method: "POST", token },
  );
  return mapMappingReviewResponse(response);
}

export async function rejectMappingSnapshot(
  token: string,
  projectId: string,
  sourceDefinitionId: string,
  reason: string,
): Promise<MappingReviewRecord> {
  const response = await requestMappingJson<MappingReviewRaw>(
    `/projects/${projectId}/sources/${sourceDefinitionId}/mapping/reject`,
    {
      method: "POST",
      token,
      body: JSON.stringify({ reason }),
    },
  );
  return mapMappingReviewResponse(response);
}
