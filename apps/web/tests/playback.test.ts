import { describe, expect, it } from "vitest";
import { findActiveSegment, formatTime } from "@/features/lecture-player/utils/playback";
import type { PlaybackSegment } from "@/lib/types";

const profile: PlaybackSegment[] = [
  { start_seconds: 0, end_seconds: 20, playback_rate: 2, complexity_score: 1, category: "INTRODUCTION", reason: "Simple" },
  { start_seconds: 20, end_seconds: 40, playback_rate: 1, complexity_score: 5, category: "DENSE_CONCEPT", reason: "Dense" },
];

describe("adaptive playback utilities", () => {
  it("finds the segment at exact boundaries", () => {
    expect(findActiveSegment(profile, 19.99)?.playback_rate).toBe(2);
    expect(findActiveSegment(profile, 20)?.playback_rate).toBe(1);
  });

  it("formats timestamps", () => {
    expect(formatTime(65.9)).toBe("1:05");
  });
});
