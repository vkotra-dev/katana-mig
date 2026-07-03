import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { FeedCommentThread } from "../FeedCommentThread";

const { listFeedCommentsMock, createFeedCommentMock } = vi.hoisted(() => ({
  listFeedCommentsMock: vi.fn(),
  createFeedCommentMock: vi.fn(),
}));

vi.mock("../../../lib/feeds-api", () => ({
  listFeedComments: listFeedCommentsMock,
  createFeedComment: createFeedCommentMock,
}));

const mockComment = {
  commentId: "comment-1",
  feedId: "feed-abc",
  userId: "user-1",
  displayName: "Janet Smith",
  role: "project_stakeholder",
  body: "ACCT_TYPE value RETD should map to Retired.",
  createdAt: "2026-07-01T10:00:00Z",
};

describe("FeedCommentThread", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    listFeedCommentsMock.mockResolvedValue([mockComment]);
    createFeedCommentMock.mockResolvedValue({
      ...mockComment,
      commentId: "comment-2",
      body: "New comment from test",
    });
  });

  it("renders the section heading", async () => {
    render(<FeedCommentThread feedId="feed-abc" projectId="project-1" token="tok" />);

    expect(await screen.findByRole("heading", { name: /comments/i })).toBeInTheDocument();
  });

  it("loads and displays comments on mount", async () => {
    render(<FeedCommentThread feedId="feed-abc" projectId="project-1" token="tok" />);

    expect(await screen.findByText("ACCT_TYPE value RETD should map to Retired.")).toBeInTheDocument();
    expect(screen.getByText("Janet Smith")).toBeInTheDocument();
    expect(screen.getByText("project_stakeholder")).toBeInTheDocument();

    expect(listFeedCommentsMock).toHaveBeenCalledWith("tok", "project-1", "feed-abc");
  });

  it("shows empty-state message when no comments exist", async () => {
    listFeedCommentsMock.mockResolvedValue([]);

    render(<FeedCommentThread feedId="feed-abc" projectId="project-1" token="tok" />);

    expect(await screen.findByText(/no comments yet/i)).toBeInTheDocument();
  });

  it("renders the text area and submit button", async () => {
    render(<FeedCommentThread feedId="feed-abc" projectId="project-1" token="tok" />);

    await screen.findByText("ACCT_TYPE value RETD should map to Retired.");

    expect(screen.getByPlaceholderText(/add a comment/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /add comment/i })).toBeInTheDocument();
  });

  it("submits a new comment and refreshes the list", async () => {
    listFeedCommentsMock
      .mockResolvedValueOnce([mockComment])
      .mockResolvedValueOnce([
        mockComment,
        { ...mockComment, commentId: "comment-2", body: "New comment from test" },
      ]);

    render(<FeedCommentThread feedId="feed-abc" projectId="project-1" token="tok" />);

    await screen.findByText("ACCT_TYPE value RETD should map to Retired.");

    fireEvent.change(screen.getByPlaceholderText(/add a comment/i), {
      target: { value: "New comment from test" },
    });
    fireEvent.click(screen.getByRole("button", { name: /add comment/i }));

    await waitFor(() => {
      expect(createFeedCommentMock).toHaveBeenCalledWith(
        "tok",
        "project-1",
        "feed-abc",
        "New comment from test",
      );
    });

    expect(await screen.findByText("New comment from test")).toBeInTheDocument();
    expect(listFeedCommentsMock).toHaveBeenCalledTimes(2);
  });

  it("clears the textarea after a successful submit", async () => {
    render(<FeedCommentThread feedId="feed-abc" projectId="project-1" token="tok" />);

    await screen.findByText("ACCT_TYPE value RETD should map to Retired.");

    const textarea = screen.getByPlaceholderText(/add a comment/i);
    fireEvent.change(textarea, { target: { value: "Will be cleared" } });
    fireEvent.click(screen.getByRole("button", { name: /add comment/i }));

    await waitFor(() => expect(createFeedCommentMock).toHaveBeenCalled());

    expect(textarea).toHaveValue("");
  });

  it("disables submit button when textarea is empty", async () => {
    render(<FeedCommentThread feedId="feed-abc" projectId="project-1" token="tok" />);

    await screen.findByText("ACCT_TYPE value RETD should map to Retired.");

    expect(screen.getByRole("button", { name: /add comment/i })).toBeDisabled();
  });

  it("shows an error message if listFeedComments fails", async () => {
    listFeedCommentsMock.mockRejectedValue(new Error("Network error"));

    render(<FeedCommentThread feedId="feed-abc" projectId="project-1" token="tok" />);

    expect(await screen.findByRole("alert")).toBeInTheDocument();
    expect(screen.getByRole("alert")).toHaveTextContent(/unable to load comments/i);
  });
});
