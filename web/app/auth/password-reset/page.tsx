"use client";

import { useState } from "react";
import { PasswordResetRequestView } from "../../../components/PasswordResetRequestView";
import { requestPasswordReset } from "../../../lib/auth-api";

export default function PasswordResetRequestPage() {
  const [loading, setLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | undefined>();
  const [successMessage, setSuccessMessage] = useState<string | undefined>();

  const handleSubmit = async (email: string) => {
    setLoading(true);
    setErrorMessage(undefined);

    try {
      await requestPasswordReset(email);
      setSuccessMessage("If the account is eligible, reset instructions have been sent.");
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Unable to request reset.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="flex min-h-screen items-center justify-center bg-surface px-6 py-12 text-slate-800">
      <PasswordResetRequestView
        errorMessage={errorMessage}
        loading={loading}
        onSubmit={handleSubmit}
        successMessage={successMessage}
      />
    </main>
  );
}
