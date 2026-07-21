import { render, screen, fireEvent } from "@testing-library/react";
import { Dialog } from "../Dialog";

describe("Dialog", () => {
  it("renders children when open", () => {
    render(
      <Dialog open={true} onClose={() => {}} title="Test Dialog">
        <div data-testid="child">Hello</div>
      </Dialog>
    );
    expect(screen.getByTestId("child")).toBeInTheDocument();
  });

  it("renders nothing when closed", () => {
    render(
      <Dialog open={false} onClose={() => {}}>
        <div data-testid="child">Hello</div>
      </Dialog>
    );
    expect(screen.queryByTestId("child")).not.toBeInTheDocument();
  });

  it("calls onClose when Escape is pressed", () => {
    const handleClose = vi.fn();
    render(
      <Dialog open={true} onClose={handleClose}>
        <div>Hello</div>
      </Dialog>
    );
    fireEvent.keyDown(document, { key: "Escape", code: "Escape" });
    expect(handleClose).toHaveBeenCalledTimes(1);
  });

  it("does not call onClose when clicking outside", () => {
    const handleClose = vi.fn();
    render(
      <Dialog open={true} onClose={handleClose} title="Test">
        <div>Hello</div>
      </Dialog>
    );
    
    // Click backdrop
    const dialog = screen.getByRole("dialog");
    fireEvent.click(dialog);
    expect(handleClose).not.toHaveBeenCalled();
    
    // Click container
    fireEvent.click(screen.getByText("Hello"));
    expect(handleClose).not.toHaveBeenCalled();
  });
  
  it("has proper ARIA attributes", () => {
    render(
      <Dialog open={true} onClose={() => {}} title="My Dialog">
        <div>Hello</div>
      </Dialog>
    );
    const dialog = screen.getByRole("dialog");
    expect(dialog).toHaveAttribute("aria-modal", "true");
    expect(dialog).toHaveAttribute("aria-label", "My Dialog");
  });
});
