"use client";

import { useState } from "react";
import { PasswordResetConfirmView } from "../../../../components/PasswordResetConfirmView";
import { confirmPasswordReset } from "../../../../lib/auth-api";

export default function PasswordResetConfirmPage() {
  const [loading, setLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | undefined>();
  const [successMessage, setSuccessMessage] = useState<string | undefined>();

  const handleSubmit = async (resetToken: string, newPassword: string) => {
    setLoading(true);
    setErrorMessage(undefined);

    try {
      await confirmPasswordReset(resetToken, newPassword);
      setSuccessMessage("Password reset complete. You can return to sign in now.");
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Unable to confirm reset.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="flex min-h-screen items-center justify-center bg-surface px-6 py-12 text-slate-800">
      <PasswordResetConfirmView
        errorMessage={errorMessage}
        loading={loading}
        onSubmit={handleSubmit}
        successMessage={successMessage}
      />
    </main>
  );
}
