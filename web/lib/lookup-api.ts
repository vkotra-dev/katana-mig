import { jsonRequest } from "./api-base";

export interface LookupValueMapRecord {
  lookupValueMapId: string;
  sourceDefinitionId: string;
  lookupName: string;
  destinationTable: Array<Record<string, unknown>>;
  status: "draft" | "approved";
  createdAt: string;
}

export interface LookupSnapshotRecord {
  lookupSnapshotId: string;
  projectId: string;
  sourceDefinitionId: string;
  lookupName: string;
  lookupSnapshotVersion: string;
  valueMap: Record<string, string>;
  status: "draft" | "approved";
  createdAt: string;
}

export interface LookupValueMapInput {
  lookupName: string;
  destinationTable: Array<Record<string, unknown>>;
}

export interface LookupSnapshotInput {
  lookupName: string;
  valueMap: Record<string, string>;
}

function mapLookupValueMapResponse(response: {
  lookup_value_map_id: string;
  source_definition_id: string;
  lookup_name: string;
  destination_table: Array<Record<string, unknown>>;
  status: "draft" | "approved";
  created_at: string;
}): LookupValueMapRecord {
  return {
    lookupValueMapId: response.lookup_value_map_id,
    sourceDefinitionId: response.source_definition_id,
    lookupName: response.lookup_name,
    destinationTable: response.destination_table,
    status: response.status,
    createdAt: response.created_at,
  };
}

function mapLookupSnapshotResponse(response: {
  lookup_snapshot_id: string;
  project_id: string;
  source_definition_id: string;
  lookup_name: string;
  lookup_snapshot_version: string;
  value_map: Record<string, string>;
  status: "draft" | "approved";
  created_at: string;
}): LookupSnapshotRecord {
  return {
    lookupSnapshotId: response.lookup_snapshot_id,
    projectId: response.project_id,
    sourceDefinitionId: response.source_definition_id,
    lookupName: response.lookup_name,
    lookupSnapshotVersion: response.lookup_snapshot_version,
    valueMap: response.value_map,
    status: response.status,
    createdAt: response.created_at,
  };
}

export async function listLookupValueMaps(
  token: string,
  projectId: string,
  sourceDefinitionId: string,
): Promise<LookupValueMapRecord[]> {
  const response = await jsonRequest<Array<Parameters<typeof mapLookupValueMapResponse>[0]>>(
    `/projects/${projectId}/sources/${sourceDefinitionId}/lookup-maps`,
    { method: "GET", token },
  );
  return response.map(mapLookupValueMapResponse);
}

export async function createLookupValueMap(
  token: string,
  projectId: string,
  sourceDefinitionId: string,
  input: LookupValueMapInput,
): Promise<LookupValueMapRecord> {
  const response = await jsonRequest<Parameters<typeof mapLookupValueMapResponse>[0]>(
    `/projects/${projectId}/sources/${sourceDefinitionId}/lookup-maps`,
    {
      method: "POST",
      token,
      body: JSON.stringify({
        lookup_name: input.lookupName,
        destination_table: input.destinationTable,
      }),
    },
  );
  return mapLookupValueMapResponse(response);
}

export async function generateLookupSnapshot(
  token: string,
  projectId: string,
  sourceDefinitionId: string,
  input: LookupSnapshotInput,
): Promise<LookupSnapshotRecord> {
  const response = await jsonRequest<Parameters<typeof mapLookupSnapshotResponse>[0]>(
    `/projects/${projectId}/sources/${sourceDefinitionId}/lookup-snapshots`,
    {
      method: "POST",
      token,
      body: JSON.stringify({
        lookup_name: input.lookupName,
        value_map: input.valueMap,
      }),
    },
  );
  return mapLookupSnapshotResponse(response);
}

export async function approveLookupSnapshot(
  token: string,
  projectId: string,
  sourceDefinitionId: string,
  lookupSnapshotId: string,
): Promise<LookupSnapshotRecord> {
  const response = await jsonRequest<Parameters<typeof mapLookupSnapshotResponse>[0]>(
    `/projects/${projectId}/sources/${sourceDefinitionId}/lookup-snapshots/${lookupSnapshotId}/approve`,
    {
      method: "POST",
      token,
    },
  );
  return mapLookupSnapshotResponse(response);
}
