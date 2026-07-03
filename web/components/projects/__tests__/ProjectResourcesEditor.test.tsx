import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ProjectResourcesEditor } from "../ProjectResourcesEditor";

describe("ProjectResourcesEditor", () => {
  it("renders without crashing with empty initial value", () => {
    render(<ProjectResourcesEditor value="" onChange={vi.fn()} />);

    expect(screen.getByRole("button", { name: "Bold" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Bullet list" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Center" })).toBeInTheDocument();
  });

  it("renders without crashing with initial HTML content", () => {
    render(
      <ProjectResourcesEditor
        value="<p><strong>PROD</strong></p><ul><li>Host: 10.0.0.1</li></ul>"
        onChange={vi.fn()}
      />,
    );

    expect(screen.getByRole("button", { name: "Bold" })).toBeInTheDocument();
  });
});
