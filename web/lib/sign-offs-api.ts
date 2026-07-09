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

  // Handle 204 No Content
  if (response.status === 204) {
    return {} as T;
  }

  const raw = await response.json();
  return mapSnakeToCamel(raw) as T;
}

// Helper to convert snake_case JSON keys from backend to camelCase in frontend
function mapSnakeToCamel(obj: any): any {
  if (Array.isArray(obj)) {
    return obj.map(mapSnakeToCamel);
  } else if (obj !== null && typeof obj === "object" && !(obj instanceof Date)) {
    const n: Record<string, any> = {};
    for (const key of Object.keys(obj)) {
      const camel = key.replace(/_([a-z])/g, (g) => g[1].toUpperCase());
      n[camel] = mapSnakeToCamel(obj[key]);
    }
    return n;
  }
  return obj;
}

export async function getSignOffStatus(
  token: string,
  projectId: string,
  feedId: string,
): Promise<SignOffStatusRecord> {
  return requestSignOffJson<SignOffStatusRecord>(
    `/projects/${projectId}/sources/${feedId}/sign-off-status`,
    { method: "GET", token },
  );
}

export async function signBinding(
  token: string,
  projectId: string,
  feedId: string,
  destObj: string,
  sourceField: string,
): Promise<SignOffStatusRecord> {
  return requestSignOffJson<SignOffStatusRecord>(
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
}

export async function unsignBinding(
  token: string,
  projectId: string,
  feedId: string,
  destObj: string,
  sourceField: string,
): Promise<SignOffStatusRecord> {
  return requestSignOffJson<SignOffStatusRecord>(
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
}

export async function signLookup(
  token: string,
  projectId: string,
  feedId: string,
  lookupValueMapId: string,
): Promise<SignOffStatusRecord> {
  return requestSignOffJson<SignOffStatusRecord>(
    `/projects/${projectId}/sources/${feedId}/lookups/${lookupValueMapId}/sign-off`,
    { method: "POST", token },
  );
}

export async function unsignLookup(
  token: string,
  projectId: string,
  feedId: string,
  lookupValueMapId: string,
): Promise<SignOffStatusRecord> {
  return requestSignOffJson<SignOffStatusRecord>(
    `/projects/${projectId}/sources/${feedId}/lookups/${lookupValueMapId}/sign-off`,
    { method: "DELETE", token },
  );
}

export async function pushForReview(
  token: string,
  projectId: string,
  feedId: string,
): Promise<SignOffStatusRecord> {
  return requestSignOffJson<SignOffStatusRecord>(
    `/projects/${projectId}/sources/${feedId}/push-for-review`,
    { method: "POST", token },
  );
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
