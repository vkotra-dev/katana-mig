import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { AddSourceDialog } from "../AddSourceDialog";

const createFeedContractMock = vi.fn().mockResolvedValue({
  sourceDefinitionId: "source-1",
  projectId: "project-1",
  sourceType: "csv",
  label: "Customer Extract",
  encoding: "utf-8",
  destinationObjectReferences: null,
  layoutInformation: null,
  copybookText: null,
  status: "declared",
  createdAt: "2026-06-30T00:00:00Z",
});

const uploadFeedCopybookMock = vi.fn().mockResolvedValue({
  sourceDefinitionId: "source-1",
  projectId: "project-1",
  sourceType: "fixed_length_file",
  label: "Claims Feed",
  encoding: "utf-8",
  destinationObjectReferences: null,
  layoutInformation: [],
  copybookText: "copybook",
  status: "layout_ready",
  createdAt: "2026-06-30T00:00:00Z",
});

const uploadFeedSliceMock = vi.fn().mockResolvedValue({
  sourceSliceId: "slice-1",
  sourceDefinitionId: "source-1",
  headerCsv: "CUST_ID,SURNAME",
  rowCount: 1,
  status: "pending_approval",
  previewRows: ["100042,***"],
  createdAt: "2026-06-30T00:00:00Z",
});

vi.mock("../../../lib/feeds-api", () => ({
  createFeedContract: (...args: unknown[]) => createFeedContractMock(...args),
  uploadFeedCopybook: (...args: unknown[]) => uploadFeedCopybookMock(...args),
  uploadFeedSlice: (...args: unknown[]) => uploadFeedSliceMock(...args),
}));

describe("AddSourceDialog", () => {
  it("advances through the CSV flow", async () => {
    const onClose = vi.fn();
    const onCreated = vi.fn().mockResolvedValue(undefined);

    render(
      <AddSourceDialog
        open
        onClose={onClose}
        onCreated={onCreated}
        projectId="project-1"
        token="token-1"
      />,
    );

    fireEvent.change(screen.getByLabelText("Label"), { target: { value: "Customer Extract" } });
    fireEvent.click(screen.getByRole("button", { name: /create csv/i }));

    await screen.findByText("Data file");
    expect(createFeedContractMock).toHaveBeenCalledWith("token-1", "project-1", {
      sourceType: "csv",
      label: "Customer Extract",
      encoding: "utf-8",
    });

    const fileInput = screen.getByLabelText("Data file") as HTMLInputElement;
    const csvFile = new File(["CUST_ID,SURNAME\n1,Smith\n"], "source.csv", { type: "text/csv" });
    fireEvent.change(fileInput, { target: { files: [csvFile] } });
    fireEvent.click(screen.getByRole("button", { name: /upload source/i }));

    await waitFor(() => expect(uploadFeedSliceMock).toHaveBeenCalled());
    expect(onCreated).toHaveBeenCalled();
    expect(onClose).toHaveBeenCalled();
  });

  it("adds a copybook step for fixed-length sources", async () => {
    render(
      <AddSourceDialog
        open
        onClose={vi.fn()}
        onCreated={vi.fn().mockResolvedValue(undefined)}
        projectId="project-1"
        token="token-1"
      />,
    );

    fireEvent.change(screen.getByLabelText("Label"), { target: { value: "Claims Feed" } });
    fireEvent.change(screen.getByLabelText("Source type"), { target: { value: "fixed_length_file" } });
    fireEvent.click(screen.getByRole("button", { name: /create fixed-length record/i }));

    await screen.findByText("Copybook file");

    const copybookInput = screen.getByLabelText("Copybook file") as HTMLInputElement;
    const copybookFile = new File(["copybook"], "layout.cpy", { type: "text/plain" });
    fireEvent.change(copybookInput, { target: { files: [copybookFile] } });
    fireEvent.click(screen.getByRole("button", { name: /upload copybook/i }));

    await screen.findByText("Data file");
    expect(uploadFeedCopybookMock).toHaveBeenCalled();
  });
});
