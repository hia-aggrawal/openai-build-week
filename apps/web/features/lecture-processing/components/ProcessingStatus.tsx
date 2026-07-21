import type { ProcessingJob } from "@/lib/types";

const STAGE_LABELS: Record<string, string> = {
  VALIDATING: "Validating your lecture",
  INSPECTING_MEDIA: "Inspecting the video",
  EXTRACTING_AUDIO: "Preparing the audio",
  TRANSCRIBING: "Creating the transcript",
  SEGMENTING: "Finding topic boundaries",
  CLASSIFYING: "Measuring complexity",
  GENERATING_PROFILE: "Building your playback profile",
};

export function ProcessingStatus({ job }: { job: ProcessingJob }) {
  return (
    <section className="processing-card" aria-live="polite">
      <div className="processing-orbit"><span /></div>
      <div className="eyebrow">Preparing your lecture</div>
      <h1>{STAGE_LABELS[job.stage] ?? "Processing your lecture"}</h1>
      <p>StudyFlow is mapping each section to a comfortable playback speed.</p>
      <progress className="progress-bar" max="100" value={job.progress}>{job.progress}%</progress>
      <span className="progress-label">{job.progress}% complete</span>
    </section>
  );
}
