import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ReviewGrid } from "../ReviewGrid";

const props = {
  mappingTables: [
    {
      destinationTableName: "accounts",
      bindings: [
        {
          sourceField: "src_id",
          destinationField: "id",
          bindingType: "direct" as const,
        },
        {
          sourceField: "src_status",
          destinationField: "status_id",
          bindingType: "lookup_fk" as const,
        },
      ],
    },
  ],
  lookupGroups: [
    {
      lookupName: "status_map",
      referenceTableName: "status_ref",
      pairs: [
        {
          sourceValue: "A",
          destinationRow: { id: "ACTIVE", name: "Active" },
          confidenceScore: 0.95,
          status: "confirmed" as const,
        },
      ],
    },
  ],
};

describe("ReviewGrid", () => {
  it("renders mapping tables headers and allows accordion expansion", () => {
    render(<ReviewGrid {...props} />);

    expect(screen.getByText("accounts")).toBeInTheDocument();
    expect(screen.queryByText("src_id")).not.toBeInTheDocument(); // Hidden initially

    fireEvent.click(screen.getByRole("button", { name: /accounts/ }));
    expect(screen.getByText("src_id")).toBeInTheDocument();
    expect(screen.getByText("status_id")).toBeInTheDocument();
  });

  it("renders lookup mapping groups and confidence scores", () => {
    render(<ReviewGrid {...props} />);

    expect(screen.getByText("status_map")).toBeInTheDocument();
    expect(screen.getByText("status_ref")).toBeInTheDocument();
    expect(screen.getByText("A")).toBeInTheDocument();
    expect(screen.getByText(/ACTIVE/)).toBeInTheDocument();
    expect(screen.getByText("95%")).toBeInTheDocument();
  });

  it("handles conditional approval and revision request workflows", () => {
    const onApprove = vi.fn();
    const onRequestRevision = vi.fn();

    render(
      <ReviewGrid
        {...props}
        onApprove={onApprove}
        onRequestRevision={onRequestRevision}
      />
    );

    fireEvent.click(screen.getByRole("button", { name: "Approve" }));
    expect(onApprove).toHaveBeenCalled();

    fireEvent.click(screen.getByRole("button", { name: "Request Revision" }));
    const textarea = screen.getByPlaceholderText(/Describe what needs to be changed/i);
    expect(textarea).toBeInTheDocument();

    fireEvent.change(textarea, { target: { value: "Please verify status A mappings" } });
    fireEvent.click(screen.getByRole("button", { name: "Submit Revision Request" }));

    expect(onRequestRevision).toHaveBeenCalledWith("Please verify status A mappings");
  });
});
