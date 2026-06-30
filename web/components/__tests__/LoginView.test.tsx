import { render, screen } from "@testing-library/react";
import { LoginView } from "../LoginView";

describe("LoginView", () => {
  it("renders a credential form without demo account shortcuts", () => {
    render(<LoginView onSubmit={() => undefined} />);
    expect(screen.getByText("Katana Console")).toBeInTheDocument();
    expect(screen.getByPlaceholderText("operator@katana.io")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Log in" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Forgot password?" })).toHaveAttribute(
      "href",
      "/auth/password-reset"
    );
    expect(screen.queryByText("First-run Admin Seed Wizard")).not.toBeInTheDocument();
  });

  it("shows auth errors and loading state", () => {
    render(<LoginView errorMessage="Invalid credentials" loading onSubmit={() => undefined} />);

    expect(screen.getByText("Invalid credentials")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Logging in..." })).toBeDisabled();
  });
});
