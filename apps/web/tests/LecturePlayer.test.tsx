import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { LecturePlayer } from "@/features/lecture-player/components/LecturePlayer";
import type { Lecture } from "@/lib/types";

const lecture: Lecture = {
  id: "lecture-1",
  title: "Test lecture",
  duration_seconds: 40,
  video_url: "/video",
  captions_url: "/captions.vtt",
  job: { id: "job-1", status: "COMPLETED", stage: "GENERATING_PROFILE", progress: 100, error_code: null, error_message: null },
  transcript: [],
  playback_profile: [
    { start_seconds: 0, end_seconds: 20, playback_rate: 2, complexity_score: 1, category: "INTRODUCTION", reason: "Simple" },
    { start_seconds: 20, end_seconds: 40, playback_rate: 1, complexity_score: 5, category: "DENSE_CONCEPT", reason: "Dense" },
  ],
};

describe("LecturePlayer", () => {
  it("renders the lecture captions track", () => {
    const { container } = render(<LecturePlayer lecture={lecture} />);
    const track = container.querySelector("video track");

    expect(track).toHaveAttribute("kind", "captions");
    expect(track).toHaveAttribute("srclang", "en");
    expect(track).toHaveAttribute("label", "English");
    expect(track).toHaveAttribute("src", "/captions.vtt");
    expect(track).toHaveAttribute("default");
    expect(container.querySelector("video")).not.toHaveAttribute("controls");
    expect(screen.getByLabelText("Video controls")).toBeVisible();
  });

  it("custom play and pause controls follow real video events", () => {
    const { container } = render(<LecturePlayer lecture={lecture} />);
    const video = container.querySelector("video") as HTMLVideoElement;
    let paused = true;
    Object.defineProperty(video, "paused", { configurable: true, get: () => paused });
    Object.defineProperty(video, "play", {
      configurable: true,
      value: vi.fn(() => {
        paused = false;
        fireEvent.play(video);
        return Promise.resolve();
      }),
    });
    Object.defineProperty(video, "pause", {
      configurable: true,
      value: vi.fn(() => {
        paused = true;
        fireEvent.pause(video);
      }),
    });

    fireEvent.click(screen.getByRole("button", { name: "Play" }));
    expect(screen.getByRole("button", { name: "Pause" })).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "Pause" }));
    expect(screen.getByRole("button", { name: "Play" })).toBeVisible();
  });

  it("toggles playback when the video surface is clicked", () => {
    const { container } = render(<LecturePlayer lecture={lecture} />);
    const video = container.querySelector("video") as HTMLVideoElement;
    let paused = true;
    const play = vi.fn(() => {
      paused = false;
      fireEvent.play(video);
      return Promise.resolve();
    });
    const pause = vi.fn(() => {
      paused = true;
      fireEvent.pause(video);
    });
    Object.defineProperty(video, "paused", { configurable: true, get: () => paused });
    Object.defineProperty(video, "play", { configurable: true, value: play });
    Object.defineProperty(video, "pause", { configurable: true, value: pause });

    fireEvent.click(video);
    expect(play).toHaveBeenCalledOnce();
    expect(screen.getByRole("button", { name: "Pause" })).toBeVisible();
    fireEvent.click(video);
    expect(pause).toHaveBeenCalledOnce();
    expect(screen.getByRole("button", { name: "Play" })).toBeVisible();
  });

  it("renders a segmented pace scrubber and seeks by click and drag", () => {
    const { container } = render(<LecturePlayer lecture={lecture} />);
    const video = container.querySelector("video") as HTMLVideoElement;
    const scrubber = screen.getByRole("slider", { name: "Lecture pace seek bar" });
    Object.defineProperty(video, "currentTime", {
      configurable: true,
      writable: true,
      value: 0,
    });
    vi.spyOn(scrubber, "getBoundingClientRect").mockReturnValue({
      bottom: 10,
      height: 10,
      left: 100,
      right: 300,
      top: 0,
      width: 200,
      x: 100,
      y: 0,
      toJSON: () => ({}),
    });

    const segments = scrubber.querySelectorAll(".player-pace-segment");
    expect(segments).toHaveLength(2);
    expect(segments[0]).toHaveClass("timeline-rate-fast");
    expect(segments[1]).toHaveClass("timeline-rate-normal");

    const pointerEvent = (type: string, clientX: number) => {
      const event = new Event(type, { bubbles: true });
      Object.defineProperties(event, {
        clientX: { value: clientX },
        pointerId: { value: 1 },
      });
      fireEvent(scrubber, event);
    };

    pointerEvent("pointerdown", 200);
    expect(video.currentTime).toBe(20);
    pointerEvent("pointermove", 250);
    expect(video.currentTime).toBe(30);
    expect(scrubber.querySelector(".player-pace-cursor")).toHaveStyle({ left: "75%" });
    pointerEvent("pointerup", 250);
  });

  it("custom mute control follows volume changes", () => {
    const { container } = render(<LecturePlayer lecture={lecture} />);
    const video = container.querySelector("video") as HTMLVideoElement;
    let muted = false;
    Object.defineProperty(video, "muted", {
      configurable: true,
      get: () => muted,
      set: (value: boolean) => {
        muted = value;
        fireEvent.volumeChange(video);
      },
    });

    fireEvent.click(screen.getByRole("button", { name: "Mute" }));
    expect(video.muted).toBe(true);
    expect(screen.getByRole("button", { name: "Unmute" })).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "Unmute" }));
    expect(video.muted).toBe(false);
    expect(screen.getByRole("button", { name: "Mute" })).toBeVisible();
  });

  it("toggles the real captions text track mode", () => {
    const { container } = render(<LecturePlayer lecture={lecture} />);
    const track = container.querySelector("track") as HTMLTrackElement;
    const textTrack = { mode: "showing" as TextTrackMode };
    Object.defineProperty(track, "track", { configurable: true, value: textTrack });

    fireEvent.click(screen.getByRole("button", { name: "Turn captions off" }));
    expect(textTrack.mode).toBe("disabled");
    expect(screen.getByRole("button", { name: "Turn captions on" })).toHaveAttribute(
      "aria-pressed",
      "false",
    );
    fireEvent.click(screen.getByRole("button", { name: "Turn captions on" }));
    expect(textTrack.mode).toBe("showing");
  });

  it("fullscreens the video and custom-controls container", () => {
    const { container } = render(<LecturePlayer lecture={lecture} />);
    const videoShell = container.querySelector(".video-shell") as HTMLDivElement;
    const originalFullscreenElement = Object.getOwnPropertyDescriptor(
      document,
      "fullscreenElement",
    );
    const originalExitFullscreen = Object.getOwnPropertyDescriptor(document, "exitFullscreen");
    let fullscreenElement: Element | null = null;
    Object.defineProperty(document, "fullscreenElement", {
      configurable: true,
      get: () => fullscreenElement,
    });
    const exitFullscreen = vi.fn(() => {
      fullscreenElement = null;
      fireEvent(document, new Event("fullscreenchange"));
      return Promise.resolve();
    });
    Object.defineProperty(document, "exitFullscreen", {
      configurable: true,
      value: exitFullscreen,
    });
    const requestFullscreen = vi.fn(() => {
      fullscreenElement = videoShell;
      fireEvent(document, new Event("fullscreenchange"));
      return Promise.resolve();
    });
    Object.defineProperty(videoShell, "requestFullscreen", {
      configurable: true,
      value: requestFullscreen,
    });

    fireEvent.click(screen.getByRole("button", { name: "Enter fullscreen" }));

    expect(requestFullscreen).toHaveBeenCalledOnce();
    expect(screen.getByRole("button", { name: "Exit fullscreen" })).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "Exit fullscreen" }));
    expect(exitFullscreen).toHaveBeenCalledOnce();
    expect(screen.getByRole("button", { name: "Enter fullscreen" })).toBeVisible();

    if (originalFullscreenElement) {
      Object.defineProperty(document, "fullscreenElement", originalFullscreenElement);
    } else {
      Reflect.deleteProperty(document, "fullscreenElement");
    }
    if (originalExitFullscreen) {
      Object.defineProperty(document, "exitFullscreen", originalExitFullscreen);
    } else {
      Reflect.deleteProperty(document, "exitFullscreen");
    }
  });

  it("changes playback rate at segment boundaries and can disable adaptation", () => {
    const { container } = render(<LecturePlayer lecture={lecture} />);
    const video = container.querySelector("video") as HTMLVideoElement;
    Object.defineProperty(video, "currentTime", { configurable: true, writable: true, value: 21 });
    Object.defineProperty(video, "playbackRate", { configurable: true, writable: true, value: 1 });

    fireEvent.timeUpdate(video);
    expect(video.playbackRate).toBe(1);
    expect(screen.getByText("1×")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("checkbox", { name: /adaptive speed/i }));
    expect(video.playbackRate).toBe(1);
  });

  it("keeps the video source stable when a refreshed token changes", () => {
    const firstLecture = { ...lecture, video_url: "/video?token=first" };
    const { container, rerender } = render(<LecturePlayer lecture={firstLecture} />);
    const video = container.querySelector("video") as HTMLVideoElement;
    const originalSource = video.getAttribute("src");

    rerender(<LecturePlayer lecture={{ ...firstLecture, video_url: "/video?token=second" }} />);

    expect(video.getAttribute("src")).toBe(originalSource);
  });

  it("skips backward and forward by ten seconds within lecture bounds", () => {
    const { container } = render(<LecturePlayer lecture={lecture} />);
    const video = container.querySelector("video") as HTMLVideoElement;
    Object.defineProperty(video, "currentTime", {
      configurable: true,
      writable: true,
      value: 5,
    });

    fireEvent.click(screen.getByRole("button", { name: "-10s" }));
    expect(video.currentTime).toBe(0);

    video.currentTime = 35;
    fireEvent.click(screen.getByRole("button", { name: "+10s" }));
    expect(video.currentTime).toBe(40);
  });

  it("handles play, pause, and seek keyboard shortcuts", () => {
    const { container } = render(<LecturePlayer lecture={lecture} />);
    const video = container.querySelector("video") as HTMLVideoElement;
    let paused = true;
    const play = vi.fn(() => {
      paused = false;
      return Promise.resolve();
    });
    const pause = vi.fn(() => {
      paused = true;
    });
    Object.defineProperty(video, "paused", { configurable: true, get: () => paused });
    Object.defineProperty(video, "play", { configurable: true, value: play });
    Object.defineProperty(video, "pause", { configurable: true, value: pause });
    Object.defineProperty(video, "currentTime", {
      configurable: true,
      writable: true,
      value: 15,
    });

    fireEvent.keyDown(window, { key: "k" });
    expect(play).toHaveBeenCalledOnce();
    fireEvent.keyDown(window, { key: " " });
    expect(pause).toHaveBeenCalledOnce();
    fireEvent.keyDown(window, { key: "ArrowRight" });
    expect(video.currentTime).toBe(25);
    fireEvent.keyDown(window, { key: "ArrowLeft" });
    expect(video.currentTime).toBe(15);
  });
});
