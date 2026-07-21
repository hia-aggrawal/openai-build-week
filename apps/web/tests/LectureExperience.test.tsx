import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { LectureExperience } from "@/features/lecture-player/components/LectureExperience";
import { getLecture, retryLecture } from "@/lib/api";

vi.mock("@/lib/api", () => ({ getLecture: vi.fn(), retryLecture: vi.fn() }));

describe("LectureExperience", () => {
  it("offers retry when processing failed", async () => {
    vi.mocked(getLecture).mockResolvedValue({
      id: "lecture-failed",
      title: "Failed lecture",
      duration_seconds: 60,
      video_url: "/video",
      captions_url: "/captions.vtt",
      job: {
        id: "job-failed",
        status: "FAILED",
        stage: "TRANSCRIBING",
        progress: 40,
        error_code: "TRANSCRIPTION_FAILED",
        error_message: "Transcription failed.",
      },
      transcript: null,
      playback_profile: null,
    });
    vi.mocked(retryLecture).mockResolvedValue({
      lecture_id: "lecture-failed",
      job_id: "job-failed",
      status: "QUEUED",
      duplicate: false,
    });
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
    });
    render(
      <QueryClientProvider client={queryClient}>
        <LectureExperience lectureId="lecture-failed" onStartOver={vi.fn()} />
      </QueryClientProvider>,
    );

    fireEvent.click(await screen.findByRole("button", { name: "Retry" }));

    await waitFor(() => expect(retryLecture).toHaveBeenCalledWith("lecture-failed"));
  });
});
