import { render, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import AdminHomePage from "./page";

const { replaceMock } = vi.hoisted(() => ({
  replaceMock: vi.fn(),
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({
    replace: replaceMock,
  }),
}));

describe("AdminHomePage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("redirects to the admin users page", async () => {
    render(<AdminHomePage />);

    await waitFor(() => expect(replaceMock).toHaveBeenCalledWith("/admin/users"));
  });
});
