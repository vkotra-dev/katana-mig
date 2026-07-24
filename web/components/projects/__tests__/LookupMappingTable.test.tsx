import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { LookupMappingTable } from "../LookupMappingTable";

const pairs = [
  { sourceValue: "A", destinationRow: { id: "ACTIVE", name: "Active" }, confidenceScore: 0.95, status: "pending" as const, destinationId: "ACTIVE" },
  { sourceValue: "B", destinationRow: { id: "BLOCKED", name: "Blocked" }, confidenceScore: 0.5, status: "pending" as const, destinationId: "BLOCKED" },
  { sourceValue: "C", destinationRow: null, confidenceScore: 0.2, status: "rejected" as const, destinationId: undefined },
];

const destinationRows = [
  { id: "ACTIVE", name: "Active" },
  { id: "BLOCKED", name: "Blocked" },
];

describe("LookupMappingTable", () => {
  it("renders destination values with ID formatting", () => {
    render(<LookupMappingTable pairs={pairs} destinationRows={destinationRows} />);

    // Destination values appear with label+ID
    expect(screen.getByText(/Active/)).toBeInTheDocument();
    expect(screen.getByText(/ACTIVE/)).toBeInTheDocument();
    expect(screen.getByText(/Blocked/)).toBeInTheDocument();
    expect(screen.getByText(/BLOCKED/)).toBeInTheDocument();
  });

  it("renders source values in row-per-pair table", () => {
    render(<LookupMappingTable pairs={pairs} destinationRows={destinationRows} />);

    expect(screen.getByText("A")).toBeInTheDocument();
    expect(screen.getByText("B")).toBeInTheDocument();
    expect(screen.getByText("C")).toBeInTheDocument();
  });

  it("renders status badges from pair status", () => {
    render(<LookupMappingTable pairs={pairs} destinationRows={destinationRows} />);

    // All pairs have "pending" status
    const pendingEls = screen.getAllByText(/Pending/);
    expect(pendingEls.length).toBeGreaterThanOrEqual(1);
    // C has "rejected" status
    const rejectedEls = screen.getAllByText(/Rejected/);
    expect(rejectedEls.length).toBeGreaterThanOrEqual(1);
  });

  it("handles empty pairs", () => {
    render(<LookupMappingTable pairs={[]} destinationRows={[]} />);

    expect(screen.getByText("No mappings yet.")).toBeInTheDocument();
  });

  it("renders each pair as a separate row", () => {
    render(<LookupMappingTable pairs={pairs} destinationRows={destinationRows} />);

    // Each pair renders as a row — 3 pairs = 3 data rows
    const table = document.querySelector("table");
    const rows = table?.querySelectorAll("tbody tr");
    expect(rows?.length).toBe(3);
  });

  it("displays destination label+ID when available", () => {
    const { container } = render(<LookupMappingTable pairs={pairs} destinationRows={destinationRows} />);
    const table = container.querySelector("table");
    const textContent = table?.textContent || "";
    // ACTIVE and BLOCKED have labels in destinationRows
    expect(textContent).toContain("Active");
    expect(textContent).toContain("ACTIVE");
    expect(textContent).toContain("Blocked");
    expect(textContent).toContain("BLOCKED");
  });
});
