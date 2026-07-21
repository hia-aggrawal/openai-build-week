"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { PointerEvent as ReactPointerEvent } from "react";
import type { Lecture } from "@/lib/types";
import { findActiveSegment, formatTime, safePlaybackRate } from "../utils/playback";
import {
  PlaybackTimeline,
  playbackRateClass,
} from "@/features/playback-timeline/components/PlaybackTimeline";

export function LecturePlayer({ lecture }: { lecture: Lecture }) {
  const videoShellRef = useRef<HTMLDivElement>(null);
  const videoRef = useRef<HTMLVideoElement>(null);
  const captionsTrackRef = useRef<HTMLTrackElement>(null);
  const scrubPointerRef = useRef<number | null>(null);
  const sourceRef = useRef({ lectureId: lecture.id, url: lecture.video_url });
  if (sourceRef.current.lectureId !== lecture.id) {
    sourceRef.current = { lectureId: lecture.id, url: lecture.video_url };
  }
  const profile = useMemo(() => lecture.playback_profile ?? [], [lecture.playback_profile]);
  const [adaptive, setAdaptive] = useState(true);
  const [currentTime, setCurrentTime] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [muted, setMuted] = useState(false);
  const [fullscreen, setFullscreen] = useState(false);
  const [captionsEnabled, setCaptionsEnabled] = useState(true);
  const active = findActiveSegment(profile, currentTime);

  const syncPlayback = useCallback(() => {
    const video = videoRef.current;
    if (!video) return;
    setCurrentTime(video.currentTime);
    const next = findActiveSegment(profile, video.currentTime);
    const requestedRate = adaptive ? safePlaybackRate(next?.playback_rate ?? 1) : 1;
    if (video.playbackRate !== requestedRate) video.playbackRate = requestedRate;
  }, [adaptive, profile]);

  function toggleAdaptive() {
    setAdaptive((enabled) => {
      const nextEnabled = !enabled;
      const video = videoRef.current;
      if (video) video.playbackRate = nextEnabled
        ? safePlaybackRate(active?.playback_rate ?? 1)
        : 1;
      return nextEnabled;
    });
  }

  const seek = useCallback((time: number) => {
    if (videoRef.current) {
      videoRef.current.currentTime = Math.min(
        lecture.duration_seconds,
        Math.max(0, time),
      );
      syncPlayback();
    }
  }, [lecture.duration_seconds, syncPlayback]);

  const skipBy = useCallback((seconds: number) => {
    const video = videoRef.current;
    if (video) seek(video.currentTime + seconds);
  }, [seek]);

  const seekFromPointer = useCallback((event: ReactPointerEvent<HTMLDivElement>) => {
    const bounds = event.currentTarget.getBoundingClientRect();
    if (bounds.width <= 0) return;
    const progress = (event.clientX - bounds.left) / bounds.width;
    seek(progress * lecture.duration_seconds);
  }, [lecture.duration_seconds, seek]);

  const startScrubbing = useCallback((event: ReactPointerEvent<HTMLDivElement>) => {
    scrubPointerRef.current = event.pointerId;
    event.currentTarget.setPointerCapture?.(event.pointerId);
    seekFromPointer(event);
  }, [seekFromPointer]);

  const continueScrubbing = useCallback((event: ReactPointerEvent<HTMLDivElement>) => {
    if (scrubPointerRef.current === event.pointerId) seekFromPointer(event);
  }, [seekFromPointer]);

  const stopScrubbing = useCallback((event: ReactPointerEvent<HTMLDivElement>) => {
    if (scrubPointerRef.current !== event.pointerId) return;
    seekFromPointer(event);
    scrubPointerRef.current = null;
    event.currentTarget.releasePointerCapture?.(event.pointerId);
  }, [seekFromPointer]);

  const togglePlayback = useCallback(() => {
    const video = videoRef.current;
    if (!video) return;
    if (video.paused) {
      void video.play().catch(() => undefined);
    } else {
      video.pause();
    }
  }, []);

  const toggleMuted = useCallback(() => {
    const video = videoRef.current;
    if (video) video.muted = !video.muted;
  }, []);

  const toggleFullscreen = useCallback(() => {
    const videoShell = videoShellRef.current;
    if (!videoShell) return;
    if (document.fullscreenElement) {
      if (typeof document.exitFullscreen === "function") {
        void document.exitFullscreen().catch(() => undefined);
      }
    } else if (typeof videoShell.requestFullscreen === "function") {
      void videoShell.requestFullscreen().catch(() => undefined);
    }
  }, []);

  const toggleCaptions = useCallback(() => {
    const textTrack = captionsTrackRef.current?.track;
    const nextEnabled = textTrack ? textTrack.mode !== "showing" : !captionsEnabled;
    if (textTrack) textTrack.mode = nextEnabled ? "showing" : "disabled";
    setCaptionsEnabled(nextEnabled);
  }, [captionsEnabled]);

  useEffect(() => {
    function handleFullscreenChange() {
      setFullscreen(document.fullscreenElement === videoShellRef.current);
    }

    document.addEventListener("fullscreenchange", handleFullscreenChange);
    return () => document.removeEventListener("fullscreenchange", handleFullscreenChange);
  }, []);

  useEffect(() => {
    function handleKeyDown(event: KeyboardEvent) {
      const target = event.target;
      if (target instanceof HTMLElement) {
        const editableAncestor = target.closest<HTMLElement>("[contenteditable]");
        if (
          target.tagName === "INPUT"
          || target.tagName === "TEXTAREA"
          || target.isContentEditable
          || (editableAncestor && editableAncestor.contentEditable !== "false")
        ) {
          return;
        }
      }

      const video = videoRef.current;
      if (!video) return;
      const key = event.key.toLowerCase();
      if (key === " " || key === "k") {
        event.preventDefault();
        togglePlayback();
      } else if (key === "arrowleft") {
        event.preventDefault();
        skipBy(-10);
      } else if (key === "arrowright") {
        event.preventDefault();
        skipBy(10);
      } else if (key === "f") {
        event.preventDefault();
        toggleFullscreen();
      } else if (key === "m") {
        event.preventDefault();
        toggleMuted();
      }
    }

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [skipBy, toggleFullscreen, toggleMuted, togglePlayback]);

  return (
    <>
      <section className="player-grid">
        <div className="video-shell" ref={videoShellRef}>
          <video
            ref={videoRef}
            src={sourceRef.current.url}
            onEnded={() => setPlaying(false)}
            onClick={togglePlayback}
            onLoadedMetadata={() => {
              const video = videoRef.current;
              setMuted(video?.muted ?? false);
              setPlaying(video ? !video.paused : false);
              syncPlayback();
            }}
            onPause={() => setPlaying(false)}
            onPlay={() => {
              setPlaying(true);
              syncPlayback();
            }}
            onTimeUpdate={syncPlayback}
            onSeeked={syncPlayback}
            onVolumeChange={() => setMuted(videoRef.current?.muted ?? false)}
          >
            <track
              default
              kind="captions"
              label="English"
              onLoad={() => {
                const textTrack = captionsTrackRef.current?.track;
                if (textTrack) setCaptionsEnabled(textTrack.mode === "showing");
              }}
              ref={captionsTrackRef}
              src={lecture.captions_url}
              srcLang="en"
            />
          </video>
          <div className="player-controls" aria-label="Video controls">
            <button
              aria-label={playing ? "Pause" : "Play"}
              className="player-icon-button"
              onClick={togglePlayback}
              type="button"
            >
              {playing ? (
                <svg aria-hidden="true" viewBox="0 0 20 20">
                  <path d="M6 4v12M14 4v12" />
                </svg>
              ) : (
                <svg aria-hidden="true" viewBox="0 0 20 20">
                  <path d="m6 4 10 6-10 6Z" />
                </svg>
              )}
            </button>
            <button className="player-skip-button" onClick={() => skipBy(-10)} type="button">
              -10s
            </button>
            <button className="player-skip-button" onClick={() => skipBy(10)} type="button">
              +10s
            </button>
            <span className="player-control-time">
              {formatTime(currentTime)} <span>/ {formatTime(lecture.duration_seconds)}</span>
            </span>
            <div
              aria-label="Lecture pace seek bar"
              aria-valuemax={lecture.duration_seconds}
              aria-valuemin={0}
              aria-valuenow={Math.round(currentTime)}
              aria-valuetext={`${formatTime(currentTime)} of ${formatTime(lecture.duration_seconds)}`}
              className="player-pace-scrubber"
              onLostPointerCapture={() => {
                scrubPointerRef.current = null;
              }}
              onPointerCancel={(event) => {
                if (scrubPointerRef.current === event.pointerId) scrubPointerRef.current = null;
              }}
              onPointerDown={startScrubbing}
              onPointerMove={continueScrubbing}
              onPointerUp={stopScrubbing}
              role="slider"
              tabIndex={0}
            >
              {profile.map((segment) => (
                <span
                  aria-hidden="true"
                  className={`player-pace-segment ${playbackRateClass(segment.playback_rate)}`}
                  key={`${segment.start_seconds}-${segment.end_seconds}`}
                  style={{
                    left: `${(segment.start_seconds / lecture.duration_seconds) * 100}%`,
                    width: `${((segment.end_seconds - segment.start_seconds) / lecture.duration_seconds) * 100}%`,
                  }}
                />
              ))}
              <span
                aria-hidden="true"
                className="player-pace-cursor"
                style={{
                  left: `${Math.min(100, Math.max(0, (currentTime / lecture.duration_seconds) * 100))}%`,
                }}
              />
            </div>
            <button
              aria-label={captionsEnabled ? "Turn captions off" : "Turn captions on"}
              aria-pressed={captionsEnabled}
              className="player-icon-button player-cc-button"
              onClick={toggleCaptions}
              type="button"
            >
              <svg aria-hidden="true" viewBox="0 0 24 20">
                <rect x="1" y="2" width="22" height="16" rx="3" />
                <path d="M10 8a3 3 0 1 0 0 4M19 8a3 3 0 1 0 0 4" />
              </svg>
            </button>
            <button
              aria-label={muted ? "Unmute" : "Mute"}
              className="player-icon-button"
              onClick={toggleMuted}
              type="button"
            >
              <svg aria-hidden="true" viewBox="0 0 20 20">
                <path d="M3 8h3l4-3v10l-4-3H3ZM13 7a4 4 0 0 1 0 6M15 4a8 8 0 0 1 0 12" />
                {muted && <path className="mute-slash" d="M3 3l14 14" />}
              </svg>
            </button>
            <button
              aria-label={fullscreen ? "Exit fullscreen" : "Enter fullscreen"}
              className="player-icon-button"
              onClick={toggleFullscreen}
              type="button"
            >
              <svg aria-hidden="true" viewBox="0 0 20 20">
                <path d="M7 3H3v4M13 3h4v4M7 17H3v-4M13 17h4v-4" />
              </svg>
            </button>
          </div>
        </div>
        <aside className="now-playing">
          <div className="eyebrow">Now playing</div>
          <div className="speed-display"><strong>{adaptive ? safePlaybackRate(active?.playback_rate ?? 1) : 1}×</strong><span>current speed</span></div>
          <div className="complexity-meter" aria-label={`Complexity ${active?.complexity_score ?? 3} of 5`}>
            {[1, 2, 3, 4, 5].map((level) => <i className={level <= (active?.complexity_score ?? 0) ? "filled" : ""} key={level} />)}
          </div>
          <h2>{active?.category.replaceAll("_", " ") ?? "Lecture"}</h2>
          <p>{active?.reason}</p>
          <label className="switch-row">
            <span><strong>Adaptive speed</strong><small>Changes pace automatically</small></span>
            <input type="checkbox" checked={adaptive} onChange={toggleAdaptive} />
          </label>
        </aside>
      </section>
      <PlaybackTimeline profile={profile} duration={lecture.duration_seconds} currentTime={currentTime} onSeek={seek} />
    </>
  );
}
