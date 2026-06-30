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
        onAdd={onAdd}
        onRemove={onRemove}
        projectId="project-1"
        warning="User is already a member of this project."
      />
    );

    fireEvent.change(screen.getByPlaceholderText("User ID"), {
      target: { value: "user-2" },
    });
    fireEvent.submit(screen.getByRole("button", { name: "Add member" }).closest("form") as HTMLFormElement);

    await waitFor(() => expect(onAdd).toHaveBeenCalledWith("user-2"));
    expect(screen.getByText("User is already a member of this project.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Remove" })).toBeInTheDocument();
  });
});
