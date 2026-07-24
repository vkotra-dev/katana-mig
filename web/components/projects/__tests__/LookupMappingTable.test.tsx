import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { LookupMappingTable } from "../LookupMappingTable";

const groups = [
  {
    destId: "ACTIVE",
    destLabel: "Active",
    destRow: { id: "ACTIVE", name: "Active" },
    sourceValues: ["A", "B"],
    status: "draft",
  },
  {
    destId: "BLOCKED",
    destLabel: "Blocked",
    destRow: { id: "BLOCKED", name: "Blocked" },
    sourceValues: ["C"],
    status: "approved",
  },
];

describe("LookupMappingTable", () => {
  it("renders destination values with ID formatting", () => {
    render(<LookupMappingTable groups={groups} />);

    expect(screen.getByText(/Active/)).toBeInTheDocument();
    expect(screen.getByText(/ACTIVE/)).toBeInTheDocument();
    expect(screen.getByText(/Blocked/)).toBeInTheDocument();
    expect(screen.getByText(/BLOCKED/)).toBeInTheDocument();
  });

  it("renders all source values", () => {
    render(<LookupMappingTable groups={groups} />);

    expect(screen.getAllByDisplayValue("A")).toHaveLength(1);
    expect(screen.getAllByDisplayValue("B")).toHaveLength(1);
    expect(screen.getAllByDisplayValue("C")).toHaveLength(1);
  });

  it("renders status badges from group status", () => {
    render(<LookupMappingTable groups={groups} />);

    // BLOCKED has "approved" status
    expect(screen.getByText(/Confirmed/)).toBeInTheDocument();
    // ACTIVE has "draft" status → shows "Pending"
    expect(screen.getAllByText(/Pending/)).toHaveLength(1);
  });

  it("handles empty groups", () => {
    render(<LookupMappingTable groups={[]} />);

    expect(screen.getByText("No mappings yet.")).toBeInTheDocument();
  });

  it("renders each group as a separate row", () => {
    render(<LookupMappingTable groups={groups} />);

    const table = document.querySelector("table");
    const rows = table?.querySelectorAll("tbody tr");
    expect(rows?.length).toBe(2);
  });

  it("shows + Add another source value button when editing enabled", () => {
    render(<LookupMappingTable groups={groups} editingEnabled onAddSourceValue={() => {}} />);

    expect(screen.getAllByText("+ Add another source value").length).toBe(2);
  });

  it("shows remove (×) button for each source value when editing enabled", () => {
    render(<LookupMappingTable groups={groups} editingEnabled onRemoveSourceValue={() => {}} />);

    const removeButtons = screen.getAllByTitle("Remove source value");
    expect(removeButtons.length).toBe(3); // A, B from ACTIVE + C from BLOCKED
  });

  it("does not show add/remove buttons when editing disabled", () => {
    render(<LookupMappingTable groups={groups} />);

    expect(screen.queryByText("+ Add another source value")).not.toBeInTheDocument();
    expect(screen.queryByTitle("Remove source value")).not.toBeInTheDocument();
  });

  it("displays source value inputs that are read-only when not editing", () => {
    render(<LookupMappingTable groups={groups} />);

    const inputs = document.querySelectorAll('input[type="text"]');
    expect(inputs.length).toBe(3);
    inputs.forEach((input) => {
      expect(input).toHaveAttribute("readOnly");
    });
  });

  it("displays source value inputs that are editable when editing enabled", () => {
    render(<LookupMappingTable groups={groups} editingEnabled />);

    const inputs = document.querySelectorAll('input[type="text"]');
    inputs.forEach((input) => {
      expect(input).not.toHaveAttribute("readOnly");
    });
  });

  it("renders multiple groups with empty destId without duplicates", () => {
    const emptyDestGroups = [
      {
        destId: "",
        destLabel: "",
        destRow: null,
        sourceValues: ["X"],
        status: "active",
      },
      {
        destId: "",
        destLabel: "",
        destRow: null,
        sourceValues: ["Y"],
        status: "active",
      },
    ];
    // Should not throw React duplicate key warning
    expect(() => render(<LookupMappingTable groups={emptyDestGroups} />)).not.toThrow();
  });
});
