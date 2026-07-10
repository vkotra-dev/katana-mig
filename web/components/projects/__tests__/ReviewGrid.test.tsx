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
    expect(screen.getByText(/Active/)).toBeInTheDocument();
    expect(screen.getByText("95%")).toBeInTheDocument();
  });

  it("handles conditional approval and revision request workflows", () => {
    const onApprove = vi.fn();
    const onRequestRevision = vi.fn();
    const signOffStatus = {
      complete: true,
      currentBallRole: "project_stakeholder" as const,
      bindings: {
        accounts: {
          src_id: {
            centralTeam: { signed: true, signedAt: null, userId: null },
            projectStakeholder: { signed: true, signedAt: null, userId: null },
          },
          src_status: {
            centralTeam: { signed: true, signedAt: null, userId: null },
            projectStakeholder: { signed: true, signedAt: null, userId: null },
          },
        },
      },
      lookups: {
        status_map: {
          centralTeam: { signed: true, signedAt: null, userId: null },
          projectStakeholder: { signed: true, signedAt: null, userId: null },
        },
      },
    };

    render(
      <ReviewGrid
        {...props}
        onApprove={onApprove}
        onRequestRevision={onRequestRevision}
        signOffStatus={signOffStatus}
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

  it("renders AutocompleteInput and calls onDestinationFieldChange when option is selected", () => {
    const onDestinationFieldChange = vi.fn();
    const testProps = {
      ...props,
      editingEnabled: true,
      onDestinationFieldChange,
      mappingTables: [
        {
          destinationTableName: "accounts",
          destinationFields: ["id", "status_id", "name", "created_at"],
          bindings: [
            {
              sourceField: "src_id",
              destinationField: "id",
              bindingType: "direct" as const,
            },
          ],
        },
      ],
    };

    render(<ReviewGrid {...testProps} />);

    // Expand the accounts accordion
    fireEvent.click(screen.getByRole("button", { name: /accounts/ }));

    // Find the input field
    const input = screen.getByPlaceholderText("destination field...") as HTMLInputElement;
    expect(input).toBeInTheDocument();
    expect(input.value).toBe("id");

    // Click input to open dropdown or type
    fireEvent.focus(input);
    fireEvent.change(input, { target: { value: "stat" } });

    // Find dropdown option "status_id" and click it
    const option = screen.getByText("status_id");
    expect(option).toBeInTheDocument();
    fireEvent.click(option);

    expect(onDestinationFieldChange).toHaveBeenCalledWith("accounts", "src_id", "status_id");
  });
});
