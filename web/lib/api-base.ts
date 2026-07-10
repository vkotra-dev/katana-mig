export const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

export async function jsonRequest<TResponse>(
  path: string,
  init: RequestInit & { token?: string } = {},
): Promise<TResponse> {
  const { token, headers, ...rest } = init;
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...rest,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(headers ?? {}),
    },
  });

  if (!response.ok) {
    const text = await response.text();
    let errorMessage = text;
    try {
      const parsed = JSON.parse(text);
      const detail = parsed.detail || parsed.error || parsed;
      if (detail && typeof detail === "object" && "message" in detail && typeof detail.message === "string") {
        errorMessage = detail.message;
      } else if (typeof detail === "string") {
        errorMessage = detail;
      }
    } catch {
      // not JSON or parsing failed, fallback
    }
    throw new Error(errorMessage);
  }

  return (await response.json()) as TResponse;
}
