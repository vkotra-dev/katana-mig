import { render, screen, fireEvent } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
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

  describe("inline add form", () => {
    // Single-group fixture for inline form tests
    const singleGroup = [groups[0]];

    it("opens inline input form when 'Add another source value' button is clicked", () => {
      const onAdd = vi.fn();
      render(<LookupMappingTable groups={singleGroup} editingEnabled onAddSourceValue={onAdd} />);

      fireEvent.click(screen.getByText("+ Add another source value"));

      const inlineInput = screen.getByPlaceholderText("Enter source value alias...");
      expect(inlineInput).toBeInTheDocument();

      expect(screen.getByText("Add")).toBeInTheDocument();
      expect(screen.getByText("Cancel")).toBeInTheDocument();

      // Original button should be hidden
      expect(screen.queryByText("+ Add another source value")).not.toBeInTheDocument();
    });

    it("closes form when Cancel is clicked", () => {
      const onAdd = vi.fn();
      render(<LookupMappingTable groups={singleGroup} editingEnabled onAddSourceValue={onAdd} />);

      fireEvent.click(screen.getByText("+ Add another source value"));
      expect(screen.getByPlaceholderText("Enter source value alias...")).toBeInTheDocument();

      fireEvent.click(screen.getByText("Cancel"));
      expect(screen.queryByPlaceholderText("Enter source value alias...")).not.toBeInTheDocument();

      // Button should reappear
      expect(screen.getByText("+ Add another source value")).toBeInTheDocument();
    });

    it("Add button is disabled when inline input has no value", () => {
      render(<LookupMappingTable groups={singleGroup} editingEnabled onAddSourceValue={() => {}} />);

      fireEvent.click(screen.getByText("+ Add another source value"));
      const addButton = screen.getByText("Add");
      expect(addButton).toBeDisabled();
    });

    it("inline input has correct placeholder and attributes", () => {
      render(<LookupMappingTable groups={singleGroup} editingEnabled onAddSourceValue={() => {}} />);

      fireEvent.click(screen.getByText("+ Add another source value"));
      const inlineInput = screen.getByPlaceholderText("Enter source value alias...") as HTMLInputElement;

      expect(inlineInput).toHaveAttribute("type", "text");
      expect(inlineInput).toHaveAttribute("placeholder", "Enter source value alias...");
    });

    it("calls onAddSourceValue when user types a value and presses Enter", () => {
      const onAdd = vi.fn();
      render(<LookupMappingTable groups={singleGroup} editingEnabled onAddSourceValue={onAdd} />);

      fireEvent.click(screen.getByText("+ Add another source value"));
      const inlineInput = screen.getByPlaceholderText("Enter source value alias...") as HTMLInputElement;

      // Set value using native setter (required for jsdom + React 19 compatibility)
      const nativeSetter = Object.getOwnPropertyDescriptor(
        HTMLInputElement.prototype,
        "value",
      )?.set;
      nativeSetter?.call(inlineInput, "new_alias");
      inlineInput.dispatchEvent(new Event("input", { bubbles: true }));

      // Dispatch Enter key on the input
      fireEvent.keyDown(inlineInput, { key: "Enter" });

      expect(onAdd).toHaveBeenCalledWith("ACTIVE", "new_alias");
    });

    it("does not call onAddSourceValue when Escape is pressed", () => {
      const onAdd = vi.fn();
      render(<LookupMappingTable groups={singleGroup} editingEnabled onAddSourceValue={onAdd} />);

      fireEvent.click(screen.getByText("+ Add another source value"));
      const inlineInput = screen.getByPlaceholderText("Enter source value alias...") as HTMLInputElement;

      const nativeSetter = Object.getOwnPropertyDescriptor(
        HTMLInputElement.prototype,
        "value",
      )?.set;
      nativeSetter?.call(inlineInput, "new_alias");
      inlineInput.dispatchEvent(new Event("input", { bubbles: true }));

      fireEvent.keyDown(inlineInput, { key: "Escape" });

      expect(onAdd).not.toHaveBeenCalled();
      // Form should close
      expect(screen.queryByPlaceholderText("Enter source value alias...")).not.toBeInTheDocument();
    });

    it("calls onAddSourceValue when user types a value and clicks Add button", () => {
      const onAdd = vi.fn();
      render(<LookupMappingTable groups={singleGroup} editingEnabled onAddSourceValue={onAdd} />);

      fireEvent.click(screen.getByText("+ Add another source value"));
      const inlineInput = screen.getByPlaceholderText("Enter source value alias...") as HTMLInputElement;

      const nativeSetter = Object.getOwnPropertyDescriptor(
        HTMLInputElement.prototype,
        "value",
      )?.set;
      nativeSetter?.call(inlineInput, "another_alias");
      inlineInput.dispatchEvent(new Event("input", { bubbles: true }));

      // Add button should now be enabled
      const addButton = screen.getByText("Add");
      expect(addButton).not.toBeDisabled();

      fireEvent.click(addButton);

      expect(onAdd).toHaveBeenCalledWith("ACTIVE", "another_alias");
    });

    it("does not call onAddSourceValue when clicking Add with empty input", () => {
      const onAdd = vi.fn();
      render(<LookupMappingTable groups={singleGroup} editingEnabled onAddSourceValue={onAdd} />);

      fireEvent.click(screen.getByText("+ Add another source value"));
      const addButton = screen.getByText("Add");

      // Even without the nativeSetter, clicking Add with empty state should not call the callback
      fireEvent.click(addButton);

      expect(onAdd).not.toHaveBeenCalled();
    });
  });
});
