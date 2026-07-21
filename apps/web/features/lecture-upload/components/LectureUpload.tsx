"use client";

import { FormEvent, useEffect, useRef, useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { uploadLecture } from "@/lib/api";

const ACCEPTED_TYPES = ["video/mp4", "video/webm", "video/quicktime"];

function readDuration(file: File): Promise<number> {
  return new Promise((resolve, reject) => {
    const video = document.createElement("video");
    const url = URL.createObjectURL(file);
    video.preload = "metadata";
    video.onloadedmetadata = () => {
      URL.revokeObjectURL(url);
      if (Number.isFinite(video.duration) && video.duration > 0) {
        resolve(video.duration);
      } else {
        reject(new Error("We could not read this video's duration."));
      }
    };
    video.onerror = () => {
      URL.revokeObjectURL(url);
      reject(new Error("We could not read this video. Try an MP4, WebM, or MOV file."));
    };
    video.src = url;
  });
}

export function LectureUpload({
  onCreated,
  compact = false,
}: {
  onCreated: (lectureId: string) => void;
  compact?: boolean;
}) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [uploadProgress, setUploadProgress] = useState(0);
  const navigationTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  useEffect(
    () => () => {
      if (navigationTimer.current) clearTimeout(navigationTimer.current);
    },
    [],
  );
  const mutation = useMutation({
    mutationFn: async ({ selected, title }: { selected: File; title: string }) =>
      uploadLecture(selected, title, await readDuration(selected), setUploadProgress),
    onSuccess: (result) => {
      if (!result.duplicate) {
        onCreated(result.lecture_id);
        return;
      }
      setNotice("You've already uploaded this lecture");
      navigationTimer.current = setTimeout(() => onCreated(result.lecture_id), 900);
    },
    onError: (uploadError) => setError(uploadError.message),
  });

  function chooseFile(selected: File | undefined) {
    setError(null);
    setNotice(null);
    if (!selected) return;
    if (!ACCEPTED_TYPES.includes(selected.type)) {
      setFile(null);
      setError("Choose an MP4, WebM, or MOV video.");
      return;
    }
    setFile(selected);
  }

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!file) {
      setError("Choose a lecture video first.");
      return;
    }
    setUploadProgress(0);
    setNotice(null);
    const form = new FormData(event.currentTarget);
    mutation.mutate({ selected: file, title: String(form.get("title") ?? "") });
  }

  const uploadForm = (
    <form className="upload-card" onSubmit={submit}>
        <label htmlFor="title">Lecture title <span>optional</span></label>
        <input id="title" name="title" placeholder="e.g. Introduction to neural networks" />
        <label className="dropzone" htmlFor="video">
          <span aria-hidden="true" className="upload-icon">
            <svg viewBox="0 0 20 20">
              <path d="M10 16.5V5.5M5.5 10 10 5.5l4.5 4.5" />
            </svg>
          </span>
          <strong>{file ? file.name : "Choose a lecture video"}</strong>
          <span>{file ? `${(file.size / 1024 / 1024).toFixed(1)} MB` : "MP4, WebM, or MOV"}</span>
        </label>
        <input
          ref={inputRef}
          className="visually-hidden"
          id="video"
          type="file"
          accept="video/mp4,video/webm,video/quicktime"
          onChange={(event) => chooseFile(event.target.files?.[0])}
        />
        {error && <p className="error" role="alert">{error}</p>}
        {notice && <p className="upload-notice" role="status">{notice}</p>}
        {mutation.isPending && (
          <div className="upload-progress">
            <progress
              aria-label="Upload progress"
              className="progress-bar"
              max="100"
              value={uploadProgress}
            />
            <span>{uploadProgress}% uploaded</span>
          </div>
        )}
        <button className="primary-button" disabled={mutation.isPending} type="submit">
          {mutation.isPending ? `Uploading… ${uploadProgress}%` : "Create adaptive lecture"}
        </button>
    </form>
  );

  if (compact) {
    return (
      <div className="compact-upload">
        <span className="eyebrow">New adaptive lecture</span>
        <h2>Upload a lecture</h2>
        <p>Choose a video and StudyFlow will prepare its adaptive playback profile.</p>
        {uploadForm}
      </div>
    );
  }

  return (
    <section className="hero" aria-labelledby="upload-heading">
      <div className="hero-text">
        <div className="eyebrow">Adaptive lecture playback</div>
        <h1 id="upload-heading">Spend time where<br />the thinking gets hard.</h1>
        <p className="hero-copy">
          Upload a lecture and StudyFlow will move quickly through simple material, then slow down
          for dense concepts—automatically.
        </p>
      </div>
      {uploadForm}
      <div className="steps" aria-label="How it works">
        <span><b>01</b> Upload</span><span><b>02</b> Analyze</span><span><b>03</b> Watch adaptively</span>
      </div>
    </section>
  );
}
