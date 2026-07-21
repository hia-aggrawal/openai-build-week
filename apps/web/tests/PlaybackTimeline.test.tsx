import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { PlaybackTimeline } from "@/features/playback-timeline/components/PlaybackTimeline";

const profile = [
  { start_seconds: 0, end_seconds: 20, playback_rate: 2, complexity_score: 1, category: "INTRODUCTION", reason: "Simple" },
  { start_seconds: 20, end_seconds: 40, playback_rate: 1, complexity_score: 5, category: "DENSE_CONCEPT", reason: "Dense" },
];

describe("PlaybackTimeline", () => {
  it("renders profile sections and seeks when one is selected", () => {
    const onSeek = vi.fn();
    render(<PlaybackTimeline profile={profile} duration={40} currentTime={10} onSeek={onSeek} />);

    fireEvent.click(screen.getByRole("button", { name: /seek to 0:20/i }));

    expect(onSeek).toHaveBeenCalledWith(20);
    expect(screen.getAllByRole("button")).toHaveLength(2);
  });
});
