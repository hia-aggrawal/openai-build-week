import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterAll, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import { LectureUpload } from "@/features/lecture-upload/components/LectureUpload";
import { uploadLecture } from "@/lib/api";

vi.mock("@/lib/api", () => ({ uploadLecture: vi.fn() }));

const durationDescriptor = Object.getOwnPropertyDescriptor(
  HTMLMediaElement.prototype,
  "duration",
);
const sourceDescriptor = Object.getOwnPropertyDescriptor(HTMLMediaElement.prototype, "src");

function renderUpload(onCreated = vi.fn()) {
  const queryClient = new QueryClient({
    defaultOptions: { mutations: { retry: false } },
  });
  const result = render(
    <QueryClientProvider client={queryClient}>
      <LectureUpload onCreated={onCreated} />
    </QueryClientProvider>,
  );
  const input = result.container.querySelector('input[type="file"]') as HTMLInputElement;
  return { ...result, input, onCreated };
}

beforeAll(() => {
  Object.defineProperty(URL, "createObjectURL", {
    configurable: true,
    value: vi.fn(() => "blob:lecture"),
  });
  Object.defineProperty(URL, "revokeObjectURL", {
    configurable: true,
    value: vi.fn(),
  });
  Object.defineProperty(HTMLMediaElement.prototype, "duration", {
    configurable: true,
    get: () => 60,
  });
  Object.defineProperty(HTMLMediaElement.prototype, "src", {
    configurable: true,
    get: () => "blob:lecture",
    set() {
      queueMicrotask(() => this.onloadedmetadata?.(new Event("loadedmetadata")));
    },
  });
});

afterAll(() => {
  if (durationDescriptor) {
    Object.defineProperty(HTMLMediaElement.prototype, "duration", durationDescriptor);
  }
  if (sourceDescriptor) {
    Object.defineProperty(HTMLMediaElement.prototype, "src", sourceDescriptor);
  }
});

beforeEach(() => {
  vi.clearAllMocks();
});

describe("LectureUpload", () => {
  it.each([
    ["lecture.mp4", "video/mp4"],
    ["lecture.webm", "video/webm"],
    ["lecture.mov", "video/quicktime"],
  ])("accepts %s uploads", async (name, type) => {
    vi.mocked(uploadLecture).mockResolvedValue({
      lecture_id: "lecture-123",
      job_id: "job-123",
      status: "QUEUED",
      duplicate: false,
    });
    const { input, onCreated } = renderUpload();

    fireEvent.change(input, { target: { files: [new File(["video"], name, { type })] } });
    fireEvent.click(screen.getByRole("button", { name: "Create adaptive lecture" }));

    await waitFor(() =>
      expect(uploadLecture).toHaveBeenCalledWith(expect.any(File), "", 60, expect.any(Function)),
    );
    expect(onCreated).toHaveBeenCalledWith("lecture-123");
  });

  it("rejects unsupported file types", () => {
    const { input } = renderUpload();

    fireEvent.change(input, {
      target: { files: [new File(["notes"], "notes.txt", { type: "text/plain" })] },
    });

    expect(screen.getByRole("alert")).toHaveTextContent("Choose an MP4, WebM, or MOV video.");
    expect(uploadLecture).not.toHaveBeenCalled();
  });

  it("requires a file before submission", () => {
    renderUpload();

    fireEvent.click(screen.getByRole("button", { name: "Create adaptive lecture" }));

    expect(screen.getByRole("alert")).toHaveTextContent("Choose a lecture video first.");
    expect(uploadLecture).not.toHaveBeenCalled();
  });

  it("renders upload API failures", async () => {
    vi.mocked(uploadLecture).mockRejectedValue(new Error("Upload service is unavailable."));
    const { input } = renderUpload();
    fireEvent.change(input, {
      target: { files: [new File(["video"], "lecture.mp4", { type: "video/mp4" })] },
    });

    fireEvent.click(screen.getByRole("button", { name: "Create adaptive lecture" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Upload service is unavailable.");
  });

  it("renders chunk upload progress", async () => {
    let finishUpload: ((value: {
      lecture_id: string;
      job_id: string;
      status: "QUEUED";
      duplicate: boolean;
    }) => void) | undefined;
    vi.mocked(uploadLecture).mockImplementation((_file, _title, _duration, onProgress) => {
      onProgress?.(50);
      return new Promise((resolve) => {
        finishUpload = resolve;
      });
    });
    const { input } = renderUpload();
    fireEvent.change(input, {
      target: { files: [new File(["video"], "lecture.mp4", { type: "video/mp4" })] },
    });

    fireEvent.click(screen.getByRole("button", { name: "Create adaptive lecture" }));

    expect(await screen.findByRole("progressbar", { name: "Upload progress" })).toHaveValue(50);
    expect(screen.getByText("50% uploaded")).toBeVisible();
    finishUpload?.({
      lecture_id: "lecture-123",
      job_id: "job-123",
      status: "QUEUED",
      duplicate: false,
    });
  });

  it("announces a duplicate before navigating to the existing lecture", async () => {
    vi.mocked(uploadLecture).mockResolvedValue({
      lecture_id: "existing-lecture",
      job_id: "existing-job",
      status: "COMPLETED",
      duplicate: true,
    });
    const { input, onCreated } = renderUpload();
    fireEvent.change(input, {
      target: { files: [new File(["video"], "lecture.mp4", { type: "video/mp4" })] },
    });

    fireEvent.click(screen.getByRole("button", { name: "Create adaptive lecture" }));

    expect(await screen.findByRole("status")).toHaveTextContent(
      "You've already uploaded this lecture",
    );
    expect(onCreated).not.toHaveBeenCalled();
    await waitFor(() => expect(onCreated).toHaveBeenCalledWith("existing-lecture"), {
      timeout: 1500,
    });
  });
});
