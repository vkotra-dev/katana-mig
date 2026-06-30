import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import PasswordResetRequestPage from "./page";

const { requestPasswordResetMock } = vi.hoisted(() => ({
  requestPasswordResetMock: vi.fn(),
}));

vi.mock("../../../lib/auth-api", () => ({
  requestPasswordReset: requestPasswordResetMock,
}));

describe("PasswordResetRequestPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    requestPasswordResetMock.mockResolvedValue({ accepted: true });
  });

  it("submits the reset request to the auth API", async () => {
    render(<PasswordResetRequestPage />);

    fireEvent.change(screen.getByPlaceholderText("operator@katana.io"), {
      target: { value: "operator@example.com" },
    });
    fireEvent.submit(screen.getByRole("button", { name: "Send reset link" }).closest("form") as HTMLFormElement);

    await waitFor(() => expect(requestPasswordResetMock).toHaveBeenCalledWith("operator@example.com"));
    await waitFor(() => expect(screen.getByText("If the account is eligible, reset instructions have been sent.")).toBeInTheDocument());
  });
});
