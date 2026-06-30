import { describe, expect, it, vi } from "vitest";
import { addProjectMember, createUser, deleteUser, getUser, listProjectMembers, listUsers, removeProjectMember, updateUser } from "./management-api";

describe("management-api", () => {
  it("posts new users to /users", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        user_id: "user-1",
        email: "stakeholder@example.com",
        display_name: "Stakeholder",
        role: "project_stakeholder",
        status: "active",
        created_at: "2026-06-29T12:00:00Z",
        updated_at: "2026-06-29T12:00:00Z",
      }),
    });
    vi.stubGlobal("fetch", fetchMock);

    await createUser("token-1", {
      email: "stakeholder@example.com",
      password: "password-123",
      displayName: "Stakeholder",
      role: "project_stakeholder",
    });

    expect(fetchMock).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/users",
      expect.objectContaining({
        method: "POST",
        headers: expect.objectContaining({
          Authorization: "Bearer token-1",
        }),
        body: JSON.stringify({
          email: "stakeholder@example.com",
          password: "password-123",
          display_name: "Stakeholder",
          role: "project_stakeholder",
        }),
      })
    );
  });

  it("posts project members to the membership endpoint", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        project_id: "project-1",
        user_id: "user-1",
        warning: null,
      }),
    });
    vi.stubGlobal("fetch", fetchMock);

    await addProjectMember("token-1", "project-1", "user-1");

    expect(fetchMock).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/projects/project-1/members",
      expect.objectContaining({
        method: "POST",
        headers: expect.objectContaining({
          Authorization: "Bearer token-1",
        }),
        body: JSON.stringify({ user_id: "user-1" }),
      })
    );
  });

  it("lists and removes users through the management endpoints", async () => {
    const listUsersMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => [],
    });
    const deleteUserMock = vi.fn().mockResolvedValue({
      ok: true,
      text: async () => "",
    });
    const listMembersMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => [],
    });
    const removeMemberMock = vi.fn().mockResolvedValue({
      ok: true,
      text: async () => "",
    });
    vi.stubGlobal("fetch", listUsersMock);
    await listUsers("token-1");
    expect(listUsersMock).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/users",
      expect.objectContaining({
        method: "GET",
        headers: expect.objectContaining({ Authorization: "Bearer token-1" }),
      })
    );

    vi.stubGlobal("fetch", deleteUserMock);
    await deleteUser("token-1", "user-1");
    expect(deleteUserMock).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/users/user-1",
      expect.objectContaining({
        method: "DELETE",
        headers: expect.objectContaining({ Authorization: "Bearer token-1" }),
      })
    );

    vi.stubGlobal("fetch", listMembersMock);
    await listProjectMembers("token-1", "project-1");
    expect(listMembersMock).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/projects/project-1/members",
      expect.objectContaining({
        method: "GET",
        headers: expect.objectContaining({ Authorization: "Bearer token-1" }),
      })
    );

    vi.stubGlobal("fetch", removeMemberMock);
    await removeProjectMember("token-1", "project-1", "user-1");
    expect(removeMemberMock).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/projects/project-1/members/user-1",
      expect.objectContaining({
        method: "DELETE",
        headers: expect.objectContaining({ Authorization: "Bearer token-1" }),
      })
    );
  });

  it("fetches a single user by id", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        user_id: "user-1",
        email: "operator@example.com",
        display_name: "Operator",
        role: "central_team",
        status: "active",
        created_at: "2026-06-29T12:00:00Z",
        updated_at: "2026-06-29T12:00:00Z",
      }),
    });
    vi.stubGlobal("fetch", fetchMock);

    await getUser("token-1", "user-1");

    expect(fetchMock).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/users/user-1",
      expect.objectContaining({
        method: "GET",
        headers: expect.objectContaining({
          Authorization: "Bearer token-1",
        }),
      })
    );
  });
});
