"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import { getLecture, retryLecture } from "@/lib/api";
import { ProcessingStatus } from "@/features/lecture-processing/components/ProcessingStatus";
import { LecturePlayer } from "./LecturePlayer";

export function LectureExperience({ lectureId, onStartOver }: { lectureId: string; onStartOver: () => void }) {
  const query = useQuery({
    queryKey: ["lecture", lectureId],
    queryFn: () => getLecture(lectureId),
    refetchInterval: (result) => {
      const status = result.state.data?.job.status;
      return status === "COMPLETED" || status === "FAILED" ? false : 500;
    },
    refetchOnReconnect: (result) => result.state.data?.job.status !== "COMPLETED",
    refetchOnWindowFocus: (result) => result.state.data?.job.status !== "COMPLETED",
  });
  const retryMutation = useMutation({
    mutationFn: () => retryLecture(lectureId),
    onSuccess: () => query.refetch(),
  });

  if (query.isPending) {
    return (
      <section className="page-message" aria-live="polite">
        <span className="eyebrow">Loading lecture</span>
        <h1>Opening your lecture</h1>
        <p>StudyFlow is retrieving the latest processing status.</p>
      </section>
    );
  }
  if (query.isError) {
    return (
      <section className="page-message" role="alert">
        <span className="eyebrow">Unable to load</span>
        <h1>We couldn’t open this lecture</h1>
        <p className="error-text">{query.error.message}</p>
        <button className="primary-button" onClick={onStartOver} type="button">
          Back to uploads
        </button>
      </section>
    );
  }
  const lecture = query.data;
  if (lecture.job.status === "FAILED") {
    return (
      <section className="page-message" role="alert">
        <span className="eyebrow">Unable to process</span>
        <h1>Processing stopped</h1>
        <p className="error-text">{lecture.job.error_message}</p>
        <div className="page-message-actions">
          <button
            className="primary-button"
            disabled={retryMutation.isPending}
            onClick={() => retryMutation.mutate()}
            type="button"
          >
            {retryMutation.isPending ? "Retrying…" : "Retry"}
          </button>
          <button className="text-button" onClick={onStartOver} type="button">
            Try another video
          </button>
        </div>
        {retryMutation.isError && <p className="error-text">{retryMutation.error.message}</p>}
      </section>
    );
  }
  if (lecture.job.status !== "COMPLETED") return <ProcessingStatus job={lecture.job} />;

  return (
    <div className="lecture-page">
      <div className="lecture-title-row">
        <div><span className="eyebrow">Ready to watch</span><h1>{lecture.title}</h1></div>
      </div>
      <LecturePlayer lecture={lecture} />
    </div>
  );
}
