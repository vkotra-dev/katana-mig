import { jsonRequest } from "./api-base";

export interface DestinationMappingGroup {
  destId: string;
  destLabel: string;
  destRow?: Record<string, unknown>;
  sourceValues: string[];
  status: string;
}

export interface LookupValueMapRecord {
  lookupValueMapId: string;
  projectId: string;
  lookupName: string;
  destinationTable: Array<Record<string, unknown>>;
  sourceValueMap: Record<string, string>;
  destinationMappings: DestinationMappingGroup[];
  status: "draft" | "approved";
  unmappedRowCount?: number;
  createdAt: string;
}

export interface LookupSnapshotRecord {
  lookupSnapshotId: string;
  projectId: string;
  lookupName: string;
  lookupSnapshotVersion: string;
  valueMap: Record<string, string>;
  status: "draft" | "approved";
  createdAt: string;
}

export interface LookupValueMapInput {
  lookupName: string;
  destinationTable: Array<Record<string, unknown>>;
  sourceValueMap: Record<string, string>;
}

export interface LookupSnapshotInput {
  lookupName: string;
}

function mapLookupValueMapResponse(response: {
  lookup_value_map_id: string;
  project_id: string;
  lookup_name: string;
  destination_table: Array<Record<string, unknown>>;
  source_value_map: Record<string, string>;
  destination_mappings?: Array<Record<string, unknown>>;
  status: "draft" | "approved";
  created_at: string;
}): LookupValueMapRecord {
  return {
    lookupValueMapId: response.lookup_value_map_id,
    projectId: response.project_id,
    lookupName: response.lookup_name,
    destinationTable: response.destination_table,
    sourceValueMap: response.source_value_map,
    destinationMappings: (response.destination_mappings || []).map((g: Record<string, unknown>) => ({
      destId: String(g.dest_id ?? g.destId ?? ""),
      destLabel: String(g.dest_label ?? g.destLabel ?? ""),
      destRow: g.dest_row ?? g.destRow,
      sourceValues: Array.isArray(g.source_values ?? g.sourceValues) ? g.source_values ?? g.sourceValues : [],
      status: String(g.status ?? "draft"),
    })),
    status: response.status,
    createdAt: response.created_at,
  };
}

function mapLookupSnapshotResponse(response: {
  lookup_snapshot_id: string;
  project_id: string;
  lookup_name: string;
  lookup_snapshot_version: string;
  value_map: Record<string, string>;
  status: "draft" | "approved";
  created_at: string;
}): LookupSnapshotRecord {
  return {
    lookupSnapshotId: response.lookup_snapshot_id,
    projectId: response.project_id,
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
  feedId?: string,
): Promise<LookupValueMapRecord[]> {
  const url = feedId
    ? `/projects/${projectId}/lookup-maps?feed_id=${feedId}`
    : `/projects/${projectId}/lookup-maps`;
  const response = await jsonRequest<Array<Parameters<typeof mapLookupValueMapResponse>[0]>>(
    url,
    { method: "GET", token },
  );
  return response.map(mapLookupValueMapResponse);
}

export async function createLookupValueMap(
  token: string,
  projectId: string,
  input: LookupValueMapInput,
): Promise<LookupValueMapRecord> {
  const response = await jsonRequest<Parameters<typeof mapLookupValueMapResponse>[0]>(
    `/projects/${projectId}/lookup-maps`,
    {
      method: "POST",
      token,
      body: JSON.stringify({
        lookup_name: input.lookupName,
        destination_table: input.destinationTable,
        source_value_map: input.sourceValueMap,
      }),
    },
  );
  return mapLookupValueMapResponse(response);
}

export interface PatchLookupValueMapInput {
  sourceValueMap?: Record<string, string>;
  destinationMappings?: DestinationMappingGroup[];
  addSourceValue?: { destId: string; sourceValue: string };
  removeSourceValue?: { destId: string; sourceValue: string };
  moveSourceValue?: { sourceValue: string; oldDestId: string; newDestId: string };
}

export async function patchLookupValueMap(
  token: string,
  projectId: string,
  lookupValueMapId: string,
  input: PatchLookupValueMapInput,
): Promise<LookupValueMapRecord> {
  const body: Record<string, unknown> = {};
  if (input.sourceValueMap) body.source_value_map = input.sourceValueMap;
  if (input.destinationMappings) body.destination_mappings = input.destinationMappings;
  if (input.addSourceValue) body.add_source_value = input.addSourceValue;
  if (input.removeSourceValue) body.removeSourceValue = input.removeSourceValue;
  if (input.moveSourceValue) body.move_source_value = input.moveSourceValue;

  const response = await jsonRequest<Parameters<typeof mapLookupValueMapResponse>[0]>(
    `/projects/${projectId}/lookup-maps/${lookupValueMapId}`,
    {
      method: "PATCH",
      token,
      body: JSON.stringify(body),
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
      }),
    },
  );
  return mapLookupSnapshotResponse(response);
}

export async function approveLookupSnapshot(
  token: string,
  projectId: string,
  lookupSnapshotId: string,
): Promise<LookupSnapshotRecord> {
  const response = await jsonRequest<Parameters<typeof mapLookupSnapshotResponse>[0]>(
    `/projects/${projectId}/lookup-snapshots/${lookupSnapshotId}/approve`,
    {
      method: "POST",
      token,
    },
  );
  return mapLookupSnapshotResponse(response);
}

export interface SubmitLookupInputsInput {
  sourceValues: string[];
  destinationLookupCsv: string;
}

export async function submitLookupInputs(
  token: string,
  projectId: string,
  feedId: string,
  fiberId: string,
  input: SubmitLookupInputsInput,
): Promise<void> {
  await jsonRequest<void>(
    `/projects/${projectId}/feeds/${feedId}/fibers/${fiberId}/lookup-inputs`,
    {
      method: "POST",
      token,
      body: JSON.stringify({
        source_values: input.sourceValues,
        destination_lookup_csv: input.destinationLookupCsv,
      }),
    },
  );
}
