import { API_BASE_URL, jsonRequest } from "./api-base";
import type { UserRole, UserStatus } from "../components/UserForm";

export interface UserResponse {
  userId: string;
  email: string;
  displayName: string | null;
  role: UserRole;
  status: UserStatus;
  createdAt: string;
  updatedAt: string;
}

export interface UserCreateInput {
  email: string;
  password: string;
  displayName: string | null;
  role: UserRole;
}

export interface UserUpdateInput {
  displayName?: string | null;
  role?: UserRole;
  status?: UserStatus;
}

export interface ProjectMemberResponse {
  projectId: string;
  userId: string;
  createdAt: string;
}

export interface MembershipResponse {
  projectId: string;
  userId: string;
  warning: string | null;
}

function mapUserResponse(response: {
  user_id: string;
  email: string;
  display_name: string | null;
  role: UserRole;
  status: UserStatus;
  created_at: string;
  updated_at: string;
}): UserResponse {
  return {
    userId: response.user_id,
    email: response.email,
    displayName: response.display_name,
    role: response.role,
    status: response.status,
    createdAt: response.created_at,
    updatedAt: response.updated_at,
  };
}

function mapMemberResponse(response: {
  project_id: string;
  user_id: string;
  created_at: string;
}): ProjectMemberResponse {
  return {
    projectId: response.project_id,
    userId: response.user_id,
    createdAt: response.created_at,
  };
}

function mapMembershipResponse(response: {
  project_id: string;
  user_id: string;
  warning: string | null;
}): MembershipResponse {
  return {
    projectId: response.project_id,
    userId: response.user_id,
    warning: response.warning,
  };
}

export async function listUsers(token: string): Promise<UserResponse[]> {
  const response = await jsonRequest<
    Array<{
      user_id: string;
      email: string;
      display_name: string | null;
      role: UserRole;
      status: UserStatus;
      created_at: string;
      updated_at: string;
    }>
  >("/users", {
    method: "GET",
    token,
  });

  return response.map(mapUserResponse);
}

export async function getUser(token: string, userId: string): Promise<UserResponse> {
  const response = await jsonRequest<{
    user_id: string;
    email: string;
    display_name: string | null;
    role: UserRole;
    status: UserStatus;
    created_at: string;
    updated_at: string;
  }>(`/users/${userId}`, {
    method: "GET",
    token,
  });

  return mapUserResponse(response);
}

export async function createUser(token: string, input: UserCreateInput): Promise<UserResponse> {
  const response = await jsonRequest<{
    user_id: string;
    email: string;
    display_name: string | null;
    role: UserRole;
    status: UserStatus;
    created_at: string;
    updated_at: string;
  }>("/users", {
    method: "POST",
    token,
    body: JSON.stringify({
      email: input.email,
      password: input.password,
      display_name: input.displayName,
      role: input.role,
    }),
  });

  return mapUserResponse(response);
}

export async function updateUser(
  token: string,
  userId: string,
  input: UserUpdateInput,
): Promise<UserResponse> {
  const response = await jsonRequest<{
    user_id: string;
    email: string;
    display_name: string | null;
    role: UserRole;
    status: UserStatus;
    created_at: string;
    updated_at: string;
  }>(`/users/${userId}`, {
    method: "PATCH",
    token,
    body: JSON.stringify({
      display_name: input.displayName,
      role: input.role,
      status: input.status,
    }),
  });

  return mapUserResponse(response);
}

export async function deleteUser(token: string, userId: string): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/users/${userId}`, {
    method: "DELETE",
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });

  if (!response.ok) {
    throw new Error(await response.text());
  }
}

export async function listProjectMembers(token: string, projectId: string): Promise<ProjectMemberResponse[]> {
  const response = await jsonRequest<
    Array<{
      project_id: string;
      user_id: string;
      created_at: string;
    }>
  >(`/projects/${projectId}/members`, {
    method: "GET",
    token,
  });

  return response.map(mapMemberResponse);
}

export async function addProjectMember(
  token: string,
  projectId: string,
  userId: string,
): Promise<MembershipResponse> {
  const response = await jsonRequest<{
    project_id: string;
    user_id: string;
    warning: string | null;
  }>(`/projects/${projectId}/members`, {
    method: "POST",
    token,
    body: JSON.stringify({ user_id: userId }),
  });

  return mapMembershipResponse(response);
}

export async function removeProjectMember(
  token: string,
  projectId: string,
  userId: string,
): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/projects/${projectId}/members/${userId}`, {
    method: "DELETE",
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });

  if (!response.ok) {
    throw new Error(await response.text());
  }
}

export const MANAGEMENT_API_BASE_URL = API_BASE_URL;
