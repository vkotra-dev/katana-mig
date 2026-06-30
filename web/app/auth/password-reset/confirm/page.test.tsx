import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import PasswordResetConfirmPage from "./page";

const { confirmPasswordResetMock } = vi.hoisted(() => ({
  confirmPasswordResetMock: vi.fn(),
}));

vi.mock("../../../../lib/auth-api", () => ({
  confirmPasswordReset: confirmPasswordResetMock,
}));

describe("PasswordResetConfirmPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    confirmPasswordResetMock.mockResolvedValue(undefined);
  });

  it("submits the reset token and new password to the auth API", async () => {
    render(<PasswordResetConfirmPage />);

    fireEvent.change(screen.getByPlaceholderText("Opaque reset token"), {
      target: { value: "reset-token-123" },
    });
    fireEvent.change(screen.getByPlaceholderText("New password"), {
      target: { value: "new-secret-123" },
    });
    fireEvent.submit(screen.getByRole("button", { name: "Reset password" }).closest("form") as HTMLFormElement);

    await waitFor(() => expect(confirmPasswordResetMock).toHaveBeenCalledWith("reset-token-123", "new-secret-123"));
    await waitFor(() => expect(screen.getByText("Password reset complete. You can return to sign in now.")).toBeInTheDocument());
  });
});
