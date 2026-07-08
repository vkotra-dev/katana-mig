import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ProjectNavigationTabs } from "../ProjectNavigationTabs";

const { routerPushMock } = vi.hoisted(() => ({
  routerPushMock: vi.fn(),
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: routerPushMock }),
}));

describe("ProjectNavigationTabs", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("pushes to codegen from the project detail tab row", () => {
    render(<ProjectNavigationTabs activeTab="overview" mode="detail" onTabChange={vi.fn()} projectId="proj-1" />);

    fireEvent.click(screen.getByRole("button", { name: "SQL Bundle" }));
    expect(routerPushMock).toHaveBeenCalledWith("/projects/proj-1/codegen");
  });

  it("marks SQL Bundle active on the codegen tab row", () => {
    render(<ProjectNavigationTabs activeTab="sql-bundle" mode="codegen" projectId="proj-1" />);

    expect(screen.getByRole("button", { name: "SQL Bundle" })).toHaveClass("bg-primary");
  });

  it("renders Feeds tab button and invokes onTabChange", () => {
    const onTabChange = vi.fn();
    render(<ProjectNavigationTabs activeTab="overview" mode="detail" onTabChange={onTabChange} projectId="proj-1" />);

    const feedsTab = screen.getByRole("button", { name: "Feeds" });
    expect(feedsTab).toBeInTheDocument();
    fireEvent.click(feedsTab);
    expect(onTabChange).toHaveBeenCalledWith("feeds");
  });

  it("shows Members tab only for pm role", () => {
    const { rerender } = render(
      <ProjectNavigationTabs activeTab="overview" mode="detail" onTabChange={vi.fn()} projectId="proj-1" role="pm" />,
    );
    expect(screen.getByRole("button", { name: "Members" })).toBeInTheDocument();

    rerender(
      <ProjectNavigationTabs activeTab="overview" mode="detail" onTabChange={vi.fn()} projectId="proj-1" role="central_team" />,
    );
    expect(screen.queryByRole("button", { name: "Members" })).not.toBeInTheDocument();
  });

  it("invokes onTabChange with members when Members tab is clicked by pm", () => {
    const onTabChange = vi.fn();
    render(
      <ProjectNavigationTabs activeTab="overview" mode="detail" onTabChange={onTabChange} projectId="proj-1" role="pm" />,
    );
    fireEvent.click(screen.getByRole("button", { name: "Members" }));
    expect(onTabChange).toHaveBeenCalledWith("members");
  });
});
