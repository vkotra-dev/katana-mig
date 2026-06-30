import { render, screen } from "@testing-library/react";
import { Sidebar } from "../Sidebar";

describe("Sidebar", () => {
  it("renders a role-specific sidebar", () => {
    render(<Sidebar role="project_stakeholder" />);

    expect(screen.getByText("Portfolio")).toBeInTheDocument();
    expect(screen.getByText("Approvals")).toBeInTheDocument();
    expect(screen.queryByText("Admin")).not.toBeInTheDocument();
  });

  it("hides approvals and admin for read-only auditors", () => {
    render(<Sidebar role="read_only_auditor" />);

    expect(screen.getByText("Portfolio")).toBeInTheDocument();
    expect(screen.queryByText("Approvals")).not.toBeInTheDocument();
    expect(screen.queryByText("Admin")).not.toBeInTheDocument();
  });
});
