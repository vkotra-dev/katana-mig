import { render, screen } from "@testing-library/react";
import { Topbar } from "../Topbar";

describe("Topbar", () => {
  it("renders the Katana brand and role-aware navigation", () => {
    render(<Topbar role="central_team" />);
    expect(screen.getByText("Katana")).toBeInTheDocument();
    expect(screen.getByText("Portfolio")).toBeInTheDocument();
    expect(screen.getByText("Admin")).toBeInTheDocument();
    expect(screen.queryByLabelText("Search")).not.toBeInTheDocument();
  });

  it("hides admin and approvals for read-only auditors", () => {
    render(<Topbar role="read_only_auditor" />);

    expect(screen.getByText("Portfolio")).toBeInTheDocument();
    expect(screen.getByText("Projects")).toBeInTheDocument();
    expect(screen.queryByText("Approvals")).not.toBeInTheDocument();
    expect(screen.queryByText("Admin")).not.toBeInTheDocument();
  });
});
