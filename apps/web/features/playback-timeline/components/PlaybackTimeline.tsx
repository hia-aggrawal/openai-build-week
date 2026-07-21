import type { PlaybackSegment } from "@/lib/types";
import { formatTime, safePlaybackRate } from "@/features/lecture-player/utils/playback";

const RATE_CLASSES: Record<string, string> = {
  "2": "timeline-rate-fast",
  "1.5": "timeline-rate-fast-mid",
  "1": "timeline-rate-normal",
};

export function playbackRateClass(playbackRate: number) {
  const rate = safePlaybackRate(playbackRate);
  return RATE_CLASSES[String(rate)] ?? "timeline-rate-normal";
}

export function PlaybackTimeline({
  profile,
  duration,
  currentTime,
  onSeek,
}: {
  profile: PlaybackSegment[];
  duration: number;
  currentTime: number;
  onSeek: (time: number) => void;
}) {
  return (
    <section className="timeline-section" aria-label="Adaptive playback timeline">
      <div className="timeline-heading">
        <div><span className="eyebrow">Playback map</span><h2>The pace of this lecture</h2></div>
        <div className="legend"><span>2.0× faster</span><i className="fast" /><i className="normal" /><span>1.0× normal</span></div>
      </div>
      <div className="timeline-track">
        {profile.map((segment) => {
          const rate = safePlaybackRate(segment.playback_rate);
          return (
            <button
              aria-label={`Seek to ${formatTime(segment.start_seconds)}, ${rate} times speed`}
              className={`timeline-segment ${playbackRateClass(rate)}`}
              key={segment.start_seconds}
              onClick={() => onSeek(segment.start_seconds)}
              style={{
                width: `${((segment.end_seconds - segment.start_seconds) / duration) * 100}%`,
              }}
              title={`${formatTime(segment.start_seconds)} · ${rate}× · ${segment.category.replaceAll("_", " ")}`}
            />
          );
        })}
        <span className="timeline-cursor" style={{ left: `${(currentTime / duration) * 100}%` }} />
      </div>
      <div className="timeline-times"><span>0:00</span><span>{formatTime(duration)}</span></div>
    </section>
  );
}
