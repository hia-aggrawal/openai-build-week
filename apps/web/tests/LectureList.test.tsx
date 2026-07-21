import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { LectureList } from "@/features/lecture-list/components/LectureList";
import { deleteLecture, getLectures, retryLecture } from "@/lib/api";

vi.mock("@/lib/api", () => ({
  deleteLecture: vi.fn(),
  getLectures: vi.fn(),
  retryLecture: vi.fn(),
}));

beforeEach(() => {
  vi.clearAllMocks();
});

describe("LectureList", () => {
  it("renders summary-only lecture links from the paginated endpoint", async () => {
    vi.mocked(getLectures).mockResolvedValue({
      items: [
        {
          id: "lecture-new",
          title: "Systems and feedback",
          duration_seconds: 125,
          created_at: "2026-07-19T14:00:00Z",
          job_status: "COMPLETED",
        },
        {
          id: "lecture-processing",
          title: "Graph theory",
          duration_seconds: 60,
          created_at: "2026-07-18T14:00:00Z",
          job_status: "PROCESSING",
        },
      ],
      limit: 6,
      offset: 0,
      next_offset: null,
    });
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });

    render(
      <QueryClientProvider client={queryClient}>
        <LectureList />
      </QueryClientProvider>,
    );

    expect(await screen.findByRole("link", { name: /Systems and feedback/ })).toHaveAttribute(
      "href",
      "/lectures/lecture-new",
    );
    expect(screen.getByRole("link", { name: /Graph theory/ })).toHaveAttribute(
      "href",
      "/lectures/lecture-processing",
    );
    expect(screen.getByText("2:05", { exact: false })).toBeVisible();
    expect(getLectures).toHaveBeenCalledWith(6, 0);
  });

  it("invites an empty library to upload its first lecture", async () => {
    vi.mocked(getLectures).mockResolvedValue({
      items: [],
      limit: 6,
      offset: 0,
      next_offset: null,
    });
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });

    render(
      <QueryClientProvider client={queryClient}>
        <LectureList />
      </QueryClientProvider>,
    );

    expect(await screen.findByRole("heading", { name: "No lectures yet" })).toBeVisible();
    expect(screen.getByText(/Use Upload at the top of the page/)).toBeVisible();
    expect(screen.queryByRole("link", { name: /upload/i })).not.toBeInTheDocument();
  });

  it("opens an in-app dialog and supports canceling or confirming deletion", async () => {
    vi.mocked(getLectures).mockResolvedValue({
      items: [
        {
          id: "lecture-delete",
          title: "Delete me",
          duration_seconds: 60,
          created_at: "2026-07-19T14:00:00Z",
          job_status: "COMPLETED",
        },
      ],
      limit: 6,
      offset: 0,
      next_offset: null,
    });
    vi.mocked(deleteLecture).mockResolvedValue();
    const nativeConfirm = vi.spyOn(window, "confirm");
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
    render(
      <QueryClientProvider client={queryClient}>
        <LectureList />
      </QueryClientProvider>,
    );

    fireEvent.click(await screen.findByRole("button", { name: "Delete Delete me" }));

    const dialog = await screen.findByRole("dialog", { name: "Remove this lecture?" });
    expect(dialog).toHaveTextContent("“Delete me”");
    expect(dialog).toHaveTextContent("This action can’t be undone.");
    expect(nativeConfirm).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));

    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(deleteLecture).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole("button", { name: "Delete Delete me" }));
    fireEvent.click(await screen.findByRole("button", { name: "Delete" }));

    await waitFor(() => expect(deleteLecture).toHaveBeenCalled());
    expect(vi.mocked(deleteLecture).mock.calls[0][0]).toBe("lecture-delete");
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    nativeConfirm.mockRestore();
  });

  it("shows retry only for failed lectures", async () => {
    vi.mocked(getLectures).mockResolvedValue({
      items: [
        {
          id: "lecture-failed",
          title: "Failed lecture",
          duration_seconds: 60,
          created_at: "2026-07-19T14:00:00Z",
          job_status: "FAILED",
        },
        {
          id: "lecture-complete",
          title: "Completed lecture",
          duration_seconds: 60,
          created_at: "2026-07-18T14:00:00Z",
          job_status: "COMPLETED",
        },
      ],
      limit: 6,
      offset: 0,
      next_offset: null,
    });
    vi.mocked(retryLecture).mockResolvedValue({
      lecture_id: "lecture-failed",
      job_id: "job-failed",
      status: "QUEUED",
      duplicate: false,
    });
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={queryClient}>
        <LectureList />
      </QueryClientProvider>,
    );

    const retry = await screen.findByRole("button", { name: "Retry" });
    expect(screen.getAllByRole("button", { name: "Retry" })).toHaveLength(1);
    fireEvent.click(retry);
    await waitFor(() => expect(retryLecture).toHaveBeenCalled());
    expect(vi.mocked(retryLecture).mock.calls[0][0]).toBe("lecture-failed");
  });
});
