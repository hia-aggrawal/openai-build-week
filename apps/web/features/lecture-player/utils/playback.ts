import type { PlaybackSegment } from "@/lib/types";

export function findActiveSegment(profile: PlaybackSegment[], currentTime: number) {
  return profile.find(
    (segment) => currentTime >= segment.start_seconds && currentTime < segment.end_seconds,
  ) ?? profile.at(-1);
}

export function formatTime(seconds: number) {
  const whole = Math.max(0, Math.floor(seconds));
  return `${Math.floor(whole / 60)}:${String(whole % 60).padStart(2, "0")}`;
}

export function safePlaybackRate(rate: number): number {
  return Math.min(2, Math.max(1, rate));
}
