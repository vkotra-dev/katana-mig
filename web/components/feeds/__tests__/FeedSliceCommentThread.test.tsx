import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { FeedSliceCommentThread } from "../FeedSliceCommentThread";

const { listFeedSliceCommentsMock, createFeedSliceCommentMock } = vi.hoisted(() => ({
  listFeedSliceCommentsMock: vi.fn(),
  createFeedSliceCommentMock: vi.fn(),
}));

vi.mock("../../../lib/feed-slice-comments-api", () => ({
  listFeedSliceComments: listFeedSliceCommentsMock,
  createFeedSliceComment: createFeedSliceCommentMock,
}));

const mockComment = {
  commentId: "comment-1",
  sourceSliceId: "slice-123",
  userId: "user-1",
  displayName: "Janet Smith",
  role: "project_stakeholder",
  body: "Slice looks good but needs date formatting corrections.",
  createdAt: "2026-07-01T10:00:00Z",
};

describe("FeedSliceCommentThread", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    listFeedSliceCommentsMock.mockResolvedValue([mockComment]);
    createFeedSliceCommentMock.mockResolvedValue({
      ...mockComment,
      commentId: "comment-2",
      body: "New comment from test",
    });
  });

  it("renders the section heading", async () => {
    render(<FeedSliceCommentThread feedId="feed-abc" projectId="project-1" sliceId="slice-123" token="tok" />);

    expect(await screen.findByRole("heading", { name: /slice comments/i })).toBeInTheDocument();
  });

  it("loads and displays comments on mount", async () => {
    render(<FeedSliceCommentThread feedId="feed-abc" projectId="project-1" sliceId="slice-123" token="tok" />);

    expect(await screen.findByText("Slice looks good but needs date formatting corrections.")).toBeInTheDocument();
    expect(screen.getByText("Janet Smith")).toBeInTheDocument();
    expect(screen.getByText("project_stakeholder")).toBeInTheDocument();

    expect(listFeedSliceCommentsMock).toHaveBeenCalledWith("tok", "project-1", "feed-abc", "slice-123");
  });

  it("shows empty-state message when no comments exist", async () => {
    listFeedSliceCommentsMock.mockResolvedValue([]);

    render(<FeedSliceCommentThread feedId="feed-abc" projectId="project-1" sliceId="slice-123" token="tok" />);

    expect(await screen.findByText(/no comments yet/i)).toBeInTheDocument();
  });

  it("renders the text area and submit button", async () => {
    render(<FeedSliceCommentThread feedId="feed-abc" projectId="project-1" sliceId="slice-123" token="tok" />);

    await screen.findByText("Slice looks good but needs date formatting corrections.");

    expect(screen.getByPlaceholderText(/add a comment/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /add comment/i })).toBeInTheDocument();
  });

  it("submits a new comment and refreshes the list", async () => {
    listFeedSliceCommentsMock
      .mockResolvedValueOnce([mockComment])
      .mockResolvedValueOnce([
        mockComment,
        { ...mockComment, commentId: "comment-2", body: "New comment from test" },
      ]);

    render(<FeedSliceCommentThread feedId="feed-abc" projectId="project-1" sliceId="slice-123" token="tok" />);

    await screen.findByText("Slice looks good but needs date formatting corrections.");

    fireEvent.change(screen.getByPlaceholderText(/add a comment/i), {
      target: { value: "New comment from test" },
    });
    fireEvent.click(screen.getByRole("button", { name: /add comment/i }));

    await waitFor(() => {
      expect(createFeedSliceCommentMock).toHaveBeenCalledWith(
        "tok",
        "project-1",
        "feed-abc",
        "slice-123",
        "New comment from test",
      );
    });

    expect(await screen.findByText("New comment from test")).toBeInTheDocument();
    expect(listFeedSliceCommentsMock).toHaveBeenCalledTimes(2);
  });

  it("clears the textarea after a successful submit", async () => {
    render(<FeedSliceCommentThread feedId="feed-abc" projectId="project-1" sliceId="slice-123" token="tok" />);

    await screen.findByText("Slice looks good but needs date formatting corrections.");

    const textarea = screen.getByPlaceholderText(/add a comment/i);
    fireEvent.change(textarea, { target: { value: "Will be cleared" } });
    fireEvent.click(screen.getByRole("button", { name: /add comment/i }));

    await waitFor(() => expect(createFeedSliceCommentMock).toHaveBeenCalled());

    expect(textarea).toHaveValue("");
  });

  it("disables submit button when textarea is empty", async () => {
    render(<FeedSliceCommentThread feedId="feed-abc" projectId="project-1" sliceId="slice-123" token="tok" />);

    await screen.findByText("Slice looks good but needs date formatting corrections.");

    expect(screen.getByRole("button", { name: /add comment/i })).toBeDisabled();
  });

  it("shows an error message if listFeedSliceComments fails", async () => {
    listFeedSliceCommentsMock.mockRejectedValue(new Error("Network error"));

    render(<FeedSliceCommentThread feedId="feed-abc" projectId="project-1" sliceId="slice-123" token="tok" />);

    expect(await screen.findByRole("alert")).toBeInTheDocument();
    expect(screen.getByRole("alert")).toHaveTextContent(/unable to load slice comments/i);
  });
});
