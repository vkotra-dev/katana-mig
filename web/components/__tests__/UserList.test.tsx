import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { UserList } from "../UserList";

describe("UserList", () => {
  it("renders edit and delete actions", () => {
    const onDelete = vi.fn();
    const onEdit = vi.fn();
    const onSelect = vi.fn();

    render(
      <UserList
        onDelete={onDelete}
        onEdit={onEdit}
        onSelect={onSelect}
        users={[
          {
            userId: "user-1",
            email: "operator@example.com",
            displayName: "Operator",
            role: "central_team",
            status: "active",
          },
        ]}
      />
    );

    expect(screen.getByText("operator@example.com")).toBeInTheDocument();
    screen.getByRole("button", { name: "Edit" }).click();
    expect(onEdit).toHaveBeenCalledWith("user-1");
    expect(screen.getByRole("button", { name: "Delete" })).toBeInTheDocument();
  });
});
