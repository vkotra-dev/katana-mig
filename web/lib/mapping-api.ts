import { jsonRequest } from "./api-base";

export interface MappingFieldBindingRecord {
  sourceField: string;
  destinationField: string;
  lookupName: string | null;
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
}

function mapMappingSnapshotResponse(response: {
  mapping_snapshot_id: string;
  project_id: string;
  destination_object_name: string;
  mapping_snapshot_version: string;
  field_bindings: Array<{
    source_field: string;
    destination_field: string;
    lookup_name: string | null;
  }>;
  status: string;
  approved_at: string | null;
  approved_by_user_id: string | null;
  created_at: string;
}): MappingSnapshotRecord {
  return {
    mappingSnapshotId: response.mapping_snapshot_id,
    projectId: response.project_id,
    destinationObjectName: response.destination_object_name,
    mappingSnapshotVersion: response.mapping_snapshot_version,
    fieldBindings: response.field_bindings.map((binding) => ({
      sourceField: binding.source_field,
      destinationField: binding.destination_field,
      lookupName: binding.lookup_name,
    })),
    status: response.status,
    approvedAt: response.approved_at,
    approvedByUserId: response.approved_by_user_id,
    createdAt: response.created_at,
  };
}

export async function getLatestApprovedMappingSnapshot(
  token: string,
  projectId: string,
  sourceDefinitionId: string,
): Promise<MappingSnapshotRecord> {
  const response = await jsonRequest<Parameters<typeof mapMappingSnapshotResponse>[0]>(
    `/projects/${projectId}/sources/${sourceDefinitionId}/mapping-snapshot`,
    { method: "GET", token },
  );
  return mapMappingSnapshotResponse(response);
}
