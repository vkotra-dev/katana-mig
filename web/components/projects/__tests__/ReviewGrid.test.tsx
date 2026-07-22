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
            id: {
              centralTeam: { signed: true, signedAt: null, userId: null },
              projectStakeholder: { signed: true, signedAt: null, userId: null },
            }
          },
          src_status: {
            status_id: {
              centralTeam: { signed: true, signedAt: null, userId: null },
              projectStakeholder: { signed: true, signedAt: null, userId: null },
            }
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

    expect(onDestinationFieldChange).toHaveBeenCalledWith("accounts", "src_id", "id", "status_id");
  });

  it("shows all destination field options when the picker is opened before typing", () => {
    const testProps = {
      ...props,
      editingEnabled: true,
      onDestinationFieldChange: vi.fn(),
      mappingTables: [
        {
          destinationTableName: "accounts",
          destinationFields: ["id", "status_id", "email_address", "region_code"],
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
    fireEvent.click(screen.getByRole("button", { name: /accounts/ }));

    const input = screen.getByPlaceholderText("destination field...") as HTMLInputElement;
    fireEvent.focus(input);

    expect(screen.getByText("status_id")).toBeInTheDocument();
    expect(screen.getByText("email_address")).toBeInTheDocument();
    expect(screen.getByText("region_code")).toBeInTheDocument();
  });

  it("narrows destination field options once the user types", () => {
    const testProps = {
      ...props,
      editingEnabled: true,
      onDestinationFieldChange: vi.fn(),
      mappingTables: [
        {
          destinationTableName: "accounts",
          destinationFields: ["id", "status_id", "email_address", "region_code"],
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
    fireEvent.click(screen.getByRole("button", { name: /accounts/ }));

    const input = screen.getByPlaceholderText("destination field...") as HTMLInputElement;
    fireEvent.focus(input);
    fireEvent.change(input, { target: { value: "stat" } });

    expect(screen.getByText("status_id")).toBeInTheDocument();
    expect(screen.queryByText("email_address")).not.toBeInTheDocument();
    expect(screen.queryByText("region_code")).not.toBeInTheDocument();
  });

  it("renders per-row 'Map to another destination' buttons for editable bindings with available destinations", () => {
    const onAddBinding = vi.fn();
    const testProps = {
      ...props,
      editingEnabled: true,
      onAddBinding,
      mappingTables: [
        {
          destinationTableName: "accounts",
          destinationFields: ["id", "status_id", "name", "email", "created_at"],
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
    };

    render(<ReviewGrid {...testProps} />);

    // Expand the accounts accordion
    fireEvent.click(screen.getByRole("button", { name: /accounts/ }));

    // Both rows should have a "Map to another destination" button since editing is enabled
    const buttons = screen.getAllByText(/Map to another destination/);
    expect(buttons.length).toBe(2);

    // Click the button on the first row
    fireEvent.click(buttons[0]);
    expect(onAddBinding).toHaveBeenCalledWith("accounts", "src_id", expect.any(Array));

    // Click the button on the second row
    fireEvent.click(buttons[1]);
    expect(onAddBinding).toHaveBeenCalledWith("accounts", "src_status", expect.any(Array));
  });

  it("does not render 'Map to another destination' buttons when editing is disabled", () => {
    const onAddBinding = vi.fn();
    const testProps = {
      ...props,
      editingEnabled: false,
      onAddBinding,
      mappingTables: [
        {
          destinationTableName: "accounts",
          destinationFields: ["id", "name"],
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
    fireEvent.click(screen.getByRole("button", { name: /accounts/ }));

    expect(screen.queryByText(/Map to another destination/)).not.toBeInTheDocument();
  });

  describe("handleAddBinding", () => {
    it("should allow adding a new binding when a row has available alternative destinations", async () => {
      const onAddBinding = vi.fn();
      const testProps = {
        ...props,
        editingEnabled: true,
        onAddBinding,
        onDestinationFieldChange: vi.fn(),
        mappingTables: [
          {
            destinationTableName: "accounts",
            destinationFields: ["id", "status_id", "name", "email", "created_at"],
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

      // Click the "Map to another destination" button on the first row
      const mapButtons = screen.getAllByText(/Map to another destination/);
      fireEvent.click(mapButtons[0]);

      expect(onAddBinding).toHaveBeenCalledWith(
        "accounts",
        "src_id",
        expect.any(Array)
      );
    });

    it("should NOT show 'Map to another destination' button when all destination fields are already used for a source field", async () => {
      const onAddBinding = vi.fn();
      const testProps = {
        ...props,
        editingEnabled: true,
        onAddBinding,
        onDestinationFieldChange: vi.fn(),
        mappingTables: [
          {
            destinationTableName: "accounts",
            destinationFields: ["id", "status_id"],
            bindings: [
              {
                sourceField: "src_id",
                destinationField: "id",
                bindingType: "direct" as const,
              },
              {
                sourceField: "src_id",
                destinationField: "status_id",
                bindingType: "lookup_fk" as const,
              },
            ],
          },
        ],
      };

      render(<ReviewGrid {...testProps} />);

      // Expand the accounts accordion
      fireEvent.click(screen.getByRole("button", { name: /accounts/ }));

      // No rows should have the "Map to another destination" button
      // because src_id already maps to both available destination fields
      const mapButtons = screen.queryAllByText(/Map to another destination/);
      expect(mapButtons).toHaveLength(0);
    });

    it("should NOT show 'Map to another destination' button for signed-off rows", async () => {
      const onAddBinding = vi.fn();
      const testProps = {
        ...props,
        editingEnabled: true,
        onAddBinding,
        onDestinationFieldChange: vi.fn(),
        mappingTables: [
          {
            destinationTableName: "accounts",
            destinationFields: ["id", "name", "email"],
            bindings: [
              {
                sourceField: "src_id",
                destinationField: "id",
                bindingType: "direct" as const,
              },
            ],
          },
        ],
        signOffStatus: {
          complete: true,
          currentBallRole: "central_team",
          bindings: {
            accounts: {
              src_id: {
                id: {
                  centralTeam: { signed: true, signedAt: new Date(), userId: "user1" },
                  projectStakeholder: { signed: true, signedAt: new Date(), userId: "user2" },
                },
              },
            },
          },
          lookups: {},
        } as any,
      };

      render(<ReviewGrid {...testProps} />);

      // Expand the accounts accordion
      fireEvent.click(screen.getByRole("button", { name: /accounts/ }));

      // The "Map to another destination" button should NOT appear for a signed-off row
      const mapButtons = screen.queryAllByText(/Map to another destination/);
      expect(mapButtons).toHaveLength(0);
    });
  });
});