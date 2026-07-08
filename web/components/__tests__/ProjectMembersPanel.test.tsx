import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ProjectMembersPanel } from "../ProjectMembersPanel";

describe("ProjectMembersPanel", () => {
  it("submits member additions and shows duplicate warnings", async () => {
    const onAdd = vi.fn();
    const onRemove = vi.fn();

    render(
      <ProjectMembersPanel
        members={[
          {
            projectId: "project-1",
            userId: "user-1",
            displayName: "Operator",
            email: "operator@example.com",
            role: "project_stakeholder",
            status: "active",
            warning: "User is already a member of this project.",
          },
        ]}
        availableUsers={[
          {
            userId: "user-2",
            email: "other@example.com",
            displayName: "Other User",
            role: "project_stakeholder",
            status: "active",
            createdAt: "2026-06-30T12:00:00Z",
            updatedAt: "2026-06-30T12:00:00Z",
          }
        ]}
        onAdd={onAdd}
        onRemove={onRemove}
        projectId="project-1"
        warning="User is already a member of this project."
      />
    );

    const input = screen.getByPlaceholderText("Search users by email or name...");
    fireEvent.focus(input);
    fireEvent.change(input, {
      target: { value: "other" },
    });

    const option = await screen.findByText("other@example.com — Other User (project_stakeholder)");
    fireEvent.click(option);

    await waitFor(() => expect(onAdd).toHaveBeenCalledWith("user-2"));
    expect(screen.getByText("User is already a member of this project.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Remove" })).toBeInTheDocument();
  });
});
