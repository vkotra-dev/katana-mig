import { API_BASE_URL } from "./api-base";

export interface BindingSignOffEntry {
  signed: boolean;
  signedAt: string | null;
  userId: string | null;
}

export interface BindingSignOffStatus {
  centralTeam: BindingSignOffEntry;
  projectStakeholder: BindingSignOffEntry;
}

export interface SignOffStatusRecord {
  complete: boolean;
  currentBallRole: "central_team" | "project_stakeholder" | null;
  bindings: Record<string, Record<string, BindingSignOffStatus>>; // obj_name -> source_field -> status
  lookups: Record<string, Record<string, BindingSignOffEntry>>;    // lookup_id -> role -> status
}

export class SignOffApiError extends Error {
  code: string;
  status: number;

  constructor(code: string, message: string, status: number) {
    super(message || code);
    this.name = "SignOffApiError";
    this.code = code;
    this.status = status;
  }
}

async function requestSignOffJson<T>(
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
      throw new SignOffApiError(
        body.error?.code ?? "api_error",
        body.error?.message ?? "api_error",
        response.status,
      );
    } catch (error) {
      if (error instanceof SignOffApiError) {
        throw error;
      }
      throw new SignOffApiError("api_error", await response.text(), response.status);
    }
  }

  if (response.status === 204) {
    return {} as T;
  }

  return response.json() as Promise<T>;
}

// Custom manual mapper to preserve case of dynamic table/field names
function mapSignOffStatus(raw: any): SignOffStatusRecord {
  const bindings: Record<string, Record<string, BindingSignOffStatus>> = {};
  if (raw.bindings) {
    for (const [tableName, fields] of Object.entries(raw.bindings)) {
      bindings[tableName] = {};
      if (fields && typeof fields === "object") {
        for (const [fieldName, status] of Object.entries(fields as any)) {
          const s = status as any;
          bindings[tableName][fieldName] = {
            centralTeam: {
              signed: s?.central_team?.signed ?? false,
              signedAt: s?.central_team?.signed_at ?? null,
              userId: s?.central_team?.user_id ?? null,
            },
            projectStakeholder: {
              signed: s?.project_stakeholder?.signed ?? false,
              signedAt: s?.project_stakeholder?.signed_at ?? null,
              userId: s?.project_stakeholder?.user_id ?? null,
            },
          };
        }
      }
    }
  }

  const lookups: Record<string, Record<string, BindingSignOffEntry>> = {};
  if (raw.lookups) {
    for (const [lookupId, rolesMap] of Object.entries(raw.lookups)) {
      const r = rolesMap as any;
      lookups[lookupId] = {
        centralTeam: {
          signed: r?.central_team?.signed ?? false,
          signedAt: r?.central_team?.signed_at ?? null,
          userId: r?.central_team?.user_id ?? null,
        },
        projectStakeholder: {
          signed: r?.project_stakeholder?.signed ?? false,
          signedAt: r?.project_stakeholder?.signed_at ?? null,
          userId: r?.project_stakeholder?.user_id ?? null,
        },
      };
    }
  }

  return {
    complete: raw.complete ?? false,
    currentBallRole: raw.current_ball_role ?? null,
    bindings,
    lookups,
  };
}

export async function getSignOffStatus(
  token: string,
  projectId: string,
  feedId: string,
): Promise<SignOffStatusRecord> {
  const raw = await requestSignOffJson<any>(
    `/projects/${projectId}/sources/${feedId}/sign-off-status`,
    { method: "GET", token },
  );
  return mapSignOffStatus(raw);
}

export async function signBinding(
  token: string,
  projectId: string,
  feedId: string,
  destObj: string,
  sourceField: string,
): Promise<SignOffStatusRecord> {
  const raw = await requestSignOffJson<any>(
    `/projects/${projectId}/sources/${feedId}/mapping/sign-off`,
    {
      method: "POST",
      token,
      body: JSON.stringify({
        destination_object_name: destObj,
        source_field: sourceField,
      }),
    },
  );
  return mapSignOffStatus(raw);
}

export async function unsignBinding(
  token: string,
  projectId: string,
  feedId: string,
  destObj: string,
  sourceField: string,
): Promise<SignOffStatusRecord> {
  const raw = await requestSignOffJson<any>(
    `/projects/${projectId}/sources/${feedId}/mapping/sign-off`,
    {
      method: "DELETE",
      token,
      body: JSON.stringify({
        destination_object_name: destObj,
        source_field: sourceField,
      }),
    },
  );
  return mapSignOffStatus(raw);
}

export async function signLookup(
  token: string,
  projectId: string,
  feedId: string,
  lookupValueMapId: string,
): Promise<SignOffStatusRecord> {
  const raw = await requestSignOffJson<any>(
    `/projects/${projectId}/sources/${feedId}/lookups/${lookupValueMapId}/sign-off`,
    { method: "POST", token },
  );
  return mapSignOffStatus(raw);
}

export async function unsignLookup(
  token: string,
  projectId: string,
  feedId: string,
  lookupValueMapId: string,
): Promise<SignOffStatusRecord> {
  const raw = await requestSignOffJson<any>(
    `/projects/${projectId}/sources/${feedId}/lookups/${lookupValueMapId}/sign-off`,
    { method: "DELETE", token },
  );
  return mapSignOffStatus(raw);
}

export async function pushForReview(
  token: string,
  projectId: string,
  feedId: string,
): Promise<SignOffStatusRecord> {
  const raw = await requestSignOffJson<any>(
    `/projects/${projectId}/sources/${feedId}/push-for-review`,
    { method: "POST", token },
  );
  return mapSignOffStatus(raw);
}

export async function pokeReviewer(
  token: string,
  projectId: string,
  feedId: string,
  targetRole: "central_team" | "project_stakeholder",
): Promise<void> {
  await requestSignOffJson<void>(
    `/projects/${projectId}/sources/${feedId}/review/poke`,
    {
      method: "POST",
      token,
      body: JSON.stringify({ target_role: targetRole }),
    },
  );
}
