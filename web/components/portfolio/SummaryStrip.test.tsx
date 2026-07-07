import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { SummaryStrip } from "./SummaryStrip";

describe("SummaryStrip", () => {
  it("renders the five summary cards", () => {
    render(<SummaryStrip active={4} archived={2} total={6} needsAttention={1} pendingReview={3} />);

    expect(screen.getByText("6")).toBeInTheDocument();
    expect(screen.getByText("4")).toBeInTheDocument();
    expect(screen.getByText("2")).toBeInTheDocument();
    expect(screen.getByText("1")).toBeInTheDocument();
    expect(screen.getByText("3")).toBeInTheDocument();
    expect(screen.getByText("Total Projects")).toBeInTheDocument();
    expect(screen.getByText("Active")).toBeInTheDocument();
    expect(screen.getByText("Needs Attention")).toBeInTheDocument();
    expect(screen.getByText("Pending Review")).toBeInTheDocument();
    expect(screen.getByText("Archived")).toBeInTheDocument();
  });
});
