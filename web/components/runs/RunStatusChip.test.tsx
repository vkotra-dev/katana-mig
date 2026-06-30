import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { RunStatusChip } from "./RunStatusChip";

describe("RunStatusChip", () => {
  it("renders a status chip with the awaiting approval label", () => {
    render(<RunStatusChip status="awaiting_approval" />);

    const chip = screen.getByText("awaiting approval");
    expect(chip).toHaveAttribute("data-status", "awaiting_approval");
    expect(chip.className).toContain("bg-amber-100");
  });

  it("renders a completed chip", () => {
    render(<RunStatusChip status="completed" />);

    expect(screen.getByText("completed")).toHaveClass("bg-emerald-100");
  });
});
