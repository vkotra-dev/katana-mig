import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { StageTimeline } from "./StageTimeline";

describe("StageTimeline", () => {
  it("renders the lifecycle stepper for a running project", () => {
    render(
      <StageTimeline
        latestRunSummary={{
          currentStage: "implementation",
          runStatus: "running",
          sourceType: "csv",
          stageEnteredAt: "2026-06-29T00:00:00Z",
        }}
      />,
    );

    expect(screen.getByText("Lifecycle timeline")).toBeInTheDocument();
    expect(screen.getByText("Implementation", { selector: "p span" })).toBeInTheDocument();
    expect(screen.getByText("Current stage:", { selector: "p" })).toBeInTheDocument();
  });

  it("shows the empty state when no run summary exists", () => {
    render(<StageTimeline latestRunSummary={null} />);

    expect(screen.getByText("No runs have started for this project yet.")).toBeInTheDocument();
  });
});
