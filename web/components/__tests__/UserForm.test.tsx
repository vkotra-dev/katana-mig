import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { UserForm } from "../UserForm";

describe("UserForm", () => {
  it("collects the create-user fields", async () => {
    const onSubmit = vi.fn();
    render(<UserForm mode="create" onSubmit={onSubmit} />);

    fireEvent.change(screen.getByPlaceholderText("operator@example.com"), {
      target: { value: "stakeholder@example.com" },
    });
    fireEvent.change(screen.getByPlaceholderText("Initial password"), {
      target: { value: "password-123" },
    });
    fireEvent.change(screen.getByPlaceholderText("Operator"), {
      target: { value: "Stakeholder" },
    });
    fireEvent.submit(screen.getByRole("button", { name: "Create user" }).closest("form") as HTMLFormElement);

    await waitFor(() =>
      expect(onSubmit).toHaveBeenCalledWith({
        email: "stakeholder@example.com",
        password: "password-123",
        displayName: "Stakeholder",
        role: "project_stakeholder",
        status: "active",
      })
    );
  });

  it("pre-fills edit values", () => {
    render(
      <UserForm
        initialValue={{
          email: "operator@example.com",
          displayName: "Operator",
          role: "central_team",
          status: "disabled",
        }}
        mode="edit"
        onSubmit={vi.fn()}
      />
    );

    expect(screen.getByDisplayValue("operator@example.com")).toBeInTheDocument();
    expect(screen.getByDisplayValue("Operator")).toBeInTheDocument();
    expect(screen.getByDisplayValue("central_team")).toBeInTheDocument();
    expect(screen.getByDisplayValue("disabled")).toBeInTheDocument();
    expect(screen.queryByPlaceholderText("Initial password")).not.toBeInTheDocument();
  });
});
