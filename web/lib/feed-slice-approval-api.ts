import { API_BASE_URL } from "./api-base";



export class FeedSliceApprovalApiError extends Error {
  code: string;
  status: number;

  constructor(code: string, message: string, status: number) {
    super(message || code);
    this.name = "FeedSliceApprovalApiError";
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

  if (response.status === 204) {
    return undefined as T;
  }

  return (await response.json()) as T;
}

async function parseApiError(response: Response): Promise<FeedSliceApprovalApiError> {
  try {
    const body = (await response.json()) as { error?: { code?: string; message?: string } };
    const code = body.error?.code ?? "api_error";
    const message = body.error?.message ?? code;
    return new FeedSliceApprovalApiError(code, message, response.status);
  } catch {
    const message = await response.text();
    return new FeedSliceApprovalApiError("api_error", message || "api_error", response.status);
  }
}



export async function approveFeedSlice(
  token: string,
  projectId: string,
  sourceDefinitionId: string,
  sourceSliceId: string,
): Promise<void> {
  await requestJson<void>(
    `/projects/${projectId}/sources/${sourceDefinitionId}/slices/${sourceSliceId}/approve`,
    { method: "POST", token },
  );
}

export async function rejectFeedSlice(
  token: string,
  projectId: string,
  sourceDefinitionId: string,
  sourceSliceId: string,
  reason: string,
): Promise<void> {
  await requestJson<void>(
    `/projects/${projectId}/sources/${sourceDefinitionId}/slices/${sourceSliceId}/reject`,
    {
      method: "POST",
      token,
      body: JSON.stringify({ reason }),
    },
  );
}

export async function resubmitFeedSlice(
  token: string,
  projectId: string,
  sourceDefinitionId: string,
  sourceSliceId: string,
  input: { encoding?: string | null; parseSettings?: Record<string, unknown> | null },
): Promise<void> {
  await requestJson<void>(
    `/projects/${projectId}/sources/${sourceDefinitionId}/slices/${sourceSliceId}/resubmit`,
    {
      method: "POST",
      token,
      body: JSON.stringify({
        encoding: input.encoding ?? null,
        parse_settings: input.parseSettings ?? null,
      }),
    },
  );
}
