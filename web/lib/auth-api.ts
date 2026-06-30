import { API_BASE_URL, jsonRequest } from "./api-base";
import type { SessionRole } from "./session";

export interface BootstrapStatusResponse {
  bootstrap_required: boolean;
}

export interface LoginResponse {
  accessToken: string;
  tokenType: "bearer";
  expiresAt: string;
  sessionVersion: number;
  user: {
    user_id: string;
    email: string;
    display_name: string | null;
    role: SessionRole;
    status: "active" | "disabled";
  };
}

export interface SessionResponse {
  user_id: string;
  email: string;
  display_name: string | null;
  role: SessionRole;
  status: "active" | "disabled";
  expires_at: string;
  session_version: number;
}

export interface PasswordResetAccepted {
  accepted: boolean;
}

export async function login(email: string, password: string): Promise<LoginResponse> {
  const response = await jsonRequest<{
    access_token: string;
    token_type: "bearer";
    expires_at: string;
    session_version: number;
    user: LoginResponse["user"];
  }>("/auth/login", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });

  return {
    accessToken: response.access_token,
    tokenType: response.token_type,
    expiresAt: response.expires_at,
    sessionVersion: response.session_version,
    user: response.user,
  };
}

export async function fetchSession(token: string): Promise<SessionResponse> {
  return jsonRequest<SessionResponse>("/auth/session", {
    method: "GET",
    token,
  });
}

export async function logout(token: string): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/auth/logout`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });

  if (!response.ok) {
    throw new Error(await response.text());
  }
}

export async function requestPasswordReset(email: string): Promise<PasswordResetAccepted> {
  return jsonRequest<PasswordResetAccepted>("/auth/password-reset/request", {
    method: "POST",
    body: JSON.stringify({ email }),
  });
}

export async function confirmPasswordReset(resetToken: string, newPassword: string): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/auth/password-reset/confirm`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ reset_token: resetToken, new_password: newPassword }),
  });

  if (!response.ok) {
    throw new Error(await response.text());
  }
}

export async function getBootstrapStatus(): Promise<BootstrapStatusResponse> {
  return jsonRequest<BootstrapStatusResponse>("/auth/bootstrap/status", {
    method: "GET",
  });
}
