"use client";

import { useState, type FormEvent } from "react";
import {
  createFeedContract,
  type FeedContractRecord,
  type FeedType,
  uploadFeedCopybook,
  uploadFeedSlice,
} from "../../lib/feeds-api";

type DialogStep = "declare" | "copybook" | "upload";

export interface AddSourceDialogProps {
  projectId: string;
  token: string;
  open: boolean;
  onClose: () => void;
  onCreated: () => Promise<void> | void;
}

function sourceTypeLabel(sourceType: FeedType): string {
  return sourceType === "csv" ? "CSV" : "Fixed-Length Record";
}

async function readFileAsText(file: File): Promise<string> {
  return await new Promise<string>((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result ?? ""));
    reader.onerror = () => reject(reader.error ?? new Error("Unable to read file."));
    reader.readAsText(file);
  });
}

export function AddSourceDialog({
  projectId,
  token,
  open,
  onClose,
  onCreated,
}: AddSourceDialogProps) {
  const [step, setStep] = useState<DialogStep>("declare");
  const [sourceType, setSourceType] = useState<FeedType>("csv");
  const [label, setLabel] = useState("");
  const [encoding, setEncoding] = useState("utf-8");
  const [source, setSource] = useState<FeedContractRecord | null>(null);
  const [loading, setLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  if (!open) {
    return null;
  }

  const reset = () => {
    setStep("declare");
    setSourceType("csv");
    setLabel("");
    setEncoding("utf-8");
    setSource(null);
    setLoading(false);
    setErrorMessage(null);
  };

  const close = () => {
    reset();
    onClose();
  };

  const submitDeclare = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setLoading(true);
    setErrorMessage(null);
    try {
      const created = await createFeedContract(token, projectId, {
        sourceType,
        label,
        encoding,
      });
      setSource(created);
      setStep(sourceType === "csv" ? "upload" : "copybook");
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Unable to create source contract.");
    } finally {
      setLoading(false);
    }
  };

  const submitCopybook = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!source) {
      return;
    }
    const form = new FormData(event.currentTarget);
    const file = form.get("copybook") as File | null;
    if (!file) {
      setErrorMessage("Choose a copybook file.");
      return;
    }
    setLoading(true);
    setErrorMessage(null);
    try {
      const content = await readFileAsText(file);
      const updated = await uploadFeedCopybook(token, projectId, source.sourceDefinitionId, { content });
      setSource(updated);
      setStep("upload");
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Unable to upload copybook.");
    } finally {
      setLoading(false);
    }
  };

  const submitUpload = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!source) {
      return;
    }
    const form = new FormData(event.currentTarget);
    const file = form.get("sourceFile") as File | null;
    if (!file) {
      setErrorMessage("Choose a data file.");
      return;
    }
    setLoading(true);
    setErrorMessage(null);
    try {
      const content = await readFileAsText(file);
      await uploadFeedSlice(token, projectId, source.sourceDefinitionId, { content });
      await onCreated();
      close();
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Unable to upload source data.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/50 px-4 py-8">
      <div className="max-h-[90vh] w-full max-w-2xl overflow-y-auto rounded-2xl border border-outline-variant bg-surface-container p-6 shadow-2xl">
        <div className="flex items-start justify-between gap-4">
          <div>
            <h2 className="text-2xl font-semibold text-slate-900">Add source</h2>
            <p className="text-sm text-slate-600">
              {step === "declare"
                ? "Declare the source contract first."
                : step === "copybook"
                  ? "Upload the fixed-length copybook."
                  : "Upload the source data file."}
            </p>
          </div>
          <button
            className="rounded-md border border-outline-variant px-3 py-2 text-sm text-slate-700"
            onClick={close}
            type="button"
          >
            Close
          </button>
        </div>

        <div className="mt-4 flex gap-2 text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">
          <span className={step === "declare" ? "text-slate-900" : ""}>1. Declare</span>
          <span>•</span>
          <span className={step === "copybook" ? "text-slate-900" : ""}>2. Layout</span>
          <span>•</span>
          <span className={step === "upload" ? "text-slate-900" : ""}>3. Upload</span>
        </div>

        {step === "declare" ? (
          <form className="mt-6 space-y-4" onSubmit={submitDeclare}>
            <div className="space-y-2">
              <label
                className="block text-xs font-semibold uppercase tracking-[0.16em] text-slate-500"
                htmlFor="source-label"
              >
                Label
              </label>
              <input
                className="w-full rounded-md border border-outline-variant bg-white px-3 py-3 text-sm text-slate-900"
                id="source-label"
                name="label"
                onChange={(event) => setLabel(event.currentTarget.value)}
                required
                value={label}
              />
            </div>

            <div className="grid gap-4 sm:grid-cols-2">
              <div className="space-y-2">
                <label
                  className="block text-xs font-semibold uppercase tracking-[0.16em] text-slate-500"
                  htmlFor="source-type"
                >
                  Source type
                </label>
                <select
                  className="w-full rounded-md border border-outline-variant bg-white px-3 py-3 text-sm text-slate-900"
                  id="source-type"
                  name="sourceType"
                  onChange={(event) => setSourceType(event.currentTarget.value as FeedType)}
                  value={sourceType}
                >
                  <option value="csv">CSV</option>
                  <option value="fixed_length_file">Fixed-Length Record</option>
                </select>
              </div>

              <div className="space-y-2">
                <label
                  className="block text-xs font-semibold uppercase tracking-[0.16em] text-slate-500"
                  htmlFor="source-encoding"
                >
                  Encoding
                </label>
                <select
                  className="w-full rounded-md border border-outline-variant bg-white px-3 py-3 text-sm text-slate-900"
                  id="source-encoding"
                  name="encoding"
                  onChange={(event) => setEncoding(event.currentTarget.value)}
                  value={encoding}
                >
                  <option value="utf-8">utf-8</option>
                  <option value="latin-1">latin-1</option>
                  <option value="cp1252">cp1252</option>
                </select>
              </div>
            </div>

            {errorMessage ? (
              <p className="rounded-md border border-error/30 bg-error/10 px-3 py-2 text-sm text-error" role="alert">
                {errorMessage}
              </p>
            ) : null}

            <div className="flex justify-end">
              <button
                className="rounded-md bg-primary px-4 py-3 text-sm font-semibold text-white disabled:opacity-60"
                disabled={loading}
                type="submit"
              >
                {loading ? "Creating..." : `Create ${sourceTypeLabel(sourceType)}`}
              </button>
            </div>
          </form>
        ) : null}

        {step === "copybook" ? (
          <form className="mt-6 space-y-4" onSubmit={submitCopybook}>
            <div className="space-y-2">
              <label
                className="block text-xs font-semibold uppercase tracking-[0.16em] text-slate-500"
                htmlFor="copybook-file"
              >
                Copybook file
              </label>
              <input
                accept=".cpy,.txt,.cob"
                className="w-full rounded-md border border-outline-variant bg-white px-3 py-3 text-sm text-slate-900"
                id="copybook-file"
                name="copybook"
                type="file"
              />
            </div>

            {errorMessage ? (
              <p className="rounded-md border border-error/30 bg-error/10 px-3 py-2 text-sm text-error" role="alert">
                {errorMessage}
              </p>
            ) : null}

            <div className="flex justify-end gap-3">
              <button
                className="rounded-md border border-outline-variant px-4 py-3 text-sm font-semibold text-slate-700"
                onClick={() => setStep("declare")}
                type="button"
              >
                Back
              </button>
              <button
                className="rounded-md bg-primary px-4 py-3 text-sm font-semibold text-white disabled:opacity-60"
                disabled={loading}
                type="submit"
              >
                {loading ? "Uploading..." : "Upload copybook"}
              </button>
            </div>
          </form>
        ) : null}

        {step === "upload" ? (
          <form className="mt-6 space-y-4" onSubmit={submitUpload}>
            <div className="space-y-2">
              <label
                className="block text-xs font-semibold uppercase tracking-[0.16em] text-slate-500"
                htmlFor="source-data-file"
              >
                Data file
              </label>
              <input
                accept=".csv,.txt,.dat"
                className="w-full rounded-md border border-outline-variant bg-white px-3 py-3 text-sm text-slate-900"
                id="source-data-file"
                name="sourceFile"
                type="file"
              />
            </div>

            {errorMessage ? (
              <p className="rounded-md border border-error/30 bg-error/10 px-3 py-2 text-sm text-error" role="alert">
                {errorMessage}
              </p>
            ) : null}

            <div className="flex justify-end gap-3">
              <button
                className="rounded-md border border-outline-variant px-4 py-3 text-sm font-semibold text-slate-700"
                onClick={() => {
                  setStep(source?.sourceType === "csv" ? "declare" : "copybook");
                }}
                type="button"
              >
                Back
              </button>
              <button
                className="rounded-md bg-primary px-4 py-3 text-sm font-semibold text-white disabled:opacity-60"
                disabled={loading}
                type="submit"
              >
                {loading ? "Uploading..." : "Upload source"}
              </button>
            </div>
          </form>
        ) : null}
      </div>
    </div>
  );
}
